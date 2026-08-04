<script setup lang="ts">
/**
 * Renders the editor widget for one Contenttype field (TagConfig), keyed off
 * its field_handler — text/number/link/wysiwyg/image/icon/arrows/checkbox/
 * table/datetime_format/pretalx_table. Extracted from ContentEditView.vue so
 * the Contenttype editor's field-preset panel (ContentTypesView.vue) can
 * reuse the exact same widgets rather than a simplified subset.
 *
 * `fields` is a flat, mutable key/value bag this component reads/writes
 * directly (the same shape ContentEditView.vue's createForm.fields always
 * was — no event plumbing needed since Vue reactivity propagates through the
 * passed object itself). Keys are `tag.name` plus handler-specific suffixes
 * (`__size`, `_size`, `__image_mode`, `__image_tags`, pretalx's `__xxx`
 * keys, etc) — application/admin/content/helper.py's render_content_fields()
 * reads this exact shape, whether it comes from a real ContentElement's
 * serialized_input or (for a Contenttype field preset) a TagConfig's
 * default_value.
 */
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useSocket } from '../composables/useSocket'

import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import Editor from 'primevue/editor'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import Tag from 'primevue/tag'
import PretalxTableFieldEditor from './PretalxTableFieldEditor.vue'
import { blankPretalxTableValue, type PretalxTableValue } from '../utils/pretalxTable'
import IconPickerField from './IconPickerField.vue'
import type { IconPickerValue } from '../utils/iconLibraries'
import OptionFlagToggle from './OptionFlagToggle.vue'
import type { OptionFlags } from '../utils/optionFlags'

interface MediaItem {
  id: number
  title: string
  filename: string
  mimetype: string
  url: string
  preview_url: string
  tags: string[]
}

const props = withDefaults(defineProps<{
  tag: { name: string; fieldHandler: string; max_length?: number }
  fields: Record<string, any>
  disabled?: boolean
  /**
   * 'edit' (default): a real Content Editor — hides/disables individual
   * sub-controls per optionFlags. 'preset': the Contenttype editor's preset
   * panel — shows an inline lock/hide toggle next to every control instead,
   * and never hides/disables anything (the admin needs to see/edit every
   * control to author the preset in the first place).
   */
  mode?: 'edit' | 'preset'
  optionFlags?: OptionFlags
}>(), {
  disabled: false,
  mode: 'edit',
  optionFlags: undefined,
})

const emit = defineEmits<{
  'update:optionFlags': [OptionFlags]
}>()

const { on, off, emit: socketEmit } = useSocket()

const getFieldValue = (tagName: string): string | number | boolean => {
  return props.fields[tagName] ?? ''
}
const setFieldValue = (tagName: string, value: string | number | boolean) => {
  props.fields[tagName] = value
}

// --- per-option lock/hide (see utils/optionFlags.ts for the shared shape) --
const isHidden = (key: string) => props.mode === 'edit' && !!props.optionFlags?.[key]?.hidden
const isLocked = (key: string) => props.mode === 'edit' && !!props.optionFlags?.[key]?.locked
const flagsFor = (key: string) => props.optionFlags?.[key] ?? { locked: false, hidden: false }
const toggleFlag = (key: string, kind: 'locked' | 'hidden') => {
  const current = flagsFor(key)
  emit('update:optionFlags', { ...(props.optionFlags || {}), [key]: { ...current, [kind]: !current[kind] } })
}

// --- pretalx_table field adapter ------------------------------------------
const getPretalxTableValue = (name: string): PretalxTableValue => ({
  url: String(props.fields[name] || ''),
  type: String(props.fields[name + '__type'] || 'list'),
  roomname: String(props.fields[name + '__roomname'] || ''),
  fields: String(props.fields[name + '__fields'] || ''),
  linecount: Number(props.fields[name + '__linecount'] ?? 10),
  author_under_title: !!props.fields[name + '__author_under_title'],
  tracks_by_color: !!props.fields[name + '__tracks_by_color'],
  today_only: !!props.fields[name + '__today_only'],
  separate_days: !!props.fields[name + '__separate_days'],
  day_prefix: String(props.fields[name + '__day_prefix'] || ''),
  empty_text: String(props.fields[name + '__empty_text'] || ''),
  tracklist_columns: String(props.fields[name + '__tracklist_columns'] || 'name|Name,color|Color'),
  tracklist_layout: String(props.fields[name + '__tracklist_layout'] || 'list'),
  tracklist_exclude: String(props.fields[name + '__tracklist_exclude'] || ''),
  invalid_data_text: String(props.fields[name + '__invalid_data_text'] || ''),
})

const setPretalxTableValue = (name: string, v: PretalxTableValue) => {
  props.fields[name] = v.url
  props.fields[name + '__type'] = v.type
  props.fields[name + '__roomname'] = v.roomname
  props.fields[name + '__fields'] = v.fields
  props.fields[name + '__linecount'] = v.linecount
  props.fields[name + '__author_under_title'] = v.author_under_title
  props.fields[name + '__tracks_by_color'] = v.tracks_by_color
  props.fields[name + '__today_only'] = v.today_only
  props.fields[name + '__separate_days'] = v.separate_days
  props.fields[name + '__day_prefix'] = v.day_prefix
  props.fields[name + '__empty_text'] = v.empty_text
  props.fields[name + '__tracklist_columns'] = v.tracklist_columns
  props.fields[name + '__tracklist_layout'] = v.tracklist_layout
  props.fields[name + '__tracklist_exclude'] = v.tracklist_exclude
  props.fields[name + '__invalid_data_text'] = v.invalid_data_text
}

