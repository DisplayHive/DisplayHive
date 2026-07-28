<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useRightsStore } from '../stores/rights'
import type { Layout, ContentContainer } from '../types/models'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Dialog from 'primevue/dialog'
import Card from 'primevue/card'
import Dropdown from 'primevue/dropdown'
import Tag from 'primevue/tag'

interface TagConfig {
  id?: number | null
  name: string
  title: string
  field_handler: string
  contentcontainer_id: number | null
}

interface ContentType {
  id: number
  name: string
  description: string
  layout_id: number | null
  layout_name?: string
  field_count?: number
}

const toast = useToast()
const confirm = useConfirm()
const { on, off, emit, emitWithAck } = useSocket()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('contenttypes.create'))
const canEdit = computed(() => rightsStore.can('contenttypes.edit'))
const canDelete = computed(() => rightsStore.can('contenttypes.delete'))

const contentTypes = ref<ContentType[]>([])
const layouts = ref<Layout[]>([])
const containers = ref<ContentContainer[]>([])
const loading = ref(true)
const filterText = ref('')

const layoutOptions = computed(() => layouts.value.map(l => ({ label: l.name, value: l.id })))

// Containers available to the currently-selected Layout in the edit form.
const containerOptionsForLayout = computed(() => {
  const layout = layouts.value.find(l => l.id === editForm.value.layout_id)
  const ids = new Set(layout?.container_ids || [])
  return containers.value
    .filter(c => ids.has(c.id))
    .map(c => ({ label: c.title || c.name, value: c.id }))
})

// Field handler options (matches legacy UI and DB schema)
const fieldHandlerOptions = [
  { label: 'Text (klein)', value: 'textklein' },
  { label: 'Text (groß)', value: 'textbig' },
  { label: 'WYSIWYG', value: 'wysiwyg' },
  { label: 'Link/URL', value: 'link' },
  { label: 'Zahl', value: 'numbers' },
  { label: 'Image', value: 'image' },
  { label: 'Pfeil (Arrow)', value: 'arrows' },
  { label: 'pretalx', value: 'pretalx_table' },
  { label: 'Table', value: 'table' },
  { label: 'Date / Time Format', value: 'datetime_format' },
]

// Copy dialog
const showCopyDialog = ref(false)
const copySourceId = ref<number | null>(null)
const copyNewName = ref('')
const pendingCopyName = ref('')

const openCopyDialog = (ct: { id: number; name: string }) => {
  copySourceId.value = ct.id
  copyNewName.value = `Copy of ${ct.name}`
  showCopyDialog.value = true
}

const executeCopyContentType = () => {
  if (!copySourceId.value || !copyNewName.value.trim()) return
  pendingCopyName.value = copyNewName.value.trim()
  emit('displayhive:admin:cts:get_contenttype', { id: copySourceId.value })
  showCopyDialog.value = false
}

// Edit dialog
const showEditDialog = ref(false)
const isNew = ref(false)
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

const addField = () => {
  editForm.value.tagconfigs.push({
    id: null, name: '', title: '', field_handler: 'textklein', contentcontainer_id: null,
  })
}

// Drag and drop state for reordering the fields list
const dragIndex = ref<number | null>(null)
const onTagDragStart = (idx: number) => { dragIndex.value = idx }
const onTagDragOver = (e: DragEvent) => e.preventDefault()
const onTagDrop = (idx: number) => {
  const from = dragIndex.value
  if (from === null || from === idx) { dragIndex.value = null; return }
  const tagconfigs = editForm.value.tagconfigs
  const item = tagconfigs.splice(from, 1)[0]
  if (item) tagconfigs.splice(idx, 0, item)
  dragIndex.value = null
}

const removeTagConfig = (idx: number) => {
  editForm.value.tagconfigs.splice(idx, 1)
}

const prepareTagConfigsPayload = () => {
  return editForm.value.tagconfigs.map((t, i) => ({
    id: t.id, name: t.name, title: t.title, field_handler: t.field_handler,
    contentcontainer_id: t.contentcontainer_id, order: i,
  }))
}

