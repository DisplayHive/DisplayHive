<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import Popover from 'primevue/popover'
import DialogTitle from '../DialogTitle.vue'
import DialogFooter from '../DialogFooter.vue'
import RouteLink from '../RouteLink.vue'
import FieldValueEditor from '../FieldValueEditor.vue'
import { links } from '../../utils/links'
import { useAck } from '../../composables/useAck'
import { useSocket } from '../../composables/useSocket'
import { useRightsStore } from '../../stores/rights'
import type { Layout, ContentContainer, DefaultColor } from '../../types/models'
import type { OptionFlags } from '../../utils/optionFlags'
import type { ContentType, TagConfig, RawContentTypeDetail } from './types'

// Create / edit dialog of the Content Types page. `contentType` null means
// "new"; otherwise the dialog loads that type's fields from the server each
// time it opens. Every container of the chosen Layout gets one field slot.
const props = defineProps<{
  contentType: ContentType | null
  layouts: Layout[]
  containers: ContentContainer[]
  designPalette: DefaultColor[]
}>()
const visible = defineModel<boolean>('visible', { default: false })

const layoutHelpPopover = ref<InstanceType<typeof Popover> | null>(null)
const toggleLayoutHelp = (e: Event) => layoutHelpPopover.value?.toggle(e)
const toast = useToast()
const { on, off, emit } = useSocket()
const { request } = useAck()
const rightsStore = useRightsStore()

const isNew = computed(() => !props.contentType)

const layoutOptions = computed(() => props.layouts.map(l => ({ label: l.name, value: l.id })))

// Containers belonging to the currently-selected Layout in the edit form,
// in display order — each one gets exactly one field slot.
const containersForLayout = computed(() => {
  const layout = props.layouts.find(l => l.id === editForm.value.layout_id)
  // Any aspect-ratio variant counts — a container only present in, say, the
  // 4:3 variation can still be targeted by a field.
  const ids = new Set([
    ...(layout?.container_ids || []),
    ...(layout?.variations || []).flatMap(v => v.container_ids),
  ])
  return props.containers
    .filter(c => ids.has(c.id))
    .slice()
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0) || a.id - b.id)
})

// Field handler options (matches legacy UI and DB schema), English labels, A→Z
// (except 'None', kept first — it means "no input for this field in the
// ContentElement editor; always fall through to the container's own
// default_content", same value/meaning as ContentContainer.default_field_handler's
// own 'None' option in LayoutCanvasEditor.vue).
const fieldHandlerOptions = [
  { label: 'None', value: '' },
  { label: 'Arrow', value: 'arrows' },
  { label: 'Countdown', value: 'countdown' },
  { label: 'Date / Time Format', value: 'datetime_format' },
  { label: 'HTML (raw)', value: 'rawhtml' },
  { label: 'Icon', value: 'icon' },
  { label: 'iFrame', value: 'iframe' },
  { label: 'Lauftext (Marquee)', value: 'marquee' },
  { label: 'Image', value: 'image' },
  { label: 'Link/URL', value: 'link' },
  { label: 'Long Text', value: 'textbig' },
  { label: 'Number', value: 'numbers' },
  { label: 'Pretalx Table', value: 'pretalx_table' },
  { label: 'Short Text', value: 'textklein' },
  { label: 'Table', value: 'table' },
  { label: 'WYSIWYG', value: 'wysiwyg' },
]

const editForm = ref({
  id: null as number | null,
  name: '',
  description: '',
  layout_id: null as number | null,
  tagconfigs: [] as TagConfig[],
})

const loadingContentType = ref(false)
const loadingContentTypeError = ref('')
let contentTypeLoadTimer: number | null = null

