<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useMagicTagsStore } from '../stores/magicTags'
import { useRightsStore } from '../stores/rights'
import type { Design, ContentContainer } from '../types/models'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Dialog from 'primevue/dialog'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Panel from 'primevue/panel'
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'
import ColorPicker from 'primevue/colorpicker'

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

// --- Per-container "Font" style overrides ----------------------------------
// A generic (property, value) key/value row per container per Design (see
// DesignContainerStyle on the backend) — starting with this one "Font"
// group. Blank/"(not set)" means the property is omitted from the generated
// CSS entirely, not rendered as `prop: ;`.

interface FontOption { label: string; value: string }
interface FontProperty {
  key: string
  label: string
  /** 'dropdown' (editable Dropdown, default) | 'vh-number' (numeric vh input) | 'color' (ColorPicker) */
  type?: 'dropdown' | 'vh-number' | 'color'
  options?: FontOption[]
}

const NOT_SET: FontOption = { label: '(not set)', value: '' }

const WEB_SAFE_FONTS: FontOption[] = [
  { label: 'Arial', value: 'Arial, sans-serif' },
  { label: 'Arial Black', value: '"Arial Black", sans-serif' },
  { label: 'Verdana', value: 'Verdana, sans-serif' },
  { label: 'Tahoma', value: 'Tahoma, sans-serif' },
  { label: 'Trebuchet MS', value: '"Trebuchet MS", sans-serif' },
  { label: 'Impact', value: 'Impact, sans-serif' },
  { label: 'Segoe UI', value: '"Segoe UI", sans-serif' },
  { label: 'Times New Roman', value: '"Times New Roman", serif' },
  { label: 'Georgia', value: 'Georgia, serif' },
  { label: 'Garamond', value: 'Garamond, serif' },
  { label: 'Courier New', value: '"Courier New", monospace' },
  { label: 'Lucida Console', value: '"Lucida Console", monospace' },
  { label: 'Monaco', value: 'Monaco, monospace' },
  { label: 'Brush Script MT', value: '"Brush Script MT", cursive' },
  { label: 'Comic Sans MS', value: '"Comic Sans MS", cursive' },
  { label: 'Sans-serif (generic)', value: 'sans-serif' },
  { label: 'Serif (generic)', value: 'serif' },
  { label: 'Monospace (generic)', value: 'monospace' },
  { label: 'Cursive (generic)', value: 'cursive' },
  { label: 'Fantasy (generic)', value: 'fantasy' },
  { label: 'System UI (generic)', value: 'system-ui' },
]

const keywordOptions = (...values: string[]): FontOption[] => values.map((v) => ({ label: v, value: v }))

const FONT_PROPERTIES: FontProperty[] = [
  { key: 'font-family', label: 'Font Family', options: [NOT_SET, ...WEB_SAFE_FONTS] },
  { key: 'font-variant', label: 'Font Variant', options: [NOT_SET, ...keywordOptions(
    'normal', 'small-caps', 'all-small-caps', 'petite-caps', 'all-petite-caps', 'unicase', 'titling-caps',
  )] },
  { key: 'font-weight', label: 'Font Weight', options: [NOT_SET, ...keywordOptions(
    'normal', 'bold', 'bolder', 'lighter', '100', '200', '300', '400', '500', '600', '700', '800', '900',
  )] },
  { key: 'font-stretch', label: 'Font Stretch', options: [NOT_SET, ...keywordOptions(
    'normal', 'ultra-condensed', 'extra-condensed', 'condensed', 'semi-condensed',
    'semi-expanded', 'expanded', 'extra-expanded', 'ultra-expanded',
  )] },
  { key: 'font-size', label: 'Font Size', type: 'vh-number' },
  { key: 'line-height', label: 'Line Height', options: [NOT_SET, ...keywordOptions('normal')] },
  { key: 'font-style', label: 'Font Style', options: [NOT_SET, ...keywordOptions('normal', 'italic', 'oblique')] },
  { key: 'color', label: 'Color', type: 'color' },
]

const containers = ref<ContentContainer[]>([])
// contentcontainer id -> { property: value }
const containerStyles = ref<Record<number, Record<string, string>>>({})

const handleContainersList = (data: any) => {
  containers.value = data?.data || []
}

// A stored value that no longer matches its property's current input type
// (e.g. "xx-small" for font-size after it changed from a keyword dropdown to
// a vh number) can't be shown OR cleared by that control — it would just
// look blank/unset while actually still being sent back unchanged on every
// autosave. Discarding it here, once, on load turns "invisible stale value"
// into a real, visible "not set" the moment the Design is opened.
const isValidForType = (type: FontProperty['type'], value: string): boolean => {
  if (!value) return true
  if (type === 'vh-number') return /^-?\d+(\.\d+)?vh$/.test(value)
  if (type === 'color') return /^#[0-9a-fA-F]{6}$/.test(value)
  return true
}