if (props.tag.fieldHandler === 'pretalx_table' && !(props.tag.name in props.fields)) {
  setPretalxTableValue(props.tag.name, blankPretalxTableValue())
}

// Pretalx's own local field names (its PretalxTableValue shape) map onto
// wire keys as `<name>` for 'url' and `<name>__<localKey>` for the rest —
// translate optionFlags in and out of that namespace so
// PretalxTableFieldEditor never needs to know about the wire-key shape.
const PRETALX_LOCAL_KEYS = [
  'url', 'type', 'roomname', 'fields', 'linecount', 'author_under_title',
  'tracks_by_color', 'today_only', 'separate_days', 'day_prefix', 'empty_text',
  'tracklist_columns', 'tracklist_layout', 'tracklist_exclude', 'invalid_data_text',
] as const

const pretalxWireKey = (name: string, local: string) => (local === 'url' ? name : `${name}__${local}`)

const pretalxOptionFlags = computed<OptionFlags>(() => {
  const out: OptionFlags = {}
  for (const local of PRETALX_LOCAL_KEYS) {
    const wire = pretalxWireKey(props.tag.name, local)
    if (props.optionFlags?.[wire]) out[local] = props.optionFlags[wire]
  }
  return out
})

const onPretalxOptionFlagsUpdate = (localFlags: OptionFlags) => {
  const next = { ...(props.optionFlags || {}) }
  for (const [local, flag] of Object.entries(localFlags)) {
    next[pretalxWireKey(props.tag.name, local)] = flag
  }
  emit('update:optionFlags', next)
}

// --- icon field adapter ----------------------------------------------------
const getIconValue = (name: string): IconPickerValue => ({
  icon: String(props.fields[name] ?? ''),
  size: Number(props.fields[name + '__size']) || 5,
})

const setIconValue = (name: string, v: IconPickerValue) => {
  props.fields[name] = v.icon
  props.fields[name + '__size'] = v.size
}

// Icon's two local keys ('icon', 'size') map onto wire keys `<name>` and
// `<name>__size` — same translation purpose as the pretalx one above.
const iconOptionFlags = computed<OptionFlags>(() => {
  const out: OptionFlags = {}
  if (props.optionFlags?.[props.tag.name]) out.icon = props.optionFlags[props.tag.name]
  const sizeKey = `${props.tag.name}__size`
  if (props.optionFlags?.[sizeKey]) out.size = props.optionFlags[sizeKey]
  return out
})

const onIconOptionFlagsUpdate = (localFlags: OptionFlags) => {
  const next = { ...(props.optionFlags || {}) }
  if (localFlags.icon) next[props.tag.name] = localFlags.icon
  if (localFlags.size) next[`${props.tag.name}__size`] = localFlags.size
  emit('update:optionFlags', next)
}

// --- wysiwyg ---------------------------------------------------------------
// Deferred one tick past mount so the Editor only initializes once `fields`
// already holds its final value — otherwise Quill can grab a stale/blank
// value before a parent's own async load finishes populating `fields`.
const editorReady = ref(false)
onMounted(() => { nextTick(() => { editorReady.value = true }) })

const onEditorLoad = (fieldName: string, event: { instance: any }) => {
  const quill = event.instance
  const html = String(props.fields[fieldName] || '')
  if (html && quill && quill.clipboard) {
    const delta = quill.clipboard.convert(html)
    quill.setContents(delta, 'silent')
  }
}

// --- image field adapter ----------------------------------------------------
const imageModeOptions = [
  { label: 'Single Image', value: 'single' },
  { label: 'Random Image from Tags', value: 'random_tags' },
]

const availableImageTags = ref<string[]>([])

const getImageMode = (fieldName: string): string =>
  String(props.fields[`${fieldName}__image_mode`] || 'single')

const setImageMode = (fieldName: string, mode: string) => {
  props.fields[`${fieldName}__image_mode`] = mode
  if (mode === 'random_tags' && availableImageTags.value.length === 0) {
    socketEmit('displayhive:admin:cts:get_image_tags')
  }
}

const getImageTags = (fieldName: string): string[] => {
  const v = props.fields[`${fieldName}__image_tags`]
  if (Array.isArray(v)) return v as unknown as string[]
  if (typeof v === 'string' && v) {
    try { return JSON.parse(v) } catch { return [] }
  }
  return []
}

const toggleImageTag = (fieldName: string, tag: string) => {
  const current = getImageTags(fieldName)
  const idx = current.indexOf(tag)
  const next = idx === -1 ? [...current, tag] : current.filter((t) => t !== tag)
  props.fields[`${fieldName}__image_tags`] = next as unknown as string
}

const clearImageField = (fieldName: string) => {
  setFieldValue(fieldName, '')
}

// Fixes the rendered <img>'s height (vh) regardless of its container's own
// height — blank/0 leaves it scaling to fit the container, as before.
const getImageSize = (fieldName: string): number | null => {
  const v = props.fields[`${fieldName}__size`]
  const n = Number(v)
  return v !== '' && v != null && !isNaN(n) && n > 0 ? n : null
}

const setImageSize = (fieldName: string, v: number | null) => {
  props.fields[`${fieldName}__size`] = v ?? ''
}

const showImagePickerDialog = ref(false)
const pickerMediaItems = ref<MediaItem[]>([])
const pickerSearchText = ref('')
const pickerLoading = ref(false)

