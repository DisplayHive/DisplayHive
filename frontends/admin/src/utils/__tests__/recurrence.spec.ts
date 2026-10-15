import { describe, expect, it } from 'vitest'
import { describeDays, describeWindows, isInWindows, weekMinute, type WeeklyWindow } from '../content/recurrence'

// 2026-10-12 is a Monday.
const at = (iso: string) => new Date(iso)
const office: WeeklyWindow[] = [{ days: [1, 2, 3, 4, 5], from: '08:00', to: '18:00' }]

describe('isInWindows', () => {
  it('is always true without windows', () => {
    expect(isInWindows([], at('2026-10-12T12:00:00Z'), 'UTC')).toBe(true)
    expect(isInWindows(undefined, at('2026-10-12T12:00:00Z'), 'UTC')).toBe(true)
  })

  it('is true on the listed days between from (inclusive) and to (exclusive)', () => {
    expect(isInWindows(office, at('2026-10-12T08:00:00Z'), 'UTC')).toBe(true)
    expect(isInWindows(office, at('2026-10-12T18:00:00Z'), 'UTC')).toBe(false)
    expect(isInWindows(office, at('2026-10-17T12:00:00Z'), 'UTC')).toBe(false)
  })

  it('reads the times in the time zone', () => {
    expect(isInWindows(office, at('2026-10-12T06:30:00Z'), 'Europe/Berlin')).toBe(true)
    expect(isInWindows(office, at('2026-10-12T17:00:00Z'), 'Europe/Berlin')).toBe(false)
  })

  it('runs past midnight and past the end of the week', () => {
    const night: WeeklyWindow[] = [{ days: [7], from: '22:00', to: '02:00' }]
    expect(isInWindows(night, at('2026-10-18T23:00:00Z'), 'UTC')).toBe(true) // Sunday 23:00
    expect(isInWindows(night, at('2026-10-12T01:30:00Z'), 'UTC')).toBe(true) // Monday 01:30
    expect(isInWindows(night, at('2026-10-12T02:00:00Z'), 'UTC')).toBe(false)
  })
})

describe('weekMinute', () => {
  it('counts from Monday 00:00', () => {
    expect(weekMinute(at('2026-10-12T00:00:00Z'), 'UTC')).toBe(0)
    expect(weekMinute(at('2026-10-13T01:00:00Z'), 'UTC')).toBe(24 * 60 + 60)
  })
})

describe('describing windows', () => {
  it('joins consecutive days to a range', () => {
    expect(describeDays([1, 2, 3, 4, 5])).toBe('Mon–Fri')
    expect(describeDays([1, 3, 6])).toBe('Mon, Wed, Sat')
    expect(describeDays([6, 7])).toBe('Sat, Sun')
    expect(describeDays([1, 2, 3, 4, 5, 6, 7])).toBe('every day')
  })

  it('writes one line for the whole list', () => {
    expect(describeWindows([...office, { days: [6], from: '10:00', to: '14:00' }])).toBe('Mon–Fri 08:00–18:00; Sat 10:00–14:00')
  })
})
