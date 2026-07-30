<script setup lang="ts">
/**
 * Full config editor for the `pretalx_table` field handler — shared by
 * ContentEditor.vue (a Contenttype field's live value) and
 * LayoutCanvasEditor.vue (a container's default_content) so this fairly
 * involved multi-part config isn't duplicated across both editors.
 *
 * The value shape is deliberately flat/serializable (matches what
 * `application/admin/content/pretalx_render.py`'s `_render_pretalx_table`
 * expects) rather than mirroring the wire format either caller happens to
 * store it in — each caller adapts its own storage to/from this shape.
 */
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useSocket } from '../composables/useSocket'
import type { PretalxTableValue } from '../utils/pretalxTable'

import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Checkbox from 'primevue/checkbox'
import Button from 'primevue/button'

const props = defineProps<{
  modelValue: PretalxTableValue
  /** Label for the API-endpoint select — callers phrase this differently (a field vs. a container default). */
  label?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: PretalxTableValue]
}>()

const patch = (partial: Partial<PretalxTableValue>) => emit('update:modelValue', { ...props.modelValue, ...partial })

const { emit: socketEmit, emitWithAck: socketEmitWithAck, on, off } = useSocket()

interface PretalxApiUrlOption {
  id: number
  name: string
  url: string
  is_valid: boolean | null
  has_cache: boolean
}
const pretalxApiUrls = ref<PretalxApiUrlOption[]>([])
const pretalxRoomsCache = ref<Record<string, string[]>>({})

const handlePretalxUrls = (data: any) => {
  pretalxApiUrls.value = (data?.urls || []).map((u: any) => ({
    id: u.id,
    name: u.name,
    url: u.url,
    is_valid: u.is_valid,
    has_cache: u.has_cache,
  }))
}

async function fetchPretalxRooms(urlId: string) {
  if (!urlId || urlId in pretalxRoomsCache.value) return
  pretalxRoomsCache.value[urlId] = []
  try {
    const ack = await socketEmitWithAck<any>('displayhive:admin:pretalx:cts:get_rooms', { id: Number(urlId) })
    if (ack?.ok) pretalxRoomsCache.value[urlId] = ack.rooms || []
  } catch { /* keep empty */ }
}

const roomsForCurrentUrl = computed(() => (props.modelValue.url ? (pretalxRoomsCache.value[props.modelValue.url] ?? []) : []))

const setRoomSelected = (room: string, selected: boolean) => {
  const current = props.modelValue.roomname.split(',').map(r => r.trim()).filter(Boolean)
  const next = selected ? [...new Set([...current, room])] : current.filter(r => r !== room)
  patch({ roomname: next.join(',') })
}
const isRoomSelected = (room: string): boolean =>
  props.modelValue.roomname.split(',').map(r => r.trim()).includes(room)

watch(() => props.modelValue.url, (urlId) => { if (urlId) fetchPretalxRooms(urlId) }, { immediate: true })

onMounted(() => {
  on('displayhive:admin:pretalx:stc:urls', handlePretalxUrls)
  socketEmit('displayhive:admin:pretalx:cts:get_urls')
})
onUnmounted(() => {
  off('displayhive:admin:pretalx:stc:urls', handlePretalxUrls)
})

// --- Event-field / tracklist-column list editors (same "key|Label,key|Label" format) ---
interface ColumnRow { key: string; label: string }

const parseColumns = (raw: string): ColumnRow[] =>
  raw.split(',').filter(Boolean).map(part => {
    const pipe = part.indexOf('|')
    return pipe === -1
      ? { key: part.trim(), label: part.trim() }
      : { key: part.slice(0, pipe).trim(), label: part.slice(pipe + 1).trim() }
  })

const serializeColumns = (rows: ColumnRow[]): string =>
  rows.filter(r => r.key).map(r => `${r.key}|${r.label}`).join(',')

