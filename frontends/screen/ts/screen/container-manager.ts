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

import type { Scene } from "./types.js";
import { tickNow } from "./clock.js";
import { resolveIcons } from "./icon-resolver.js";
import { log } from "./logger.js";

// Optional emitter injected by socket setup so this module does not
// directly depend on `window.socket`. Call `setSocketEmitter` with
// a function `(event, payload) => void` (for example `socket.emit`).
let socketEmitter: ((event: string, payload?: any) => void) | null = null;

export function setSocketEmitter(
  emitter: (event: string, payload?: any) => void,
): void {
  socketEmitter = emitter;
}

export function getSocketEmitter():
  | ((event: string, payload?: any) => void)
  | null {
  return socketEmitter;
}

// containerId (string) -> its DOM element
const containerElements: Record<string, HTMLElement> = {};

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

function ensureContainerElement(containerId: string): HTMLElement | null {
  const existing = containerElements[containerId];
  if (existing) return existing;

  const root = getOverlayRoot();
  if (!root) {
    log("error", "ensureContainerElement", "#scene-containers not found in DOM");
    return null;
  }

  const el = document.createElement("div");
  el.dataset.containerId = containerId;
  // `.dh-container` is shared by every container (a Design's global style
  // hook); `.dh-container-<id>` is this one's stable per-container hook —
  // unlike the container's name (editable any time in the admin), the id
  // never changes, so a Design's rule keeps working across renames.
  el.classList.add("dh-container", `dh-container-${containerId}`);
  el.style.position = "absolute";
  root.appendChild(el);
  containerElements[containerId] = el;
  return el;
}

/** Empty a container's DOM element and its scoped CSS, without removing it from the DOM. */
function clearContainerElement(containerId: string): void {
  if (!(containerId in lastPainted)) return; // already blank — nothing to do
  const el = containerElements[containerId];
  if (el) el.innerHTML = "";
  const cssEl = document.getElementById(`content-type-css-${containerId}`);
  if (cssEl) cssEl.textContent = "";
  delete lastPainted[containerId];
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
): boolean {
  const el = ensureContainerElement(containerId);
  if (!el) return false;

  const css = c.css || "";
  const html = c.html || "";
  const prev = lastPainted[containerId];
  const positionChanged = !prev || prev.top !== c.top || prev.left !== c.left || prev.width !== c.width || prev.height !== c.height;
  const contentChanged = !prev || prev.html !== html;
  const cssChanged = !prev || prev.css !== css;

  if (positionChanged) {
    el.style.top = `${c.top}vh`;
    el.style.left = `${c.left}vw`;
    el.style.width = `${c.width}vw`;
    el.style.height = `${c.height}vh`;
  }

  if (contentChanged) {
    el.innerHTML = html;
  }

  if (cssChanged) {
    const cssId = `content-type-css-${containerId}`;
    let cssEl = document.getElementById(cssId) as HTMLStyleElement | null;
    if (!cssEl) {
      cssEl = document.createElement("style");
      cssEl.id = cssId;
      document.head.appendChild(cssEl);
    }
    cssEl.textContent = css;
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
export function renderScene(scene: Scene): void {
  const activeIds = new Set(Object.keys(scene.containers));

  for (const id of Object.keys(containerElements)) {
    if (!activeIds.has(id)) clearContainerElement(id);
  }

  const changedIds: string[] = [];
  for (const [id, c] of Object.entries(scene.containers)) {
    if (paintContainerElement(id, c)) changedIds.push(id);
  }

  tickNow(); // immediately fill any dh-clock elements in the new HTML
  // Only re-resolve icon placeholders inside containers whose content
  // actually changed — resolveIcons() re-fetches+reinjects unconditionally
  // for whatever it's given, so scoping this avoids needlessly reloading an
  // icon that was already showing correctly.
  for (const id of changedIds) {
    const el = containerElements[id];
    if (el) void resolveIcons(el);
  }
  log(
    "info", "renderScene",
    `Rendered scene ${scene.id} across ${activeIds.size} container(s), ${changedIds.length} changed`,
  );
}

/** Blank every known container (e.g. when the rotation has nothing to show). */
export function clearAllContainers(): void {
  for (const id of Object.keys(containerElements)) {
    clearContainerElement(id);
  }
}
