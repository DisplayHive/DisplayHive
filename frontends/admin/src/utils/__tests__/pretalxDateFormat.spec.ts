import { describe, expect, it } from 'vitest'
import { FORMAT_TOKENS, formatDateStr } from '../pretalxDateFormat'

const d = new Date('2024-06-07T14:05:09Z')

describe('formatDateStr', () => {
  it('formats date and 24h time tokens in the given timezone', () => {
    expect(formatDateStr(d, 'YYYY-MM-DD HH:mm:ss', 'UTC')).toBe('2024-06-07 14:05:09')
    expect(formatDateStr(d, 'HH:mm', 'Europe/Berlin')).toBe('16:05')
  })

  it('formats 12h time, period and weekday tokens', () => {
    expect(formatDateStr(d, 'h:mm A', 'UTC')).toBe('2:05 PM')
    expect(formatDateStr(d, 'dddd ddd', 'UTC')).toBe('Friday Fri')
  })

  it('lists every token that has a description', () => {
    expect(FORMAT_TOKENS.map((t) => t.token)).toContain('YYYY')
  })
})
