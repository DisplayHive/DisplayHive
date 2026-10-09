import type { Ref } from 'vue'
import type { DesignForm } from '../../types/designForm'

// --- Default Colors: a named palette scoped to this Design, offered as
// quick-pick swatches by every other color field (ColorPalettePicker).
// Picking one stores a "@default:<id>" *reference*, not a copy of the hex —
// so editing the palette entry later updates every field that picked it,
// here and (once saved) on the actual screens — see resolve_default_color()
// in application/admin/designs/helper.py for the backend side of this.
const DEFAULT_COLOR_PREFIX = '@default:'

export const colorRefFor = (id: string) => `${DEFAULT_COLOR_PREFIX}${id}`
export const isColorRef = (v: string | undefined | null): boolean => !!v && v.startsWith(DEFAULT_COLOR_PREFIX)

export const newColorId = (): string =>
  crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`

/** Resolving and showing palette references against the Design's own palette. */
export function useDefaultColors(form: Ref<DesignForm>) {
  const resolveColorRef = (v: string | undefined | null): string => {
    if (!isColorRef(v)) return v || ''
    const id = (v as string).slice(DEFAULT_COLOR_PREFIX.length)
    return form.value.default_colors.find((c) => c.id === id)?.hex || ''
  }

  // For the "(not set)"-style readouts: show the palette entry's name for a
  // reference, the literal value otherwise.
  const colorDisplayLabel = (v: string | undefined | null): string => {
    if (!v) return '(not set)'
    if (!isColorRef(v)) return v
    const id = v.slice(DEFAULT_COLOR_PREFIX.length)
    const c = form.value.default_colors.find((c) => c.id === id)
    return c ? `🎨 ${c.name || c.hex}` : '(deleted default color)'
  }

  return { resolveColorRef, colorDisplayLabel, colorRefFor, isColorRef }
}