const EVENT_FIELD_OPTIONS = [
  { label: 'Date/Time',   value: 'date'        },
  { label: 'Title',       value: 'title'       },
  { label: 'Abstract',    value: 'abstract'    },
  { label: 'Speaker',     value: 'person'      },
  { label: 'Track',       value: 'track'       },
  { label: 'Track Color', value: 'color'       },
  { label: 'Room',        value: 'room'        },
  { label: 'Duration',    value: 'duration'    },
  { label: 'Description', value: 'description' },
]

const TRACKLIST_COL_OPTIONS = [
  { label: 'Name',  value: 'name'  },
  { label: 'Slug',  value: 'slug'  },
  { label: 'Color', value: 'color' },
]

const eventFieldRows = computed(() => parseColumns(props.modelValue.fields))
const updateEventFieldKey = (idx: number, key: string) => {
  const rows = eventFieldRows.value
  if (rows[idx]) { rows[idx].key = key; if (!rows[idx].label) rows[idx].label = key }
  patch({ fields: serializeColumns(rows) })
}
const updateEventFieldLabel = (idx: number, label: string) => {
  const rows = eventFieldRows.value
  if (rows[idx]) rows[idx].label = label
  patch({ fields: serializeColumns(rows) })
}
const removeEventField = (idx: number) => {
  const rows = eventFieldRows.value
  rows.splice(idx, 1)
  patch({ fields: serializeColumns(rows) })
}
const addEventField = () => {
  const rows = eventFieldRows.value
  rows.push({ key: 'date', label: 'Date/Time' })
  patch({ fields: serializeColumns(rows) })
}

const tracklistRows = computed(() => parseColumns(props.modelValue.tracklist_columns))
const updateTracklistKey = (idx: number, key: string) => {
  const rows = tracklistRows.value
  if (rows[idx]) { rows[idx].key = key; if (!rows[idx].label) rows[idx].label = key }
  patch({ tracklist_columns: serializeColumns(rows) })
}
const updateTracklistLabel = (idx: number, label: string) => {
  const rows = tracklistRows.value
  if (rows[idx]) rows[idx].label = label
  patch({ tracklist_columns: serializeColumns(rows) })
}
const removeTracklistColumn = (idx: number) => {
  const rows = tracklistRows.value
  rows.splice(idx, 1)
  patch({ tracklist_columns: serializeColumns(rows) })
}
const addTracklistColumn = () => {
  const rows = tracklistRows.value
  rows.push({ key: 'name', label: 'Name' })
  patch({ tracklist_columns: serializeColumns(rows) })
}

// Which fields are relevant depends on `type` — mirrors _render_pretalx_table's own
// per-type behavior (e.g. a Tracklist doesn't use a room filter or line count).
const VISIBLE_FOR_TYPE: Record<string, string[]> = {
  roomname:           ['list', 'current', 'coming_up'],
  linecount:          ['list'],
  fields:             ['list', 'current', 'coming_up'],
  author_under_title: ['list', 'current', 'coming_up'],
  tracks_by_color:    ['list', 'current', 'coming_up'],
  today_only:         ['list'],
  separate_days:      ['list'],
  day_prefix:         ['list', 'eventday'],
  empty_text:         ['current', 'coming_up'],
  tracklist_columns:  ['tracklist'],
  tracklist_layout:   ['tracklist'],
  tracklist_exclude:  ['tracklist'],
}
const isVisible = (key: keyof typeof VISIBLE_FOR_TYPE): boolean =>
  !VISIBLE_FOR_TYPE[key] || VISIBLE_FOR_TYPE[key].includes(props.modelValue.type)
</script>

