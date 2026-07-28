<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useMagicTagsStore } from '../stores/magicTags'
import { useRightsStore } from '../stores/rights'
import type { Design } from '../types/models'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Dialog from 'primevue/dialog'
import Card from 'primevue/card'
import Tag from 'primevue/tag'

import { Codemirror } from 'vue-codemirror'
import { html as cmHtml } from '@codemirror/lang-html'
import { css as cmCss } from '@codemirror/lang-css'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from '@codemirror/view'

const cmHtmlExtensions = [cmHtml(), oneDark, EditorView.lineWrapping]
const cmCssExtensions = [cmCss(), oneDark, EditorView.lineWrapping]

const htmlEditorRef = ref<{ view: EditorView } | null>(null)
const cssEditorRef = ref<{ view: EditorView } | null>(null)
const lastFocusedEditor = ref<'html' | 'css'>('html')

const onMagicTagDragStart = (e: DragEvent, tagName: string) => {
  e.dataTransfer?.setData('text/plain', `{{ var_${tagName} }}`)
}

const toast = useToast()
const confirm = useConfirm()
const { on, off, emit } = useSocket()
const magicTagsStore = useMagicTagsStore()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('designs.create'))
const canEdit = computed(() => rightsStore.can('designs.edit'))
const canDelete = computed(() => rightsStore.can('designs.delete'))
const canMagicTagsPage = computed(() => rightsStore.can('magictags.page'))

const designs = ref<Design[]>([])
const loading = ref(true)
const filterText = ref('')

// Copy dialog
const showCopyDialog = ref(false)
const copySourceId = ref<number | null>(null)
const copyNewName = ref('')
const pendingCopyName = ref('')

const openCopyDialog = (design: { id: number; name: string }) => {
  copySourceId.value = design.id
  copyNewName.value = `Copy of ${design.name}`
  showCopyDialog.value = true
}

const executeCopyDesign = () => {
  if (!copySourceId.value || !copyNewName.value.trim()) return
  pendingCopyName.value = copyNewName.value.trim()
  emit('displayhive:admin:cts:get_design', { id: copySourceId.value })
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
})

// Loading state for when we request full design detail (html/css)
const loadingDesign = ref(false)
const loadingDesignError = ref('')
let designLoadTimer: number | null = null

const filteredDesigns = computed(() => {
  if (!filterText.value) return designs.value
  const search = filterText.value.toLowerCase()
  return designs.value.filter(
    (d) =>
      d.name?.toLowerCase().includes(search) ||
      d.description?.toLowerCase().includes(search)
  )
})

const handleDesignsList = (data: any) => {
  const list = data?.data || data?.designs || []
  designs.value = list
  loading.value = false
}

const handleDesignDetail = (data: any) => {
  try {
    const design = data?.design || null
    if (!design) return

    // Copy operation
    if (pendingCopyName.value) {
      const name = pendingCopyName.value
      pendingCopyName.value = ''
      emit('displayhive:admin:cts:create_design', {
        name,
        description: design.description || '',
        html: design.html || '',
        css: design.css || '',
      })
      toast.add({ severity: 'success', summary: 'Copied', detail: `"${name}" created`, life: 3000 })
      refreshData()
      return
    }

    const id = Number(design.id)
    if (showEditDialog.value && editForm.value.id === id) {
      editForm.value.html = design.html || ''
      editForm.value.css = design.css || ''
      loadingDesign.value = false
      loadingDesignError.value = ''
      if (designLoadTimer) {
        clearTimeout(designLoadTimer)
        designLoadTimer = null
      }
    }
  } catch (e) {
    console.warn('[DesignsView] handleDesignDetail error', e)
  }
}

onMounted(() => {
  on('displayhive:admin:stc:upd_designs', handleDesignsList)
  on('displayhive:admin:stc:design_detail', handleDesignDetail)
  refreshData()
  magicTagsStore.fetch()
})

onUnmounted(() => {
  off('displayhive:admin:stc:upd_designs', handleDesignsList)
  off('displayhive:admin:stc:design_detail', handleDesignDetail)
})

const refreshData = () => {
  loading.value = true
  emit('displayhive:admin:cts:get_designs')
}

const openNewDialog = () => {
  isNew.value = true
  editForm.value = { id: null, name: '', description: '', html: '', css: '' }
  showEditDialog.value = true
}

const openEditDialog = (design: Design) => {
  isNew.value = false
  editForm.value = {
    id: design.id,
    name: design.name,
    description: design.description || '',
    html: design.html || '',
    css: design.css || '',
  }
  try {
    loadingDesign.value = true
    loadingDesignError.value = ''
    emit('displayhive:admin:cts:get_design', { id: design.id })
    if (designLoadTimer) clearTimeout(designLoadTimer)
    designLoadTimer = window.setTimeout(() => {
      loadingDesign.value = false
      loadingDesignError.value = 'Timed out while fetching design content.'
      designLoadTimer = null
    }, 8000)
  } catch (e) {}

  showEditDialog.value = true
}

const closeDialog = () => {
  showEditDialog.value = false
  loadingDesign.value = false
  loadingDesignError.value = ''
  if (designLoadTimer) {
    clearTimeout(designLoadTimer)
    designLoadTimer = null
  }
}

const saveDesign = async (keepOpen = false) => {
  const event = isNew.value
    ? 'displayhive:admin:cts:create_design'
    : 'displayhive:admin:cts:update_design'

  emit(event, {
    id: editForm.value.id,
    name: editForm.value.name,
    description: editForm.value.description,
    html: editForm.value.html,
    css: editForm.value.css,
  })

  toast.add({
    severity: 'success',
    summary: 'Success',
    detail: isNew.value ? 'Design created' : 'Design updated',
    life: 3000,
  })
  if (!keepOpen) showEditDialog.value = false
  refreshData()
}