// Each container of the selected Layout automatically gets exactly one
// field slot — there is no manual container picker or add/remove step. A
// field's name (used as its storage key) is never its own — it's always the
// container's current name, so renaming a container elsewhere can't leave a
// field pointing at a stale key. Title, field_handler, order and id survive
// a re-sync; containers newly in the Layout get a fresh field appended at
// the end, and fields for containers no longer in the Layout are dropped.
const syncFieldsToLayoutContainers = () => {
  const layoutContainerIds = new Set(containersForLayout.value.map(c => c.id))
  const existingByContainer = new Map(
    editForm.value.tagconfigs
      .filter(t => t.contentcontainer_id != null)
      .map(t => [t.contentcontainer_id as number, t])
  )
  // Fields whose container is still in the Layout keep their position, title
  // and field_handler — only their name is re-synced to the container's
  // current name (see comment above). Fields for containers no longer in the
  // Layout are dropped; containers newly in the Layout get a fresh field
  // appended at the end.
  const kept = editForm.value.tagconfigs
    .filter(t => t.contentcontainer_id != null && layoutContainerIds.has(t.contentcontainer_id as number))
    .map(t => {
      const c = containersForLayout.value.find(c => c.id === t.contentcontainer_id)
      return { ...t, name: c ? c.name : t.name }
    })
  const added = containersForLayout.value
    .filter(c => !existingByContainer.has(c.id))
    .map(c => ({
      id: null,
      name: c.name,
      title: c.name,
      field_handler: 'textklein',
      contentcontainer_id: c.id,
      default_value: {},
      option_flags: {},
    }))
  editForm.value.tagconfigs = [...kept, ...added]
}

// Which fields' Preset panel is currently expanded, keyed by tagconfig id
// (or "new-<index>" for not-yet-saved fields, matching the row :key below).
const expandedPresetKeys = ref<Set<string | number>>(new Set())
const presetKeyFor = (t: TagConfig, idx: number) => t.id ?? `new-${idx}`
const togglePresetPanel = (key: string | number) => {
  const next = new Set(expandedPresetKeys.value)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  expandedPresetKeys.value = next
}

// Whether any individual sub-option on this field currently has a lock/hide
// flag set — drives the Preset button's highlighted state.
const hasAnyOptionFlag = (t: TagConfig): boolean =>
  Object.values(t.option_flags || {}).some((f) => f.locked || f.hidden)

const dragFieldIndex = ref<number | null>(null)
const onFieldDragStart = (index: number) => {
  dragFieldIndex.value = index
}
const onFieldDrop = (index: number) => {
  if (dragFieldIndex.value === null || dragFieldIndex.value === index) return
  const arr = editForm.value.tagconfigs
  const [moved] = arr.splice(dragFieldIndex.value, 1)
  if (moved) arr.splice(index, 0, moved)
  dragFieldIndex.value = null
}

watch(() => editForm.value.layout_id, () => {
  if (visible.value) syncFieldsToLayoutContainers()
})

const containerLabelFor = (contentcontainerId: number | null) => {
  const c = props.containers.find(c => c.id === contentcontainerId)
  return c ? c.name : '?'
}

const prepareTagConfigsPayload = () => {
  return editForm.value.tagconfigs.map((t, i) => ({
    id: t.id, name: t.name, title: t.title, field_handler: t.field_handler,
    contentcontainer_id: t.contentcontainer_id, order: i,
    default_value: JSON.stringify(t.default_value || {}),
    option_flags: JSON.stringify(t.option_flags || {}),
  }))
}

const load = (ct: ContentType | null) => {
  if (!ct) {
    editForm.value = { id: null, name: '', description: '', layout_id: null, tagconfigs: [] }
    return
  }
  editForm.value = { id: ct.id, name: ct.name, description: ct.description || '', layout_id: ct.layout_id, tagconfigs: [] }
  try {
    loadingContentType.value = true
    loadingContentTypeError.value = ''
    emit('displayhive:admin:cts:get_contenttype', { id: ct.id })
    if (contentTypeLoadTimer) clearTimeout(contentTypeLoadTimer)
    contentTypeLoadTimer = window.setTimeout(() => {
      loadingContentType.value = false
      loadingContentTypeError.value = 'Timed out while fetching content type detail.'
      contentTypeLoadTimer = null
    }, 8000)
  } catch {}
}

