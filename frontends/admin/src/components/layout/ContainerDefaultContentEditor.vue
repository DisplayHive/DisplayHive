<script setup lang="ts">
import { computed, ref } from 'vue'
import { blankPretalxTableValue, type PretalxTableValue } from '../../utils/pretalxTable'
import type { IconPickerValue } from '../../utils/iconLibraries'
import type { DefaultColor } from '../../types/models'
import MediaPickerDialog from '../MediaPickerDialog.vue'
import PretalxTableFieldEditor from '../PretalxTableFieldEditor.vue'
import IconPickerField from '../IconPickerField.vue'
import Button from 'primevue/button'
import DatePicker from 'primevue/datepicker'
import Editor from 'primevue/editor'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'

// The editor of a container's default content for the chosen field handler. Handlers that keep
// structured data pack it as JSON into the one `content` string; the helpers below read and
// write that JSON. (The handler itself is chosen in the settings card.)
defineProps<{
  handler: string
  /** The active Design's palette, offered by the icon picker. */
  palette: DefaultColor[]
}>()
const content = defineModel<string>('content', { required: true })

interface MediaItem { id: number; url: string }

// Same arrow set as ContentEditView.vue's field picker.
const ARROW_OPTIONS = [
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
]

// --- 'image' handler: {url, size}, packed as JSON into default_content —
// back-compat: existing containers stored the raw URL string directly (no
// size), so a plain non-JSON value is read as that URL with size unset.
const showImagePicker = ref(false)
const parseImageData = (): { url: string; size: number | null } => {
  const raw = content.value || ''
  try {
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object' && 'url' in parsed) {
      return { url: parsed.url || '', size: parsed.size || null }
    }
  } catch { /* not JSON — legacy plain URL string */ }
  return { url: raw, size: null }
}
const imageUrl = computed(() => parseImageData().url)
const imageSize = computed(() => parseImageData().size)
const setImageData = (data: { url: string; size: number | null }) => {
  content.value = JSON.stringify(data)
}
const onImagePicked = (item: MediaItem) => {
  setImageData({ url: item.url, size: imageSize.value })
}

// --- 'icon' handler: {icon, size, color}, packed as JSON into default_content
const iconValue = computed<IconPickerValue>(() => {
  try {
    const parsed = JSON.parse(content.value || '{}')
    if (parsed && typeof parsed === 'object' && 'icon' in parsed) {
      return { icon: parsed.icon || '', size: parsed.size ?? 5, color: parsed.color || '' }
    }
  } catch { /* not JSON yet */ }
  return { icon: '', size: 5, color: '' }
})
const setIconData = (v: IconPickerValue) => {
  content.value = JSON.stringify(v)
}

// --- 'arrows' handler: char + size, packed as JSON into default_content ----
const arrowChar = computed({
  get: () => {
    try { return JSON.parse(content.value || '{}').char || '' } catch { return '' }
  },
  set: (v: string) => {
    let size = 5
    try { size = JSON.parse(content.value || '{}').size ?? 5 } catch { /* keep default */ }
    content.value = JSON.stringify({ char: v, size })
  },
})
const arrowSize = computed({
  get: () => {
    try { return JSON.parse(content.value || '{}').size ?? 5 } catch { return 5 }
  },
  set: (v: number | null) => {
    let char = ''
    try { char = JSON.parse(content.value || '{}').char || '' } catch { /* keep default */ }
    content.value = JSON.stringify({ char, size: v ?? 5 })
  },
})

// --- 'marquee' handler: {text, speed}, packed as JSON into default_content --
const marqueeText = computed({
  get: () => {
    try { return JSON.parse(content.value || '{}').text || '' } catch { return '' }
  },
  set: (v: string) => {
    let speed = 20
    try { speed = JSON.parse(content.value || '{}').speed ?? 20 } catch { /* keep default */ }
    content.value = JSON.stringify({ text: v, speed })
  },
})
const marqueeSpeed = computed({
  get: () => {
    try { return JSON.parse(content.value || '{}').speed ?? 20 } catch { return 20 }
  },
  set: (v: number | null) => {
    let text = ''
    try { text = JSON.parse(content.value || '{}').text || '' } catch { /* keep default */ }
    content.value = JSON.stringify({ text, speed: v ?? 20 })
  },
})

