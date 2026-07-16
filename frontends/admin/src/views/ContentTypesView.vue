<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useMagicTagsStore } from '../stores/magicTags'
import { useRightsStore } from '../stores/rights'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Dialog from 'primevue/dialog'
import Card from 'primevue/card'
import MultiSelect from 'primevue/multiselect'
import Dropdown from 'primevue/dropdown'

import { Codemirror } from 'vue-codemirror'
import { html as cmHtml } from '@codemirror/lang-html'
import { css as cmCss } from '@codemirror/lang-css'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from '@codemirror/view'

interface ContentType {
  id: number
  name: string
  description: string
  html: string
  css: string
  container_ids: number[]
}

interface Container {
  id?: number
  name: string
  title?: string
  template_name?: string
  order?: number
}

const toast = useToast()
const confirm = useConfirm()
const { on, off, emit, emitWithAck } = useSocket()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('contenttypes.create'))
const canEdit = computed(() => rightsStore.can('contenttypes.edit'))
const canDelete = computed(() => rightsStore.can('contenttypes.delete'))
const canMagicTagsPage = computed(() => rightsStore.can('magictags.page'))

const contentTypes = ref<ContentType[]>([])
const containers = ref<Container[]>([])
const loading = ref(true)
const filterText = ref('')

// Loading state for when we request full contenttype detail (html)
const loadingContentType = ref(false)
const loadingContentTypeError = ref('')
let contentTypeLoadTimer: number | null = null

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
  html: '',
  css: '',
  container_ids: [] as number[],
})

const cmHtmlExtensions = [cmHtml(), oneDark, EditorView.lineWrapping]
const cmCssExtensions = [cmCss(), oneDark, EditorView.lineWrapping]

const magicTagsStore = useMagicTagsStore()

const htmlEditorRef = ref<{ view: EditorView } | null>(null)
const cssEditorRef = ref<{ view: EditorView } | null>(null)
const lastFocusedEditor = ref<'html' | 'css'>('html')

const insertMagicTag = (tagName: string) => {
  const text = `{{ var_${tagName} }}`
  const editorRef = lastFocusedEditor.value === 'css' ? cssEditorRef.value : htmlEditorRef.value
  if (!editorRef?.view) return
  const view = editorRef.view
  const cursor = view.state.selection.main.head
  view.dispatch({ changes: { from: cursor, insert: text }, selection: { anchor: cursor + text.length } })
  view.focus()
}

const onMagicTagDragStart = (e: DragEvent, tagName: string) => {
  e.dataTransfer?.setData('text/plain', `{{ var_${tagName} }}`)
}

// TagConfig extraction + editor for content type HTML
const tagconfigs = ref<Array<{ id?: number; name: string; title: string; field_handler: string }>>([])

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

const extractTagConfigs = () => {
  const html = editForm.value.html || ''
  const re = /{{\s*([^}]+?)\s*}}/g
  const existing = new Map(tagconfigs.value.map(t => [t.name, t]))
  const found = new Map<string, { id?: number; name: string; title: string; field_handler: string }>()
  let m: RegExpExecArray | null
  while ((m = re.exec(html))) {
    let raw = String(m[1] ?? '').trim()
    if (!raw) continue
    // strip filters or attribute access (take the first token before | or .)
    const beforeFilter = (raw.split('|')[0] ?? '').toString()
    raw = ((beforeFilter.split('.')[0] ?? '') as string).trim()
    if (!raw) continue
    if (!found.has(raw)) {
      const prev = existing.get(raw)
      found.set(raw, prev ? { ...prev } : { name: raw, title: raw, field_handler: 'textklein' })
    }
  }
  tagconfigs.value = Array.from(found.values())
}

const updateTagConfigTitle = (idx: number, title: string) => {
  if (tagconfigs.value[idx]) tagconfigs.value[idx].title = title
}

// Drag and drop state for tagconfigs
const dragIndex = ref<number | null>(null)
const onTagDragStart = (e: DragEvent, idx: number) => {
  dragIndex.value = idx
  e.dataTransfer?.setData('text/plain', String(idx))
}

