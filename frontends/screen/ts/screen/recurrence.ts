/**
 * Weekly time windows of a scene (a content element's `recurrence`, see
 * application/admin/content/recurrence.py): the scene is shown only inside them. Days are ISO
 * weekdays (1 = Monday … 7 = Sunday), times are wall-clock in the instance's time zone; a window
 * whose `to` is not after `from` runs past midnight into the next day. No windows = always.
 *
 * Arithmetic is done in "minutes of the week" (Monday 00:00 = 0), so crossing midnight or the end of
 * the week needs no calendar. The admin has the same logic in
 * frontends/admin/src/utils/content/recurrence.ts — keep them in step.
 */

export interface WeeklyWindow {
  days: number[];
  from: string;
  to: string;
}

const WEEK = 7 * 24 * 60;
const TIME = /^([01]\d|2[0-3]):([0-5]\d)$/;

function minutesOf(text: string): number | null {
  const m = TIME.exec(text);
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

/** The windows as [start, end) intervals in minutes of the week; `end` may exceed a week (past Sunday midnight). */
function intervals(windows: WeeklyWindow[]): Array<[number, number]> {
  const out: Array<[number, number]> = [];
  for (const w of windows) {
    const from = minutesOf(w.from);
    const to = minutesOf(w.to);
    if (from === null || to === null || from === to) continue;
    const length = to > from ? to - from : 24 * 60 - from + to;
    for (const day of w.days) {
      if (day < 1 || day > 7) continue;
      const start = (day - 1) * 24 * 60 + from;
      out.push([start, start + length]);
    }
  }
  return out;
}

/** Minutes since Monday 00:00 (with fraction for the seconds) of *now* in the time zone (the local one if unknown). */
export function weekMinute(now: Date, timeZone: string | null | undefined): number {
  let parts: Intl.DateTimeFormatPart[];
  try {
    parts = new Intl.DateTimeFormat("en-US", {
      timeZone: timeZone || undefined,
      weekday: "short", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
    }).formatToParts(now);
  } catch {
    return weekMinute(now, null);
  }
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const day = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].indexOf(get("weekday"));
  return Math.max(day, 0) * 24 * 60 + Number(get("hour")) * 60 + Number(get("minute")) + Number(get("second")) / 60;
}

/** True when there are no windows, or *now* is inside one. */
export function isInWindows(windows: WeeklyWindow[] | undefined | null, now: Date, timeZone: string | null | undefined): boolean {
  if (!windows || windows.length === 0) return true;
  const list = intervals(windows);
  if (list.length === 0) return true; // nothing usable: do not hide the content because of broken data
  const w = weekMinute(now, timeZone);
  return list.some(([start, end]) => (w >= start && w < end) || (w + WEEK >= start && w + WEEK < end));
}

/**
 * Minutes from *now* until a window starts or ends next (the state may change then), or null
 * without windows. Wall-clock minutes: a time change can make the real wait an hour off, so callers
 * should not trust one long timer (content-display.ts re-checks at least every few minutes).
 */
export function minutesToNextBoundary(windows: WeeklyWindow[] | undefined | null, now: Date, timeZone: string | null | undefined): number | null {
  if (!windows || windows.length === 0) return null;
  const list = intervals(windows);
  if (list.length === 0) return null;
  const w = weekMinute(now, timeZone);
  let best = Infinity;
  for (const [start, end] of list) {
    for (const edge of [start, end % WEEK]) {
      const delta = (edge - w + WEEK) % WEEK || WEEK;
      if (delta < best) best = delta;
    }
  }
  return best;
}
