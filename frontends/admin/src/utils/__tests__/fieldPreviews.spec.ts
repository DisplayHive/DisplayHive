import { describe, expect, it } from 'vitest'
import { formatCountdownPreview, formatCountdownString, formatCountdownTarget, formatDateString, parseCountdownTarget } from '../fieldPreviews'

describe('date format preview', () => {
  const d = new Date('2024-06-07T14:05:09Z')
  it('formats tokens in the given timezone', () => {
    expect(formatDateString(d, 'YYYY-MM-DD HH:mm:ss', 'UTC')).toBe('2024-06-07 14:05:09')
    expect(formatDateString(d, 'D.M.YY h:mm A', 'UTC')).toBe('7.6.24 2:05 PM')
    expect(formatDateString(d, 'dddd ddd', 'UTC')).toBe('Friday Fri')
    expect(formatDateString(d, 'HH:mm', 'Europe/Berlin')).toBe('16:05')
  })
  it('falls back to the format for an invalid timezone', () => {
    expect(formatDateString(d, 'HH:mm', 'Nowhere/Land')).toBe('HH:mm')
  })
})

describe('countdown preview', () => {
  const ms = ((3 * 24 + 5) * 3600 + 9 * 60 + 2) * 1000
  it('formats the remaining time', () => {
    expect(formatCountdownString(ms, 'DD:HH:mm:ss')).toBe('03:05:09:02')
    expect(formatCountdownString(ms, 'D-H-m-s')).toBe('3-5-9-2')
    expect(formatCountdownString(-5000, 'DD:HH')).toBe('00:00')
  })
  it('shows a dash without a target, and the finished text once it passed', () => {
    const now = new Date('2024-01-01T00:00:00')
    expect(formatCountdownPreview('', 'DD', '', now)).toBe('—')
    expect(formatCountdownPreview('nonsense', 'DD', '', now)).toBe('Invalid date')
    expect(formatCountdownPreview('2023-12-31T00:00', 'DD:HH', 'Done!', now)).toBe('Done!')
    expect(formatCountdownPreview('2024-01-03T00:00', 'D', 'Done!', now)).toBe('2')
  })
  it('stores a target without timezone and reads it back', () => {
    const d = new Date(2024, 5, 7, 8, 3)
    expect(formatCountdownTarget(d)).toBe('2024-06-07T08:03')
    expect(parseCountdownTarget('2024-06-07T08:03')?.getHours()).toBe(8)
    expect(parseCountdownTarget('')).toBeNull()
    expect(parseCountdownTarget('x')).toBeNull()
    expect(formatCountdownTarget(null)).toBe('')
  })
})
