/**
 * Progress indicator: a bar along the bottom of the stage that fills over the
 * time the current scene is shown (its `duration`), then restarts with the
 * next scene. Enabled/colour/height/direction come from the active Design
 * (`design.indicator` in the upd_content payload; see
 * application/admin/designs/helper.py's indicator_payload).
 *
 * The bar lives inside #main-container, so it rotates with everything else;
 * its height is measured along the stage's height (vh, or vw on quarter
 * turns — see rotation.ts).
 */

import { stageHeightUnit } from "./rotation.js";

export interface IndicatorConfig {
  enabled: boolean;
  color: string;
  /** Height in vh (stage height). */
  height: number;
  /** 'ltr' fills from left to right, 'rtl' from right to left. */
  direction: "ltr" | "rtl";
}

let config: IndicatorConfig | null = null;
let lastDuration = 0;
let suppressed = false;

function elements(): { box: HTMLElement; bar: HTMLElement } | null {
  const box = document.getElementById("scene-indicator");
  const bar = document.getElementById("scene-indicator-bar");
  return box && bar ? { box, bar } : null;
}

function normalize(raw: unknown): IndicatorConfig | null {
  const c = raw as Partial<IndicatorConfig> | null | undefined;
  if (!c || typeof c !== "object") return null;
  const height = Number(c.height);
  return {
    enabled: c.enabled === true,
    color: typeof c.color === "string" && c.color ? c.color : "#ffffff",
    height: Number.isFinite(height) && height > 0 ? height : 0.8,
    direction: c.direction === "rtl" ? "rtl" : "ltr",
  };
}

/** Restart the fill animation from empty over *seconds*. */
function restart(bar: HTMLElement, seconds: number): void {
  bar.style.animation = "none";
  void bar.offsetWidth; // flush so the animation really restarts
  bar.style.animation = `dh-indicator-fill ${seconds}s linear forwards`;
}

/** Shown at all: enabled in the Design, and not suppressed (see setIndicatorSuppressed). */
const visible = (): boolean => !!config && config.enabled && !suppressed;

/** Bring the element in line with the current config / suppression state. */
function refresh(): void {
  const els = elements();
  if (!els) return;
  const { box, bar } = els;
  if (!config || !visible()) {
    box.hidden = true;
    bar.style.animation = "none";
    return;
  }
  box.style.height = `${config.height}${stageHeightUnit()}`;
  bar.style.backgroundColor = config.color;
  bar.style.transformOrigin = config.direction === "rtl" ? "right center" : "left center";
  const wasHidden = box.hidden;
  box.hidden = false;
  // Switched on (or un-suppressed) while a scene is already running: start filling from now.
  if (wasHidden && lastDuration > 0) restart(bar, lastDuration);
}

/**
 * Apply the Design's indicator settings. Style changes don't restart a fill
 * already in progress; turning the indicator off hides it.
 */
export function applyIndicatorConfig(raw: unknown): void {
  config = normalize(raw);
  refresh();
}

/**
 * Hide the bar while there is nothing to count down to — with a single active
 * scene the content never changes, so a bar that fills and restarts would just
 * be noise. Shown again as soon as there are two or more.
 */
export function setIndicatorSuppressed(value: boolean): void {
  if (value === suppressed) return;
  suppressed = value;
  refresh();
}

/** A scene was (re)shown: fill the bar over its duration (no-op if hidden). */
export function startIndicator(durationSeconds: number): void {
  lastDuration = durationSeconds > 0 ? durationSeconds : 0;
  const els = elements();
  if (!els || !visible()) return;
  if (lastDuration <= 0) {
    // No duration, no advance — nothing meaningful to count down.
    els.bar.style.animation = "none";
    els.bar.style.transform = "scaleX(0)";
    return;
  }
  restart(els.bar, lastDuration);
}

/** Nothing is showing (no scenes): empty the bar. */
export function stopIndicator(): void {
  lastDuration = 0;
  const els = elements();
  if (els) els.bar.style.animation = "none";
}
