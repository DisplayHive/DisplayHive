/**
 * Daily scheduled reload: a screen that runs for weeks reloads itself once a day at a time the admin
 * sets (Settings → Screens), picking up a new release of the page and clearing whatever a long-running
 * browser tab collects. The time is read in the instance's time zone (`timezone` setting), like the
 * schedules of content.
 *
 * Before reloading the page asks the service worker to look for a new release (so the reload loads it)
 * and waits for a connection: with the server unreachable and no service worker, a reload would leave
 * a blank page, so it is tried again on the next check instead.
 */

import { log } from "./logger.js";
import { getLastScheduledReload, setLastScheduledReload } from "./storage.js";

const CHECK_EVERY_MS = 30_000;
/** After a new service worker took control, reload this soon so the page runs the new release. */
const AFTER_UPDATE_RELOAD_MS = 5_000;

const TIME = /^([01]\d|2[0-3]):([0-5]\d)$/;

/** "HH:MM" as minutes since midnight, or null (empty = off, or not a time). */
export function parseTime(text: string | null | undefined): number | null {
  const m = TIME.exec((text ?? "").trim());
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

/** The date ("YYYY-MM-DD") and minutes since midnight of *now* in the time zone (the local one if unknown). */
export function clockIn(now: Date, timeZone: string | null | undefined): { day: string; minutes: number } {
  let parts: Intl.DateTimeFormatPart[];
  try {
    parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: timeZone || undefined,
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(now);
  } catch {
    return clockIn(now, null);
  }
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "00";
  return { day: `${get("year")}-${get("month")}-${get("day")}`, minutes: Number(get("hour")) * 60 + Number(get("minute")) };
}

/** Time to reload: today's time has passed and today's reload has not happened yet. */
export function isDue(now: Date, timeZone: string | null | undefined, target: number, lastDone: string | null): boolean {
  const clock = clockIn(now, timeZone);
  return clock.minutes >= target && lastDone !== clock.day;
}

let target: number | null = null;
let timeZone: string | null = null;
let timer: ReturnType<typeof setInterval> | undefined;
let connected = () => true;

/** How the page knows the server can be reached right now. */
export function setConnectionCheck(check: () => boolean): void {
  connected = check;
}

async function reloadNow(): Promise<void> {
  try {
    const registration = await navigator.serviceWorker?.getRegistration();
    await Promise.race([registration?.update(), new Promise((resolve) => setTimeout(resolve, 5_000))]);
  } catch {
    /* no service worker: reload anyway */
  }
  window.location.reload();
}

function check(): void {
  if (target === null || !isDue(new Date(), timeZone, target, getLastScheduledReload())) return;
  if (!connected()) {
    log("warn", "scheduled-reload", "Reload is due but the server cannot be reached; trying again");
    return;
  }
  setLastScheduledReload(clockIn(new Date(), timeZone).day);
  log("info", "scheduled-reload", "Daily reload");
  void reloadNow();
}

/**
 * Apply the admin's setting (from `upd_deviceconfig`): `at` is "HH:MM" or empty for off.
 * A page that starts after the time of the day has just loaded, so today's reload counts as done.
 */
export function setScheduledReload(at: string | null | undefined, zone: string | null | undefined): void {
  target = parseTime(at);
  timeZone = zone || null;
  clearInterval(timer);
  if (target === null) return;
  const clock = clockIn(new Date(), timeZone);
  if (clock.minutes >= target && getLastScheduledReload() !== clock.day) setLastScheduledReload(clock.day);
  timer = setInterval(check, CHECK_EVERY_MS);
}

/**
 * When a new service worker takes over (a new release was deployed), reload shortly after, so the
 * page does not keep running the old release's script against the new release's files.
 */
export function reloadOnReleaseChange(): void {
  if (!("serviceWorker" in navigator) || !navigator.serviceWorker.controller) return;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    log("info", "scheduled-reload", "A new release is active; reloading");
    setTimeout(() => {
      if (connected()) window.location.reload();
    }, AFTER_UPDATE_RELOAD_MS);
  });
}