const stopLoading = () => {
  loadingContentType.value = false
  loadingContentTypeError.value = ''
  if (contentTypeLoadTimer) {
    clearTimeout(contentTypeLoadTimer)
    contentTypeLoadTimer = null
  }
}

watch(visible, (open) => {
  if (open) load(props.contentType)
  else stopLoading()
})

const closeDialog = () => {
  visible.value = false
}

const handleContentTypeDetail = (data: { contenttype?: RawContentTypeDetail; data?: RawContentTypeDetail }) => {
  const ct = data?.contenttype || data?.data || null
  // Only the open edit dialog of this very content type takes the detail.
  if (!ct || !visible.value || editForm.value.id !== ct.id) return
  editForm.value.layout_id = ct.layout_id
  editForm.value.tagconfigs = (ct.tagconfigs || [])
    .slice()
    .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
    .map((t) => {
      const c = props.containers.find(x => x.id === t.contentcontainer_id)
      let default_value: Record<string, unknown> = {}
      try { default_value = t.default_value ? JSON.parse(t.default_value) : {} } catch { default_value = {} }
      let option_flags: OptionFlags = {}
      try { option_flags = t.option_flags ? JSON.parse(t.option_flags) : {} } catch { option_flags = {} }
      return {
        id: t.id,
        name: c?.name || t.field_name || '',
        title: t.field_label || c?.name || t.field_name || '',
        field_handler: t.field_handler ?? 'textklein',
        contentcontainer_id: t.contentcontainer_id ?? null,
        default_value,
        option_flags,
      }
    })
  // Ensure every container of the Layout has a slot, even if the Layout
  // gained containers since this Contenttype's fields were last saved.
  syncFieldsToLayoutContainers()

  loadingContentType.value = false
  loadingContentTypeError.value = ''
  if (contentTypeLoadTimer) {
    clearTimeout(contentTypeLoadTimer)
    contentTypeLoadTimer = null
  }
}

