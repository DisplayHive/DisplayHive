import { describe, expect, it } from 'vitest'
import { DEFAULT_FIELD_HANDLER_OPTIONS, defaultContentFor } from '../containerDefaultContent'

describe('defaultContentFor', () => {
  it('gives structured handlers an empty value of their shape', () => {
    expect(JSON.parse(defaultContentFor('arrows'))).toEqual({ char: '', size: 5 })
    expect(JSON.parse(defaultContentFor('image'))).toEqual({ url: '', size: null })
    expect(JSON.parse(defaultContentFor('icon'))).toEqual({ icon: '', size: 5, color: '' })
    expect(JSON.parse(defaultContentFor('marquee'))).toEqual({ text: '', speed: 20 })
    expect(JSON.parse(defaultContentFor('countdown'))).toEqual({ target: '', format: 'DD:HH:mm:ss', finished_text: '' })
    expect(JSON.parse(defaultContentFor('table')).columns).toHaveLength(2)
    expect(JSON.parse(defaultContentFor('pretalx_table'))).toBeTypeOf('object')
  })

  it('starts a date format with a time pattern and everything else empty', () => {
    expect(defaultContentFor('datetime_format')).toBe('HH:mm:ss')
    expect(defaultContentFor('textklein')).toBe('')
    expect(defaultContentFor('')).toBe('')
  })

  it('offers None first and every handler once', () => {
    expect(DEFAULT_FIELD_HANDLER_OPTIONS[0]).toEqual({ label: 'None', value: '' })
    const values = DEFAULT_FIELD_HANDLER_OPTIONS.map((o) => o.value)
    expect(new Set(values).size).toBe(values.length)
  })
})