// --- 'countdown' handler: {target, format, finished_text}, packed as JSON
// into default_content. `target` is a naive "YYYY-MM-DDTHH:mm" string (no
// timezone), parsed/formatted the same way Content's start_time/end_time
// scheduling fields are — see ContentEditView.vue's parseIsoDate/fmtDt.
const parseCountdownData = (): { target: string; format: string; finished_text: string } => {
  try {
    const parsed = JSON.parse(content.value || '{}')
    return {
      target: parsed.target || '',
      format: parsed.format || 'DD:HH:mm:ss',
      finished_text: parsed.finished_text || '',
    }
  } catch {
    return { target: '', format: 'DD:HH:mm:ss', finished_text: '' }
  }
}
const setCountdownData = (data: { target: string; format: string; finished_text: string }) => {
  content.value = JSON.stringify(data)
}
const fmtCountdownDt = (d: Date | null): string => {
  if (!d) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
const countdownTargetDate = computed<Date | null>({
  get: () => {
    const raw = parseCountdownData().target
    if (!raw) return null
    const d = new Date(raw)
    return isNaN(d.getTime()) ? null : d
  },
  set: (v: Date | null) => setCountdownData({ ...parseCountdownData(), target: fmtCountdownDt(v) }),
})
const countdownFormat = computed({
  get: () => parseCountdownData().format,
  set: (v: string) => setCountdownData({ ...parseCountdownData(), format: v }),
})
const countdownFinishedText = computed({
  get: () => parseCountdownData().finished_text,
  set: (v: string) => setCountdownData({ ...parseCountdownData(), finished_text: v }),
})

// --- 'table' handler: {columns, rows}, stored directly as JSON -------------
interface TableData { columns: string[]; rows: string[][] }
const tableData = computed<TableData>(() => {
  try {
    const parsed = JSON.parse(content.value || '{}')
    if (Array.isArray(parsed.columns) && Array.isArray(parsed.rows)) return parsed
  } catch { /* fall through to default shape */ }
  return { columns: ['Column 1', 'Column 2'], rows: [['', '']] }
})
const setTableData = (data: TableData) => {
  content.value = JSON.stringify(data)
}
const addTableColumn = () => {
  const d = tableData.value
  setTableData({ columns: [...d.columns, `Column ${d.columns.length + 1}`], rows: d.rows.map((r) => [...r, '']) })
}
const removeTableColumn = (ci: number) => {
  const d = tableData.value
  if (d.columns.length <= 1) return
  setTableData({ columns: d.columns.filter((_, i) => i !== ci), rows: d.rows.map((r) => r.filter((_, i) => i !== ci)) })
}
const addTableRow = () => {
  const d = tableData.value
  setTableData({ columns: d.columns, rows: [...d.rows, d.columns.map(() => '')] })
}
const removeTableRow = (ri: number) => {
  const d = tableData.value
  if (d.rows.length <= 1) return
  setTableData({ columns: d.columns, rows: d.rows.filter((_, i) => i !== ri) })
}
const updateTableHeader = (ci: number, v: string) => {
  const d = tableData.value
  const columns = [...d.columns]
  columns[ci] = v
  setTableData({ columns, rows: d.rows })
}
const updateTableCell = (ri: number, ci: number, v: string) => {
  const d = tableData.value
  const rows = d.rows.map((r) => [...r])
  if (rows[ri]) rows[ri][ci] = v
  setTableData({ columns: d.columns, rows })
}

// --- 'pretalx_table' handler: full PretalxTableValue, stored as JSON -------
const pretalxTableData = computed<PretalxTableValue>(() => {
  try {
    return { ...blankPretalxTableValue(), ...JSON.parse(content.value || '{}') }
  } catch {
    return blankPretalxTableValue()
  }
})
const setPretalxTableData = (v: PretalxTableValue) => {
  content.value = JSON.stringify(v)
}
</script>

<template>
  <template v-if="handler">
    <div v-if="['textklein', 'link'].includes(handler)" class="field">
      <label>Default Content</label>
      <InputText v-model="content" size="small" class="w-full" />
    </div>

    <div v-else-if="handler === 'textbig'" class="field">
      <label>Default Content</label>
      <Textarea v-model="content" rows="3" class="w-full" />
    </div>

    <div v-else-if="handler === 'wysiwyg'" class="field">
      <label>Default Content</label>
      <Editor v-model="content" editorStyle="height: 160px" />
    </div>

    <div v-else-if="handler === 'numbers'" class="field">
      <label>Default Content</label>
      <InputNumber
        :model-value="Number(content) || 0"
        size="small" class="w-full"
        @update:model-value="(v) => (content = String(v ?? 0))"
      />
    </div>

    <div v-else-if="handler === 'datetime_format'" class="field">
      <label>Default Content</label>
      <InputText v-model="content" size="small" class="w-full" placeholder="HH:mm:ss" />
    </div>

    <div v-else-if="handler === 'image'" class="field image-field-wrapper">
      <label>Default Content</label>
      <div v-if="imageUrl" class="image-field-preview">
        <img :src="imageUrl" class="image-field-thumb" alt="selected" />
        <div class="image-field-actions">
          <Button icon="pi pi-pencil" size="small" label="Change" outlined @click="showImagePicker = true" />
          <Button icon="pi pi-times" size="small" severity="danger" outlined @click="setImageData({ url: '', size: imageSize })" />
        </div>
      </div>
      <div v-else class="image-field-empty" @click="showImagePicker = true">
        <i class="pi pi-image" />
        <span>Click to select an image</span>
      </div>
      <div class="image-size-row">
        <label class="image-size-label">Size (vh)</label>
        <InputNumber
          :model-value="imageSize"
          @update:model-value="(v) => setImageData({ url: imageUrl, size: v })"
          :min="0" :max="100" :step="0.5" :max-fraction-digits="2"
          suffix=" vh"
          placeholder="auto"
          style="width: 140px"
        />
      </div>
      <MediaPickerDialog
        v-model:visible="showImagePicker"
        :selected-url="content"
        @select="onImagePicked"
      />
    </div>

    <div v-else-if="handler === 'icon'" class="field">
      <label>Default Content</label>
      <IconPickerField :model-value="iconValue" @update:model-value="setIconData" :palette="palette" />
    </div>

    <div v-else-if="handler === 'arrows'" class="field arrow-picker-wrapper">
      <label>Default Content</label>
      <div class="arrow-grid">
        <button
          v-for="arrow in ARROW_OPTIONS"
          :key="arrow.char"
          type="button"
          :class="['arrow-btn', arrowChar === arrow.char ? 'arrow-btn--selected' : '']"
          :title="arrow.label"
          @click="arrowChar = arrow.char"
        >{{ arrow.char }}</button>
      </div>
      <div class="arrow-selected-preview" v-if="arrowChar">
        Selected: <span class="arrow-preview-char">{{ arrowChar }}</span>
        <Button icon="pi pi-times" size="small" text @click="arrowChar = ''" title="Clear" />
      </div>
      <div class="arrow-size-row">
        <label class="arrow-size-label">Größe (vh)</label>
        <InputNumber v-model="arrowSize" :min="0.1" :max="50" :step="0.1" suffix=" vh" style="width: 120px" />
      </div>
    </div>

    <div v-else-if="handler === 'table'" class="field">
      <label>Default Content</label>
      <div class="default-table-editor-scroll">
        <table class="default-table-editor">
          <thead>
            <tr>
              <th v-for="(col, ci) in tableData.columns" :key="ci">
                <InputText
                  :model-value="col" size="small" placeholder="Header"
                  @update:model-value="(v) => updateTableHeader(ci, String(v ?? ''))"
                />
                <Button icon="pi pi-trash" size="small" text severity="danger" :disabled="tableData.columns.length <= 1" @click="removeTableColumn(ci)" />
              </th>
              <th><Button icon="pi pi-plus" size="small" text title="Add column" @click="addTableColumn" /></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, ri) in tableData.rows" :key="ri">
              <td v-for="(cell, ci) in row" :key="ci">
                <InputText
                  :model-value="cell" size="small"
                  @update:model-value="(v) => updateTableCell(ri, ci, String(v ?? ''))"
                />
              </td>
              <td><Button icon="pi pi-trash" size="small" text severity="danger" :disabled="tableData.rows.length <= 1" @click="removeTableRow(ri)" /></td>
            </tr>
          </tbody>
        </table>
      </div>
      <Button label="Add Row" icon="pi pi-plus" size="small" text @click="addTableRow" />
    </div>

    <div v-else-if="handler === 'pretalx_table'" class="field">
      <PretalxTableFieldEditor
        :model-value="pretalxTableData"
        @update:model-value="setPretalxTableData"
      />
    </div>

    <div v-else-if="handler === 'iframe'" class="field">
      <label>iFrame URL</label>
      <InputText v-model="content" type="url" size="small" class="w-full" placeholder="https://example.com" />
    </div>

    <div v-else-if="handler === 'rawhtml'" class="field">
      <label>Default HTML</label>
      <Textarea v-model="content" rows="5" class="w-full" placeholder="<div>…</div>" />
    </div>

    <div v-else-if="handler === 'marquee'" class="field">
      <label>Lauftext</label>
      <InputText :model-value="marqueeText" size="small" class="w-full" placeholder="Dein Lauftext…" @update:model-value="(v) => (marqueeText = String(v ?? ''))" />
      <div class="arrow-size-row">
        <label class="arrow-size-label">Geschwindigkeit (s)</label>
        <InputNumber
          :model-value="marqueeSpeed"
          @update:model-value="(v) => (marqueeSpeed = v)"
          :min="1" :max="300" :step="1"
          suffix=" s"
          style="width: 130px"
        />
      </div>
      <small class="hint">Niedrigere Zahl = schnellere Laufgeschwindigkeit.</small>
    </div>

    <div v-else-if="handler === 'countdown'" class="field">
      <label>Target Date &amp; Time</label>
      <DatePicker v-model="countdownTargetDate" showTime hourFormat="24" showClear dateFormat="dd.mm.yy" placeholder="Pick a date" class="w-full" />
      <label class="mt-2 d-block">Format</label>
      <InputText v-model="countdownFormat" size="small" placeholder="DD:HH:mm:ss" style="width: 160px" />
      <label class="mt-2 d-block">Finished Text</label>
      <InputText v-model="countdownFinishedText" size="small" class="w-full" placeholder="Optional text shown once the countdown ends" />
      <small class="hint">Tokens: DD/D days, HH/H hours, mm/m minutes, ss/s seconds — remaining until the target.</small>
    </div>
  </template>
