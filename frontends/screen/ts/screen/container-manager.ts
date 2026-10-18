/**
 * Container DOM management — creates/positions/clears the absolutely
 * positioned overlay divs for whichever containers the current Scene uses.
 *
 * Containers are no longer baked into the Design's HTML as `{{ tag }}`
 * placeholders — they're dynamically created here, positioned via vh/vw
 * from the Scene payload, and appended to #scene-containers (a full-bleed
 * overlay layer separate from the Design background so re-rendering a
 * scene never touches the Design markup).
 */

import type { Scene, SocketEmitter } from "./types.js";
import { tickNow } from "./clock.js";
import { runAfterRender } from "./plugins.js";
import { log } from "./logger.js";
import { adaptCss, adaptHtml, containerGeometry } from "./rotation.js";
import { adaptMediaCss, adaptMediaImages } from "./media-renditions.js";
import {
  beginSceneTransition, chooseTransition, computeStagger, getTransitionConfig, playTransition, transitionWanted,
  type Choice, type PlayOptions, type StageGeometry,
} from "./transitions.js";

// Optional emitter injected by socket setup so this module does not
// directly depend on `window.socket`. Call `setSocketEmitter` with
// a function `(event, payload) => void` (for example `socket.emit`).
let socketEmitter: SocketEmitter | null = null;

export function setSocketEmitter(emitter: SocketEmitter): void {
  socketEmitter = emitter;
}

export function getSocketEmitter(): SocketEmitter | null {
  return socketEmitter;
}

// containerId (string) -> its DOM element (the content's element; see containerSlots)
const containerElements: Record<string, HTMLElement> = {};

// containerId -> the fixed box the container sits in. It carries the position and size; the content element inside
// fills it. During a transition the box holds the old and the new content element and, for sliding types, clips them
// along the movement so they do not travel over their neighbours (see transitions.ts); otherwise it changes nothing.
const containerSlots: Record<string, HTMLElement> = {};

// containerId -> the outro of its content, played at the end of the old scene (sequential mode, see playOutro).
// The old content stays hidden until the scene change replaces it.
const outros: Record<string, { choice: Choice; end: () => void }> = {};
// An outro ran for the scene change renderScene is about to make: the new content then comes in at once.
let outroActive = false;
let introAfterOutro = false;
// Set by renderScene: containers whose content stays the same are painted again, to animate (Design option).
let repaintUnchanged = false;

// containerId -> ends the transition running in that container (removes the old content element at once).
const runningTransitions: Record<string, () => void> = {};

// containerId (string) -> the values it was last painted with. The server
// resends every container of every active scene on every upd_content push
// (no diffing on its end — see upd_content.py), so this cache is what lets
// renderScene() skip touching the DOM (and thus avoid the visible flicker
// from innerHTML replacement — images reloading, videos restarting, etc.)
// for containers whose content hasn't actually changed since last time.
interface PaintedContainer {
  top: number;
  left: number;
  width: number;
  height: number;
  html: string;
  css: string;
}
const lastPainted: Record<string, PaintedContainer> = {};

function getOverlayRoot(): HTMLElement | null {
  return document.getElementById("scene-containers");
}

/** A container's content element: `.dh-container` is shared by every container (a Design's global style hook). */
function createContentElement(containerId: string): HTMLElement {
  const el = document.createElement("div");
  el.dataset.containerId = containerId;
  // `.dh-container` is shared by every container (a Design's global style
  // hook); `.dh-container-<id>` is this one's stable per-container hook —
  // unlike the container's name (editable any time in the admin), the id
  // never changes, so a Design's rule keeps working across renames.
  el.classList.add("dh-container", `dh-container-${containerId}`);
  el.style.position = "absolute";
  Object.assign(el.style, { top: "0", left: "0", width: "100%", height: "100%" });
  return el;
}