const handleDesignContainerStyles = (data: any) => {
  if (!data || data.design_id !== editForm.value.id) return
  const loaded: Record<number, Record<string, string>> = {}
  for (const [idStr, rawStyles] of Object.entries(data.data || {})) {
    const styles = { ...(rawStyles as Record<string, string>) }
    for (const p of FONT_PROPERTIES) {
      if (styles[p.key] && !isValidForType(p.type, styles[p.key])) {
        delete styles[p.key]
      }
    }
    loaded[Number(idStr)] = styles
  }
  containerStyles.value = loaded
}

const getStyleValue = (containerId: number, prop: string): string =>
  containerStyles.value[containerId]?.[prop] ?? ''

const saveDebounce: Record<number, ReturnType<typeof setTimeout>> = {}

const setStyleValue = (containerId: number, prop: string, value: string | undefined) => {
  const current = { ...(containerStyles.value[containerId] || {}) }
  current[prop] = value || ''
  containerStyles.value = { ...containerStyles.value, [containerId]: current }

  if (!editForm.value.id) return
  if (saveDebounce[containerId]) clearTimeout(saveDebounce[containerId])
  saveDebounce[containerId] = setTimeout(() => {
    const styles: Record<string, string> = {}
    for (const p of FONT_PROPERTIES) styles[p.key] = containerStyles.value[containerId]?.[p.key] || ''
    emit('displayhive:admin:cts:save_design_container_styles', {
      design_id: editForm.value.id, contentcontainer_id: containerId, styles,
    })
  }, 400)
}

// font-size: stored as a plain CSS value (e.g. "5vh"); the input only ever
// deals in the numeric vh amount.
const getVhNumber = (containerId: number, prop: string): number | null => {
  const raw = getStyleValue(containerId, prop)
  if (!raw) return null
  const n = parseFloat(raw)
  return isNaN(n) ? null : n
}

const setVhValue = (containerId: number, prop: string, n: number | null | undefined) => {
  setStyleValue(containerId, prop, n == null ? '' : `${n}vh`)
}

