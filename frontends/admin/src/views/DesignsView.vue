<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import PageActions from '../components/PageActions.vue'
import DialogTitle from '../components/DialogTitle.vue'
import DesignDefaultColorsPanel from '../components/designs/DesignDefaultColorsPanel.vue'
import DesignAspectRatiosPanel from '../components/designs/DesignAspectRatiosPanel.vue'
import DesignBackdropPanel from '../components/designs/DesignBackdropPanel.vue'
import DesignIndicatorPanel from '../components/designs/DesignIndicatorPanel.vue'
import DesignEffectPanel from '../components/designs/DesignEffectPanel.vue'
import DesignGlobalStylesPanel from '../components/designs/DesignGlobalStylesPanel.vue'
import DesignCodePanel from '../components/designs/DesignCodePanel.vue'
import GradientDialogs from '../components/designs/GradientDialogs.vue'
import { provideGradients } from '../composables/designs/useGradients'
import { newColorId } from '../composables/designs/useDefaultColors'
import { useConfirmAction } from '../composables/useConfirmAction'
import { useOpenFromQuery } from '../composables/useOpenFromQuery'
import { useSocket } from '../composables/useSocket'
import { useAck } from '../composables/useAck'
import { useRightsStore } from '../stores/rights'
import { blankDesignForm } from '../types/designForm'
import type { Design, DefaultColor } from '../types/models'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Dialog from 'primevue/dialog'
import Card from 'primevue/card'
import Tag from 'primevue/tag'

// The Designs page: the list, and the dialog that edits one Design. The dialog's sections are
// components/designs/Design*Panel.vue; the Gradient library is composables/designs/useGradients.ts.
const { confirmDanger } = useConfirmAction()
const { on, off, emit } = useSocket()
const { request } = useAck()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('designs.create'))
const canEdit = computed(() => rightsStore.can('designs.edit'))
const canDelete = computed(() => rightsStore.can('designs.delete'))

const designs = ref<Design[]>([])
const loading = ref(true)
const filterText = ref('')

// Edit dialog
const showEditDialog = ref(false)
const isNew = ref(false)
const editForm = ref(blankDesignForm())
const gradients = provideGradients(editForm)

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

const handleDesignsList = (data: { data?: Design[]; designs?: Design[] }) => {
  const list = data?.data || data?.designs || []
  designs.value = list
  loading.value = false
}

// The stored detail (html, css, backdrop, effect, palette, ratios, indicator) of the Design in the dialog.
const applyDetail = (design: Design) => {
  const form = editForm.value
  form.html = design.html || ''
  form.css = design.css || ''
  form.background_color = design.background_color || ''
  form.background_image_url = design.background_image_url || ''
  form.background_repeat = design.background_repeat || ''
  form.background_size = design.background_size || ''
  form.background_opacity = design.background_opacity ?? 100
  form.background_effect = design.background_effect || ''
  try {
    form.background_effect_settings = design.background_effect_settings
      ? JSON.parse(design.background_effect_settings)
      : {}
  } catch {
    form.background_effect_settings = {}
  }
  try {
    const parsed = design.default_colors ? JSON.parse(design.default_colors) : []
    form.default_colors = Array.isArray(parsed)
      ? parsed.map((c: Partial<DefaultColor>) => ({ id: c.id || newColorId(), name: c.name || '', hex: c.hex || '' }))
      : []
  } catch {
    form.default_colors = []
  }
  try {
    const parsedRatios = design.aspect_ratios ? JSON.parse(design.aspect_ratios) : []
    form.aspect_ratios = Array.isArray(parsedRatios) ? parsedRatios.filter((r: unknown) => typeof r === 'string') : []
  } catch {
    form.aspect_ratios = []
  }
  form.indicator_enabled = !!design.indicator_enabled
  form.indicator_color = design.indicator_color || ''
  form.indicator_height = design.indicator_height ?? 0.8
  form.indicator_direction = design.indicator_direction === 'rtl' ? 'rtl' : 'ltr'
}

const stopLoadTimer = () => {
  if (designLoadTimer) {
    clearTimeout(designLoadTimer)
    designLoadTimer = null
  }
}

const handleDesignDetail = async (data: { design?: Design }) => {
  try {
    const design = data?.design || null
    if (!design) return

    // Copy operation
    if (pendingCopyName.value) {
      const name = pendingCopyName.value
      pendingCopyName.value = ''
      await request('displayhive:admin:cts:create_design', {
        name,
        description: design.description || '',
        html: design.html || '',
        css: design.css || '',
      }, { success: `"${name}" created`, error: 'Could not copy the design' })
      return
    }

    if (showEditDialog.value && editForm.value.id === Number(design.id)) {
      applyDetail(design)
      loadingDesign.value = false
      loadingDesignError.value = ''
      stopLoadTimer()
    }
  } catch (e) {
    console.warn('[DesignsView] handleDesignDetail error', e)
  }
}

const refreshData = () => {
  loading.value = true
  emit('displayhive:admin:cts:get_designs')
}

onMounted(() => {
  on('displayhive:admin:stc:upd_designs', handleDesignsList)
  on('displayhive:admin:stc:design_detail', handleDesignDetail)
  refreshData()
})

onUnmounted(() => {
  off('displayhive:admin:stc:upd_designs', handleDesignsList)
  off('displayhive:admin:stc:design_detail', handleDesignDetail)
  stopLoadTimer()
})

const openNewDialog = () => {
  isNew.value = true
  editForm.value = blankDesignForm()
  showEditDialog.value = true
}

