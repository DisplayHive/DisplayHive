/**
 * Shared shape for a Contenttype field's per-option preset flags — one entry
 * per individual sub-setting a field_handler exposes (e.g. an 'image'
 * field's mode/value/size), keyed by the exact flat wire key
 * application/admin/content/helper.py's render_content_fields() reads
 * (matches FieldValueEditor.vue's `fields` prop key shape: `tag.name` plus
 * handler-specific suffixes like `__size`, `__image_mode`).
 */
export interface OptionFlag {
  locked: boolean
  hidden: boolean
}

export type OptionFlags = Record<string, OptionFlag>