<template>
  <div class="pretalx-table-editor">
    <div class="field">
      <label>{{ label || 'API Endpoint' }}</label>
      <Select
        :modelValue="modelValue.url"
        @update:modelValue="(v: string) => patch({ url: v })"
        :options="pretalxApiUrls.map(u => ({ label: u.name + (u.has_cache ? '' : ' ⚠ no cache'), value: String(u.id) }))"
        optionLabel="label"
        optionValue="value"
        placeholder="— select API endpoint —"
        emptyMessage="No Pretalx API URLs configured"
        class="w-full"
      />
    </div>

    <div class="field">
      <label>Type</label>
      <Select
        :modelValue="modelValue.type"
        @update:modelValue="(v: string) => patch({ type: v })"
        :options="[
          { label: 'List', value: 'list' },
          { label: 'Current Event', value: 'current' },
          { label: 'Coming Up', value: 'coming_up' },
          { label: 'Event Day', value: 'eventday' },
          { label: 'Tracklist', value: 'tracklist' },
        ]"
        optionLabel="label"
        optionValue="value"
        class="w-full"
      />
    </div>

    <div v-show="isVisible('roomname')" class="field">
      <label>Room Name filter</label>
      <div class="room-select">
        <template v-if="roomsForCurrentUrl.length">
          <label v-for="room in roomsForCurrentUrl" :key="room" class="room-option">
            <Checkbox :binary="true" :modelValue="isRoomSelected(room)" @update:modelValue="(v: boolean) => setRoomSelected(room, v)" />
            <span>{{ room }}</span>
          </label>
        </template>
        <span v-else class="field-hint">{{ modelValue.url ? 'No rooms found in cache' : 'Select an API endpoint first' }}</span>
      </div>
    </div>

    <div v-show="isVisible('fields')" class="field">
      <label>Fields</label>
      <div class="tracklist-cols-editor">
        <div class="tracklist-cols-header"><span>Field</span><span>Header</span><span></span></div>
        <div v-for="(row, idx) in eventFieldRows" :key="idx" class="tracklist-cols-row">
          <Select
            :modelValue="row.key || null"
            @update:modelValue="(v: string | null) => updateEventFieldKey(idx, v ?? '')"
            :options="EVENT_FIELD_OPTIONS"
            optionLabel="label"
            optionValue="value"
            placeholder="— select —"
            size="small"
            class="w-full"
          />
          <InputText :modelValue="row.label" @update:modelValue="(v: string | undefined) => updateEventFieldLabel(idx, v ?? '')" size="small" class="w-full" />
          <Button icon="pi pi-trash" size="small" text severity="danger" @click="removeEventField(idx)" />
        </div>
        <Button label="Add Field" icon="pi pi-plus" size="small" text @click="addEventField" style="margin-top:0.25rem;" />
      </div>
    </div>

    <div v-show="isVisible('linecount')" class="field">
      <label>Line Count</label>
      <InputNumber :modelValue="modelValue.linecount" @update:modelValue="(v: number | null) => patch({ linecount: v ?? 0 })" class="w-full" />
    </div>

    <div v-show="isVisible('author_under_title')" class="field field--checkbox">
      <Checkbox :inputId="'pretalx-author-under-title'" :binary="true" :modelValue="modelValue.author_under_title" @update:modelValue="(v: boolean) => patch({ author_under_title: v })" />
      <label for="pretalx-author-under-title">Display Author under Title</label>
    </div>

    <div v-show="isVisible('tracks_by_color')" class="field field--checkbox">
      <Checkbox :inputId="'pretalx-tracks-by-color'" :binary="true" :modelValue="modelValue.tracks_by_color" @update:modelValue="(v: boolean) => patch({ tracks_by_color: v })" />
      <label for="pretalx-tracks-by-color">Represent tracks by Color</label>
    </div>

    <div v-show="isVisible('today_only')" class="field field--checkbox">
      <Checkbox :inputId="'pretalx-today-only'" :binary="true" :modelValue="modelValue.today_only" @update:modelValue="(v: boolean) => patch({ today_only: v })" />
      <label for="pretalx-today-only">Only show today</label>
    </div>

    <div v-show="isVisible('separate_days')" class="field field--checkbox">
      <Checkbox :inputId="'pretalx-separate-days'" :binary="true" :modelValue="modelValue.separate_days" @update:modelValue="(v: boolean) => patch({ separate_days: v })" />
      <label for="pretalx-separate-days">Separate day tables</label>
    </div>

    <div v-show="isVisible('day_prefix')" class="field">
      <label>Day Prefix</label>
      <InputText :modelValue="modelValue.day_prefix" @update:modelValue="(v: string | undefined) => patch({ day_prefix: v ?? '' })" class="w-full" />
    </div>

    <div v-show="isVisible('empty_text')" class="field">
      <label>No session running text</label>
      <InputText :modelValue="modelValue.empty_text" @update:modelValue="(v: string | undefined) => patch({ empty_text: v ?? '' })" class="w-full" />
    </div>

    <div v-show="isVisible('tracklist_columns')" class="field">
      <label>Tracklist Columns</label>
      <div class="tracklist-cols-editor">
        <div class="tracklist-cols-header"><span>Field</span><span>Header</span><span></span></div>
        <div v-for="(row, idx) in tracklistRows" :key="idx" class="tracklist-cols-row">
          <Select
            :modelValue="row.key || null"
            @update:modelValue="(v: string | null) => updateTracklistKey(idx, v ?? '')"
            :options="TRACKLIST_COL_OPTIONS"
            optionLabel="label"
            optionValue="value"
            placeholder="— select —"
            size="small"
            class="w-full"
          />
          <InputText :modelValue="row.label" @update:modelValue="(v: string | undefined) => updateTracklistLabel(idx, v ?? '')" size="small" class="w-full" />
          <Button icon="pi pi-trash" size="small" text severity="danger" @click="removeTracklistColumn(idx)" />
        </div>
        <Button label="Add Column" icon="pi pi-plus" size="small" text @click="addTracklistColumn" style="margin-top:0.25rem;" />
      </div>
    </div>

    <div v-show="isVisible('tracklist_layout')" class="field">
      <label>Tracklist Layout</label>
      <Select
        :modelValue="modelValue.tracklist_layout"
        @update:modelValue="(v: string) => patch({ tracklist_layout: v })"
        :options="[
          { label: 'List (one track per row)', value: 'list' },
          { label: 'Row (all tracks in one row)', value: 'row' },
        ]"
        optionLabel="label"
        optionValue="value"
        class="w-full"
      />
    </div>

    <div v-show="isVisible('tracklist_exclude')" class="field">
      <label>Exclude Tracks</label>
      <small class="field-description">Comma-separated track names or slugs to exclude</small>
      <InputText :modelValue="modelValue.tracklist_exclude" @update:modelValue="(v: string | undefined) => patch({ tracklist_exclude: v ?? '' })" class="w-full" />
    </div>

    <details class="styling-collapsible">
      <summary class="styling-summary">Styling <small class="text-muted">(optional)</small></summary>
      <div class="styling-fields">
        <div class="field">
          <label>Invalid API Data Text</label>
          <InputText
            :modelValue="modelValue.invalid_data_text"
            @update:modelValue="(v: string | undefined) => patch({ invalid_data_text: v ?? '' })"
            placeholder="Uses global Pretalx setting when empty"
            class="w-full"
          />
        </div>
      </div>
    </details>
  </div>
