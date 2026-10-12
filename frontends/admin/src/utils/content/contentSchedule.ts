import type { Content } from '../types/models'

/** What a content element is doing right now, judged by its switch, schedule and assignment. */
export type ScheduleState = 'live' | 'scheduled' | 'expired' | 'inactive' | 'unassigned'

const DAY = 24 * 60 * 60 * 1000

/** Wall-clock text ("2026-10-09T18:30") as the viewer's local time — how a screen reads it. */
const at = (text?: string | null): number | null => {
  if (!text) return null
  const t = new Date(text).getTime()
  return Number.isNaN(t) ? null : t
}

export function scheduleState(c: Content, now: number): ScheduleState {
  if (c.active === false) return 'inactive'
  if (c.assigned === false) return 'unassigned'
  const start = at(c.start_time)
  const end = at(c.end_time)
  if (end !== null && end <= now) return 'expired'
  if (start !== null && start > now) return 'scheduled'
  return 'live'
}

/** Live content that stops within *days* days, soonest first. */
export function expiringSoon(list: Content[], now: number, days = 7): Array<Content & { endsAt: number }> {
  return list
    .filter((c) => scheduleState(c, now) === 'live')
    .map((c) => ({ ...c, endsAt: at(c.end_time) }))
    .filter((c): c is Content & { endsAt: number } => c.endsAt !== null && c.endsAt - now <= days * DAY)
    .sort((a, b) => a.endsAt - b.endsAt)
}

/** Not yet running (but switched on and assigned) content that starts within *days* days. */
export function startingSoon(list: Content[], now: number, days = 7): Array<Content & { startsAt: number }> {
  return list
    .filter((c) => scheduleState(c, now) === 'scheduled')
    .map((c) => ({ ...c, startsAt: at(c.start_time) }))
    .filter((c): c is Content & { startsAt: number } => c.startsAt !== null && c.startsAt - now <= days * DAY)
    .sort((a, b) => a.startsAt - b.startsAt)
}

/** The *count* most recently written elements, newest first; rows never written since the column came are left out. */
export function recentlyChanged(list: Content[], count = 6): Array<Content & { changedAt: number }> {
  return list
    .map((c) => ({ ...c, changedAt: c.updated_at ? new Date(c.updated_at).getTime() : NaN }))
    .filter((c) => !Number.isNaN(c.changedAt))
    .sort((a, b) => b.changedAt - a.changedAt)
    .slice(0, count)
}

/** "in 3 days", "2 hours ago", "just now" — for the Dashboard lists. */
export function relativeTime(target: number, now: number): string {
  const diff = target - now
  const abs = Math.abs(diff)
  const units: Array<[number, string]> = [[DAY, 'day'], [60 * 60 * 1000, 'hour'], [60 * 1000, 'minute']]
  for (const [size, name] of units) {
    if (abs >= size) {
      const n = Math.round(abs / size)
      const text = `${n} ${name}${n === 1 ? '' : 's'}`
      return diff > 0 ? `in ${text}` : `${text} ago`
    }
  }
  return 'just now'
}