function ensureContainerElement(containerId: string): HTMLElement | null {
  const existing = containerElements[containerId];
  if (existing) return existing;

  const root = getOverlayRoot();
  if (!root) {
    log("error", "ensureContainerElement", "#scene-containers not found in DOM");
    return null;
  }

  const slot = document.createElement("div");
  slot.style.position = "absolute";
  const el = createContentElement(containerId);
  slot.appendChild(el);
  root.appendChild(slot);
  containerSlots[containerId] = slot;
  containerElements[containerId] = el;
  return el;
}

/**
 * Replace the container's content element by a fresh one, keeping the old one in place for the transition.
 * Returns the new element; *finish* (called when the transition ends) removes the old one.
 */
// containerId -> its place in the start order of this scene change, 0…1 (the Design's stagger, see computeStagger).
let staggerRanks: Record<string, number> = {};

/** What playTransition needs to know about a container's box and place in the start order. */
function transitionOptions(containerId: string): PlayOptions {
  const slot = containerSlots[containerId];
  return {
    slot,
    geometry: stageGeometry(containerId),
    size: slot ? { width: slot.offsetWidth, height: slot.offsetHeight } : undefined,
    stagger: staggerRanks[containerId],
  };
}

/** This container's box in the stage, when the Design's transition spans the whole slide; else undefined. */
function stageGeometry(containerId: string): StageGeometry | undefined {
  if (getTransitionConfig().scope !== "slide") return undefined;
  const slot = containerSlots[containerId];
  const stage = slot?.parentElement;
  if (!slot || !stage) return undefined;
  return {
    left: slot.offsetLeft, top: slot.offsetTop, width: slot.offsetWidth, height: slot.offsetHeight,
    stageWidth: stage.offsetWidth, stageHeight: stage.offsetHeight,
  };
}

function startTransition(containerId: string, cssEl: HTMLElement | null): HTMLElement {
  runningTransitions[containerId]?.();
  const slot = containerSlots[containerId];
  const leaving = containerElements[containerId];
  const entering = createContentElement(containerId);
  slot.appendChild(entering);
  containerElements[containerId] = entering;
  // The old content keeps the CSS it was shown with while it leaves: the new CSS goes into a new <style>.
  if (cssEl) cssEl.id = `${cssEl.id}-leaving`;
  runningTransitions[containerId] = playTransition(leaving, entering, () => {
    leaving.remove();
    cssEl?.remove();
    delete runningTransitions[containerId];
  }, transitionOptions(containerId));
  return entering;
}

/** Empty a container's DOM element and its scoped CSS, without removing it from the DOM. */
function clearContainerElement(containerId: string): void {
  if (!(containerId in lastPainted)) return; // already blank — nothing to do
  runningTransitions[containerId]?.();
  const outro = outros[containerId];
  if (outro) {
    outro.end();
    delete outros[containerId];
  }
  const el = containerElements[containerId];
  const cssEl = document.getElementById(`content-type-css-${containerId}`);
  const blank = () => {
    if (el) el.innerHTML = "";
    if (cssEl) cssEl.textContent = "";
    // A container the scene does not use draws nothing at all: a border or background the Design gives containers
    // would otherwise stay on screen as an empty box.
    const slot = containerSlots[containerId];
    if (slot) slot.style.display = "none";
  };
  const hadContent = lastPainted[containerId].html !== "" && !outro; // with an outro it has left already
  delete lastPainted[containerId];
  if (el && hadContent && transitionWanted()) {
    // The content leaves with the Design's transition; it is emptied once it is gone. A paint that arrives sooner
    // ends the transition first (see paintContainerElement), which empties it then.
    const slot = containerSlots[containerId];
    runningTransitions[containerId] = playTransition(el, null, () => {
      blank();
      delete runningTransitions[containerId];
    }, transitionOptions(containerId));
    return;
  }
  blank();
}

/**
 * Populate a container's DOM element with the given fragment (scene content
 * or a default). Only actually touches the DOM for whatever changed since
 * this container was last painted (position/size vs. content vs. CSS are
 * compared independently) — returns true if its content (html) was
 * (re)written, so the caller knows whether to re-resolve icon placeholders
 * etc. inside it.
 */
