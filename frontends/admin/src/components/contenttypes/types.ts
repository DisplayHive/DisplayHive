import type { OptionFlags } from '../../utils/optionFlags'

export interface TagConfig {
  id?: number | null
  name: string
  title: string
  field_handler: string
  contentcontainer_id: number | null
  // Preset value for this field — same flat key-shape (field_name plus its
  // handler-specific suffixes) FieldValueEditor.vue's `fields` prop expects,
  // scoped to just this one field.
  default_value: Record<string, unknown>
  // One entry per individual sub-setting the field exposes (e.g. an 'image'
  // field's mode/value/size are each independently lockable/hideable) —
  // keyed the same way as default_value. See FieldValueEditor.vue.
  option_flags: OptionFlags
}

export interface ContentType {
  id: number
  name: string
  description: string
  layout_id: number | null
  layout_name?: string
  field_count?: number
}

// Raw tagconfig row as the backend sends it (snake_case, JSON-encoded
// default_value/option_flags) — mirrors ContentEditView.vue's RawTagConfig.
export interface RawTagConfig {
  id?: number
  field_name?: string
  field_label?: string
  field_handler?: string
  contentcontainer_id?: number | null
  order?: number
  default_value?: string
  option_flags?: string
}

export interface RawContentTypeDetail {
  id: number
  description?: string
  layout_id: number | null
  tagconfigs?: RawTagConfig[]
}