onMounted(() => {
  on('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
})

onUnmounted(() => {
  off('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
  stopLoading()
})

const saveContentType = async (keepOpen = false) => {
  if (!editForm.value.layout_id) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'A Layout is required', life: 3000 })
    return
  }

  const event = isNew.value
    ? 'displayhive:admin:cts:create_contenttype'
    : 'displayhive:admin:cts:update_contenttype'

  const ack = await request(event, {
    id: editForm.value.id,
    name: editForm.value.name,
    description: editForm.value.description,
    layout_id: editForm.value.layout_id,
    tagconfigs: prepareTagConfigsPayload(),
  }, {
    success: isNew.value ? 'Content type created' : 'Content type updated',
    error: 'The server could not save the content type.',
  })
  // The server pushes the new list to every admin (no fetch() behind the save).
  if (ack && !keepOpen) visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: '90vw', maxWidth: '1200px' }"
  >
    <template #header>
      <DialogTitle icon="pi-list" :title="isNew ? 'New Content Type' : 'Edit Content Type'" />
    </template>
    <div class="dialog-content">
      <div v-if="loadingContentType" class="tpl-loading">
        Loading content type…
        <div v-if="loadingContentTypeError" class="tpl-loading-error">{{ loadingContentTypeError }}</div>
      </div>
      <div class="field">
        <label for="ct-name">Name</label>
        <InputText id="ct-name" v-model="editForm.name" class="w-full" />
      </div>
      <div class="field">
        <label for="ct-description">Description</label>
        <Textarea id="ct-description" v-model="editForm.description" rows="2" class="w-full" />
      </div>
      <div class="field" data-tour="contenttype-layout-field">
        <label for="ct-layout">
          Layout
          <i
            class="pi pi-question-circle field-help-icon"
            role="button"
            tabindex="0"
            aria-label="Help: Layout"
            @click="toggleLayoutHelp"
            @keydown.enter="toggleLayoutHelp"
          ></i>
        </label>
        <Popover ref="layoutHelpPopover">
          <p class="field-help-text">
            The Layout determines which containers this content type's fields can target — one
            field slot is created per container of the selected Layout, kept automatically in
            sync with it.
          </p>
        </Popover>
        <Select
          id="ct-layout"
          v-model="editForm.layout_id"
          :options="layoutOptions"
          optionLabel="label"
          optionValue="value"
          placeholder="Select a layout"
          class="w-full"
        />
        <small class="hint">Scopes which containers this content type's fields may target.</small>
      </div>

      <!-- Fields (TagConfig) — one per container of the selected Layout,
           automatically kept in sync with it. Each field's transformed
           value directly becomes its container's rendered content. The
           Title is rendered as a header above the field's content in the
           actual content element (see render_content_fields), and is also
           the label shown in the Content Editor form. Drag rows by the
           handle to reorder — this order is what the Content Editor and
           the rendered content element use. -->
      <div class="fields-section" data-tour="contenttype-fields-section">
        <label>Fields <small>one per container of the selected Layout &mdash; drag to reorder</small></label>
        <p v-if="!editForm.layout_id" class="hint">Select a Layout above to see its containers.</p>
        <p v-else-if="!editForm.tagconfigs.length" class="hint">This Layout has no containers yet.</p>
        <div v-else class="tagconfigs-table">
          <div class="tagconfig-header">
            <div class="tagconfig-col-drag"></div>
            <div class="tagconfig-col-container">Container</div>
            <div class="tagconfig-col-title">Title</div>
            <div class="tagconfig-col-type">Field Handler</div>
            <div class="tagconfig-col-preset"></div>
          </div>
          <template v-for="(t, tIdx) in editForm.tagconfigs" :key="t.id ?? `new-${tIdx}`">
            <div
              class="tagconfig-row"
              draggable="true"
              @dragstart="onFieldDragStart(tIdx)"
              @dragover.prevent
              @drop="onFieldDrop(tIdx)"
            >
              <div class="tagconfig-col-drag">
                <i class="pi pi-bars drag-handle" title="Drag to reorder"></i>
              </div>
              <div class="tagconfig-col-container">
                <RouteLink
                  v-if="rightsStore.can('layouts.page') && editForm.layout_id && t.contentcontainer_id"
                  :to="links.layout(editForm.layout_id, t.contentcontainer_id)"
                  class="container-label"
                  title="Open this container in the layout editor"
                >{{ containerLabelFor(t.contentcontainer_id) }}</RouteLink>
                <span v-else class="container-label">{{ containerLabelFor(t.contentcontainer_id) }}</span>
              </div>
              <div class="tagconfig-col-title">
                <InputText v-model="t.title" placeholder="Title shown as header" class="w-full" size="small" />
              </div>
              <div class="tagconfig-col-type">
                <Select
                  v-model="t.field_handler"
                  :options="fieldHandlerOptions"
                  optionLabel="label"
                  optionValue="value"
                  class="w-full"
                  size="small"
                />
              </div>
              <div class="tagconfig-col-preset">
                <Button
                  :icon="expandedPresetKeys.has(presetKeyFor(t, tIdx)) ? 'pi pi-chevron-up' : 'pi pi-sliders-h'"
                  text
                  size="small"
                  :severity="hasAnyOptionFlag(t) ? 'warning' : undefined"
                  :title="hasAnyOptionFlag(t) ? 'Preset value (active)' : 'Preset value'"
                  @click="togglePresetPanel(presetKeyFor(t, tIdx))"
                />
              </div>
            </div>
            <div v-if="expandedPresetKeys.has(presetKeyFor(t, tIdx))" class="tagconfig-preset-panel">
              <label class="preset-panel-label">Preset value <small>use the lock/hide icons next to each option to prohibit overwrite or hide it from the Content Editor</small></label>
              <FieldValueEditor
                :tag="{ name: t.name, fieldHandler: t.field_handler }"
                :fields="t.default_value"
                mode="preset"
                :palette="designPalette"
                :option-flags="t.option_flags"
                @update:option-flags="(v) => { t.option_flags = v }"
              />
            </div>
          </template>
        </div>
      </div>
    </div>
    <template #footer>
      <div class="dialog-footer-actions" data-tour="contenttype-dialog-footer">
        <DialogFooter :show-update="!isNew" :disabled="loadingContentType" @cancel="closeDialog" @update="saveContentType(true)" @confirm="saveContentType()" />
      </div>
    </template>
  </Dialog>
