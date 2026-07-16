<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useTemplatesStore } from '../stores/templates'
import { useMagicTagsStore } from '../stores/magicTags'
import { useRightsStore } from '../stores/rights'
import type { Template, MagicTag } from '../types/models'

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
const templatesStore = useTemplatesStore()
const magicTagsStore = useMagicTagsStore()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('templates.create'))
const canEdit = computed(() => rightsStore.can('templates.edit'))
const canDelete = computed(() => rightsStore.can('templates.delete'))
const canMagicTagsPage = computed(() => rightsStore.can('magictags.page'))
const canMagicTagsCreate = computed(() => rightsStore.can('magictags.create'))
const canMagicTagsEdit = computed(() => rightsStore.can('magictags.edit'))
const canMagicTagsDelete = computed(() => rightsStore.can('magictags.delete'))

const filterText = ref('')

// Magic Tags state
// Copy dialog
const showCopyDialog = ref(false)
const copySourceId = ref<number | null>(null)
const copyNewName = ref('')
const pendingCopyName = ref('')

const openCopyDialog = (template: { id: number; name: string }) => {
  copySourceId.value = template.id
  copyNewName.value = `Copy of ${template.name}`
  showCopyDialog.value = true
}

const executeCopyTemplate = () => {
  if (!copySourceId.value || !copyNewName.value.trim()) return
  pendingCopyName.value = copyNewName.value.trim()
  emit('displayhive:admin:cts:get_template', { id: copySourceId.value })
  showCopyDialog.value = false
}

const showTagDialog = ref(false)
const isNewTag = ref(false)
const tagForm = ref<{ id: number | null; name: string; value: string; description: string }>({
  id: null,
  name: '',
  value: '',
  description: '',
})

const openNewTagDialog = () => {
  isNewTag.value = true
  tagForm.value = { id: null, name: '', value: '', description: '' }
  showTagDialog.value = true
}

const openEditTagDialog = (v: MagicTag) => {
  isNewTag.value = false
  tagForm.value = { id: v.id, name: v.name, value: v.value, description: v.description || '' }
  showTagDialog.value = true
}

const saveTag = (keepOpen = false) => {
  const event = isNewTag.value
    ? 'displayhive:admin:cts:create_magic_tag'
    : 'displayhive:admin:cts:update_magic_tag'
  emit(event, { id: tagForm.value.id, name: tagForm.value.name, value: tagForm.value.value, description: tagForm.value.description })
  toast.add({ severity: 'success', summary: 'Success', detail: isNewTag.value ? 'Magic tag created' : 'Magic tag updated', life: 3000 })
  if (!keepOpen) showTagDialog.value = false
}

