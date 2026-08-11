<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
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
const confirm = useConfirm()
const { on, off, emit, emitWithAck } = useSocket()
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
  confirm.require({
    message: `Are you sure you want to delete layout "${l.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      const ack = await emitWithAck<{ ok: boolean; error?: string }>('displayhive:admin:cts:delete_layout', { id: l.id })
      if (ack?.ok) {
        toast.add({ severity: 'success', summary: 'Success', detail: 'Layout deleted', life: 3000 })
        onDeleted?.()
      } else {
        toast.add({ severity: 'error', summary: 'Delete failed', detail: ack?.error || 'Unknown error', life: 4000 })
      }
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
  const ack = await emitWithAck<{ ok: boolean; id?: number; error?: string }>(
    'displayhive:admin:cts:create_layout',
    {
      name,
      description: copySource.value.description || '',
      container_ids: copySource.value.container_ids || [],
    },
  )
  if (ack?.ok) {
    toast.add({ severity: 'success', summary: 'Copied', detail: `"${name}" created`, life: 3000 })
    showCopyDialog.value = false
    refreshData()
  } else {
    toast.add({ severity: 'error', summary: 'Copy failed', detail: ack?.error || 'Unknown error', life: 4000 })
  }
}

// --- Data loading ---------------------------------------------------------

const handleLayoutsList = (data: any) => {
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
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Layouts page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="layouts-view">
    <Card>
      <template #content>
        <div class="filter-bar">
          <InputText v-model="filterText" placeholder="Filter layouts..." class="filter-input" />
          <div class="header-actions">
            <Button v-if="canCreate" icon="pi pi-plus" label="New Layout" @click="openNewPage" size="small" />
            <Button icon="pi pi-refresh" @click="refreshData" size="small" outlined />
          </div>
        </div>

        <DataTable
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
          <Column header="Actions" style="width: 180px">
            <template #body="{ data }">
              <div class="action-buttons">
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
    <Dialog v-model:visible="showCopyDialog" header="Clone Layout" modal :style="{ width: '400px' }">
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

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
</style>
