import { fieldHandlerDef } from '../../plugins/registry'
import type { FieldValue } from '../../plugins/types'

export type { FieldValue }

/**
 * The starting value(s) of one content field, by its handler. Most handlers keep a single
 * value under the field's name; a few keep extra sub-values next to it (`<name>_size`,
 * `<name>__size`) — the handler's plugin says which (`defaults` in plugins/types.ts). A field with no
 * handler ("None") has no input at all and is not seeded — it always falls through to its
 * container's own default content.
 */
export const defaultFieldValues = (handler: string, name: string): Record<string, FieldValue> => {
  if (handler === '') return {}
  return fieldHandlerDef(handler)?.defaults?.(name) ?? { [name]: '' }
}

/** Seed a field for a NEW element: every value is set. */
export const seedField = (fields: Record<string, FieldValue>, handler: string, name: string) => {
  Object.assign(fields, defaultFieldValues(handler, name))
}

/**
 * Seed a field of an EXISTING element that does not have a value yet (a field added to the
 * content type after the element was saved): nothing is touched when the element already has the
 * field; sub-values it already has are kept.
 */
export const seedMissingField = (fields: Record<string, FieldValue>, handler: string, name: string) => {
  if (name in fields) return
  for (const [key, value] of Object.entries(defaultFieldValues(handler, name))) {
    if (key === name || !(key in fields)) fields[key] = value
  }
}
