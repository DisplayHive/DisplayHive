<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import ToggleSwitch from 'primevue/toggleswitch'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import { useRightsStore } from '../stores/rights'

const rightsStore = useRightsStore()
const canEdit = computed(() => rightsStore.can('content.edit'))
const canDelete = computed(() => rightsStore.can('content.delete'))
const canEnable = computed(() => rightsStore.can('content.enable'))
const canCreate = computed(() => rightsStore.can('content.create'))

interface ContentElement {
  id: number
  title: string
  active: boolean
  duration: number
  start_time?: string | null
  end_time?: string | null
  contenttypeName: string
  screengroups?: Array<{ id: number; name: string }>
  [key: string]: any
}

interface ContentField {
  name: string
  label: string
  value: string
  order: number
}

const props = withDefaults(defineProps<{
  items: ContentElement[]
  emptyMessage?: string
  /** Unfiltered total from the backend. When 0 the search box and table are hidden. */
  totalItems?: number
  search?: string
  /** IDs of one-screen screengroups — used to split screengroups into screens vs groups. */
  oneScreenGroupIds?: number[]
}>(), {
  emptyMessage: 'No content',
  totalItems: undefined,
  search: '',
  oneScreenGroupIds: () => [],
})

const getScreensAndGroups = (data: ContentElement) => {
  const screenIds = new Set(props.oneScreenGroupIds)
  const all = data.screengroups || []
  return {
    screens: all.filter(sg => screenIds.has(sg.id)),
    groups: all.filter(sg => !screenIds.has(sg.id)),
  }
}

const emit = defineEmits<{
  (e: 'edit', content: ContentElement): void
  (e: 'preview', content: ContentElement): void
  (e: 'copy', content: ContentElement): void
  (e: 'delete', content: ContentElement): void
  (e: 'toggleActive', content: ContentElement): void
  (e: 'updateDuration', content: ContentElement): void
  (e: 'setDuration', content: ContentElement, val: number): void
  (e: 'update:search', value: string): void
}>()

// Hide search + table when the backend container has no items at all.
const hasBackendContent = computed(() =>
  props.totalItems !== undefined ? props.totalItems > 0 : props.items.length > 0
)

// Row expansion state — keyed by row data object
const expandedRows = ref<ContentElement[]>([])

// Disconnect observers for wrappers that left the DOM when a row collapsed
watch(expandedRows, () => {
  for (const [el, ro] of previewObservers) {
    if (!el.isConnected) {
      ro.disconnect()
      previewObservers.delete(el)
    }
  }
})

onUnmounted(() => {
  for (const ro of previewObservers.values()) ro.disconnect()
  previewObservers.clear()
})

// Scale the 1920px iframe down to fill its wrapper.
// Uses ResizeObserver so the scale is computed after the wrapper is laid out.
const previewObservers = new Map<HTMLElement, ResizeObserver>()
const scalePreviewFrame = (wrapper: HTMLElement | null) => {
  if (!wrapper) return
  const apply = () => {
    const scale = wrapper.clientWidth / 1920
    if (scale > 0) wrapper.style.setProperty('--preview-scale', String(scale))
  }
  if (!previewObservers.has(wrapper)) {
    const ro = new ResizeObserver(apply)
    ro.observe(wrapper)
    previewObservers.set(wrapper, ro)
  }
  apply()
}

/** ContentElement.html is a JSON map of {contentcontainer_id: rendered_html} — one
 * fragment per field (TagConfig) on the Contenttype. Concatenate them for a rough
 * combined preview (a full multi-container render isn't meaningful outside its Layout). */
const combinedHtml = (raw: string): string => {
  try {
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') {
      return Object.values(parsed).join('\n')
    }
  } catch {
    // Not JSON — fall back to treating it as a raw HTML string (e.g. legacy data).
  }
  return raw
}