</template>

<style scoped>
.pretalx-table-editor {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.field--checkbox {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}

.field-description {
  color: #666;
  font-size: 0.75rem;
  margin-top: -0.2rem;
}

.field-hint {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #888);
}

.room-select {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.35rem;
}

.room-option {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
}

.tracklist-cols-editor {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.tracklist-cols-header,
.tracklist-cols-row {
  display: grid;
  grid-template-columns: 1fr 1fr 36px;
  gap: 0.5rem;
  align-items: center;
}

.tracklist-cols-header {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-color-secondary, #6b7280);
  padding: 0 0 0.25rem 0;
  border-bottom: 1px solid var(--p-inputtext-border-color, #d1d5db);
}

.styling-collapsible {
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  border-radius: 6px;
}

.styling-summary {
  padding: 0.6rem 0.75rem;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  list-style: none;
  user-select: none;
}

.styling-summary::-webkit-details-marker { display: none; }

.styling-summary::before {
  content: '▶';
  display: inline-block;
  margin-right: 0.5rem;
  font-size: 0.7rem;
  transition: transform 0.2s;
}

details[open] .styling-summary::before {
  transform: rotate(90deg);
}

.styling-fields {
  padding: 0.75rem;
  border-top: 1px solid var(--p-inputtext-border-color, #d1d5db);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.styling-fields .field {
  margin: 0;
}
</style>