// color: PrimeVue's ColorPicker works in bare hex ("ff0000"), the stored
// CSS value needs the leading "#".
const getColorHex = (containerId: number, prop: string): string => {
  const raw = getStyleValue(containerId, prop)
  return raw ? raw.replace(/^#/, '') : ''
}

const setColorHex = (containerId: number, prop: string, hex: string | undefined) => {
  setStyleValue(containerId, prop, hex ? `#${hex}` : '')
}

// --- Global font styles (applied to every container via `.dh-container`) ---
// Same (property, value) shape as the per-container ones above, just not
// keyed by container id. Precedence: per-container overrides < these
// global ones < the Design's own hand-written CSS (see upd_content.py).
const globalStyles = ref<Record<string, string>>({})

const handleDesignGlobalStyles = (data: any) => {
  if (!data || data.design_id !== editForm.value.id) return
  const styles = { ...(data.data || {}) }
  for (const p of FONT_PROPERTIES) {
    if (styles[p.key] && !isValidForType(p.type, styles[p.key])) delete styles[p.key]
  }
  globalStyles.value = styles
}

const getGlobalValue = (prop: string): string => globalStyles.value[prop] ?? ''

let globalSaveDebounce: ReturnType<typeof setTimeout> | null = null

const setGlobalValue = (prop: string, value: string | undefined) => {
  globalStyles.value = { ...globalStyles.value, [prop]: value || '' }

  if (!editForm.value.id) return
  if (globalSaveDebounce) clearTimeout(globalSaveDebounce)
  globalSaveDebounce = setTimeout(() => {
    const styles: Record<string, string> = {}
    for (const p of FONT_PROPERTIES) styles[p.key] = globalStyles.value[p.key] || ''
    emit('displayhive:admin:cts:save_design_global_styles', { design_id: editForm.value.id, styles })
  }, 400)
}

const getGlobalVhNumber = (prop: string): number | null => {
  const raw = getGlobalValue(prop)
  if (!raw) return null
  const n = parseFloat(raw)
  return isNaN(n) ? null : n
}

const setGlobalVhValue = (prop: string, n: number | null | undefined) => {
  setGlobalValue(prop, n == null ? '' : `${n}vh`)
}

const getGlobalColorHex = (prop: string): string => {
  const raw = getGlobalValue(prop)
  return raw ? raw.replace(/^#/, '') : ''
}

const setGlobalColorHex = (prop: string, hex: string | undefined) => {
  setGlobalValue(prop, hex ? `#${hex}` : '')
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
  on('displayhive:admin:stc:upd_containers', handleContainersList)
  on('displayhive:admin:stc:design_container_styles', handleDesignContainerStyles)
  on('displayhive:admin:stc:design_global_styles', handleDesignGlobalStyles)
  refreshData()
  emit('displayhive:admin:cts:get_containers')
  magicTagsStore.fetch()
})

onUnmounted(() => {
  off('displayhive:admin:stc:upd_designs', handleDesignsList)
  off('displayhive:admin:stc:design_detail', handleDesignDetail)
  off('displayhive:admin:stc:upd_containers', handleContainersList)
  off('displayhive:admin:stc:design_container_styles', handleDesignContainerStyles)
  off('displayhive:admin:stc:design_global_styles', handleDesignGlobalStyles)
})

const refreshData = () => {
  loading.value = true
  emit('displayhive:admin:cts:get_designs')
}

const openNewDialog = () => {
  isNew.value = true
  editForm.value = { id: null, name: '', description: '', html: '', css: '' }
  containerStyles.value = {}
  globalStyles.value = {}
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
  containerStyles.value = {}
  globalStyles.value = {}
  try {
    loadingDesign.value = true
    loadingDesignError.value = ''
    emit('displayhive:admin:cts:get_design', { id: design.id })
    emit('displayhive:admin:cts:get_design_container_styles', { design_id: design.id })
    emit('displayhive:admin:cts:get_design_global_styles', { design_id: design.id })
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

        <div v-if="!isNew" class="container-styles-section">
          <label>Global Styles</label>
          <small class="hint">
            Applies to every container via the shared <code>.dh-container</code> class.
            Beats a per-container override below, but loses to anything in the CSS editor above.
          </small>
          <Panel header="Font" toggleable collapsed class="container-style-panel">
            <div class="font-properties-grid">
              <div v-for="p in FONT_PROPERTIES" :key="p.key" class="field">
                <label>{{ p.label }}</label>
                <InputNumber
                  v-if="p.type === 'vh-number'"
                  :model-value="getGlobalVhNumber(p.key)"
                  :min="0" :max="50" :step="0.1" :max-fraction-digits="2"
                  suffix=" vh"
                  size="small"
                  class="w-full"
                  @update:model-value="(v) => setGlobalVhValue(p.key, v)"
                />
                <div v-else-if="p.type === 'color'" class="color-field-row">
                  <ColorPicker
                    :model-value="getGlobalColorHex(p.key)"
                    @update:model-value="(v) => setGlobalColorHex(p.key, v)"
                  />
                  <span class="color-field-value">{{ getGlobalColorHex(p.key) ? `#${getGlobalColorHex(p.key)}` : '(not set)' }}</span>
                  <Button
                    v-if="getGlobalColorHex(p.key)"
                    icon="pi pi-times" text size="small" title="Clear"
                    @click="setGlobalColorHex(p.key, '')"
                  />
                </div>
                <Dropdown
                  v-else
                  :model-value="getGlobalValue(p.key)"
                  :options="p.options"
                  optionLabel="label"
                  optionValue="value"
                  editable
                  size="small"
                  class="w-full"
                  @update:model-value="(v) => setGlobalValue(p.key, v)"
                />
              </div>
            </div>
          </Panel>
        </div>

        <div v-if="!isNew && containers.length" class="container-styles-section">
          <label>Per-Container Styles</label>
          <small class="hint">
            Style an individual container's overlay by its stable <code>.dh-container-&lt;id&gt;</code> class.
            Changes save automatically. "(not set)" leaves that CSS property out entirely.
          </small>
          <Panel
            v-for="c in containers"
            :key="c.id"
            :header="`${c.title || c.name} #${c.id}`"
            toggleable
            collapsed
            class="container-style-panel"
          >
            <details class="font-collapsible">
              <summary>Font</summary>
              <div class="font-properties-grid">
                <div v-for="p in FONT_PROPERTIES" :key="p.key" class="field">
                  <label>{{ p.label }}</label>
                  <InputNumber
                    v-if="p.type === 'vh-number'"
                    :model-value="getVhNumber(c.id, p.key)"
                    :min="0" :max="50" :step="0.1" :max-fraction-digits="2"
                    suffix=" vh"
                    size="small"
                    class="w-full"
                    @update:model-value="(v) => setVhValue(c.id, p.key, v)"
                  />
                  <div v-else-if="p.type === 'color'" class="color-field-row">
                    <ColorPicker
                      :model-value="getColorHex(c.id, p.key)"
                      @update:model-value="(v) => setColorHex(c.id, p.key, v)"
                    />
                    <span class="color-field-value">{{ getColorHex(c.id, p.key) ? `#${getColorHex(c.id, p.key)}` : '(not set)' }}</span>
                    <Button
                      v-if="getColorHex(c.id, p.key)"
                      icon="pi pi-times" text size="small" title="Clear"
                      @click="setColorHex(c.id, p.key, '')"
                    />
                  </div>
                  <Dropdown
                    v-else
                    :model-value="getStyleValue(c.id, p.key)"
                    :options="p.options"
                    optionLabel="label"
                    optionValue="value"
                    editable
                    size="small"
                    class="w-full"
                    @update:model-value="(v) => setStyleValue(c.id, p.key, v)"
                  />
                </div>
              </div>
            </details>
          </Panel>
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

.container-styles-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.25rem;
}

.container-styles-section > label {
  font-weight: 600;
  font-size: 0.875rem;
}

.container-style-panel {
  font-size: 0.875rem;
}

.font-collapsible {
  border: 1px dashed var(--p-surface-border, #ddd);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
}

.font-collapsible summary {
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
}

.font-properties-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem 1rem;
  margin-top: 0.6rem;
}

.font-properties-grid .field label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #666;
}

.color-field-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.color-field-value {
  font-family: monospace;
  font-size: 0.8rem;
  color: #666;
}
</style>
