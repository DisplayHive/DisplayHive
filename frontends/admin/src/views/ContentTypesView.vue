<script setup lang="ts">
import DialogTitle from '../components/ui/DialogTitle.vue'
import DialogFooter from '../components/ui/DialogFooter.vue'
import { useConfirmAction } from '../composables/useConfirmAction'
import PageActions from '../components/ui/PageActions.vue'
import { useOpenFromQuery } from '../composables/useOpenFromQuery'
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useAck } from '../composables/useAck'
import { useRightsStore } from '../stores/rights'
import type { Layout, ContentContainer, DefaultColor } from '../types/models'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import Card from 'primevue/card'
import ContentTypeEditDialog from '../components/contenttypes/ContentTypeEditDialog.vue'
import type { RawContentTypeDetail } from '../components/contenttypes/types'

interface ContentType {
  id: number
  name: string
  description: string
  layout_id: number | null
  layout_name?: string
  field_count?: number
}

const router = useRouter()
const { confirmDanger } = useConfirmAction()
const { on, off, emit } = useSocket()
const { request } = useAck()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('contenttypes.create'))
const canEdit = computed(() => rightsStore.can('contenttypes.edit'))
const canDelete = computed(() => rightsStore.can('contenttypes.delete'))

const contentTypes = ref<ContentType[]>([])
const layouts = ref<Layout[]>([])
const containers = ref<ContentContainer[]>([])
const loading = ref(true)
const filterText = ref('')

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
const editingContentType = ref<ContentType | null>(null)

const filteredContentTypes = computed(() => {
  if (!filterText.value) return contentTypes.value
  const search = filterText.value.toLowerCase()
  return contentTypes.value.filter(
    (ct) =>
      ct.name?.toLowerCase().includes(search) ||
      ct.description?.toLowerCase().includes(search)
  )
})

const handleContentTypesList = (data: { data?: ContentType[]; contenttypes?: ContentType[] }) => {
  contentTypes.value = data?.data || data?.contenttypes || []
  loading.value = false
}

const handleLayoutsList = (data: { data?: Layout[] }) => {
  layouts.value = data?.data || []
}

const handleContainersList = (data: { data?: ContentContainer[] }) => {
  containers.value = data?.data || []
}

// Active Design's palette — passed to the preset panel's icon-color picker
// for "@default:<id>" quick-pick swatches.
const designPalette = ref<DefaultColor[]>([])
const handleActiveDesignColors = (data: { colors?: DefaultColor[] }) => {
  designPalette.value = Array.isArray(data?.colors) ? data.colors : []
}

// The detail of a content type arrives for a copy ("Copy" asked for it); the edit dialog
// listens for the same event itself.
const handleContentTypeDetail = async (data: { contenttype?: RawContentTypeDetail; data?: RawContentTypeDetail }) => {
  const ct = data?.contenttype || data?.data || null
  if (!ct || !pendingCopyName.value) return

  const name = pendingCopyName.value
  pendingCopyName.value = ''
  const tagconfigs = (ct.tagconfigs || []).map((t) => ({
    name: t.field_name, title: t.field_label, field_handler: t.field_handler,
    contentcontainer_id: t.contentcontainer_id, order: t.order,
    default_value: t.default_value, option_flags: t.option_flags,
  }))
  // The server pushes the new list to every admin.
  await request('displayhive:admin:cts:create_contenttype', {
    name,
    description: ct.description || '',
    layout_id: ct.layout_id,
    tagconfigs,
  }, { success: `"${name}" created`, error: 'Copy failed' })
}