</template>

<style scoped>
.hint {
  color: var(--p-text-muted-color, #888);
  font-size: 0.75rem;
  margin: 0;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.field label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #666);
}

/* The settings card has a fixed width — a table with many/wide columns
   scrolls inside this wrapper instead of widening the card (and the page)
   sideways. */
.default-table-editor-scroll {
  width: 100%;
  overflow-x: auto;
  margin-bottom: 0.4rem;
}

.default-table-editor {
  border-collapse: collapse;
}

.default-table-editor th,
.default-table-editor td {
  min-width: 90px;
  border: 1px solid var(--p-content-border-color, #ddd);
  padding: 0.25rem;
  text-align: left;
}

.default-table-editor th {
  display: table-cell;
}

/* Image field — mirrors ContentEditView.vue's image field widget */
.image-field-wrapper {
  width: 100%;
}

.image-field-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border: 2px dashed var(--p-content-border-color, #cbd5e1);
  border-radius: 8px;
  padding: 1.5rem;
  cursor: pointer;
  color: var(--p-text-muted-color, #94a3b8);
  font-size: 0.875rem;
  transition: border-color 0.2s, background 0.2s;
}

.image-field-empty i {
  font-size: 2rem;
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
  border: 1px solid var(--p-content-border-color, #e2e8f0);
}

.image-field-actions {
  display: flex;
  gap: 0.4rem;
}

/* Arrow picker — mirrors ContentEditView.vue's arrow field widget */
.arrow-picker-wrapper {
  width: 100%;
}

.arrow-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.5rem;
  background: var(--p-content-background, #f8fafc);
  border: 1px solid var(--p-content-border-color, #e2e8f0);
  border-radius: 8px;
}

.arrow-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.4rem;
  height: 2.4rem;
  font-size: 1.4rem;
  border: 1px solid var(--p-content-border-color, #cbd5e1);
  border-radius: 6px;
  background: var(--p-content-background, white);
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
  flex-wrap: wrap;
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
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.6rem;
}

.image-size-label {
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
  white-space: nowrap;
}
</style>
