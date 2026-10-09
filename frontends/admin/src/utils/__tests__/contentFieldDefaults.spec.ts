import { describe, expect, it } from 'vitest'
import { defaultFieldValues, seedField, seedMissingField, type FieldValue } from '../contentFieldDefaults'

describe('content field defaults', () => {
  it('seeds each handler with its empty value', () => {
    expect(defaultFieldValues('textklein', 'a')).toEqual({ a: '' })
    expect(defaultFieldValues('numbers', 'a')).toEqual({ a: 0 })
    expect(defaultFieldValues('checkbox', 'a')).toEqual({ a: false })
    expect(defaultFieldValues('datetime_format', 'a')).toEqual({ a: 'HH:mm:ss' })
    expect(defaultFieldValues('arrows', 'a')).toEqual({ a: '', a_size: 5 })
    expect(defaultFieldValues('icon', 'a')).toEqual({ a: '', a__size: 5 })
    expect(JSON.parse(String(defaultFieldValues('table', 'a').a)).columns).toHaveLength(2)
  })

  it('does not seed a field without a handler', () => {
    expect(defaultFieldValues('', 'a')).toEqual({})
  })

  it('seeds a new element completely', () => {
    const fields: Record<string, FieldValue> = { a: 'old' }
    seedField(fields, 'arrows', 'a')
    expect(fields).toEqual({ a: '', a_size: 5 })
  })

  it('leaves a field the element already has untouched', () => {
    const fields: Record<string, FieldValue> = { a: 'x' }
    seedMissingField(fields, 'arrows', 'a')
    expect(fields).toEqual({ a: 'x' })
  })

  it('adds a missing field, but keeps a sub-value that is already there', () => {
    const fields: Record<string, FieldValue> = { icon__size: 9 }
    seedMissingField(fields, 'icon', 'icon')
    expect(fields).toEqual({ icon: '', icon__size: 9 })
    const other: Record<string, FieldValue> = {}
    seedMissingField(other, 'numbers', 'n')
    expect(other).toEqual({ n: 0 })
  })
})
