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

import type { Scene, ContainerDefault } from "./types.js";
import { tickNow } from "./clock.js";
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

// containerId (string) -> its configured fallback content, refreshed on
// every `upd_content` push. Shown whenever the currently active scene
// doesn't target that container, instead of leaving it blank.
let containerDefaults: Record<string, ContainerDefault> = {};

/** Replace the known set of container fallback contents (called from upd_content). */
export function setContainerDefaults(defaults: Record<string, ContainerDefault>): void {
  containerDefaults = defaults || {};
}

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
  // Stable per-container hook for Design CSS — unlike the container's name
  // (editable any time in the admin), the id never changes, so a Design's
  // `.dh-container-<id>` rule keeps working across renames.
  el.classList.add(`dh-container-${containerId}`);
  el.style.position = "absolute";
  root.appendChild(el);
  containerElements[containerId] = el;
  return el;
}

/** Empty a container's DOM element and its scoped CSS, without removing it from the DOM. */
function clearContainerElement(containerId: string): void {
  const el = containerElements[containerId];
  if (el) el.innerHTML = "";
  const cssEl = document.getElementById(`content-type-css-${containerId}`);
  if (cssEl) cssEl.textContent = "";
}

/** Populate a container's DOM element with the given fragment (scene content or a default). */
function paintContainerElement(
  containerId: string,
  c: { top: number; left: number; width: number; height: number; html: string; css?: string },
): void {
  const el = ensureContainerElement(containerId);
  if (!el) return;

  el.style.top = `${c.top}vh`;
  el.style.left = `${c.left}vw`;
  el.style.width = `${c.width}vw`;
  el.style.height = `${c.height}vh`;
  el.innerHTML = c.html || "";

  const cssId = `content-type-css-${containerId}`;
  let cssEl = document.getElementById(cssId) as HTMLStyleElement | null;
  if (!cssEl) {
    cssEl = document.createElement("style");
    cssEl.id = cssId;
    document.head.appendChild(cssEl);
  }
  cssEl.textContent = c.css || "";
}

/**
 * Show *containerId*'s configured fallback content, if any. Returns true if
 * a default was actually rendered (so callers know not to blank it instead).
 */
function paintContainerDefault(containerId: string): boolean {
  const def = containerDefaults[containerId];
  if (!def) return false;
  paintContainerElement(containerId, def);
  return true;
}

/**
 * Render *scene*: every container it uses is created/positioned/populated;
 * any previously-known container not used by this scene falls back to its
 * own configured default content, or goes blank if it has none.
 */
export function renderScene(scene: Scene): void {
  const activeIds = new Set(Object.keys(scene.containers));

  const knownIds = new Set([...Object.keys(containerElements), ...Object.keys(containerDefaults)]);
  for (const id of knownIds) {
    if (activeIds.has(id)) continue;
    if (!paintContainerDefault(id)) clearContainerElement(id);
  }

  for (const [id, c] of Object.entries(scene.containers)) {
    paintContainerElement(id, c);
  }

  tickNow(); // immediately fill any dh-clock elements in the new HTML
  log("info", "renderScene", `Rendered scene ${scene.id} across ${activeIds.size} container(s)`);
}

/**
 * Fall every known container back to its default content (e.g. when the
 * rotation has nothing to show); containers without a configured default
 * just go blank.
 */
export function clearAllContainers(): void {
  const knownIds = new Set([...Object.keys(containerElements), ...Object.keys(containerDefaults)]);
  for (const id of knownIds) {
    if (!paintContainerDefault(id)) clearContainerElement(id);
  }
}
