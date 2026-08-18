/**
 * Countdown renderer for screen devices.
 *
 * Mirrors clock.ts's role for [data-dh-clock] elements: every second,
 * tickCountdown() updates all [data-dh-countdown] elements using the target
 * datetime, format string and finished-text stored in their data attributes.
 * Reuses clock.ts's server-corrected getNow() so a countdown stays in sync
 * with the same server time offset as the clock, rather than trusting the
 * screen's own unadjusted clock.
 */

import { getNow } from "./clock.js";

let _tickInterval: ReturnType<typeof setInterval> | null = null;

function _format(remainingMs: number, fmt: string): string {
  const totalSeconds = Math.max(0, Math.floor(remainingMs / 1000));
  const days = Math.floor(totalSeconds / 86400);
  const hours = Math.floor((totalSeconds % 86400) / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  return fmt.replace(/DD|D|HH|H|mm|m|ss|s/g, token => {
    switch (token) {
      case "DD": return String(days).padStart(2, "0");
      case "D":  return String(days);
      case "HH": return String(hours).padStart(2, "0");
      case "H":  return String(hours);
      case "mm": return String(minutes).padStart(2, "0");
      case "m":  return String(minutes);
      case "ss": return String(seconds).padStart(2, "0");
      case "s":  return String(seconds);
      default:   return token;
    }
  });
}

export function tickCountdown(): void {
  const now = getNow().getTime();
  document.querySelectorAll<HTMLElement>("[data-dh-countdown]").forEach(el => {
    const targetRaw = el.getAttribute("data-dh-countdown-target") || "";
    const fmt = el.getAttribute("data-dh-countdown-format") || "DD:HH:mm:ss";
    const finishedText = el.getAttribute("data-dh-countdown-finished") || "";
    const target = new Date(targetRaw).getTime();
    if (isNaN(target)) {
      el.textContent = "";
      return;
    }
    const remainingMs = target - now;
    el.textContent = remainingMs <= 0 && finishedText
      ? finishedText
      : _format(remainingMs, fmt);
  });
}

export function startCountdownTicker(): void {
  if (_tickInterval) return;
  tickCountdown();
  _tickInterval = setInterval(tickCountdown, 1000);
}