onMounted(() => {
  on('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
  on('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
  on('displayhive:admin:stc:upd_layouts', handleLayoutsList)
  on('displayhive:admin:stc:upd_containers', handleContainersList)
  on('displayhive:admin:stc:active_design_colors', handleActiveDesignColors)

  emit('displayhive:admin:cts:get_contenttypes')
  emit('displayhive:admin:cts:get_layouts')
  emit('displayhive:admin:cts:get_containers')
  emit('displayhive:admin:cts:get_active_design_colors')
})

onUnmounted(() => {
  off('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
  off('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
  off('displayhive:admin:stc:upd_layouts', handleLayoutsList)
  off('displayhive:admin:stc:upd_containers', handleContainersList)
  off('displayhive:admin:stc:active_design_colors', handleActiveDesignColors)
})

const openNewDialog = () => {
  editingContentType.value = null
  showEditDialog.value = true
}

const openEditDialog = (ct: ContentType) => {
  editingContentType.value = ct
  showEditDialog.value = true
}

const deleteContentType = (ct: ContentType) => {
  confirmDanger({
    message: `Are you sure you want to delete "${ct.name}"?`,
    accept: async () => {
      await request('displayhive:admin:cts:delete_contenttype', { id: ct.id }, {
        success: 'Content type deleted',
        error: 'Failed to delete content type',
      })
    },
  })
}

// Reached via a link like /contenttypes?edit=<id>: open that content type.
useOpenFromQuery(() => contentTypes.value, openEditDialog, () => canEdit.value)
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('contenttypes.page')" class="contenttypes-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Content Types page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="contenttypes-page" class="contenttypes-view">
    <PageActions
      :primary="canCreate ? { label: 'New Content Type', icon: 'pi pi-plus', tour: 'contenttypes-new', onClick: openNewDialog } : null"
    />
    <Card>
      <template #content>
        <DataTable
          data-tour="contenttypes-table"
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
          <template #header>
            <div class="dt-header">
              <div class="dt-left">
                <InputText
                  data-tour="contenttypes-filter"
                  v-model="filterText"
                  placeholder="Filter content types..."
                  class="filter-input"
                />
              </div>
            </div>
          </template>
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="name" header="Name" sortable />
          <Column field="description" header="Description">
            <template #body="{ data }">
              {{ data.description ? data.description.substring(0, 50) + (data.description.length > 50 ? '...' : '') : '-' }}
            </template>
          </Column>
          <Column header="Layout" style="width: 160px">
            <template #body="{ data }">
              <a
                v-if="data.layout_name && data.layout_id"
                :href="router.resolve({ name: 'layout-edit', params: { id: data.layout_id } }).href"
                class="layout-link"
                @click.prevent="router.push({ name: 'layout-edit', params: { id: data.layout_id } })"
              >{{ data.layout_name }}</a>
              <span v-else-if="data.layout_name">{{ data.layout_name }}</span>
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
    <Dialog v-model:visible="showCopyDialog" modal :style="{ width: '400px' }">
      <template #header>
        <DialogTitle icon="pi-copy" title="Copy Content Type" />
      </template>
      <div class="field">
        <label for="copy-ct-name">New Name</label>
        <InputText id="copy-ct-name" v-model="copyNewName" class="w-full" autofocus @keyup.enter="executeCopyContentType" />
      </div>
      <template #footer>
        <DialogFooter confirm-label="Copy" confirm-icon="pi pi-copy" :disabled="!copyNewName.trim()" @cancel="showCopyDialog = false" @confirm="executeCopyContentType" />
      </template>
    </Dialog>

    <ContentTypeEditDialog
      v-model:visible="showEditDialog"
      :content-type="editingContentType"
      :layouts="layouts"
      :containers="containers"
      :design-palette="designPalette"
    />
  </div>
</template>

<style scoped>
.contenttypes-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* No title text left in the card header — keep the action buttons
   right-aligned instead of collapsing to the start. */
.card-header {
  justify-content: flex-end;
}

.hint {
  color: var(--p-text-muted-color, #888);
  font-size: 0.75rem;
}

.layout-link {
  color: var(--p-text-color, #333);
  text-decoration: none;
}

.layout-link:hover {
  text-decoration: underline;
}
</style>