function paintContainerElement(
  containerId: string,
  c: { top: number; left: number; width: number; height: number; html: string; css?: string },
  inPlace = false,
): boolean {
  let el = ensureContainerElement(containerId);
  if (!el) return false;

  const css = c.css || "";
  const html = c.html || "";
  const prev = lastPainted[containerId];
  const positionChanged = !prev || prev.top !== c.top || prev.left !== c.left || prev.width !== c.width || prev.height !== c.height;
  // With the Design's "also animate unchanged" the same content is painted again as new, so it animates too.
  const repaintSame = !inPlace && !!prev && prev.html === html && html !== "" && repaintUnchanged;
  const contentChanged = !prev || prev.html !== html || repaintSame;
  const cssChanged = !prev || prev.css !== css;

  if (positionChanged) {
    Object.assign(containerSlots[containerId].style, containerGeometry(c));
  }

  // New content animates in (the Design's transition): over the content it replaces, or on its own when the
  // container was blank. A running transition of this container ends first.
  const replaces = !!prev && prev.html !== "";
  // An update of what is showing (fresh data for the current scene) is not a scene change: it neither animates nor
  // interrupts the animation that may still be running.
  const transitions = !inPlace && contentChanged && html !== "" && transitionWanted();
  if (contentChanged && !inPlace) runningTransitions[containerId]?.();
  const outro = contentChanged && !inPlace ? outros[containerId] : undefined;
  if (outro) {
    // The old content has left at the end of its scene; this element is reused for the new one.
    outro.end();
    delete outros[containerId];
  }
  containerSlots[containerId].style.display = ""; // (after the end of a running leave, which hides it)
  if (transitions && replaces && !outro) {
    const oldCssEl = cssChanged ? document.getElementById(`content-type-css-${containerId}`) : null;
    el = startTransition(containerId, oldCssEl);
  } else if (transitions) {
    const slot = containerSlots[containerId];
    // After an outro only the second half is left (sequential mode); the pick of the outro carries on.
    const options = introAfterOutro && getTransitionConfig().sequential ? { phase: "in" as const, choice: outro?.choice } : {};
    runningTransitions[containerId] = playTransition(null, el, () => {
      delete runningTransitions[containerId];
    }, { ...options, ...transitionOptions(containerId) });
  }

  if (contentChanged) {
    el.innerHTML = adaptHtml(html);
    adaptMediaImages(el);
  }

  if (cssChanged) {
    const cssId = `content-type-css-${containerId}`;
    let cssEl = document.getElementById(cssId) as HTMLStyleElement | null;
    if (!cssEl) {
      cssEl = document.createElement("style");
      cssEl.id = cssId;
      document.head.appendChild(cssEl);
    }
    const adapted = adaptCss(css);
    cssEl.textContent = adapted;
    // Swap uploaded-image urls for renditions once they're confirmed to exist.
    void adaptMediaCss(adapted).then((withRenditions) => {
      // Only if nothing wrote this style in the meantime (a newer scene, or the container was emptied).
      if (withRenditions !== adapted && cssEl && cssEl.textContent === adapted) cssEl.textContent = withRenditions;
    });
  }

  lastPainted[containerId] = { top: c.top, left: c.left, width: c.width, height: c.height, html, css };
  return contentChanged;
}

/**
 * Render *scene*: every container it uses (including any of its own Layout's
 * containers the server already fell back to a default for) is
 * created/positioned/populated; any previously-known container NOT used by
 * this scene goes blank — even if it belongs to a different Layout and has
 * its own default configured, since that default only applies while a scene
 * from *its own* Layout is showing (see upd_content.py).
 */