const setDefault = (design: Design) => {
  emit('displayhive:admin:cts:set_default_design', { id: design.id })
  toast.add({ severity: 'success', summary: 'Success', detail: 'Active design updated', life: 3000 })
  refreshData()
}

const deleteDesign = (design: Design) => {
  confirm.require({
    message: `Are you sure you want to delete "${design.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      emit('displayhive:admin:cts:delete_design', { id: design.id })
      toast.add({ severity: 'success', summary: 'Success', detail: 'Design deleted', life: 3000 })
      refreshData()
    },
  })
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('designs.page')" class="designs-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Designs page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="designs-view">
    <Card>
      <template #title>
        <div class="card-header">
          <span>Designs</span>
          <div class="header-actions">
            <Button v-if="canCreate" icon="pi pi-plus" label="New Design" @click="openNewDialog" size="small" />
            <Button icon="pi pi-refresh" @click="refreshData" size="small" outlined />
          </div>
        </div>
      </template>
      <template #content>
        <div class="filter-bar">
          <InputText v-model="filterText" placeholder="Filter designs..." class="filter-input" />
        </div>

        <DataTable
          :value="filteredDesigns"
          :loading="loading"
          sortField="name"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="filteredDesigns.length > 10"
          :rows="10"
          responsiveLayout="scroll"
        >
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="name" header="Name" sortable>
            <template #body="{ data }">
              {{ data.name }}
              <Tag v-if="data.isDefault" severity="info" value="Active" class="ml-2" />
            </template>
          </Column>
          <Column field="description" header="Description">
            <template #body="{ data }">
              {{ data.description ? data.description.substring(0, 50) + (data.description.length > 50 ? '...' : '') : '-' }}
            </template>
          </Column>
          <Column header="Actions" style="width: 200px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button v-if="canEdit" icon="pi pi-pencil" @click="openEditDialog(data)" size="small" outlined title="Edit" />
                <Button
                  v-if="canEdit && !data.isDefault"
                  icon="pi pi-check"
                  @click="setDefault(data)"
                  size="small"
                  severity="success"
                  outlined
                  title="Make Active"
                />
                <Button v-if="canCreate" icon="pi pi-copy" @click="openCopyDialog(data)" size="small" outlined title="Copy" />
                <Button v-if="canDelete" icon="pi pi-trash" @click="deleteDesign(data)" size="small" severity="danger" outlined title="Delete" />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Copy Dialog -->
    <Dialog v-model:visible="showCopyDialog" header="Copy Design" modal :style="{ width: '400px' }">
      <div class="field">
        <label for="copy-design-name">New Name</label>
        <InputText id="copy-design-name" v-model="copyNewName" class="w-full" autofocus @keyup.enter="executeCopyDesign" />
      </div>
      <template #footer>
        <Button label="Cancel" @click="showCopyDialog = false" text />
        <Button label="Copy" icon="pi pi-copy" @click="executeCopyDesign" :disabled="!copyNewName.trim()" />
      </template>
    </Dialog>

    <!-- Edit Dialog -->
    <Dialog
      v-model:visible="showEditDialog"
      :header="isNew ? 'New Design' : 'Edit Design'"
      modal
      :style="{ width: '95vw', maxWidth: '1800px' }"
    >
      <div class="dialog-content">
        <div v-if="loadingDesign" class="tpl-loading">
          Loading design HTML/CSS…
          <div v-if="loadingDesignError" class="tpl-loading-error">{{ loadingDesignError }}</div>
        </div>
        <div class="field">
          <label for="design-name">Name</label>
          <InputText id="design-name" v-model="editForm.name" class="w-full" />
        </div>
        <div class="field">
          <label for="design-description">Description</label>
          <Textarea id="design-description" v-model="editForm.description" rows="2" class="w-full" />
        </div>
        <div class="code-editors-row">
          <div class="code-editor-field" @focusin="lastFocusedEditor = 'html'">
            <label>Background HTML</label>
            <Codemirror
              ref="htmlEditorRef"
              v-model="editForm.html"
              :extensions="cmHtmlExtensions"
              :style="{ height: '400px' }"
              :autofocus="false"
              :indent-with-tab="true"
              :tab-size="2"
            />
            <small class="hint">This renders once as the screen's static background — content containers are positioned on top of it via the Layouts page, not placed with tags here.</small>
          </div>
          <div class="code-editor-field" @focusin="lastFocusedEditor = 'css'">
            <label>CSS Styles</label>
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
          <label>Magic Tags</label>
          <div class="var-chips">
            <span
              v-for="v in magicTagsStore.magicTags"
              :key="v.id"
              class="var-chip"
              draggable="true"
              @dragstart="onMagicTagDragStart($event, v.name)"
              :title="v.description ? `${v.description}\n\nDrag {{ var_${v.name} }} into the editor` : `Drag {{ var_${v.name} }} into the editor`"
            >&#123;&#123; var_{{ v.name }} &#125;&#125;</span>
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="closeDialog" text />
        <Button v-if="!isNew" label="Update" severity="secondary" outlined @click="saveDesign(true)" :disabled="loadingDesign" />
        <Button label="Save" @click="saveDesign()" :disabled="loadingDesign" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.designs-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.hint {
  color: #888;
  font-size: 0.75rem;
}

.ml-2 {
  margin-left: 0.5rem;
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