const buildSrcdoc = (data: ContentElement): string => {
  const css = data.preview_css || ''
  const html = combinedHtml(data.html || '')
  // Strip sourceMappingURL comments from injected CSS — srcdoc iframes use
  // "about:srcdoc" as base URL so relative map paths can never resolve,
  // which causes a noisy DevTools warning.
  const safeCss = css.replace(/\/\*#\s*sourceMappingURL=[^*]*\*\//g, '')
  return `<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=1920">
<style>
/* Base reset — template CSS overrides these */
html, body {
  margin: 0; padding: 0;
  width: 1920px; height: 1080px;
  overflow: hidden;
}
${safeCss}
</style>
</head>
<body>
${html}
</body>
</html>`
}

const getContentFields = (content: any): ContentField[] => {
  if (!content) return []
  const ignore = new Set([
    'id', 'title', 'active', 'duration', 'start_time', 'end_time',
    'contenttypeName', 'screengroups', 'contenttype_id', 'template', 'html', 'preview_css', '_field_metadata',
  ])
  const fields: ContentField[] = []
  const metadata = content._field_metadata || {}

  for (const k of Object.keys(content)) {
    if (ignore.has(k)) continue
    if (k.endsWith('__image_mode') || k.endsWith('__image_tags')) continue
    const v = content[k]
    if (v === null || v === undefined || v === '') continue

    let textValue = ''
    if (typeof v === 'object') {
      try { textValue = JSON.stringify(v) } catch { continue }
    } else {
      textValue = String(v)
    }

    textValue = textValue.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
    if (!textValue) continue
    if (textValue.length > 100) textValue = textValue.slice(0, 100) + '…'

    const meta = metadata[k] || {}
    fields.push({
      name: k,
      label: meta.label || k,
      value: textValue,
      order: meta.order ?? 999,
    })
  }

  return fields.sort((a, b) => a.order - b.order)
}
</script>

<template>
  <!-- No backend content at all — compact empty state, no search or table -->
  <div v-if="!hasBackendContent" class="empty-state">
    <i class="pi pi-inbox"></i>
    <p>{{ emptyMessage }}</p>
  </div>

  <template v-else>
    <div class="search-box">
      <InputText
        :modelValue="search"
        @update:modelValue="(v: string | undefined) => emit('update:search', v ?? '')"
        placeholder="Search title or content..."
        class="search-input"
      />
    </div>

    <DataTable
      v-model:expandedRows="expandedRows"
      :value="items"
      stripedRows
      size="small"
      :paginator="items.length > 10"
      :rows="10"
      responsiveLayout="scroll"
      dataKey="id"
    >
      <template #empty>
        <div class="empty-state">
          <i class="pi pi-inbox"></i>
          <p>{{ emptyMessage }}</p>
        </div>
      </template>

      <!-- Expand toggle -->
      <Column expander style="width: 3rem" />

      <!-- Active -->
      <Column field="active" header="Active" style="width: 80px">
        <template #body="{ data }">
          <ToggleSwitch v-model="data.active" :disabled="!canEnable" @change="emit('toggleActive', data)" />
        </template>
      </Column>

      <!-- Title + type tag + membership chips -->
      <Column field="title" header="Title" sortable>
        <template #body="{ data }">
          <div class="title-cell">
            <span class="title-text">{{ data.title }}</span>
            <Tag :value="data.contenttypeName" severity="info" class="title-type-tag" />
          </div>
          <div v-if="(data.screengroups || []).length > 0" class="membership-chips">
            <template v-if="getScreensAndGroups(data).screens.length > 0">
              <span class="membership-label">Screens:</span>
              <span
                v-for="sg in getScreensAndGroups(data).screens"
                :key="sg.id"
                class="membership-chip membership-chip--screen"
              >{{ sg.name }}</span>
            </template>
            <template v-if="getScreensAndGroups(data).groups.length > 0">
              <span class="membership-label">Groups:</span>
              <span
                v-for="sg in getScreensAndGroups(data).groups"
                :key="sg.id"
                class="membership-chip membership-chip--group"
              >{{ sg.name }}</span>
            </template>
          </div>
        </template>
      </Column>

      <!-- Actions -->
      <Column header="Actions" style="width: 150px">
        <template #body="{ data }">
          <div class="action-buttons">
            <Button v-if="canEdit" icon="pi pi-pencil" @click="emit('edit', data)" size="small" outlined title="Edit" />
            <Button icon="pi pi-eye" @click="emit('preview', data)" size="small" outlined title="Preview" />
            <Button
              v-if="canCreate"
              icon="pi pi-copy"
              @click="emit('copy', data)"
              size="small"
              outlined
              title="Copy"
            />
            <Button
              v-if="canDelete"
              icon="pi pi-trash"
              @click="emit('delete', data)"
              size="small"
              severity="danger"
              outlined
              title="Delete"
            />
          </div>
        </template>
      </Column>

      <!-- Expanded detail row — spans full width -->
      <template #expansion="{ data }">
        <div class="content-expansion">
          <div class="expansion-details">
            <div class="expansion-duration">
              <span class="expansion-label">Duration</span>
              <InputNumber
                v-model="data.duration"
                :disabled="!canEdit"
                @blur="emit('updateDuration', data)"
                :min="0"
                :max="3600"
                showButtons
                buttonLayout="horizontal"
                class="duration-input-inline"
              />
              <div v-if="canEdit" class="duration-presets">
                <Button
                  v-for="val in [10, 20, 30]"
                  :key="val"
                  :label="`${val}s`"
                  size="small"
                  class="preset-btn"
                  @click="emit('setDuration', data, val)"
                />
              </div>
            </div>
            <div v-if="data.start_time || data.end_time" class="expansion-schedule">
              <span class="expansion-label">Schedule</span>
              <span v-if="data.start_time" class="schedule-chip schedule-chip--start">
                <i class="pi pi-calendar" /> From&nbsp;{{ data.start_time?.replace('T', ' ') }}
              </span>
              <span v-if="data.end_time" class="schedule-chip schedule-chip--end">
                <i class="pi pi-calendar-times" /> Until&nbsp;{{ data.end_time?.replace('T', ' ') }}
              </span>
            </div>
          </div>
          <div v-if="getContentFields(data).length > 0" class="expansion-fields">
            <div v-for="field in getContentFields(data)" :key="field.name" class="content-field-row">
              <span class="field-label">{{ field.label }}</span>
              <span class="field-value">{{ field.value }}</span>
            </div>
          </div>
          <div v-if="data.html" class="expansion-preview">
            <span class="expansion-label">Preview</span>
            <div class="preview-frame-wrapper" :ref="(el) => scalePreviewFrame(el as HTMLElement | null)">
              <iframe
                :srcdoc="buildSrcdoc(data)"
                sandbox="allow-same-origin"
                class="preview-frame"
                width="1920"
                height="1080"
                scrolling="no"
              />
            </div>
          </div>
        </div>
      </template>
    </DataTable>
  </template>
</template>

<style scoped>
.title-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.membership-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem;
  margin-top: 0.25rem;
}

