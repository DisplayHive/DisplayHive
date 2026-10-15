/**
 * Weekly time windows of a content element (`recurrence`, see application/admin/content/recurrence.py):
 * the element is shown only inside them, on top of its start and end time. Days are ISO weekdays
 * (1 = Monday … 7 = Sunday); times are wall-clock "HH:MM" in the instance's time zone; a window whose
 * `to` is not after `from` runs past midnight into the next day. No windows = always.
 *
 * `isInWindows` is the same arithmetic as the screen's (frontends/screen/ts/screen/recurrence.ts) —
 * keep them in step.
 */

export interface WeeklyWindow {
  days: number[]
  from: string
  to: string
}

const WEEK = 7 * 24 * 60
const TIME = /^([01]\d|2[0-3]):([0-5]\d)$/

export const WEEKDAYS = [
  { value: 1, short: 'Mon', label: 'Monday' },
  { value: 2, short: 'Tue', label: 'Tuesday' },
  { value: 3, short: 'Wed', label: 'Wednesday' },
  { value: 4, short: 'Thu', label: 'Thursday' },
  { value: 5, short: 'Fri', label: 'Friday' },
  { value: 6, short: 'Sat', label: 'Saturday' },
  { value: 7, short: 'Sun', label: 'Sunday' },
] as const

/** Ready-made windows offered next to "Add window". */
export const WINDOW_PRESETS: Array<{ label: string; window: WeeklyWindow }> = [
  { label: 'Mon–Fri 08:00–18:00', window: { days: [1, 2, 3, 4, 5], from: '08:00', to: '18:00' } },
  { label: 'Every day 09:00–21:00', window: { days: [1, 2, 3, 4, 5, 6, 7], from: '09:00', to: '21:00' } },
  { label: 'Weekend 10:00–16:00', window: { days: [6, 7], from: '10:00', to: '16:00' } },
]

const minutesOf = (text: string): number | null => {
  const m = TIME.exec(text)
  return m ? Number(m[1]) * 60 + Number(m[2]) : null
}

/** The windows as [start, end) intervals in minutes of the week; `end` may exceed a week. */
function intervals(windows: WeeklyWindow[]): Array<[number, number]> {
  const out: Array<[number, number]> = []
  for (const w of windows) {
    const from = minutesOf(w.from)
    const to = minutesOf(w.to)
    if (from === null || to === null || from === to) continue
    const length = to > from ? to - from : 24 * 60 - from + to
    for (const day of w.days) {
      if (day < 1 || day > 7) continue
      const start = (day - 1) * 24 * 60 + from
      out.push([start, start + length])
    }
  }
  return out
}

/** Minutes since Monday 00:00 of *now* in the time zone (the local one if unknown). */
export function weekMinute(now: Date, timeZone?: string | null): number {
  let parts: Intl.DateTimeFormatPart[]
  try {
    parts = new Intl.DateTimeFormat('en-US', {
      timeZone: timeZone || undefined,
      weekday: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23',
    }).formatToParts(now)
  } catch {
    return weekMinute(now, null)
  }
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? ''
  const day = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].indexOf(get('weekday'))
  return Math.max(day, 0) * 24 * 60 + Number(get('hour')) * 60 + Number(get('minute')) + Number(get('second')) / 60
}

/** True when there are no windows, or *now* is inside one. */
export function isInWindows(windows: WeeklyWindow[] | null | undefined, now: Date, timeZone?: string | null): boolean {
  if (!windows || windows.length === 0) return true
  const list = intervals(windows)
  if (list.length === 0) return true
  const w = weekMinute(now, timeZone)
  return list.some(([start, end]) => (w >= start && w < end) || (w + WEEK >= start && w + WEEK < end))
}

/** "Mon–Fri", "Mon, Wed, Sat", "every day" — consecutive days are joined to a range. */
export function describeDays(days: number[]): string {
  const sorted = [...new Set(days)].filter((d) => d >= 1 && d <= 7).sort((a, b) => a - b)
  if (sorted.length === 7) return 'every day'
  const name = (d: number) => WEEKDAYS[d - 1]!.short
  const parts: string[] = []
  for (let i = 0; i < sorted.length; ) {
    let j = i
    while (j + 1 < sorted.length && sorted[j + 1] === sorted[j]! + 1) j++
    parts.push(j - i >= 2 ? `${name(sorted[i]!)}–${name(sorted[j]!)}` : sorted.slice(i, j + 1).map(name).join(', '))
    i = j + 1
  }
  return parts.join(', ')
}

/** One line for a window list: "Mon–Fri 08:00–18:00; Sat 10:00–14:00". */
export function describeWindows(windows: WeeklyWindow[]): string {
  return windows.map((w) => `${describeDays(w.days)} ${w.from}–${w.to}`).join('; ')
}