const onTagDragOver = (e: DragEvent) => {
  e.preventDefault()
}

const onTagDrop = (e: DragEvent, idx: number) => {
  e.preventDefault()
  const from = dragIndex.value
  if (from === null || from === idx) return
  const item = tagconfigs.value.splice(from, 1)[0]
  if (!item) {
    dragIndex.value = null
    return
  }
  tagconfigs.value.splice(idx, 0, item)
  dragIndex.value = null
}

const prepareTagConfigs = () => {
  return tagconfigs.value.map((t, i) => ({ id: t.id, name: t.name, title: t.title, field_handler: t.field_handler, order: i }))
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

const containerOptions = computed(() =>
  // Use the container id when available, otherwise fall back to the container name.
  // This preserves previous behaviour where option values could be either numeric ids
  // or string names so already-selected values still render correctly when the
  // dropdown is not opened.
  containers.value.map((c) => {
    const tmpl = c.template_name && String(c.template_name).trim()
    const title = (c.title && String(c.title).trim()) || c.name || ''
    const label = tmpl ? `${tmpl} - ${title}` : title
    return { label, value: (c.id ?? c.name) as any }
  })
)

const handleContentTypesList = (data: any) => {
  // backend sometimes sends { data: [...] } (upd_contenttypes) or { contenttypes: [...] }
  if (data) {
    if (Array.isArray(data.contenttypes)) {
      contentTypes.value = data.contenttypes
    } else if (Array.isArray(data.data)) {
      contentTypes.value = data.data
    } else if (Array.isArray(data.contentTypes)) {
      contentTypes.value = data.contentTypes
    } else {
      contentTypes.value = []
    }
  } else {
    contentTypes.value = []
  }
  loading.value = false
}

const handleContentTypeDetail = async (data: any) => {
  const ct = data?.contenttype || data?.data || null
  if (!ct) return

  // Copy operation
  if (pendingCopyName.value) {
    const name = pendingCopyName.value
    pendingCopyName.value = ''
    const tagconfigs = (ct.tagconfigs || []).map((t: any) => ({
      name: t.field_name,
      title: t.field_label,
      field_handler: t.field_handler,
      order: t.order,
    }))
    const ack = await emitWithAck<{ ok: boolean; error?: string }>('displayhive:admin:cts:create_contenttype', {
      name,
      description: ct.description || '',
      html: ct.html || '',
      css: ct.css || '',
      container_ids: ct.container_ids || [],
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

  // If edit dialog is open for this id, populate html and container ids
  if (showEditDialog.value && editForm.value.id === ct.id) {
    editForm.value.html = ct.html || ''
    editForm.value.css = ct.css || ''
    // Restore previous behaviour: accept whatever the server sent for container ids
    // (they may be numeric ids or string names). Do not aggressively coerce or
    // filter here so selected values keep their labels when the dropdown is closed.
    editForm.value.container_ids = ct.container_ids || ct.containerIds || []

    // If the detail payload also includes `containers`, merge them into the
    // global `containers.value` list so the UI has labels available immediately.
    const incomingContainers = Array.isArray(ct.containers) ? ct.containers : []
    if (incomingContainers.length) {
      incomingContainers.forEach((ic: any) => {
        const key = ic.id ?? ic.name
        // Normalise container object
        const normalized: Container = {
          id: ic.id ?? undefined,
          name: ic.name ?? String(ic.id ?? ''),
          title: ic.title ?? ic.name ?? String(ic.id ?? ''),
          template_name: ic.template_name ?? undefined,
          order: ic.order ?? undefined,
        }

        const idx = containers.value.findIndex((c) => (c.id ?? c.name) === key)
        if (idx >= 0) {
          // update existing entry
          containers.value[idx] = { ...containers.value[idx], ...normalized }
        } else {
          // add new entry
          containers.value.push(normalized)
        }
      })
      // keep containers sorted by `order` if present
      containers.value.sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
    }

          // If the detail payload includes saved tagconfigs, use them to populate the
          // tagconfigs editor (this preserves server-saved titles and order).
          const incomingTagConfigs = Array.isArray(ct.tagconfigs) ? ct.tagconfigs : []
          if (incomingTagConfigs.length) {
            tagconfigs.value = incomingTagConfigs
              .slice()
              .sort((a: any, b: any) => (a.order ?? 0) - (b.order ?? 0))
              .map((t: any) => ({ id: t.id, name: t.field_name || String(t.id || ''), title: t.field_label || t.field_name || String(t.id || ''), field_handler: t.field_handler || 'textklein' }))
          } else {
            // fallback: extract tags from HTML
            extractTagConfigs()
          }

    // loaded successfully
    loadingContentType.value = false
    loadingContentTypeError.value = ''
    if (contentTypeLoadTimer) {
      clearTimeout(contentTypeLoadTimer)
      contentTypeLoadTimer = null
    }
  }
}

const handleContainersList = (data: { containers: Container[] }) => {
  containers.value = data.containers || []
  // Do not alter `editForm.container_ids` here — keep the selected list as the
  // server provided it so the MultiSelect shows the correct labels when closed.
}

onMounted(() => {
  // backend emits 'displayhive:admin:stc:upd_contenttypes' with payload { data: [...] }
  on('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
  on('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
  // Use all-containers picker endpoint so every template's containers appear with template_name
  on('displayhive:admin:stc:all_containers_for_picker', handleContainersList)

  // emit legacy event name the server registers ('get_contenttypes')
  emit('displayhive:admin:cts:get_contenttypes')
  // request all containers across all templates
  emit('displayhive:admin:cts:get_all_containers_for_picker')
  magicTagsStore.fetch()
})

onUnmounted(() => {
  off('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
  off('displayhive:admin:stc:all_containers_for_picker', handleContainersList)
})

const refreshData = () => {
  loading.value = true
  emit('displayhive:admin:cts:get_contenttypes')
}

const openNewDialog = () => {
  isNew.value = true
  editForm.value = {
    id: null,
    name: '',
    description: '',
    html: '',
    css: '',
    container_ids: [],
  }
  showEditDialog.value = true
}

const openEditDialog = (ct: ContentType) => {
  isNew.value = false
  editForm.value = {
    id: ct.id,
    name: ct.name,
    description: ct.description || '',
    html: ct.html,
    css: ct.css || '',
    container_ids: ct.container_ids || [],
  }
  // Request full contenttype detail (including html) from server
  try {
    loadingContentType.value = true
    loadingContentTypeError.value = ''
    emit('get_contenttype', { id: ct.id })
    emit('displayhive:admin:cts:get_contenttype', { id: ct.id })
    if (contentTypeLoadTimer) clearTimeout(contentTypeLoadTimer)
    contentTypeLoadTimer = window.setTimeout(() => {
      loadingContentType.value = false
      loadingContentTypeError.value = 'Timed out while fetching content type HTML.'
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
  const event = isNew.value
    ? 'displayhive:admin:cts:create_contenttype'
    : 'displayhive:admin:cts:update_contenttype'

  // include jinja tag configuration (name/title/order)
  const tagconfigs_payload = prepareTagConfigs()

  try {
    const ack = await emitWithAck<{ ok: boolean; error?: string }>(event, {
      id: editForm.value.id,
      name: editForm.value.name,
      description: editForm.value.description,
      html: editForm.value.html,
      css: editForm.value.css,
      container_ids: editForm.value.container_ids,
      tagconfigs: tagconfigs_payload,
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
          <!-- HTML column removed to declutter the list -->
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
      :style="{ width: '95vw', maxWidth: '1800px' }"
    >
      <div class="dialog-content">
        <div v-if="loadingContentType" class="tpl-loading">
          Loading content type HTML…
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
          <label for="ct-containers">Containers</label>
          <MultiSelect
            id="ct-containers"
            v-model="editForm.container_ids"
            :options="containerOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Select containers"
            class="w-full"
          />
        </div>
        <div class="code-editors-row">
          <div class="code-editor-field" @focusin="lastFocusedEditor = 'html'">
            <label>HTML Template</label>
            <Codemirror
              ref="htmlEditorRef"
              v-model="editForm.html"
              :extensions="cmHtmlExtensions"
              :style="{ height: '400px' }"
              :autofocus="false"
              :indent-with-tab="true"
              :tab-size="2"
            />
          </div>
          <div class="code-editor-field" @focusin="lastFocusedEditor = 'css'">
            <label>CSS</label>
            <Codemirror
              ref="cssEditorRef"
              v-model="editForm.css"
              :extensions="cmCssExtensions"
              :style="{ height: '400px' }"
              :autofocus="false"
              :indent-with-tab="true"
              :tab-size="2"
            />
          </div>
        </div>
        <div v-if="canMagicTagsPage && magicTagsStore.magicTags.length" class="var-tags-section">
          <label>Magic Tags <small>(click or drag into editor)</small></label>
          <div class="var-chips">
            <span
              v-for="v in magicTagsStore.magicTags"
              :key="v.id"
              class="var-chip"
              draggable="true"
              @dragstart="onMagicTagDragStart($event, v.name)"
              @click="insertMagicTag(v.name)"
              :title="v.description ? `${v.description}\n\nInsert {{ var_${v.name} }} into the active editor` : `Insert {{ var_${v.name} }} into the active editor`"
            >&#123;&#123; var_{{ v.name }} &#125;&#125;</span>
          </div>
        </div>
        <div class="field jinja-tags-field">
          <label>Jinja Tags</label>
            <div style="display:flex;gap:0.5rem;align-items:center;margin-bottom:0.5rem;">
            <Button label="Extract Tags" icon="pi pi-search" @click="extractTagConfigs" size="small" />
            <small class="p-m-0" style="align-self:center;color:var(--text-secondary);">Detects &#123;&#123; variable &#125;&#125; tokens from the HTML.</small>
          </div>

          <div v-if="!(tagconfigs && tagconfigs.length)" class="p-text-muted">No tags extracted yet.</div>
          <div v-else class="tagconfigs-table">
            <div class="tagconfig-header">
              <div class="tagconfig-col-drag"></div>
              <div class="tagconfig-col-name">Tag</div>
              <div class="tagconfig-col-title">Label</div>
              <div class="tagconfig-col-type">Field Handler</div>
            </div>
            <div 
              v-for="(t, idx) in tagconfigs" 
              :key="t.id ?? t.name" 
              class="tagconfig-row" 
              draggable="true" 
              @dragstart="onTagDragStart($event, idx)" 
              @dragover.prevent="onTagDragOver" 
              @drop="onTagDrop($event, idx)"
            >
              <div class="tagconfig-col-drag">
                <i class="pi pi-bars" style="cursor: grab;"></i>
              </div>
              <div class="tagconfig-col-name">
                <label style="font-size:0.875rem;font-weight:600;color:var(--text-color);">{{ t.name }}</label>
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

.html-preview {
  font-size: 0.75rem;
  background: #f5f5f5;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 300px;
}

.code-editors-row {
  display: flex;
  gap: 1rem;
}

.code-editor-field {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.code-editor-field label {
  font-weight: 600;
  font-size: 0.875rem;
}

.code-editor-field .vue-codemirror {
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  border-radius: 6px;
  overflow: hidden;
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
  grid-template-columns: 40px 180px 1fr 200px;
  gap: 0.5rem;
  padding: 0.5rem;
  background: #f5f5f5;
  font-weight: 600;
  font-size: 0.875rem;
  border-bottom: 2px solid #ddd;
}

.tagconfig-row {
  display: grid;
  grid-template-columns: 40px 180px 1fr 200px;
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
.tagconfig-col-type {
  display: flex;
  align-items: center;
}

.var-tags-section {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.25rem;
}

.var-tags-section label {
  font-weight: 600;
  font-size: 0.875rem;
}

.var-tags-section label small {
  font-weight: 400;
  color: #888;
  margin-left: 0.3rem;
}

.var-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.var-chip {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  background: #1e3a5f;
  color: #7dd3fc;
  border: 1px solid #2563ab;
  border-radius: 4px;
  font-family: monospace;
  font-size: 0.8rem;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s, color 0.15s;
}

.var-chip:hover {
  background: #2563ab;
  color: #e0f2fe;
}
</style>
