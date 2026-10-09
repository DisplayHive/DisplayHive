import { describe, expect, it } from 'vitest'
import { expiringSoon, recentlyChanged, relativeTime, scheduleState, startingSoon } from '../contentSchedule'
import type { Content } from '../../types/models'

const NOW = new Date('2026-10-09T12:00').getTime()
const c = (over: Partial<Content>): Content => ({ id: 1, title: 't', active: true, assigned: true, ...over })

describe('scheduleState', () => {
  it('judges switch, assignment and schedule', () => {
    expect(scheduleState(c({}), NOW)).toBe('live')
    expect(scheduleState(c({ active: false }), NOW)).toBe('inactive')
    expect(scheduleState(c({ assigned: false }), NOW)).toBe('unassigned')
    expect(scheduleState(c({ end_time: '2026-10-09T11:59' }), NOW)).toBe('expired')
    expect(scheduleState(c({ start_time: '2026-10-09T12:01' }), NOW)).toBe('scheduled')
    expect(scheduleState(c({ start_time: '2026-10-01T00:00', end_time: '2026-10-30T00:00' }), NOW)).toBe('live')
  })
})

describe('lists', () => {
  it('expiringSoon: live content ending within the window, soonest first', () => {
    const list = [
      c({ id: 1, end_time: '2026-10-12T00:00' }),
      c({ id: 2, end_time: '2026-10-10T00:00' }),
      c({ id: 3, end_time: '2026-11-30T00:00' }),
      c({ id: 4 }),
      c({ id: 5, end_time: '2026-10-08T00:00' }),
    ]
    expect(expiringSoon(list, NOW).map((x) => x.id)).toEqual([2, 1])
  })

  it('startingSoon: waiting content starting within the window', () => {
    const list = [c({ id: 1, start_time: '2026-10-11T08:00' }), c({ id: 2, start_time: '2026-12-01T08:00' }), c({ id: 3 })]
    expect(startingSoon(list, NOW).map((x) => x.id)).toEqual([1])
  })

  it('recentlyChanged: newest first, unknown dates left out, capped', () => {
    const list = [
      c({ id: 1, updated_at: '2026-10-01T00:00:00Z' }),
      c({ id: 2, updated_at: '2026-10-05T00:00:00Z' }),
      c({ id: 3, updated_at: null }),
    ]
    expect(recentlyChanged(list, 5).map((x) => x.id)).toEqual([2, 1])
    expect(recentlyChanged(list, 1).map((x) => x.id)).toEqual([2])
  })
})

describe('relativeTime', () => {
  it('words the distance in the largest fitting unit', () => {
    expect(relativeTime(NOW + 3 * 24 * 3600e3, NOW)).toBe('in 3 days')
    expect(relativeTime(NOW - 3600e3, NOW)).toBe('1 hour ago')
    expect(relativeTime(NOW + 5 * 60e3, NOW)).toBe('in 5 minutes')
    expect(relativeTime(NOW + 1000, NOW)).toBe('just now')
  })
})
