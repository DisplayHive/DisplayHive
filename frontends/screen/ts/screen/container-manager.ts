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

/**
 * Render *scene*: every container it uses is created/positioned/populated;
 * any previously-known container not used by this scene goes blank.
 */
export function renderScene(scene: Scene): void {
  const activeIds = new Set(Object.keys(scene.containers));

  for (const id of Object.keys(containerElements)) {
    if (!activeIds.has(id)) clearContainerElement(id);
  }

  for (const [id, c] of Object.entries(scene.containers)) {
    const el = ensureContainerElement(id);
    if (!el) continue;

    el.style.top = `${c.top}vh`;
    el.style.left = `${c.left}vw`;
    el.style.width = `${c.width}vw`;
    el.style.height = `${c.height}vh`;
    el.innerHTML = c.html || "";

    const cssId = `content-type-css-${id}`;
    let cssEl = document.getElementById(cssId) as HTMLStyleElement | null;
    if (!cssEl) {
      cssEl = document.createElement("style");
      cssEl.id = cssId;
      document.head.appendChild(cssEl);
    }
    cssEl.textContent = c.css || "";
  }

  tickNow(); // immediately fill any dh-clock elements in the new HTML
  log("info", "renderScene", `Rendered scene ${scene.id} across ${activeIds.size} container(s)`);
}

/** Blank every known container element (e.g. when the rotation has nothing to show). */
export function clearAllContainers(): void {
  for (const id of Object.keys(containerElements)) clearContainerElement(id);
}