const openEditDialog = (design: Design) => {
  isNew.value = false
  editForm.value = {
    ...blankDesignForm(),
    id: design.id,
    name: design.name,
    description: design.description || '',
    html: design.html || '',
    css: design.css || '',
    background_color: design.background_color || '',
    background_image_url: design.background_image_url || '',
    background_repeat: design.background_repeat || '',
    background_size: design.background_size || '',
    background_opacity: design.background_opacity ?? 100,
    background_effect: design.background_effect || '',
  }
  loadingDesign.value = true
  loadingDesignError.value = ''
  emit('displayhive:admin:cts:get_design', { id: design.id })
  gradients.loadForDesign(design.id)
  stopLoadTimer()
  designLoadTimer = window.setTimeout(() => {
    loadingDesign.value = false
    loadingDesignError.value = 'Timed out while fetching design content.'
    designLoadTimer = null
  }, 8000)
  showEditDialog.value = true
}

const closeDialog = () => {
  showEditDialog.value = false
  loadingDesign.value = false
  loadingDesignError.value = ''
  stopLoadTimer()
}

const saveDesign = async (keepOpen = false) => {
  const form = editForm.value
  const event = isNew.value
    ? 'displayhive:admin:cts:create_design'
    : 'displayhive:admin:cts:update_design'

  const ack = await request(event, {
    id: form.id,
    name: form.name,
    description: form.description,
    html: form.html,
    css: form.css,
    background_color: form.background_color,
    background_image_url: form.background_image_url,
    background_repeat: form.background_repeat,
    background_size: form.background_size,
    background_opacity: form.background_opacity,
    background_effect: form.background_effect,
    background_effect_settings: form.background_effect
      ? JSON.stringify(form.background_effect_settings)
      : '',
    default_colors: JSON.stringify(form.default_colors.filter((c) => c.name.trim() && c.hex.trim())),
    aspect_ratios: JSON.stringify(form.aspect_ratios),
    indicator_enabled: form.indicator_enabled,
    indicator_color: form.indicator_color,
    indicator_height: form.indicator_height,
    indicator_direction: form.indicator_direction,
  }, { success: isNew.value ? 'Design created' : 'Design updated', error: 'Could not save the design' })
  if (ack && !keepOpen) showEditDialog.value = false
}

const setDefault = async (design: Design) => {
  const ack = await request('displayhive:admin:cts:set_default_design', { id: design.id }, { success: 'Active design updated', error: 'Could not change the active design' })
  if (ack) refreshData()
}

const deleteDesign = (design: Design) => {
  confirmDanger({
    message: `Are you sure you want to delete "${design.name}"?`,
    accept: async () => {
      await request('displayhive:admin:cts:delete_design', { id: design.id }, { success: 'Design deleted', error: 'Could not delete the design' })
    },
  })
}

// Reached via a link like /designs?edit=<id>: open that design.
useOpenFromQuery(() => designs.value, openEditDialog, () => canEdit.value)
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('designs.page')" class="designs-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Designs page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="designs-page" class="designs-view">
    <PageActions
      :primary="canCreate ? { label: 'New Design', icon: 'pi pi-plus', tour: 'designs-new', onClick: openNewDialog } : null"
    />
    <Card>
      <template #content>
        <DataTable
          data-tour="designs-table"
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
          <template #header>
            <div class="dt-header">
              <div class="dt-left">
                <InputText
                  v-model="filterText"
                  data-tour="designs-filter"
                  placeholder="Filter designs..."
                  class="filter-input"
                />
              </div>
            </div>
          </template>
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
                <Button v-if="canEdit" data-tour="designs-row-edit" icon="pi pi-pencil" @click="openEditDialog(data)" size="small" outlined title="Edit" />
                <Button
                  v-if="canEdit && !data.isDefault"
                  data-tour="designs-row-make-active"
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
    <Dialog v-model:visible="showCopyDialog" modal :style="{ width: '400px' }">
      <template #header>
        <DialogTitle icon="pi-copy" title="Copy Design" />
      </template>
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
      modal
      :style="{ width: '95vw', maxWidth: '1800px' }"
    >
      <template #header>
        <DialogTitle icon="pi-palette" :title="isNew ? 'New Design' : 'Edit Design'" />
      </template>
      <div class="dialog-content">
        <div v-if="loadingDesign" class="tpl-loading">
          Loading design HTML/CSS…
          <div v-if="loadingDesignError" class="tpl-loading-error">{{ loadingDesignError }}</div>
        </div>
        <div class="field" data-tour="designs-name-fields">
          <label for="design-name">Name</label>
          <InputText id="design-name" v-model="editForm.name" class="w-full" />
        </div>
        <div class="field">
          <label for="design-description">Description</label>
          <Textarea id="design-description" v-model="editForm.description" rows="2" class="w-full" />
        </div>
        <template v-if="!isNew">
          <DesignDefaultColorsPanel v-model:form="editForm" />
          <DesignAspectRatiosPanel v-model:form="editForm" />
          <DesignBackdropPanel v-model:form="editForm" />
          <DesignIndicatorPanel v-model:form="editForm" />
          <DesignEffectPanel v-model:form="editForm" />
          <DesignGlobalStylesPanel v-model:form="editForm" />
        </template>
        <DesignCodePanel v-model:form="editForm" />
      </div>
      <template #footer>
        <Button data-tour="designs-dialog-cancel" label="Cancel" @click="closeDialog" text />
        <Button v-if="!isNew" label="Update" severity="secondary" outlined @click="saveDesign(true)" :disabled="loadingDesign" />
        <Button label="Save" @click="saveDesign()" :disabled="loadingDesign" />
      </template>
    </Dialog>

    <GradientDialogs />
  </div>
</template>

<style scoped>
.designs-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* No title text left in the card header — keep the action buttons
   right-aligned instead of collapsing to the start. */
.card-header {
  justify-content: flex-end;
}

.ml-2 {
  margin-left: 0.5rem;
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
</style>