const deleteTag = (v: MagicTag) => {
  confirm.require({
    message: `Are you sure you want to delete "${v.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      emit('displayhive:admin:cts:delete_magic_tag', { id: v.id })
      toast.add({ severity: 'success', summary: 'Success', detail: 'Magic tag deleted', life: 3000 })
    },
  })
}

// Containers (loaded from server via socket)
const containers = ref<any[]>([])

const handleContainersList = (data: any) => {
  const list = data?.containers || data?.data || []
  containers.value = list
  // merge into tagConfigMap so extractJinjaTags can pick up titles/orders
  ;(list || []).forEach((c: any) => {
    try {
      if (c && c.name) tagConfigMap[c.name] = { order: c.order, title: c.title }
    } catch (e) {}
  })

  // If edit dialog is open and we have HTML, auto-extract tags so the UI shows configured titles/orders
  if (showEditDialog.value && editForm.value.html) {
    extractJinjaTags(true)
  }
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

// Loading state for when we request full template detail (html/css)
const loadingTemplate = ref(false)
const loadingTemplateError = ref('')
let templateLoadTimer: number | null = null

const filteredTemplates = computed(() => {
  if (!filterText.value) return templatesStore.templates
  const search = filterText.value.toLowerCase()
  return templatesStore.templates.filter(
    (t) =>
      t.name?.toLowerCase().includes(search) ||
      t.description?.toLowerCase().includes(search)
  )
})

const handleTemplateDetail = (data: any) => {
  try {
    const tpl = data?.template || data?.data || null
    if (!tpl) return

    // Copy operation
    if (pendingCopyName.value) {
      const name = pendingCopyName.value
      pendingCopyName.value = ''
      const containerConfig: Record<string, { order: number; title: string }> = {}
      for (const c of (tpl.containers || [])) {
        containerConfig[c.name] = { order: c.order ?? 0, title: c.title || '' }
      }
      emit('displayhive:admin:cts:create_template', {
        name,
        description: tpl.description || '',
        html: tpl.html || '',
        css: tpl.css || '',
        container_config: containerConfig,
      })
      toast.add({ severity: 'success', summary: 'Copied', detail: `"${name}" created`, life: 3000 })
      refreshData()
      return
    }

    const id = Number(tpl.id)
    // If edit dialog is open for this template, populate html/css
    if (showEditDialog.value && editForm.value.id === id) {
      editForm.value.html = tpl.html || ''
      editForm.value.css = tpl.css || ''
      // Populate tagConfigMap from the containers included in the detail response
      const templateContainers: any[] = tpl.containers || []
      templateContainers.forEach((c: any) => {
        if (c?.name) tagConfigMap[c.name] = { order: c.order, title: c.title || '' }
      })
      // Auto-extract and show jinja tags if the template has containers
      if (templateContainers.length > 0 && editForm.value.html) {
        extractJinjaTags(true)
      }
      loadingTemplate.value = false
      loadingTemplateError.value = ''
      if (templateLoadTimer) {
        clearTimeout(templateLoadTimer)
        templateLoadTimer = null
      }
    }
  } catch (e) {
    console.warn('[TemplatesView] handleTemplateDetail error', e)
  }
}

// Jinja tag extraction & config
const jinjaTags = ref<Array<{ name: string; title: string; order: number }>>([])
const showJinjaSection = ref(false)
const tagConfigMap: Record<string, { order?: number; title?: string }> = {}

// DnD state
const dragIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)

const onDragStart = (ev: DragEvent, idx: number) => {
  dragIndex.value = idx
  try {
    ev.dataTransfer?.setData('text/plain', String(idx))
    ev.dataTransfer!.effectAllowed = 'move'
  } catch (e) {}
}

const onDragOver = (_ev: DragEvent, idx: number) => {
  // track current hovered row for styling
  dragOverIndex.value = idx
}

const onDrop = (_ev: DragEvent, idx: number) => {
  const from = dragIndex.value
  if (from === null || from === undefined) return
  if (from === idx) {
    dragIndex.value = null
    dragOverIndex.value = null
    return
  }
  const arr = jinjaTags.value
  const item = arr.splice(from, 1)[0]
  if (!item) return
  // when removing an earlier element, inserting at same idx will place correctly
  arr.splice(idx, 0, item)
  arr.forEach((t, i) => (t.order = i + 1))
  dragIndex.value = null
  dragOverIndex.value = null
}

const onDragEnd = () => {
  dragIndex.value = null
  dragOverIndex.value = null
}

const extractJinjaTags = (silent = false) => {
  const html = editForm.value.html || ''
  const regex = /\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}/g
  const allFound: string[] = []
  let m: RegExpExecArray | null
  while ((m = regex.exec(html)) !== null) {
    const name = m[1] as string
    if (name && !allFound.includes(name)) allFound.push(name)
  }

  // var_<name> tags are magic tags, not containers: ensure the magic tag
  // exists and exclude it from the container list below.
  const magicNames = allFound.filter((name) => name.startsWith('var_'))
  magicNames.forEach((name) => {
    const magicName = name.slice(4)
    if (!magicName) return
    const exists = magicTagsStore.magicTags.some((t) => t.name.toLowerCase() === magicName.toLowerCase())
    if (!exists) {
      emit('displayhive:admin:cts:create_magic_tag', { name: magicName, value: '' })
    }
  })
  if (magicNames.length > 0) magicTagsStore.fetch()

  const found = allFound.filter((name) => !name.startsWith('var_'))

  if (found.length === 0) {
    if (!silent) {
      toast.add({ severity: 'info', summary: 'No tags', detail: 'No Jinja tags found in HTML', life: 3000 })
      jinjaTags.value = []
      showJinjaSection.value = true
    }
    return
  }

  // build jinjaTags array merging existing tagConfigMap
  const arr = found.map((name, idx) => {
    const cfg = tagConfigMap[name] || {}
    return { name, title: cfg.title || '', order: cfg.order || idx + 1 }
  })

  // sort by order
  arr.sort((a, b) => (a.order || 999) - (b.order || 999))
  jinjaTags.value = arr
  showJinjaSection.value = true
}

// moveTagUp/moveTagDown removed — drag-and-drop is used instead

const prepareContainerConfig = () => {
  const cfg: Record<string, any> = {}
  jinjaTags.value.forEach((t, idx) => {
    cfg[t.name] = { order: idx + 1, title: t.title || '' }
  })
  return cfg
}

onMounted(() => {
  on('displayhive:admin:stc:template_detail', handleTemplateDetail)
  on('displayhive:admin:stc:containers', handleContainersList)
  templatesStore.fetch()
  magicTagsStore.fetch()
  try { emit('displayhive:admin:cts:get_containers') } catch (e) {}
})

onUnmounted(() => {
  off('displayhive:admin:stc:template_detail', handleTemplateDetail)
  off('displayhive:admin:stc:containers', handleContainersList)
})

const refreshData = () => templatesStore.fetch()

const resetJinjaState = () => {
  jinjaTags.value = []
  showJinjaSection.value = false
  Object.keys(tagConfigMap).forEach((k) => delete tagConfigMap[k])
}

const openNewDialog = () => {
  isNew.value = true
  resetJinjaState()
  editForm.value = {
    id: null,
    name: '',
    description: '',
    html: '<div class="container">\n  {{ maincontent }}\n</div>',
    css: '',
  }
  showEditDialog.value = true
}

const openEditDialog = (template: Template) => {
  isNew.value = false
  resetJinjaState()
  editForm.value = {
    id: template.id,
    name: template.name,
    description: template.description || '',
    html: template.html || '',
    css: template.css || '',
  }
  // Request full template detail (html/css) from server and open dialog.
  // Server may only emit minimal list initially.
  try {
    // show loading indicator while detail is fetched
    loadingTemplate.value = true
    loadingTemplateError.value = ''
    emit('get_template', { id: template.id })
    emit('displayhive:admin:cts:get_template', { id: template.id })
    // set a timeout so UI doesn't block forever
    if (templateLoadTimer) {
      clearTimeout(templateLoadTimer)
    }
    templateLoadTimer = window.setTimeout(() => {
      loadingTemplate.value = false
      loadingTemplateError.value = 'Timed out while fetching template content.'
      templateLoadTimer = null
    }, 8000)
  } catch (e) {}
  // Request per-template container config via socket (replaces legacy REST endpoint)
  try {
    emit('displayhive:admin:cts:get_template_containers', { id: template.id })
    emit('get_template_containers', { id: template.id })
  } catch (e) {}

  showEditDialog.value = true
}

const closeDialog = () => {
  showEditDialog.value = false
  loadingTemplate.value = false
  loadingTemplateError.value = ''
  if (templateLoadTimer) {
    clearTimeout(templateLoadTimer)
    templateLoadTimer = null
  }
}

const saveTemplate = async (keepOpen = false) => {
  const event = isNew.value
    ? 'displayhive:admin:cts:create_template'
    : 'displayhive:admin:cts:update_template'

  const payload: any = {
    id: editForm.value.id,
    name: editForm.value.name,
    description: editForm.value.description,
    html: editForm.value.html,
    css: editForm.value.css,
  }
  if (showJinjaSection.value) {
    payload.container_config = prepareContainerConfig()
  }

  emit(event, payload)

  toast.add({
    severity: 'success',
    summary: 'Success',
    detail: isNew.value ? 'Template created' : 'Template updated',
    life: 3000,
  })
  if (!keepOpen) showEditDialog.value = false
  refreshData()
}

const setDefault = (template: Template) => {
  emit('displayhive:admin:cts:set_default_template', { id: template.id })
  toast.add({ severity: 'success', summary: 'Success', detail: 'Default template updated', life: 3000 })
  refreshData()
}

const deleteTemplate = (template: Template) => {
  confirm.require({
    message: `Are you sure you want to delete "${template.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      emit('displayhive:admin:cts:delete_template', { id: template.id })
      toast.add({ severity: 'success', summary: 'Success', detail: 'Template deleted', life: 3000 })
      refreshData()
    },
  })
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('templates.page')" class="templates-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Templates page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="templates-view">
    <Card>
      <template #title>
        <div class="card-header">
          <span>Templates</span>
          <div class="header-actions">
            <Button v-if="canCreate" icon="pi pi-plus" label="New Template" @click="openNewDialog" size="small" />
            <Button icon="pi pi-refresh" @click="refreshData" size="small" outlined />
          </div>
        </div>
      </template>
      <template #content>
        <div class="filter-bar">
          <InputText v-model="filterText" placeholder="Filter templates..." class="filter-input" />
        </div>

        <DataTable
          :value="filteredTemplates"
          :loading="templatesStore.loading"
          sortField="name"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="filteredTemplates.length > 10"
          :rows="10"
          responsiveLayout="scroll"
        >
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="name" header="Name" sortable>
            <template #body="{ data }">
              {{ data.name }}
              <Tag v-if="data.is_default" severity="info" value="Default" class="ml-2" />
            </template>
          </Column>
          <Column field="description" header="Description">
            <template #body="{ data }">
              {{ data.description ? data.description.substring(0, 50) + (data.description.length > 50 ? '...' : '') : '-' }}
            </template>
          </Column>
          <!-- HTML column removed: templates list now shows container count and default marker -->
          <Column field="container_count" header="Containers" style="width: 100px">
            <template #body ="{ data }">
              <Tag :value="`${data.container_count || 0}`" />
            </template>
          </Column>
          <Column header="Actions" style="width: 200px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button v-if="canEdit" icon="pi pi-pencil" @click="openEditDialog(data)" size="small" outlined title="Edit" />
                <Button
                  v-if="canEdit && !data.is_default"
                  icon="pi pi-check"
                  @click="setDefault(data)"
                  size="small"
                  severity="success"
                  outlined
                  title="Set as Default"
                />
                <Button v-if="canCreate" icon="pi pi-copy" @click="openCopyDialog(data)" size="small" outlined title="Copy" />
                <Button v-if="canDelete" icon="pi pi-trash" @click="deleteTemplate(data)" size="small" severity="danger" outlined title="Delete" />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Magic Tags Card -->
    <Card v-if="canMagicTagsPage">
      <template #title>
        <div class="card-header">
          <span>Magic Tags</span>
          <div class="header-actions">
            <Button v-if="canMagicTagsCreate" icon="pi pi-plus" label="New Magic Tag" @click="openNewTagDialog" size="small" />
            <Button icon="pi pi-refresh" @click="magicTagsStore.fetch()" size="small" outlined />
          </div>
        </div>
      </template>
      <template #content>
        <DataTable
          :value="magicTagsStore.magicTags"
          :loading="magicTagsStore.loading"
          sortField="name"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="magicTagsStore.magicTags.length > 10"
          :rows="10"
          responsiveLayout="scroll"
        >
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="name" header="Name" sortable />
          <Column field="value" header="Value">
            <template #body="{ data }">
              {{ data.value.length > 80 ? data.value.substring(0, 80) + '...' : data.value }}
            </template>
          </Column>
          <Column field="description" header="Description">
            <template #body="{ data }">
              {{ data.description && data.description.length > 80 ? data.description.substring(0, 80) + '...' : (data.description || '-') }}
            </template>
          </Column>
          <Column header="Actions" style="width: 120px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button v-if="canMagicTagsEdit" icon="pi pi-pencil" @click="openEditTagDialog(data)" size="small" outlined title="Edit" />
                <Button v-if="canMagicTagsDelete" icon="pi pi-trash" @click="deleteTag(data)" size="small" severity="danger" outlined title="Delete" />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Magic Tag Edit Dialog -->
    <Dialog
      v-model:visible="showTagDialog"
      :header="isNewTag ? 'New Magic Tag' : 'Edit Magic Tag'"
      modal
      :style="{ width: '480px' }"
    >
      <div class="dialog-content">
        <div class="field">
          <label for="var-name">Name</label>
          <InputText id="var-name" v-model="tagForm.name" class="w-full" />
        </div>
        <div class="field">
          <label for="var-value">Value</label>
          <Textarea id="var-value" v-model="tagForm.value" rows="4" class="w-full" />
        </div>
        <div class="field">
          <label for="var-description">Description</label>
          <Textarea id="var-description" v-model="tagForm.description" rows="2" class="w-full" />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="showTagDialog = false" text />
        <Button v-if="!isNewTag" label="Update" severity="secondary" outlined @click="saveTag(true)" />
        <Button label="Save" @click="saveTag()" />
      </template>
    </Dialog>

    <!-- Copy Dialog -->
    <Dialog v-model:visible="showCopyDialog" header="Copy Template" modal :style="{ width: '400px' }">
      <div class="field">
        <label for="copy-tpl-name">New Name</label>
        <InputText id="copy-tpl-name" v-model="copyNewName" class="w-full" autofocus @keyup.enter="executeCopyTemplate" />
      </div>
      <template #footer>
        <Button label="Cancel" @click="showCopyDialog = false" text />
        <Button label="Copy" icon="pi pi-copy" @click="executeCopyTemplate" :disabled="!copyNewName.trim()" />
      </template>
    </Dialog>

    <!-- Edit Dialog -->
    <Dialog
      v-model:visible="showEditDialog"
      :header="isNew ? 'New Template' : 'Edit Template'"
      modal
      :style="{ width: '95vw', maxWidth: '1800px' }"
    >
      <div class="dialog-content">
        <div v-if="loadingTemplate" class="tpl-loading">
          Loading template HTML/CSS…
          <div v-if="loadingTemplateError" class="tpl-loading-error">{{ loadingTemplateError }}</div>
        </div>
        <div class="field">
          <label for="tpl-name">Name</label>
          <InputText id="tpl-name" v-model="editForm.name" class="w-full" />
        </div>
        <div class="field">
          <label for="tpl-description">Description</label>
          <Textarea id="tpl-description" v-model="editForm.description" rows="2" class="w-full" />
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
            <div style="display:flex;gap:0.5rem;align-items:center;margin-top:0.5rem;">
              <Button label="Extract Tags" icon="pi pi-tags" size="small" @click="() => extractJinjaTags(false)" />
              <small class="hint" v-text="'Use {{ container_name }} syntax for content placeholders'"></small>
            </div>
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

        <!-- Jinja Tags Configuration -->
        <div v-if="showJinjaSection" class="field jinja-section">
          <label>Jinja Tags Configuration</label>
          <div class="table-responsive">
            <table class="table table-sm table-bordered">
              <thead>
                <tr>
                  <th style="width:40px"></th>
                  <th>Tag</th>
                  <th>Titel</th>
                  <th style="width:120px">Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(tag, idx) in jinjaTags"
                  :key="tag.name"
                  draggable="true"
                  @dragstart="onDragStart($event, idx)"
                  @dragover.prevent="onDragOver($event, idx)"
                  @drop="onDrop($event, idx)"
                  @dragend="onDragEnd"
                  :class="{ 'drag-over': dragOverIndex === idx }"
                >
                  <td class="drag-handle">⋮⋮</td>
                  <td>
                    <InputText :value="tag.name" readonly class="w-full" />
                  </td>
                  <td>
                    <InputText v-model="tag.title" placeholder="z.B. Hauptbereich" class="w-full" />
                  </td>
                  <td>
                    <small class="hint">Drag to reorder</small>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="form-text">Ziehe die Zeilen, um die Reihenfolge der Tags zu ändern oder benutze die Aktionen.</div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="closeDialog" text />
        <Button v-if="!isNew" label="Update" severity="secondary" outlined @click="saveTemplate(true)" :disabled="loadingTemplate" />
        <Button label="Save" @click="saveTemplate()" :disabled="loadingTemplate" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.templates-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.code-preview {
  font-size: 0.75rem;
  background: #f5f5f5;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 250px;
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

.drag-handle {
  cursor: move;
  user-select: none;
  text-align: center;
}

.drag-over {
  outline: 2px dashed rgba(0,0,0,0.15);
  background: rgba(0,0,0,0.02);
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
