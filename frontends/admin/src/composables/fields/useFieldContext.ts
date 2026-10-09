import { computed, inject, provide, reactive, watch, type InjectionKey } from 'vue'
import type { DefaultColor } from '../../types/models'
import type { OptionFlags } from '../../utils/optionFlags'

export interface FieldEditorProps {
  tag: { name: string; fieldHandler: string; max_length?: number }
  /**
   * A flat, mutable key/value bag the editors read and write directly (the shape
   * ContentEditView's form always had — Vue reactivity carries the change through the shared
   * object, no event plumbing). Keys are `tag.name` plus handler-specific suffixes (`__size`,
   * `_size`, `__image_mode`, pretalx's `__xxx` …) — application/admin/content/helper.py's
   * render_content_fields() reads this exact shape, whether it comes from a real content
   * element's serialized_input or (for a preset) a TagConfig's default_value.
   */
  fields: Record<string, unknown>
  disabled?: boolean
  /**
   * 'edit': a real Content Editor — hides/disables individual sub-controls per optionFlags.
   * 'preset': the Contenttype editor's preset panel — shows an inline lock/hide toggle next to
   * every control instead, and never hides/disables anything (the admin needs to see/edit every
   * control to author the preset in the first place).
   */
  mode?: 'edit' | 'preset'
  optionFlags?: OptionFlags
  /** Active Design's color palette — for the icon field's color picker. */
  palette?: DefaultColor[]
}

export interface FieldEditorEmit {
  (e: 'update:optionFlags', flags: OptionFlags): void
  (e: 'update:hasVisibleControl', visible: boolean): void
}

/**
 * What every field editor of one field (components/fields/*) needs: the field's name and values,
 * the mode, and the per-option lock/hide flags (see utils/optionFlags.ts for the shared shape).
 * Provided by FieldValueEditor, injected by the editor of the field's handler.
 */
function createFieldContext(props: FieldEditorProps, emit: FieldEditorEmit) {
  const name = computed(() => props.tag.name)
  const tag = computed(() => props.tag)
  const mode = computed(() => props.mode ?? 'edit')
  const palette = computed(() => props.palette ?? [])
  const fields = computed(() => props.fields)
  const optionFlags = computed(() => props.optionFlags)

  const get = (key: string): string | number | boolean =>
    (props.fields[key] as string | number | boolean | undefined) ?? ''
  const set = (key: string, value: unknown) => {
    props.fields[key] = value
  }

  const isHidden = (key: string) => mode.value === 'edit' && !!props.optionFlags?.[key]?.hidden
  const isLocked = (key: string) => mode.value === 'edit' && !!props.optionFlags?.[key]?.locked
  const flagsFor = (key: string) => props.optionFlags?.[key] ?? { locked: false, hidden: false }
  const toggleFlag = (key: string, kind: 'locked' | 'hidden') => {
    const current = flagsFor(key)
    emit('update:optionFlags', { ...props.optionFlags, [key]: { ...current, [kind]: !current[kind] } })
  }
  const setOptionFlags = (flags: OptionFlags) => emit('update:optionFlags', flags)

  /**
   * Tell the page whether this field renders any editable control, so it can hide a field's
   * label when every control has been hidden via the per-field "hide" flag (instead of a bare
   * label over empty space). Editors that always render something don't call this.
   */
  const reportVisibleWhen = (visible: () => boolean) => {
    watch(
      () => (mode.value !== 'edit' ? true : visible()),
      (v) => emit('update:hasVisibleControl', v),
      { immediate: true },
    )
  }

  return reactive({
    name, tag, mode, palette, fields, optionFlags,
    get, set, isHidden, isLocked, flagsFor, toggleFlag, setOptionFlags, reportVisibleWhen,
  })
}

export type FieldContext = ReturnType<typeof createFieldContext>

const KEY: InjectionKey<FieldContext> = Symbol('fieldContext')

export function provideFieldContext(props: FieldEditorProps, emit: FieldEditorEmit): FieldContext {
  const ctx = createFieldContext(props, emit)
  provide(KEY, ctx)
  return ctx
}

export function useFieldContext(): FieldContext {
  const ctx = inject(KEY)
  if (!ctx) throw new Error('useFieldContext() needs provideFieldContext() in a parent component')
  return ctx
}