const filteredContentTypes = computed(() => {
  if (!filterText.value) return contentTypes.value
  const search = filterText.value.toLowerCase()
  return contentTypes.value.filter(
    (ct) =>
      ct.name?.toLowerCase().includes(search) ||
      ct.description?.toLowerCase().includes(search)
  )
})

const handleContentTypesList = (data: any) => {
  contentTypes.value = data?.data || data?.contenttypes || []
  loading.value = false
}

const handleLayoutsList = (data: any) => {
  layouts.value = data?.data || []
}

const handleContainersList = (data: any) => {
  containers.value = data?.data || []
}

const handleContentTypeDetail = async (data: any) => {
  const ct = data?.contenttype || data?.data || null
  if (!ct) return

  // Copy operation
  if (pendingCopyName.value) {
    const name = pendingCopyName.value
    pendingCopyName.value = ''
    const tagconfigs = (ct.tagconfigs || []).map((t: any) => ({
      name: t.field_name, title: t.field_label, field_handler: t.field_handler,
      contentcontainer_id: t.contentcontainer_id, order: t.order,
    }))
    const ack = await emitWithAck<{ ok: boolean; error?: string }>('displayhive:admin:cts:create_contenttype', {
      name,
      description: ct.description || '',
      layout_id: ct.layout_id,
      tagconfigs,
    })
    if (ack?.ok) {
      toast.add({ severity: 'success', summary: 'Copied', detail: `"${name}" created`, life: 3000 })
      refreshData()
    } else {
      toast.add({ severity: 'error', summary: 'Copy failed', detail: ack?.error || 'Unknown error', life: 4000 })
    }
    return
  }

  // If edit dialog is open for this id, populate fields
  if (showEditDialog.value && editForm.value.id === ct.id) {
    editForm.value.layout_id = ct.layout_id
    editForm.value.tagconfigs = (ct.tagconfigs || [])
      .slice()
      .sort((a: any, b: any) => (a.order ?? 0) - (b.order ?? 0))
      .map((t: any) => ({
        id: t.id, name: t.field_name, title: t.field_label || t.field_name,
        field_handler: t.field_handler || 'textklein', contentcontainer_id: t.contentcontainer_id ?? null,
      }))

    loadingContentType.value = false
    loadingContentTypeError.value = ''
    if (contentTypeLoadTimer) {
      clearTimeout(contentTypeLoadTimer)
      contentTypeLoadTimer = null
    }
  }
}

onMounted(() => {
  on('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
  on('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
  on('displayhive:admin:stc:upd_layouts', handleLayoutsList)
  on('displayhive:admin:stc:upd_containers', handleContainersList)

  emit('displayhive:admin:cts:get_contenttypes')
  emit('displayhive:admin:cts:get_layouts')
  emit('displayhive:admin:cts:get_containers')
})

onUnmounted(() => {
  off('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
  off('displayhive:admin:stc:upd_layouts', handleLayoutsList)
  off('displayhive:admin:stc:upd_containers', handleContainersList)
})

const refreshData = () => {
  loading.value = true
  emit('displayhive:admin:cts:get_contenttypes')
}

const openNewDialog = () => {
  isNew.value = true
  editForm.value = { id: null, name: '', description: '', layout_id: null, tagconfigs: [] }
  showEditDialog.value = true
}

const openEditDialog = (ct: ContentType) => {
  isNew.value = false
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
  } catch (e) {}
  showEditDialog.value = true
}

const closeDialog = () => {
  showEditDialog.value = false
  loadingContentType.value = false
  loadingContentTypeError.value = ''
  if (contentTypeLoadTimer) {
    clearTimeout(contentTypeLoadTimer)
    contentTypeLoadTimer = null
  }
}

const saveContentType = async (keepOpen = false) => {
  if (!editForm.value.layout_id) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'A Layout is required', life: 3000 })
    return
  }

  const event = isNew.value
    ? 'displayhive:admin:cts:create_contenttype'
    : 'displayhive:admin:cts:update_contenttype'

  try {
    const ack = await emitWithAck<{ ok: boolean; error?: string }>(event, {
      id: editForm.value.id,
      name: editForm.value.name,
      description: editForm.value.description,
      layout_id: editForm.value.layout_id,
      tagconfigs: prepareTagConfigsPayload(),
    })

    if (ack?.ok) {
      toast.add({
        severity: 'success',
        summary: 'Success',
        detail: isNew.value ? 'Content type created' : 'Content type updated',
        life: 3000,
      })
      if (!keepOpen) showEditDialog.value = false
      refreshData()
    } else {
      toast.add({
        severity: 'error',
        summary: 'Save failed',
        detail: ack?.error || 'The server could not save the content type.',
        life: 5000,
      })
    }
  } catch {
    toast.add({
      severity: 'error',
      summary: 'Save failed',
      detail: 'Could not reach the server. Please try again.',
      life: 5000,
    })
  }
}