const pickerFiltered = computed(() => {
  const q = pickerSearchText.value.toLowerCase()
  const images = pickerMediaItems.value.filter((m) => m.mimetype.startsWith('image/'))
  if (!q) return images
  return images.filter(
    (m) =>
      m.title?.toLowerCase().includes(q) ||
      m.filename?.toLowerCase().includes(q) ||
      (m.tags || []).some((t) => t.toLowerCase().includes(q))
  )
})

const pickerTargetField = ref<string | null>(null)

const openImagePicker = (fieldName: string) => {
  pickerTargetField.value = fieldName
  pickerSearchText.value = ''
  pickerLoading.value = true
  showImagePickerDialog.value = true
  socketEmit('displayhive:admin:cts:get_media_for_picker')
}

const selectPickerImage = (item: MediaItem) => {
  if (!pickerTargetField.value) return
  setFieldValue(pickerTargetField.value, item.url)
  showImagePickerDialog.value = false
  pickerTargetField.value = null
}

const handleMediaForPicker = (data: { media: MediaItem[] }) => {
  pickerMediaItems.value = data.media || []
  pickerLoading.value = false
}
const handleImageTags = (data: { tags: string[] }) => {
  availableImageTags.value = data.tags || []
}

// --- table field adapter ----------------------------------------------------
interface TableData { columns: string[]; rows: string[][] }

const parseTableData = (fieldName: string): TableData => {
  try {
    const parsed = JSON.parse(String(getFieldValue(fieldName) || ''))
    if (parsed && Array.isArray(parsed.columns) && Array.isArray(parsed.rows)) return parsed
  } catch {}
  return { columns: ['Column 1', 'Column 2'], rows: [['', '']] }
}

const setTableData = (fieldName: string, data: TableData) => {
  setFieldValue(fieldName, JSON.stringify(data))
}

const updateTableHeader = (fieldName: string, ci: number, value: string) => {
  const d = parseTableData(fieldName); d.columns[ci] = value; setTableData(fieldName, d)
}

const updateTableCell = (fieldName: string, ri: number, ci: number, value: string) => {
  const d = parseTableData(fieldName)
  if (d.rows[ri]) d.rows[ri][ci] = value
  setTableData(fieldName, d)
}

const addTableRow = (fieldName: string) => {
  const d = parseTableData(fieldName)
  d.rows.push(d.columns.map(() => ''))
  setTableData(fieldName, d)
}

const removeTableRow = (fieldName: string, ri: number) => {
  const d = parseTableData(fieldName); d.rows.splice(ri, 1); setTableData(fieldName, d)
}

const addTableColumn = (fieldName: string) => {
  const d = parseTableData(fieldName)
  d.columns.push(`Column ${d.columns.length + 1}`)
  d.rows.forEach(r => r.push(''))
  setTableData(fieldName, d)
}

const removeTableColumn = (fieldName: string, ci: number) => {
  const d = parseTableData(fieldName)
  d.columns.splice(ci, 1)
  d.rows.forEach(r => r.splice(ci, 1))
  setTableData(fieldName, d)
}

const tableDragState = ref<{ fieldName: string; type: 'row' | 'col'; fromIdx: number } | null>(null)

const onTableDragStart = (fieldName: string, type: 'row' | 'col', idx: number, e: DragEvent) => {
  tableDragState.value = { fieldName, type, fromIdx: idx }
  e.dataTransfer?.setData('text/plain', '')
}

const onTableDrop = (fieldName: string, type: 'row' | 'col', toIdx: number) => {
  const s = tableDragState.value
  if (!s || s.fieldName !== fieldName || s.type !== type || s.fromIdx === toIdx) { tableDragState.value = null; return }
  const d = parseTableData(fieldName)
  if (type === 'row') {
    const row = d.rows.splice(s.fromIdx, 1)[0] ?? []
    d.rows.splice(toIdx, 0, row)
  } else {
    const hdr = d.columns.splice(s.fromIdx, 1)[0] ?? ''
    d.columns.splice(toIdx, 0, hdr)
    d.rows.forEach(r => { const cell = r.splice(s.fromIdx, 1)[0] ?? ''; r.splice(toIdx, 0, cell) })
  }
  setTableData(fieldName, d)
  tableDragState.value = null
}

// --- datetime_format preview -------------------------------------------------
const previewNow = ref(new Date())
const previewTimezone = ref('UTC')
let previewInterval: ReturnType<typeof setInterval> | null = null

const FORMAT_TOKENS = [
  { token: 'YYYY',  desc: 'Year (4 digits)',        example: '2024'   },
  { token: 'YY',    desc: 'Year (2 digits)',         example: '24'     },
  { token: 'MM',    desc: 'Month (01–12)',           example: '06'     },
  { token: 'M',     desc: 'Month (1–12)',            example: '6'      },
  { token: 'DD',    desc: 'Day (01–31)',             example: '07'     },
  { token: 'D',     desc: 'Day (1–31)',              example: '7'      },
  { token: 'HH',    desc: 'Hour 24h (00–23)',        example: '14'     },
  { token: 'H',     desc: 'Hour 24h (0–23)',         example: '14'     },
  { token: 'hh',    desc: 'Hour 12h (01–12)',        example: '02'     },
  { token: 'h',     desc: 'Hour 12h (1–12)',         example: '2'      },
  { token: 'mm',    desc: 'Minute (00–59)',          example: '05'     },
  { token: 'ss',    desc: 'Second (00–59)',          example: '09'     },
  { token: 'A',     desc: 'AM / PM',                example: 'PM'     },
  { token: 'dddd',  desc: 'Weekday (full)',          example: 'Monday' },
  { token: 'ddd',   desc: 'Weekday (short)',         example: 'Mon'    },
]

