<script setup lang="ts">
import DialogTitle from '../components/DialogTitle.vue'
import { useConfirmAction } from '../composables/useConfirmAction'
import PageActions from '../components/PageActions.vue'
import RouteLink from '../components/RouteLink.vue'
import { links } from '../utils/links'
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useAck } from '../composables/useAck'
import { useToast } from 'primevue/usetoast'
import { useRightsStore } from '../stores/rights'
import type { Layout } from '../types/models'

import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Card from 'primevue/card'
import Dialog from 'primevue/dialog'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'

const router = useRouter()
const toast = useToast()
const { confirmDanger } = useConfirmAction()
const { on, off, emit } = useSocket()
const { request } = useAck()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('layouts.create'))
const canEdit = computed(() => rightsStore.can('layouts.edit'))
const canDelete = computed(() => rightsStore.can('layouts.delete'))

const layouts = ref<Layout[]>([])
const loading = ref(true)
const filterText = ref('')

const filteredLayouts = computed(() => {
  if (!filterText.value) return layouts.value
  const search = filterText.value.toLowerCase()
  return layouts.value.filter(
    (l) =>
      l.name?.toLowerCase().includes(search) ||
      l.description?.toLowerCase().includes(search)
  )
})

const openNewPage = () => router.push({ name: 'layout-new' })
const openEditPage = (l: Layout) => router.push({ name: 'layout-edit', params: { id: l.id } })

const deleteLayout = (l: Layout, onDeleted?: () => void) => {
  if (l.in_use) {
    toast.add({ severity: 'warn', summary: 'Cannot delete', detail: 'This layout is used by a Contenttype — reassign it first.', life: 4000 })
    return
  }
  confirmDanger({
    message: `Are you sure you want to delete layout "${l.name}"?`,
    accept: async () => {
      const ack = await request('displayhive:admin:cts:delete_layout', { id: l.id }, { success: 'Layout deleted', error: 'Delete failed' })
      if (ack) onDeleted?.()
    },
  })
}

// --- Clone: duplicates a Layout as a brand new one, keeping its current set
// of containers (the containers themselves aren't copied — they're shared,
// standalone entities — the new Layout just references the same ones).
const showCopyDialog = ref(false)
const copySource = ref<Layout | null>(null)
const copyNewName = ref('')

const openCopyDialog = (l: Layout) => {
  copySource.value = l
  copyNewName.value = `Copy of ${l.name}`
  showCopyDialog.value = true
}

const executeCopyLayout = async () => {
  if (!copySource.value || !copyNewName.value.trim()) return
  const name = copyNewName.value.trim()
  const ack = await request(
    'displayhive:admin:cts:create_layout',
    {
      name,
      description: copySource.value.description || '',
      container_ids: copySource.value.container_ids || [],
      variations: copySource.value.variations || [],
    },
    { success: `"${name}" created`, error: 'Copy failed' },
  )
  if (ack) {
    showCopyDialog.value = false
    refreshData()
  }
}

// --- Data loading ---------------------------------------------------------

const handleLayoutsList = (data: { data?: Layout[] }) => {
  layouts.value = data?.data || []
  loading.value = false
}

onMounted(() => {
  on('displayhive:admin:stc:upd_layouts', handleLayoutsList)
  refreshData()
})

onUnmounted(() => {
  off('displayhive:admin:stc:upd_layouts', handleLayoutsList)
})

const refreshData = () => {
  loading.value = true
  emit('displayhive:admin:cts:get_layouts')
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('layouts.page')" class="layouts-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Layouts page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="layouts-page" class="layouts-view">
    <PageActions
      :primary="canCreate ? { label: 'New Layout', icon: 'pi pi-plus', tour: 'layouts-new', onClick: openNewPage } : null"
    />
    <Card>
      <template #content>
        <DataTable
          data-tour="layouts-table"
          :value="filteredLayouts"
          :loading="loading"
          sortField="name"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="filteredLayouts.length > 10"
          :rows="10"
          responsiveLayout="scroll"
        >
          <template #header>
            <div class="dt-header">
              <div class="dt-left">
                <InputText
                  v-model="filterText"
                  data-tour="layouts-filter"
                  placeholder="Filter layouts..."
                  class="filter-input"
                />
              </div>
            </div>
          </template>
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="name" header="Name" sortable />
          <Column field="description" header="Description">
            <template #body="{ data }">
              {{ data.description ? data.description.substring(0, 60) + (data.description.length > 60 ? '...' : '') : '-' }}
            </template>
          </Column>
          <Column header="Containers" style="width: 110px">
            <template #body="{ data }">{{ (data.container_ids || []).length }}</template>
          </Column>
          <Column header="Used by" style="width: 200px">
            <template #body="{ data }">
              <template v-if="(data.contenttypes || []).length">
                <template v-for="(ct, i) in data.contenttypes" :key="ct.id">
                  <span v-if="i">, </span>
                  <RouteLink v-if="rightsStore.can('contenttypes.page')" :to="links.contentType(ct.id)" title="Open this content type">{{ ct.name }}</RouteLink>
                  <span v-else>{{ ct.name }}</span>
                </template>
              </template>
              <span v-else class="hint">-</span>
            </template>
          </Column>
          <Column header="Actions" style="width: 180px">
            <template #body="{ data }">
              <div class="action-buttons" data-tour="layouts-row-actions">
                <Button v-if="canEdit" icon="pi pi-pencil" @click="openEditPage(data)" size="small" outlined title="Edit" />
                <Button v-if="canCreate" icon="pi pi-copy" @click="openCopyDialog(data)" size="small" outlined title="Clone" />
                <Button
                  v-if="canDelete"
                  icon="pi pi-trash"
                  @click="deleteLayout(data, refreshData)"
                  size="small"
                  severity="danger"
                  outlined
                  :disabled="data.in_use"
                  :title="data.in_use ? 'Used by a Contenttype — cannot delete' : 'Delete'"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Clone Layout Dialog -->
    <Dialog v-model:visible="showCopyDialog" modal :style="{ width: '400px' }">
      <template #header>
        <DialogTitle icon="pi-copy" title="Clone Layout" />
      </template>
      <div class="field">
        <label for="copy-layout-name">New Name</label>
        <InputText id="copy-layout-name" v-model="copyNewName" class="w-full" autofocus @keyup.enter="executeCopyLayout" />
      </div>
      <template #footer>
        <Button label="Cancel" @click="showCopyDialog = false" text />
        <Button label="Clone" icon="pi pi-copy" @click="executeCopyLayout" :disabled="!copyNewName.trim()" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.layouts-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* No title text left in the card header — keep the action buttons
   right-aligned instead of collapsing to the start. */
.card-header {
  justify-content: flex-end;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
</style>