</template>

<style scoped>
.hint {
  color: var(--p-text-muted-color, #888);
  font-size: 0.75rem;
}

/* PrimeVue's own .p-dialog-footer flex styling applies to this slot's
   direct children — wrapping the buttons in a div (so the tour has one
   element to highlight/advanceOnClick regardless of which button is
   clicked) needs the same layout repeated on the wrapper. */
.dialog-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.tpl-loading {
  background: var(--p-content-background, #f5f5f5);
  border: 1px dashed var(--p-content-border-color, #ccc);
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  color: var(--p-text-color, #333);
  font-style: italic;
  margin-bottom: 0.5rem;
}

.tpl-loading-error {
  color: var(--error-color, #c62828);
  margin-top: 0.25rem;
  font-size: 0.85rem;
}

/* Tagconfigs table styling */
.tagconfigs-table {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--p-content-border-color, #ddd);
  border-radius: 4px;
  overflow: hidden;
}

.tagconfig-header {
  display: grid;
  grid-template-columns: 28px 160px 1fr 1fr 40px;
  gap: 0.5rem;
  padding: 0.5rem;
  background: var(--p-surface-100, #f5f5f5);
  font-weight: 600;
  font-size: 0.875rem;
  border-bottom: 2px solid var(--p-content-border-color, #ddd);
}

.tagconfig-row {
  display: grid;
  grid-template-columns: 28px 160px 1fr 1fr 40px;
  gap: 0.5rem;
  padding: 0.5rem;
  border-bottom: 1px solid var(--p-content-border-color, #eee);
  align-items: center;
  transition: background 0.2s;
}

.tagconfig-row:hover {
  background: var(--p-content-hover-background, #f9f9f9);
}

.tagconfig-row:last-child {
  border-bottom: none;
}

.tagconfig-col-type,
.tagconfig-col-container,
.tagconfig-col-title {
  display: flex;
  align-items: center;
}

.tagconfig-col-drag {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  color: var(--p-text-muted-color, #999);
}

.tagconfig-col-preset {
  display: flex;
  align-items: center;
}

.container-label {
  font-size: 0.85rem;
  color: var(--p-text-color, #333);
}

.field-help-icon {
  font-size: 0.85rem;
  margin-left: 0.35rem;
  color: var(--p-text-muted-color, #9ca3af);
  cursor: pointer;
}

.field-help-text {
  max-width: 300px;
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
}

.tagconfig-row[draggable='true'] {
  cursor: default;
}

.tagconfig-preset-panel {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  padding: 0.75rem 0.75rem 0.75rem 2.5rem;
  background: var(--p-content-background, #fafafa);
  border-bottom: 1px solid var(--p-content-border-color, #eee);
}

.preset-panel-label {
  font-weight: 600;
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #6b7280);
}

.preset-panel-label small {
  font-weight: 400;
  color: var(--p-text-muted-color, #888);
  margin-left: 0.3rem;
}

.fields-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.fields-section > label {
  font-weight: 600;
  font-size: 0.875rem;
  color: var(--p-text-muted-color, #6b7280);
}

.fields-section > label small {
  font-weight: 400;
  color: var(--p-text-muted-color, #888);
  margin-left: 0.3rem;
}

/* Dark mode: --p-surface-100 is a fixed ramp point, kept as the light-mode
   header shade above — see docs/developer/styleguide.md. */
.dark-mode .tagconfig-header {
  background: var(--p-surface-800, #1e293b);
}
</style>