const deleteContentType = (ct: ContentType) => {
  confirm.require({
    message: `Are you sure you want to delete "${ct.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      emit('displayhive:admin:cts:delete_contenttype', { id: ct.id })
      toast.add({ severity: 'success', summary: 'Success', detail: 'Content type deleted', life: 3000 })
      refreshData()
    },
  })
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('contenttypes.page')" class="contenttypes-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Content Types page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="contenttypes-view">
    <Card>
      <template #title>
        <div class="card-header">
          <span>Content Types</span>
          <div class="header-actions">
            <Button v-if="canCreate" icon="pi pi-plus" label="New Content Type" @click="openNewDialog" size="small" />
            <Button icon="pi pi-refresh" @click="refreshData" size="small" outlined />
          </div>
        </div>
      </template>
      <template #content>
        <div class="filter-bar">
          <InputText v-model="filterText" placeholder="Filter content types..." class="filter-input" />
        </div>

        <DataTable
          :value="filteredContentTypes"
          :loading="loading"
          sortField="name"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="filteredContentTypes.length > 10"
          :rows="10"
          responsiveLayout="scroll"
        >
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="name" header="Name" sortable />
          <Column field="description" header="Description">
            <template #body="{ data }">
              {{ data.description ? data.description.substring(0, 50) + (data.description.length > 50 ? '...' : '') : '-' }}
            </template>
          </Column>
          <Column header="Layout" style="width: 160px">
            <template #body="{ data }">
              <Tag v-if="data.layout_name" :value="data.layout_name" />
              <span v-else class="hint">none</span>
            </template>
          </Column>
          <Column header="Fields" style="width: 100px">
            <template #body="{ data }">{{ data.field_count || 0 }}</template>
          </Column>
          <Column header="Actions" style="width: 150px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button v-if="canEdit" icon="pi pi-pencil" @click="openEditDialog(data)" size="small" outlined title="Edit" />
                <Button v-if="canCreate" icon="pi pi-copy" @click="openCopyDialog(data)" size="small" outlined title="Copy" />
                <Button v-if="canDelete" icon="pi pi-trash" @click="deleteContentType(data)" size="small" severity="danger" outlined title="Delete" />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Copy Dialog -->
    <Dialog v-model:visible="showCopyDialog" header="Copy Content Type" modal :style="{ width: '400px' }">
      <div class="field">
        <label for="copy-ct-name">New Name</label>
        <InputText id="copy-ct-name" v-model="copyNewName" class="w-full" autofocus @keyup.enter="executeCopyContentType" />
      </div>
      <template #footer>
        <Button label="Cancel" @click="showCopyDialog = false" text />
        <Button label="Copy" icon="pi pi-copy" @click="executeCopyContentType" :disabled="!copyNewName.trim()" />
      </template>
    </Dialog>

    <!-- Edit Dialog -->
    <Dialog
      v-model:visible="showEditDialog"
      :header="isNew ? 'New Content Type' : 'Edit Content Type'"
      modal
      :style="{ width: '90vw', maxWidth: '1200px' }"
    >
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
        <div class="field">
          <label for="ct-layout">Layout</label>
          <Dropdown
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

        <!-- Fields (TagConfig) — each is one container of the selected Layout,
             rendered directly from its field_handler's transformed value. -->
        <div class="fields-section">
          <div class="fields-header">
            <label>Fields <small>one per container this type populates</small></label>
            <Button
              label="Add Field"
              icon="pi pi-plus"
              size="small"
              :disabled="!editForm.layout_id"
              @click="addField"
            />
          </div>
          <p v-if="!editForm.layout_id" class="hint">Select a Layout above before adding fields.</p>
          <div v-else-if="!editForm.tagconfigs.length" class="p-text-muted">No fields yet — click "Add Field" to bind a container to a field.</div>
          <div v-else class="tagconfigs-table">
            <div class="tagconfig-header">
              <div class="tagconfig-col-drag"></div>
              <div class="tagconfig-col-name">Name</div>
              <div class="tagconfig-col-title">Label</div>
              <div class="tagconfig-col-type">Field Handler</div>
              <div class="tagconfig-col-container">Container</div>
              <div></div>
            </div>
            <div
              v-for="(t, tIdx) in editForm.tagconfigs"
              :key="t.id ?? `new-${tIdx}`"
              class="tagconfig-row"
              draggable="true"
              @dragstart="onTagDragStart(tIdx)"
              @dragover.prevent="onTagDragOver"
              @drop="onTagDrop(tIdx)"
            >
              <div class="tagconfig-col-drag">
                <i class="pi pi-bars" style="cursor: grab;"></i>
              </div>
              <div class="tagconfig-col-name">
                <InputText v-model="t.name" class="w-full" size="small" placeholder="field_name" />
              </div>
              <div class="tagconfig-col-title">
                <InputText v-model="t.title" class="w-full" size="small" />
              </div>
              <div class="tagconfig-col-type">
                <Dropdown
                  v-model="t.field_handler"
                  :options="fieldHandlerOptions"
                  optionLabel="label"
                  optionValue="value"
                  class="w-full"
                  size="small"
                />
              </div>
              <div class="tagconfig-col-container">
                <Dropdown
                  v-model="t.contentcontainer_id"
                  :options="containerOptionsForLayout"
                  optionLabel="label"
                  optionValue="value"
                  placeholder="Container"
                  class="w-full"
                  size="small"
                />
              </div>
              <div>
                <Button icon="pi pi-trash" severity="danger" text size="small" @click="removeTagConfig(tIdx)" title="Remove field" />
              </div>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="closeDialog" text />
        <Button v-if="!isNew" label="Update" severity="secondary" outlined @click="saveContentType(true)" :disabled="loadingContentType" />
        <Button label="Save" @click="saveContentType()" :disabled="loadingContentType" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.contenttypes-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.hint {
  color: #888;
  font-size: 0.75rem;
}

.tpl-loading {
  background: var(--surface-b);
  border: 1px dashed var(--surface-d);
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  color: var(--text-color, #333);
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
  border: 1px solid #ddd;
  border-radius: 4px;
  overflow: hidden;
}

.tagconfig-header {
  display: grid;
  grid-template-columns: 40px 160px 1fr 180px 200px 40px;
  gap: 0.5rem;
  padding: 0.5rem;
  background: #f5f5f5;
  font-weight: 600;
  font-size: 0.875rem;
  border-bottom: 2px solid #ddd;
}

.tagconfig-row {
  display: grid;
  grid-template-columns: 40px 160px 1fr 180px 200px 40px;
  gap: 0.5rem;
  padding: 0.5rem;
  border-bottom: 1px solid #eee;
  align-items: center;
  transition: background 0.2s;
  cursor: move;
}

.tagconfig-row:hover {
  background: #f9f9f9;
}

.tagconfig-row:last-child {
  border-bottom: none;
}

.tagconfig-col-drag {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
}

.tagconfig-col-name {
  display: flex;
  align-items: center;
}

.tagconfig-col-title,
.tagconfig-col-type,
.tagconfig-col-container {
  display: flex;
  align-items: center;
}

.fields-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 0.5rem;
}

.fields-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.fields-header label {
  font-weight: 600;
  font-size: 0.875rem;
}

.fields-header label small {
  font-weight: 400;
  color: #888;
  margin-left: 0.3rem;
}
</style>