.membership-label {
  font-size: 0.7rem;
  color: var(--p-text-muted-color, #aaa);
  white-space: nowrap;
}

.membership-chip {
  font-size: 0.7rem;
  padding: 0.1rem 0.45rem;
  border-radius: 0.75rem;
  white-space: nowrap;
}

.membership-chip--screen {
  background: var(--p-blue-100, #dbeafe);
  color: var(--p-blue-700, #1d4ed8);
  border: 1px solid var(--p-blue-300, #93c5fd);
}

.membership-chip--group {
  background: var(--p-purple-100, #ede9fe);
  color: var(--p-purple-700, #6d28d9);
  border: 1px solid var(--p-purple-300, #c4b5fd);
}

.title-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-type-tag {
  flex-shrink: 0;
  font-size: 0.75rem;
  margin-left: auto;
}

.content-expansion {
  padding: 0.75rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.expansion-details {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.expansion-type-tag {
  flex-shrink: 0;
}

.expansion-duration {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.expansion-label {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #888);
  white-space: nowrap;
}

.duration-input-inline {
  width: 7rem;
}

.duration-presets {
  display: flex;
  gap: 0.25rem;
}

.expansion-fields {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.content-field-row {
  display: flex;
  gap: 0.5rem;
  font-size: 0.85rem;
}

.field-label {
  color: var(--p-text-muted-color, #888);
  min-width: 6rem;
  flex-shrink: 0;
}

.field-value {
  color: var(--p-text-color, inherit);
}

.expansion-schedule {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.schedule-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.8rem;
  padding: 0.15rem 0.55rem;
  border-radius: 1rem;
  white-space: nowrap;
}

.schedule-chip--start {
  background: var(--p-green-100, #dcfce7);
  color: var(--p-green-700, #15803d);
  border: 1px solid var(--p-green-300, #86efac);
}

.schedule-chip--end {
  background: var(--p-orange-100, #ffedd5);
  color: var(--p-orange-700, #c2410c);
  border: 1px solid var(--p-orange-300, #fdba74);
}

.expansion-preview {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.preview-frame-wrapper {
  border: 1px solid var(--p-surface-border, #ddd);
  border-radius: 4px;
  overflow: hidden;
  background: #000;
  width: 100%;
  aspect-ratio: 16 / 9;
  position: relative;
}

.preview-frame {
  position: absolute;
  top: 0;
  left: 0;
  width: 1920px;
  height: 1080px;
  border: none;
  display: block;
  transform-origin: top left;
  transform: scale(var(--preview-scale, 0.25));
}
</style>