function _formatDateStr(d: Date, fmt: string, timezone: string): string {
  try {
    const tz = timezone || 'UTC'
    const p = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false, weekday: 'long',
    }).formatToParts(d)
    const p12 = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, hour: 'numeric', hour12: true,
    }).formatToParts(d)
    const wdShort = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, weekday: 'short',
    }).format(d)

    const get   = (type: string) => p.find(x => x.type === type)?.value ?? ''
    const get12 = (type: string) => p12.find(x => x.type === type)?.value ?? ''

    const year   = get('year')
    const month  = get('month')
    const day    = get('day')
    const h24    = parseInt(get('hour'), 10) % 24
    const minute = get('minute')
    const second = get('second')
    const wdFull = get('weekday')
    const h12r   = parseInt(get12('hour'), 10)
    const h12    = h12r === 0 ? 12 : h12r
    const period = (get12('dayPeriod') || (h24 < 12 ? 'AM' : 'PM')).toUpperCase()

    return fmt.replace(/YYYY|YY|dddd|ddd|MM|M|DD|D|HH|H|hh|h|mm|m|ss|s|A|a/g, t => {
      switch (t) {
        case 'YYYY': return year
        case 'YY':   return year.slice(-2)
        case 'dddd': return wdFull
        case 'ddd':  return wdShort
        case 'MM':   return month
        case 'M':    return String(parseInt(month, 10))
        case 'DD':   return day
        case 'D':    return String(parseInt(day, 10))
        case 'HH':   return String(h24).padStart(2, '0')
        case 'H':    return String(h24)
        case 'hh':   return String(h12).padStart(2, '0')
        case 'h':    return String(h12)
        case 'mm':   return minute
        case 'm':    return String(parseInt(minute, 10))
        case 'ss':   return second
        case 's':    return String(parseInt(second, 10))
        case 'A':    return period
        case 'a':    return period.toLowerCase()
        default:     return t
      }
    })
  } catch {
    return fmt
  }
}

const formatDatePreview = (format: string): string =>
  _formatDateStr(previewNow.value, format || 'HH:mm:ss', previewTimezone.value)

const handleAdminSettingsForPreview = (data: any) => {
  const tz = data?.system_settings?.timezone
  if (tz) previewTimezone.value = tz
}

onMounted(() => {
  on('displayhive:admin:stc:media_for_picker', handleMediaForPicker)
  on('displayhive:admin:stc:image_tags', handleImageTags)

  if (props.tag.fieldHandler === 'image' && getImageMode(props.tag.name) === 'random_tags') {
    socketEmit('displayhive:admin:cts:get_image_tags')
  }

  if (props.tag.fieldHandler === 'datetime_format') {
    on('displayhive:admin:stc:admin_settings', handleAdminSettingsForPreview)
    socketEmit('displayhive:admin:cts:get_admin_settings')
    previewInterval = setInterval(() => { previewNow.value = new Date() }, 1000)
  }
})

onUnmounted(() => {
  off('displayhive:admin:stc:media_for_picker', handleMediaForPicker)
  off('displayhive:admin:stc:image_tags', handleImageTags)
  if (props.tag.fieldHandler === 'datetime_format') {
    off('displayhive:admin:stc:admin_settings', handleAdminSettingsForPreview)
  }
  if (previewInterval) clearInterval(previewInterval)
})
</script>

