/**
 * Status indicator: a small dot with its codes in the top-left corner of the stage — shown only
 * when something is wrong, hidden while everything is fine.
 *
 *   red     con  the connection to the server is down (disconnected / connection error)
 *   yellow  mim  content is missing: nothing to show, or an image/video of the stage failed to load
 *   yellow  js   an uncaught JavaScript error (clears after JS_ERROR_TTL_MS without a new one)
 *
 * Red wins over yellow. Every code that switches on is also written to the screen log (see
 * logger.ts), so an admin sees the cause without standing in front of the screen. The Settings page
 * can switch the dot off (`statusindicator` in upd_deviceconfig); the states are tracked and logged
 * either way.
 *
 * Style: by default the colored dot plus the codes above. Settings can switch it to icons
 * (`statusstyle` in upd_deviceconfig): one pictogram per active problem instead, in the order
 * red first, without the dot and without text. The icons are drawn here (inline SVG) so the screen
 * needs no icon font; the codes stay in the tooltip and the screen log.
 */

import { log } from "./logger.js";

export type StatusCode = "con" | "mim" | "js";

const RED: StatusCode[] = ["con"];
const JS_ERROR_TTL_MS = 5 * 60 * 1000;

export type StatusStyle = "dot" | "icons";

/** 24×24 line pictograms, drawn with `currentColor`. */
const ICONS: Record<StatusCode, { label: string; paths: string[] }> = {
  // wifi arcs with a slash: no connection to the server
  con: {
    label: "No connection to the server",
    paths: ["M3 9c5-4.5 13-4.5 18 0", "M6 13c3.5-3 8.5-3 12 0", "M9.5 17c1.5-1.2 3.5-1.2 5 0", "M12 20.5h.01", "M3 3l18 18"],
  },
  // picture frame with a slash: content missing or an image/video did not load
  mim: {
    label: "Content is missing",
    paths: ["M5 4h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z", "M3 16l5-5 4 4 3-3 6 6", "M9 8.5h.01", "M3 3l18 18"],
  },
  // angle brackets with an exclamation mark: a script error
  js: {
    label: "A script error occurred",
    paths: ["M8 7l-5 5 5 5", "M16 7l5 5-5 5", "M12 8v5", "M12 16.5h.01"],
  },
};

const SVG_NS = "http://www.w3.org/2000/svg";

function iconElement(code: StatusCode): SVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "2");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("class", `status-icon status-icon--${code}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", ICONS[code].label);
  for (const d of ICONS[code].paths) {
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", d);
    svg.appendChild(path);
  }
  return svg;
}

const reasons = new Map<StatusCode, string>();
let enabled = true;
let style: StatusStyle = "dot";
let jsTimer: ReturnType<typeof setTimeout> | undefined;
const failedMedia = new Set<string>();

function element(): HTMLElement | null {
  let el = document.getElementById("status-indicator");
  if (!el) {
    const stage = document.getElementById("main-container");
    if (!stage) return null;
    el = document.createElement("div");
    el.id = "status-indicator";
    el.hidden = true;
    el.setAttribute("role", "status");
    stage.appendChild(el);
  }
  return el;
}

/** The codes currently on, red ones first. */
export function activeCodes(): StatusCode[] {
  const all = Array.from(reasons.keys());
  return [...all.filter((c) => RED.includes(c)), ...all.filter((c) => !RED.includes(c))];
}

/** "red", "yellow", or null when everything is fine. */
export function statusLevel(): "red" | "yellow" | null {
  const codes = activeCodes();
  if (!codes.length) return null;
  return codes.some((c) => RED.includes(c)) ? "red" : "yellow";
}

function render(): void {
  const el = element();
  if (!el) return;
  const level = statusLevel();
  if (!enabled || !level) {
    el.hidden = true;
    return;
  }
  el.dataset.level = level;
  el.dataset.style = style;
  if (style === "icons") el.replaceChildren(...activeCodes().map(iconElement));
  else el.textContent = activeCodes().join(" ");
  el.title = Array.from(reasons.entries()).map(([c, r]) => `${c}: ${r}`).join("\n");
  el.hidden = false;
}

/** Switch a code on (with the reason, for the log and the tooltip) or off (`reason` null). */
export function setStatus(code: StatusCode, reason: string | null): void {
  if (reason === null) {
    if (reasons.delete(code)) {
      log("info", "status-indicator", `${code} cleared`);
      render();
    }
    return;
  }
  const isNew = !reasons.has(code);
  reasons.set(code, reason);
  if (isNew) log(RED.includes(code) ? "error" : "warn", "status-indicator", `${code}: ${reason}`);
  render();
}

/** Show or hide the dot (the admin's setting). */
export function setStatusIndicatorEnabled(value: boolean): void {
  enabled = value;
  render();
}

/** Dot with codes (default) or icons (the admin's setting). */
export function setStatusIndicatorStyle(value: StatusStyle): void {
  style = value;
  render();
}

function describeError(value: unknown): string {
  if (value instanceof Error) return value.message;
  return String(value ?? "unknown error").slice(0, 200);
}

function noteJsError(reason: string): void {
  setStatus("js", reason);
  clearTimeout(jsTimer);
  jsTimer = setTimeout(() => setStatus("js", null), JS_ERROR_TTL_MS);
}

/** A media element of the stage failed (`mediaSrc`) or loaded after all. */
function noteMedia(src: string, failed: boolean): void {
  if (failed) failedMedia.add(src);
  else failedMedia.delete(src);
  setStatus("mim", failedMedia.size ? `media failed to load: ${Array.from(failedMedia)[0]}` : null);
}

/** The content is gone (no scenes) or back; media errors of the old scenes are forgotten. */
export function setContentMissing(missing: boolean): void {
  failedMedia.clear();
  setStatus("mim", missing ? "no content to show" : null);
}

/** Install the global listeners (JavaScript errors, failing media). Call once. */
let installed = false;
export function initStatusIndicator(): void {
  if (installed) return;
  installed = true;
  window.addEventListener("error", (event) => {
    // Resource errors are dispatched to the element, not window — handled in the capture listener below.
    if (event.target && event.target !== window) return;
    noteJsError(describeError(event.error ?? event.message));
  });
  window.addEventListener("unhandledrejection", (event) => noteJsError(describeError(event.reason)));
  // Errors of elements don't bubble: listen in the capture phase.
  document.addEventListener(
    "error",
    (event) => {
      const t = event.target;
      if ((t instanceof HTMLImageElement || t instanceof HTMLVideoElement || t instanceof HTMLSourceElement) && t.closest("#main-container")) {
        noteMedia((t as HTMLImageElement).currentSrc || (t as HTMLImageElement).src || "unknown", true);
      }
    },
    true,
  );
  document.addEventListener(
    "load",
    (event) => {
      const t = event.target;
      if (t instanceof HTMLImageElement && failedMedia.has(t.currentSrc || t.src)) noteMedia(t.currentSrc || t.src, false);
    },
    true,
  );
  render();
}
