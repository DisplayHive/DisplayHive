<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import Button from 'primevue/button'
import FieldValueEditor from '../fields/FieldValueEditor.vue'
import { useAck } from '../../composables/useAck'
import { useRightsStore } from '../../stores/rights'
import { useSocket } from '../../composables/useSocket'
import type { TagConfig } from '../../composables/contentEdit/useContentEditor'
import type { ContainerTextStyle, PreviewContainer } from '../../utils/design/designPreview'
import { registerRowEdit } from '../../composables/contentEdit/useRowEditSession'
import PreviewEditLayer from '../contentEdit/PreviewEditLayer.vue'

// Editing in the preview of a row of the content list: the same hot spots as on the Content edit
// page (PreviewEditLayer.vue), on content that is already saved. Changes are kept in the preview
// until *Save* is pressed (or dropped with *Discard*); only those fields are written
// (`update_content_fields`) — the title, times and assignments are not touched. Needs content.edit;
// without it there is nothing to click.
const props = defineProps<{
  /** The list row: its field values are keys of the row, what each field is is in `_field_metadata`. */
  row: Record<string, unknown> & { id: number }
  containers: Record<string, PreviewContainer>
  textStyles?: Record<string, ContainerTextStyle>
  /** The aspect ratio the row's preview shows. */
  ratio?: string
  /** CSS selector of the box in the row where the editor of a picked field and the Save / Discard buttons go. */
  panel: string
}>()

const emit = defineEmits<{ draft: [containers: Record<string, PreviewContainer> | null] }>()

interface FieldMeta { label?: string; type?: string; contentcontainer_id?: number | null; option_flags?: TagConfig['optionFlags'] }

const rights = useRightsStore()
const { request } = useAck()
const { on, off, emit: socketEmit } = useSocket()
const editable = computed(() => rights.can('content.edit'))

const tags = computed<TagConfig[]>(() =>
  Object.entries((props.row._field_metadata ?? {}) as Record<string, FieldMeta>).map(([name, meta]) => ({
    name,
    title: meta.label || name,
    fieldHandler: meta.type ?? '',
    containerId: meta.contentcontainer_id ?? null,
    optionFlags: meta.option_flags ?? {},
  })),
)

const isFieldKey = (key: string) => tags.value.some((t) => key === t.name || key.startsWith(`${t.name}_`))
const valuesOf = (row: Record<string, unknown>): Record<string, unknown> => {
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(row)) if (isFieldKey(key)) out[key] = value
  return out
}

// `fields` is what the editors change; `synced` is what the server has.
const fields = reactive<Record<string, unknown>>({})
let synced: Record<string, unknown> = {}
const load = () => {
  const values = valuesOf(props.row)
  for (const key of Object.keys(fields)) delete fields[key]
  Object.assign(fields, JSON.parse(JSON.stringify(values)))
  synced = JSON.parse(JSON.stringify(values))
}
load()

const changes = () => {
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(fields)) {
    if (JSON.stringify(value) !== JSON.stringify(synced[key])) out[key] = value
  }
  return out
}

// The field whose editor is open in the row's panel (complex fields: not a popover, the panel is part of the row).
const activeTag = ref<TagConfig | null>(null)
const dirty = ref(false)
const saving = ref(false)

// The preview shows the change as it is made, like the edit page's: the server renders the row's
// content type with the changed values (nothing is stored) and the answer replaces the row's
// containers in the preview until the change is saved or discarded.
const requestId = `row-${props.row.id}`
let previewTimer: ReturnType<typeof setTimeout> | null = null
const requestDraft = () => {
  previewTimer = null
  if (!dirty.value) return
  socketEmit('displayhive:admin:cts:preview_content_element', {
    contenttype_id: props.row.contenttype_id,
    aspect_ratio: props.ratio,
    request_id: requestId,
    ...fields,
  })
}
const onDraft = (data: { request_id?: string; containers?: Record<string, PreviewContainer> }) => {
  if (data?.request_id === requestId && dirty.value && data.containers) emit('draft', data.containers)
}
onMounted(() => on('displayhive:admin:stc:content_element_preview', onDraft))
onBeforeUnmount(() => {
  off('displayhive:admin:stc:content_element_preview', onDraft)
  if (previewTimer) clearTimeout(previewTimer)
  emit('draft', null)
})

watch(fields, () => {
  dirty.value = Object.keys(changes()).length > 0
  if (previewTimer) clearTimeout(previewTimer)
  if (dirty.value) previewTimer = setTimeout(requestDraft, 300)
  else emit('draft', null)
}, { deep: true })
watch(() => props.ratio, requestDraft)

const save = async (): Promise<boolean> => {
  const changed = changes()
  if (!Object.keys(changed).length) return true
  saving.value = true
  const ack = await request('displayhive:admin:cts:update_content_fields', { content_element_id: props.row.id, fields: changed },
    { error: 'Could not save the change' })
  saving.value = false
  if (ack) {
    synced = { ...synced, ...JSON.parse(JSON.stringify(changed)) }
    dirty.value = false
  }
  return !!ack
}

// Saved and discarded together with the row's delivery settings, by the row's one Save / Discard.
const unregister = registerRowEdit(props.row.id, { dirty, saving, save, discard: () => discard() })
onBeforeUnmount(unregister)

const discard = () => {
  load()
  activeTag.value = null
  dirty.value = false
  emit('draft', null)
}

// The server pushed new values (somebody else edited, or our own save came back): take them unless changes are waiting.
watch(() => JSON.stringify(valuesOf(props.row)), () => {
  if (dirty.value) return
  load()
  emit('draft', null)          // the saved content is what the preview shows again
})
</script>

<template>
  <PreviewEditLayer
    :containers="containers"
    :tags="tags"
    :fields="fields"
    :editable="editable"
    :text-styles="textStyles"
    docked
    :active-name="activeTag?.name ?? null"
    @pick="(tag) => (activeTag = activeTag?.name === tag.name ? null : tag)"
  />
  <Teleport v-if="editable" :to="panel" defer>
    <div v-if="activeTag" class="row-edit-panel" data-testid="row-edit-panel">
      <div v-if="activeTag" class="row-edit-panel-field">
        <div class="row-edit-panel-head">
          <strong>{{ activeTag.title || activeTag.name }}</strong>
          <Button icon="pi pi-times" size="small" text rounded aria-label="Close the editor" @click="activeTag = null" />
        </div>
        <FieldValueEditor :key="activeTag.name" :tag="activeTag" :fields="fields" mode="edit" :option-flags="activeTag.optionFlags" />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.row-edit-panel {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-top: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--p-content-border-color, #ddd);
  border-radius: 6px;
  background: var(--p-content-background, transparent);
}

.row-edit-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
</style>