<template>
  <div :class="['field-value-editor', { 'fve-disabled': disabled }]">
    <PretalxTableFieldEditor
      v-if="tag.fieldHandler === 'pretalx_table'"
      :model-value="getPretalxTableValue(tag.name)"
      @update:model-value="(v) => setPretalxTableValue(tag.name, v)"
      :mode="mode"
      :option-flags="pretalxOptionFlags"
      @update:option-flags="onPretalxOptionFlagsUpdate"
    />

    <IconPickerField
      v-else-if="tag.fieldHandler === 'icon'"
      :model-value="getIconValue(tag.name)"
      @update:model-value="(v) => setIconValue(tag.name, v)"
      :mode="mode"
      :option-flags="iconOptionFlags"
      @update:option-flags="onIconOptionFlagsUpdate"
    />

    <template v-else-if="tag.fieldHandler === 'textbig'">
      <div v-if="mode !== 'edit' || !isHidden(tag.name)" class="fve-slot">
        <Textarea
          :id="`field-${tag.name}`"
          :modelValue="String(getFieldValue(tag.name))"
          @update:modelValue="(v: string | undefined) => setFieldValue(tag.name, v ?? '')"
          rows="3"
          :maxlength="tag.max_length"
          :disabled="isLocked(tag.name)"
          class="w-full"
        />
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name)" @toggle-locked="toggleFlag(tag.name, 'locked')" @toggle-hidden="toggleFlag(tag.name, 'hidden')" />
      </div>
    </template>

    <template v-else-if="tag.fieldHandler === 'numbers'">
      <div v-if="mode !== 'edit' || !isHidden(tag.name)" class="fve-slot">
        <InputNumber
          :id="`field-${tag.name}`"
          :modelValue="Number(getFieldValue(tag.name))"
          @update:modelValue="(v: number | null) => setFieldValue(tag.name, v ?? 0)"
          :disabled="isLocked(tag.name)"
          class="w-full"
        />
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name)" @toggle-locked="toggleFlag(tag.name, 'locked')" @toggle-hidden="toggleFlag(tag.name, 'hidden')" />
      </div>
    </template>

    <template v-else-if="tag.fieldHandler === 'link'">
      <div v-if="mode !== 'edit' || !isHidden(tag.name)" class="fve-slot">
        <InputText
          :id="`field-${tag.name}`"
          :modelValue="String(getFieldValue(tag.name))"
          @update:modelValue="(v: string | undefined) => setFieldValue(tag.name, v ?? '')"
          type="url"
          placeholder="https://example.com"
          :maxlength="tag.max_length"
          :disabled="isLocked(tag.name)"
          class="w-full"
        />
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name)" @toggle-locked="toggleFlag(tag.name, 'locked')" @toggle-hidden="toggleFlag(tag.name, 'hidden')" />
      </div>
    </template>

    <template v-else-if="tag.fieldHandler === 'wysiwyg' && editorReady">
      <div v-if="mode !== 'edit' || !isHidden(tag.name)" class="fve-slot">
        <Editor
          :id="`field-${tag.name}`"
          :modelValue="String(fields[tag.name] || '')"
          @update:modelValue="(v: string | undefined) => setFieldValue(tag.name, v ?? '')"
          editorStyle="height: 220px"
          :readonly="isLocked(tag.name)"
          @load="(e: any) => onEditorLoad(tag.name, e)"
        />
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name)" @toggle-locked="toggleFlag(tag.name, 'locked')" @toggle-hidden="toggleFlag(tag.name, 'hidden')" />
      </div>
    </template>

    <!-- Image picker -->
    <div v-else-if="tag.fieldHandler === 'image'" class="image-field-wrapper">
      <div v-if="mode !== 'edit' || !isHidden(tag.name + '__image_mode')" class="fve-slot image-mode-select">
        <Select
          :modelValue="getImageMode(tag.name)"
          @update:modelValue="(v: string) => setImageMode(tag.name, v)"
          :options="imageModeOptions"
          optionLabel="label"
          optionValue="value"
          :disabled="isLocked(tag.name + '__image_mode')"
          class="w-full"
        />
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name + '__image_mode')" @toggle-locked="toggleFlag(tag.name + '__image_mode', 'locked')" @toggle-hidden="toggleFlag(tag.name + '__image_mode', 'hidden')" />
      </div>

      <div v-if="getImageMode(tag.name) === 'single' && (mode !== 'edit' || !isHidden(tag.name))" class="fve-slot">
        <div :class="['fve-slot-control', { 'fve-disabled': isLocked(tag.name) }]">
          <div v-if="getFieldValue(tag.name)" class="image-field-preview">
            <img :src="String(getFieldValue(tag.name))" class="image-field-thumb" alt="selected" />
            <div class="image-field-actions">
              <Button icon="pi pi-pencil" size="small" label="Change" outlined @click="openImagePicker(tag.name)" />
              <Button icon="pi pi-times" size="small" severity="danger" outlined @click="clearImageField(tag.name)" />
            </div>
          </div>
          <div v-else class="image-field-empty" @click="openImagePicker(tag.name)">
            <i class="pi pi-image" style="font-size: 2rem; color: #94a3b8" />
            <span>Click to select an image</span>
          </div>
        </div>
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name)" @toggle-locked="toggleFlag(tag.name, 'locked')" @toggle-hidden="toggleFlag(tag.name, 'hidden')" />
      </div>

      <div v-else-if="getImageMode(tag.name) === 'random_tags' && (mode !== 'edit' || !isHidden(tag.name + '__image_tags'))" class="fve-slot">
        <div :class="['image-tags-cloud', 'fve-slot-control', { 'fve-disabled': isLocked(tag.name + '__image_tags') }]">
          <p class="image-tags-hint">Select one or more tags — a random matching image will be shown on each display refresh.</p>
          <div v-if="availableImageTags.length === 0" class="image-tags-empty">
            <i class="pi pi-spin pi-spinner" /> Loading tags…
          </div>
          <div v-else class="image-tags-list">
            <button
              v-for="tag2 in availableImageTags"
              :key="tag2"
              type="button"
              :class="['image-tag-chip', getImageTags(tag.name).includes(tag2) ? 'image-tag-chip--selected' : '']"
              @click="toggleImageTag(tag.name, tag2)"
            >{{ tag2 }}</button>
          </div>
          <small v-if="getImageTags(tag.name).length > 0" class="image-tags-selected-summary">
            Selected: {{ getImageTags(tag.name).join(', ') }}
          </small>
        </div>
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name + '__image_tags')" @toggle-locked="toggleFlag(tag.name + '__image_tags', 'locked')" @toggle-hidden="toggleFlag(tag.name + '__image_tags', 'hidden')" />
      </div>

      <div v-if="mode !== 'edit' || !isHidden(tag.name + '__size')" class="fve-slot image-size-row">
        <label :for="`field-${tag.name}-size`" class="image-size-label">Size (vh)</label>
        <InputNumber
          :id="`field-${tag.name}-size`"
          :modelValue="getImageSize(tag.name)"
          @update:modelValue="(v: number | null) => setImageSize(tag.name, v)"
          :min="0" :max="100" :step="0.5" :max-fraction-digits="2"
          suffix=" vh"
          placeholder="auto"
          :disabled="isLocked(tag.name + '__size')"
          style="width: 140px"
        />
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name + '__size')" @toggle-locked="toggleFlag(tag.name + '__size', 'locked')" @toggle-hidden="toggleFlag(tag.name + '__size', 'hidden')" />
      </div>
    </div>

    <!-- Arrow picker -->
    <div v-else-if="tag.fieldHandler === 'arrows'" class="arrow-picker-wrapper">
      <div v-if="mode !== 'edit' || !isHidden(tag.name)" class="fve-slot">
        <div :class="['fve-slot-control', { 'fve-disabled': isLocked(tag.name) }]" style="width:100%;">
          <div class="arrow-grid">
            <button
              v-for="arrow in [
                { char: '←', label: 'Left' },
                { char: '→', label: 'Right' },
                { char: '↑', label: 'Up' },
                { char: '↓', label: 'Down' },
                { char: '↖', label: 'Up-Left' },
                { char: '↗', label: 'Up-Right' },
                { char: '↙', label: 'Down-Left' },
                { char: '↘', label: 'Down-Right' },
                { char: '↔', label: 'Left-Right' },
                { char: '↕', label: 'Up-Down' },
                { char: '⇐', label: 'Double Left' },
                { char: '⇒', label: 'Double Right' },
                { char: '⇑', label: 'Double Up' },
                { char: '⇓', label: 'Double Down' },
                { char: '⇖', label: 'Double Up-Left' },
                { char: '⇗', label: 'Double Up-Right' },
                { char: '⇙', label: 'Double Down-Left' },
                { char: '⇘', label: 'Double Down-Right' },
                { char: '⇔', label: 'Double Left-Right' },
                { char: '⇕', label: 'Double Up-Down' },
              ]"
              :key="arrow.char"
              type="button"
              :class="['arrow-btn', getFieldValue(tag.name) === arrow.char ? 'arrow-btn--selected' : '']"
              :title="arrow.label"
              @click="setFieldValue(tag.name, arrow.char)"
            >{{ arrow.char }}</button>
          </div>
          <div class="arrow-selected-preview" v-if="getFieldValue(tag.name)">
            Selected: <span class="arrow-preview-char">{{ getFieldValue(tag.name) }}</span>
            <Button icon="pi pi-times" size="small" text @click="setFieldValue(tag.name, '')" title="Clear" />
          </div>
        </div>
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name)" @toggle-locked="toggleFlag(tag.name, 'locked')" @toggle-hidden="toggleFlag(tag.name, 'hidden')" />
      </div>
      <div v-if="mode !== 'edit' || !isHidden(tag.name + '_size')" class="fve-slot arrow-size-row">
        <label :for="`field-${tag.name}-size`" class="arrow-size-label">Größe (vh)</label>
        <InputNumber
          :id="`field-${tag.name}-size`"
          :modelValue="Number(getFieldValue(tag.name + '_size')) || 5"
          @update:modelValue="(v: number | null) => setFieldValue(tag.name + '_size', v ?? 5)"
          :min="0.1"
          :max="50"
          :step="0.1"
          suffix=" vh"
          :disabled="isLocked(tag.name + '_size')"
          style="width: 120px"
        />
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name + '_size')" @toggle-locked="toggleFlag(tag.name + '_size', 'locked')" @toggle-hidden="toggleFlag(tag.name + '_size', 'hidden')" />
      </div>
    </div>

    <template v-else-if="tag.fieldHandler === 'checkbox'">
      <div v-if="mode !== 'edit' || !isHidden(tag.name)" class="fve-slot">
        <Checkbox
          :inputId="`field-${tag.name}`"
          :binary="true"
          :modelValue="!!getFieldValue(tag.name)"
          @update:modelValue="(v: boolean) => setFieldValue(tag.name, v)"
          :disabled="isLocked(tag.name)"
        />
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name)" @toggle-locked="toggleFlag(tag.name, 'locked')" @toggle-hidden="toggleFlag(tag.name, 'hidden')" />
      </div>
    </template>

    <!-- Table editor -->
    <div v-else-if="tag.fieldHandler === 'table' && (mode !== 'edit' || !isHidden(tag.name))" class="fve-slot">
      <div :class="['fve-slot-control', 'table-editor-wrapper', { 'fve-disabled': isLocked(tag.name) }]" style="width:100%;">
        <div class="table-editor-scroll">
          <table class="table-editor-tbl">
            <thead>
              <tr>
                <th class="table-editor-handle-cell"></th>
                <th
                  v-for="(col, ci) in parseTableData(tag.name).columns"
                  :key="ci"
                  class="table-editor-col-th"
                  draggable="true"
                  @dragstart="onTableDragStart(tag.name, 'col', ci, $event)"
                  @dragover.prevent
                  @drop.prevent="onTableDrop(tag.name, 'col', ci)"
                >
                  <div class="table-editor-col-header">
                    <span class="table-editor-drag-icon pi pi-bars"></span>
                    <InputText
                      :modelValue="col"
                      @update:modelValue="(v: string | undefined) => updateTableHeader(tag.name, ci, v ?? '')"
                      size="small"
                      class="table-editor-header-input"
                      placeholder="Header"
                    />
                    <Button
                      icon="pi pi-trash"
                      size="small"
                      text
                      severity="danger"
                      :disabled="parseTableData(tag.name).columns.length <= 1"
                      @click="removeTableColumn(tag.name, ci)"
                    />
                  </div>
                </th>
                <th class="table-editor-add-col-cell">
                  <Button icon="pi pi-plus" size="small" text title="Add column" @click="addTableColumn(tag.name)" />
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, ri) in parseTableData(tag.name).rows"
                :key="ri"
                draggable="true"
                @dragstart="onTableDragStart(tag.name, 'row', ri, $event)"
                @dragover.prevent
                @drop.prevent="onTableDrop(tag.name, 'row', ri)"
              >
                <td class="table-editor-handle-cell">
                  <span class="table-editor-drag-icon pi pi-bars"></span>
                </td>
                <td v-for="(cell, ci) in row" :key="ci" class="table-editor-cell">
                  <InputText
                    :modelValue="cell"
                    @update:modelValue="(v: string | undefined) => updateTableCell(tag.name, ri, ci, v ?? '')"
                    size="small"
                    class="w-full"
                  />
                </td>
                <td class="table-editor-add-col-cell">
                  <Button
                    icon="pi pi-trash"
                    size="small"
                    text
                    severity="danger"
                    :disabled="parseTableData(tag.name).rows.length <= 1"
                    @click="removeTableRow(tag.name, ri)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <Button label="Add Row" icon="pi pi-plus" size="small" text @click="addTableRow(tag.name)" style="margin-top:0.4rem;" />
      </div>
      <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name)" @toggle-locked="toggleFlag(tag.name, 'locked')" @toggle-hidden="toggleFlag(tag.name, 'hidden')" />
    </div>

    <!-- Date / Time format picker -->
    <div v-else-if="tag.fieldHandler === 'datetime_format'" class="datetime-format-wrapper">
      <div v-if="mode !== 'edit' || !isHidden(tag.name)" class="fve-slot">
        <InputText
          :id="`field-${tag.name}`"
          :modelValue="String(getFieldValue(tag.name) || 'HH:mm:ss')"
          @update:modelValue="(v: string | undefined) => setFieldValue(tag.name, v ?? '')"
          class="w-full"
          placeholder="HH:mm:ss"
          :disabled="isLocked(tag.name)"
        />
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name)" @toggle-locked="toggleFlag(tag.name, 'locked')" @toggle-hidden="toggleFlag(tag.name, 'hidden')" />
      </div>
      <div class="datetime-preview">
        <span class="datetime-preview-label">Preview</span>
        <span class="datetime-preview-value">{{ formatDatePreview(String(getFieldValue(tag.name) || 'HH:mm:ss')) }}</span>
        <span class="datetime-preview-tz">({{ previewTimezone }})</span>
      </div>
      <div class="datetime-tokens">
        <p class="datetime-tokens-title">Format tokens</p>
        <table class="token-table">
          <thead>
            <tr><th>Token</th><th>Description</th><th>Example</th></tr>
          </thead>
          <tbody>
            <tr v-for="t in FORMAT_TOKENS" :key="t.token">
              <td><code>{{ t.token }}</code></td>
              <td>{{ t.desc }}</td>
              <td>{{ t.example }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <template v-else>
      <div v-if="mode !== 'edit' || !isHidden(tag.name)" class="fve-slot">
        <InputText
          :id="`field-${tag.name}`"
          :modelValue="String(getFieldValue(tag.name))"
          @update:modelValue="(v: string | undefined) => setFieldValue(tag.name, v ?? '')"
          :maxlength="tag.max_length"
          :disabled="isLocked(tag.name)"
          class="w-full"
        />
        <OptionFlagToggle v-if="mode === 'preset'" v-bind="flagsFor(tag.name)" @toggle-locked="toggleFlag(tag.name, 'locked')" @toggle-hidden="toggleFlag(tag.name, 'hidden')" />
      </div>
    </template>

    <!-- Image Picker Dialog -->
    <Dialog
      v-model:visible="showImagePickerDialog"
      header="Select Image"
      modal
      :style="{ width: '860px', maxWidth: '95vw' }"
    >
      <div class="picker-toolbar">
        <InputText v-model="pickerSearchText" placeholder="Search images…" class="picker-search" />
        <Tag :value="`${pickerFiltered.length} images`" />
      </div>
      <div v-if="pickerLoading" class="loading-state">
        <i class="pi pi-spin pi-spinner" style="font-size: 2rem" />
        <p>Loading media…</p>
      </div>
      <div v-else-if="pickerFiltered.length === 0" class="empty-state">
        <i class="pi pi-images" style="font-size: 3rem" />
        <p>No images found</p>
      </div>
      <div v-else class="picker-grid">
        <div
          v-for="item in pickerFiltered"
          :key="item.id"
          class="picker-item"
          :class="{ 'picker-item--selected': pickerTargetField && String(getFieldValue(pickerTargetField)) === item.url }"
          @click="selectPickerImage(item)"
        >
          <div class="picker-thumb">
            <img :src="item.preview_url || item.url" :alt="item.title" />
          </div>
          <div class="picker-label">{{ item.title || item.filename }}</div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" text @click="showImagePickerDialog = false" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.field-value-editor {
  width: 100%;
}

