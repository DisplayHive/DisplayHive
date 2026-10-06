/**
 * Screen rotation: the whole rendered stage (#main-container — design
 * background, effect and every container) is turned as one piece, as if all
 * of it sat on a common rotated backdrop. There are no per-element rotations.
 *
 * The server lays the content out at the screen's aspect ratio; for a
 * quarter turn (90/270) that logical stage is the physical viewport with
 * width and height swapped. CSS viewport units always refer to the physical
 * viewport though, so for quarter turns every length in vh/vw that is meant
 * "relative to the stage" must swap axes: the stage's 1vh (1% of its height)
 * is the viewport's 1vw. adaptCss/adaptHtml/containerGeometry do that for
 * everything the server sends (Design CSS/HTML, container CSS/HTML and
 * positions). The "Powered by" badge is moved into the stage so it turns too. Body selectors in CSS are retargeted to the stage too, so a
 * Backdrop (gradient/image on `body`) turns with everything else.
 */

import { getStoredRotation, setStoredRotation } from "./storage";

let rotation = getStoredRotation();

export type Rotation = 0 | 90 | 180 | 270;

export function getRotation(): Rotation {
  return rotation as Rotation;
}

const isQuarterTurn = (): boolean => rotation === 90 || rotation === 270;

/** Sets (and remembers) the rotation, then re-applies the stage transform. */
export function setRotation(deg: number): void {
  const next = ((Math.round(deg / 90) * 90) % 360 + 360) % 360;
  rotation = next === 90 || next === 180 || next === 270 ? next : 0;
  setStoredRotation(rotation);
  applyStageTransform();
}

// 1.5vh / -.5 vw / 100dvh … -> same number with the h/w axis swapped.
const VIEWPORT_UNIT = /(-?(?:\d+\.?\d*|\.\d+))(\s*)([dsl]?)v([hw])\b/gi;

function swapViewportUnits(text: string): string {
  return text.replace(VIEWPORT_UNIT, (_m, num: string, space: string, prefix: string, axis: string) => {
    const swapped = axis === axis.toLowerCase() ? (axis === "h" ? "w" : "h") : axis === "H" ? "W" : "H";
    return `${num}${space}${prefix}v${swapped}`;
  });
}

// A rule-leading `body` (optionally `html body`) selector -> the stage.
const BODY_SELECTOR = /(^|[},]|\*\/)(\s*)(?:html\s+)?body(?![\w-])/g;

/** Adapts Design/container CSS to the current rotation. */
export function adaptCss(css: string): string {
  if (!rotation || !css) return css;
  let out = css.replace(BODY_SELECTOR, "$1$2#main-container");
  if (isQuarterTurn()) out = swapViewportUnits(out);
  return out;
}

/** Adapts HTML carrying inline vh/vw styles to the current rotation. */
export function adaptHtml(html: string): string {
  if (!isQuarterTurn() || !html) return html;
  return swapViewportUnits(html);
}

/** The unit for lengths measured along the stage's height: `vh`, or `vw` for quarter turns. */
export function stageHeightUnit(): "vh" | "vw" {
  return isQuarterTurn() ? "vw" : "vh";
}

/** A container's position as CSS lengths, axis-swapped for quarter turns. */
export function containerGeometry(c: { top: number; left: number; width: number; height: number }) {
  if (isQuarterTurn()) {
    return { top: `${c.top}vw`, left: `${c.left}vh`, width: `${c.width}vh`, height: `${c.height}vw` };
  }
  return { top: `${c.top}vh`, left: `${c.left}vw`, width: `${c.width}vw`, height: `${c.height}vh` };
}

/** Turns #main-container (the stage) for the current rotation. */
export function applyStageTransform(): void {
  if (typeof document === "undefined") return;
  const stage = document.getElementById("main-container");
  if (!stage) return;

  // The "Powered by" badge is `position: fixed` outside the stage. A transformed
  // ancestor becomes the containing block of fixed descendants, so living
  // inside the stage it keeps its bottom-right corner *of the rotated stage*
  // and turns with everything else; unrotated it goes back to the body.
  const badge = document.getElementById("powered-by-badge");
  if (badge) {
    if (rotation !== 0 && badge.parentElement !== stage) stage.appendChild(badge);
    else if (rotation === 0 && badge.parentElement === stage) document.body.appendChild(badge);
  }

  const s = stage.style;
  if (rotation === 0) {
    s.position = s.top = s.left = s.width = s.height = s.transform = s.transformOrigin = s.flex = "";
    return;
  }
  if (rotation === 180) {
    s.transformOrigin = "50% 50%";
    s.transform = "rotate(180deg)";
    return;
  }
  // Quarter turns: the stage is the viewport with its sides swapped, turned
  // about its top-left corner and slid back into view.
  s.position = "fixed";
  s.top = "0";
  s.left = "0";
  s.flex = "none";
  s.width = "100vh";
  s.height = "100vw";
  s.transformOrigin = "0 0";
  s.transform = rotation === 90 ? "translateX(100vw) rotate(90deg)" : "translateY(100vh) rotate(-90deg)";
}