export function renderScene(scene: Scene, inPlace = false): void {
  const activeIds = new Set(Object.keys(scene.containers));
  if (!inPlace) {
    introAfterOutro = outroActive;
    outroActive = false;
    repaintUnchanged = getTransitionConfig().unchanged && transitionWanted();
    beginSceneTransition(introAfterOutro);
    // The start order of everything that changes: the containers of the new scene and those that go blank.
    staggerRanks = computeStagger([
      ...Object.entries(scene.containers).map(([id, c]) => ({ id, top: c.top, left: c.left, width: c.width, height: c.height })),
      ...Object.entries(lastPainted)
        .filter(([id]) => !activeIds.has(id))
        .map(([id, c]) => ({ id, top: c.top, left: c.left, width: c.width, height: c.height })),
    ]);

    for (const id of Object.keys(containerElements)) {
      if (!activeIds.has(id)) clearContainerElement(id);
    }
  }

  const changedIds: string[] = [];
  for (const [id, c] of Object.entries(scene.containers)) {
    if (paintContainerElement(id, c, inPlace)) changedIds.push(id);
  }

  try {
    window.debugPanel?.pushLayout?.(
      scene.title || `Scene ${scene.id}`,
      Object.entries(scene.containers).map(([id, c]) => ({
        id,
        name: c.name,
        top: c.top,
        left: c.left,
        width: c.width,
        height: c.height,
        hasContent: !!c.html,
      })),
    );
  } catch (e) {
    /* intentional: debugPanel may not be initialized yet */
  }

  if (!inPlace) {
    // Outros of containers that kept their content after all: show it again.
    cancelOutros();
    introAfterOutro = false;
    repaintUnchanged = false;
  }

  tickNow(); // immediately fill any dh-clock elements in the new HTML
  // What a field handler needs to do with the HTML it was just given (start a ticker, swap a placeholder
  // for an image or an icon) is the handler's plugin's business: it is told about every container, and
  // whether its content changed.
  const changed = new Set(changedIds);
  runAfterRender(
    [...activeIds].flatMap((id) => {
      const element = containerElements[id];
      return element ? [{ id, element, changed: changed.has(id) }] : [];
    }),
  );
  log(
    "info", "renderScene",
    `Rendered scene ${scene.id} across ${activeIds.size} container(s), ${changedIds.length} changed`,
  );
}

/**
 * Sequential mode: the old content leaves in the last half of its scene instead of when the next one starts. Called
 * by the rotation shortly before the scene ends, with the scene that follows. Containers whose content changes in
 * *next* (or that it does not use) are animated out and held; renderScene() then brings the new content in.
 */
export function playOutro(next: Scene): void {
  if (!transitionWanted() || !getTransitionConfig().sequential) return;
  cancelOutros();
  beginSceneTransition();
  const leaving: string[] = [];
  for (const id of Object.keys(containerElements)) {
    const painted = lastPainted[id];
    if (!painted || painted.html === "" || runningTransitions[id]) continue;
    if ((next.containers[id]?.html ?? "") === painted.html && !getTransitionConfig().unchanged) continue;
    leaving.push(id);
  }
  staggerRanks = computeStagger(leaving.map((id) => ({ id, ...lastPainted[id] })));
  for (const id of leaving) {
    const choice = chooseTransition();
    outros[id] = { choice, end: playTransition(containerElements[id], null, () => {}, { ...transitionOptions(id), choice, phase: "out" }) };
    outroActive = true;
  }
}

/** Bring back whatever an outro hid (the scene change did not replace it). */
export function cancelOutros(): void {
  for (const id of Object.keys(outros)) {
    outros[id].end();
    delete outros[id];
  }
  outroActive = false;
}

/** Blank every known container (e.g. when the rotation has nothing to show). */
export function clearAllContainers(): void {
  introAfterOutro = outroActive;
  outroActive = false;
  beginSceneTransition(introAfterOutro);
  staggerRanks = {};
  for (const id of Object.keys(containerElements)) {
    clearContainerElement(id);
  }
  introAfterOutro = false;
}