.fve-disabled {
  pointer-events: none;
  opacity: 0.6;
  user-select: none;
}

/* One row per individual option/sub-control: the control itself (grows to
   fill available width) plus, in preset-authoring mode, its lock/hide
   toggle pair anchored to the right. */
.fve-slot {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  margin-bottom: 0.5rem;
}

.fve-slot:last-child {
  margin-bottom: 0;
}

.fve-slot > *:first-child,
.fve-slot-control {
  flex: 1;
  min-width: 0;
}

.table-editor-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.table-editor-scroll {
  overflow-x: auto;
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  border-radius: 6px;
}

.table-editor-tbl {
  border-collapse: collapse;
  min-width: 100%;
}

.table-editor-tbl th,
.table-editor-tbl td {
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  padding: 4px;
  vertical-align: middle;
  white-space: nowrap;
}

.table-editor-tbl th {
  background: var(--p-surface-100, #f3f4f6);
}

.table-editor-handle-cell {
  width: 24px;
  text-align: center;
  cursor: grab;
}

.table-editor-add-col-cell {
  width: 32px;
  text-align: center;
  border: none !important;
  background: transparent !important;
}

.table-editor-col-th {
  cursor: grab;
}

.table-editor-col-header {
  display: flex;
  align-items: center;
  gap: 4px;
}

.table-editor-header-input {
  flex: 1;
  min-width: 80px;
}

.table-editor-drag-icon {
  color: var(--p-text-muted-color, #9ca3af);
  font-size: 0.75rem;
  cursor: grab;
}

.table-editor-cell {
  min-width: 100px;
}

.image-field-wrapper {
  width: 100%;
}

.image-mode-select {
  margin-bottom: 0.75rem;
}

.image-field-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border: 2px dashed #cbd5e1;
  border-radius: 8px;
  padding: 1.5rem;
  cursor: pointer;
  color: #94a3b8;
  font-size: 0.875rem;
  transition: border-color 0.2s, background 0.2s;
}

.image-field-empty:hover {
  border-color: var(--p-primary-color, #3b82f6);
  background: rgba(59, 130, 246, 0.04);
}

.image-field-preview {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.image-field-thumb {
  width: 80px;
  height: 60px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.image-field-actions {
  display: flex;
  gap: 0.4rem;
}

.image-tags-cloud {
  border: 1px solid var(--p-surface-200, #e2e8f0);
  border-radius: 8px;
  padding: 0.75rem;
  background: var(--p-surface-50, #f8fafc);
}

.image-tags-hint {
  font-size: 0.8rem;
  color: #64748b;
  margin: 0 0 0.6rem;
}

.image-tags-empty {
  color: #94a3b8;
  font-size: 0.85rem;
}

.image-tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}

.image-tag-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  border: 1px solid var(--p-surface-300, #cbd5e1);
  background: white;
  font-size: 0.8rem;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.image-tag-chip:hover {
  border-color: var(--p-primary-color, #3b82f6);
  background: var(--p-primary-50, #eff6ff);
}

.image-tag-chip--selected {
  background: var(--p-primary-color, #3b82f6);
  border-color: var(--p-primary-color, #3b82f6);
  color: white;
}

.image-tag-chip--selected:hover {
  background: var(--p-primary-600, #2563eb);
}

.image-tags-selected-summary {
  font-size: 0.78rem;
  color: #475569;
  display: block;
  margin-top: 0.25rem;
}

/* Arrow picker */
.arrow-picker-wrapper {
  width: 100%;
}

.arrow-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.5rem;
  background: var(--p-surface-50, #f8fafc);
  border: 1px solid var(--p-surface-200, #e2e8f0);
  border-radius: 8px;
}

.arrow-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.4rem;
  height: 2.4rem;
  font-size: 1.4rem;
  border: 1px solid var(--p-surface-300, #cbd5e1);
  border-radius: 6px;
  background: white;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  line-height: 1;
}

.arrow-btn:hover {
  background: var(--p-primary-50, #eff6ff);
  border-color: var(--p-primary-color, #3b82f6);
}

.arrow-btn--selected {
  background: var(--p-primary-color, #3b82f6);
  border-color: var(--p-primary-color, #3b82f6);
  color: white;
}

.arrow-selected-preview {
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
}

.arrow-preview-char {
  font-size: 2rem;
  line-height: 1;
}

.arrow-size-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.6rem;
}

.arrow-size-label {
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
  white-space: nowrap;
}

.image-size-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.6rem;
}

.image-size-label {
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
  white-space: nowrap;
}

/* Image picker dialog */
.picker-toolbar {
  display: flex;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1rem;
}

.picker-search {
  flex: 1;
  max-width: 320px;
}

.picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.75rem;
  max-height: 460px;
  overflow-y: auto;
  padding: 0.25rem;
}

.picker-item {
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.picker-item:hover {
  border-color: var(--p-primary-color, #3b82f6);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
}

.picker-item--selected {
  border-color: var(--p-primary-color, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
}

.picker-thumb {
  width: 100%;
  height: 90px;
  background: #f1f5f9;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.picker-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.picker-label {
  padding: 0.3rem 0.4rem;
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: white;
}

.datetime-format-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.datetime-preview {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.45rem 0.75rem;
  background: var(--p-surface-100, #f3f4f6);
  border-radius: 6px;
  font-family: monospace;
}

.datetime-preview-label {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--p-text-muted-color, #6b7280);
}

.datetime-preview-value {
  font-size: 1rem;
  font-weight: 600;
}

.datetime-preview-tz {
  margin-left: auto;
  font-size: 0.7rem;
  color: var(--p-text-muted-color, #9ca3af);
}

.datetime-tokens {
  margin-top: 0.1rem;
}

.datetime-tokens-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
  margin: 0 0 0.35rem;
}

.token-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
}

.token-table th {
  text-align: left;
  padding: 0.2rem 0.5rem;
  border-bottom: 1px solid var(--p-surface-300, #d1d5db);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.token-table td {
  padding: 0.18rem 0.5rem;
  border-bottom: 1px solid var(--p-surface-200, #e5e7eb);
}

.token-table td code {
  background: var(--p-surface-200, #e5e7eb);
  padding: 0 0.3rem;
  border-radius: 3px;
  font-size: 0.74rem;
}
</style>
