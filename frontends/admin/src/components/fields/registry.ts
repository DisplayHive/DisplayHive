import type { Component } from 'vue'
import TextField from './TextField.vue'
import TextAreaField from './TextAreaField.vue'
import NumberField from './NumberField.vue'
import CheckboxField from './CheckboxField.vue'
import WysiwygField from './WysiwygField.vue'
import ImageField from './ImageField.vue'
import ArrowsField from './ArrowsField.vue'
import TableField from './TableField.vue'
import DateTimeFormatField from './DateTimeFormatField.vue'
import MarqueeField from './MarqueeField.vue'
import CountdownField from './CountdownField.vue'
import IconField from './IconField.vue'
import PretalxTableField from './PretalxTableField.vue'

interface FieldEditorEntry {
  component: Component
  /** Props that make one component serve several handlers. */
  props?: Record<string, unknown>
}

/**
 * The editor of each field handler. A handler is added here with its own component (it gets the
 * field through `useFieldContext()`); anything not listed gets the one-line text editor.
 */
const FIELD_EDITORS: Record<string, FieldEditorEntry> = {
  textklein: { component: TextField },
  link: { component: TextField, props: { type: 'url' } },
  iframe: { component: TextField, props: { type: 'url' } },
  textbig: { component: TextAreaField, props: { rows: 3 } },
  rawhtml: { component: TextAreaField, props: { rows: 5, html: true } },
  numbers: { component: NumberField },
  checkbox: { component: CheckboxField },
  wysiwyg: { component: WysiwygField },
  image: { component: ImageField },
  arrows: { component: ArrowsField },
  table: { component: TableField },
  datetime_format: { component: DateTimeFormatField },
  marquee: { component: MarqueeField },
  countdown: { component: CountdownField },
  icon: { component: IconField },
  pretalx_table: { component: PretalxTableField },
}

const FALLBACK: FieldEditorEntry = { component: TextField }

export const fieldEditorFor = (handler: string): FieldEditorEntry => FIELD_EDITORS[handler] ?? FALLBACK
