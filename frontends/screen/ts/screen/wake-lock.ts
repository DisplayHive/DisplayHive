/**
 * Keeps the display awake (Screen Wake Lock API), so a screen's browser does not dim or blank the
 * display after a while without input.
 *
 * The browser drops the lock whenever the page is hidden; it is asked for again when the page is
 * visible. Needs a secure context (https or localhost) and a browser that has the API — elsewhere
 * this does nothing (a kiosk's own power settings have to do the job).
 */

import { log } from "./logger.js";

interface WakeLockSentinelLike {
  released: boolean;
  addEventListener(type: "release", listener: () => void): void;
}
interface WakeLockApi {
  request(type: "screen"): Promise<WakeLockSentinelLike>;
}

let installed = false;
let sentinel: WakeLockSentinelLike | null = null;

async function acquire(api: WakeLockApi): Promise<void> {
  if (sentinel && !sentinel.released) return;
  if (document.visibilityState !== "visible") return;
  try {
    sentinel = await api.request("screen");
    sentinel.addEventListener("release", () => {
      sentinel = null;
    });
    log("debug", "wake-lock", "Screen wake lock acquired");
  } catch (error) {
    // Refused (battery saver, no permission): try again at the next chance.
    log("warn", "wake-lock", "Could not keep the display awake", String(error));
  }
}

export function initWakeLock(): void {
  if (installed) return;
  installed = true;
  const api = (navigator as Navigator & { wakeLock?: WakeLockApi }).wakeLock;
  if (!api) {
    log("info", "wake-lock", "Screen Wake Lock is not available here (needs https or localhost); not keeping the display awake");
    return;
  }
  void acquire(api);
  document.addEventListener("visibilitychange", () => void acquire(api));
  // Some browsers only grant it after the first interaction.
  window.addEventListener("pointerdown", () => void acquire(api), { passive: true });
}
