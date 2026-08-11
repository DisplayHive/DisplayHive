<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useScreengroupsStore } from '../stores/screengroups'
import { useScreensStore } from '../stores/screens'
import { useContentStore } from '../stores/content'
import { useRightsStore } from '../stores/rights'
import type { Screengroup, Content } from '../types/models'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import Card from 'primevue/card'
import Badge from 'primevue/badge'
import MultiSelect from 'primevue/multiselect'

// Dialog-local screen shape (backend sends flat is_online, not nested in attached_device)
interface DialogScreen {
  id: number
  name: string
  resolution?: string
  is_online?: boolean
}

const toast = useToast()
const confirm = useConfirm()
const { on, off } = useSocket()
const screengroupsStore = useScreengroupsStore()
const screensStore = useScreensStore()
const contentStore = useContentStore()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('screengroups.create'))
const canRename = computed(() => rightsStore.can('screengroups.rename'))
const canDelete = computed(() => rightsStore.can('screengroups.delete'))
const canManageScreens = computed(() => rightsStore.can('screengroups.manage_screens'))
const canManageContent = computed(() => rightsStore.can('screengroups.manage_content'))

const filterText = ref('')

// Edit/Create dialog
const isSaving = ref(false)
const showEditDialog = ref(false)
const isNew = ref(false)
const editForm = ref({
  id: null as number | null,
  name: '',
})

// Screens management dialog
const showScreensDialog = ref(false)
const selectedScreenGroup = ref<Screengroup | null>(null)
const assignedScreens = ref<DialogScreen[]>([])
const availableScreens = ref<DialogScreen[]>([])
const screensLoading = ref(false)
const assignedScreensFilter = ref('')
const availableScreensFilter = ref('')
const screensPerPage = 10

// Content management dialog
const showContentDialog = ref(false)
const assignedContent = ref<Content[]>([])
const availableContent = ref<Content[]>([])
const contentLoading = ref(false)
const assignedContentFilter = ref('')
const availableContentFilter = ref('')
const contentPerPage = 10

const filteredScreenGroups = computed(() => {
  const visible = screengroupsStore.screengroups.filter((sg) => !sg.is_one_screen)
  if (!filterText.value) return visible
  const search = filterText.value.toLowerCase()
  return visible.filter((sg) => sg.name?.toLowerCase().includes(search))
})

const filteredAssignedScreens = computed(() => {
  if (!assignedScreensFilter.value) return assignedScreens.value
  const search = assignedScreensFilter.value.toLowerCase()
  return assignedScreens.value.filter((s) => s.name?.toLowerCase().includes(search))
})

const filteredAvailableScreens = computed(() => {
  if (!availableScreensFilter.value) return availableScreens.value
  const search = availableScreensFilter.value.toLowerCase()
  return availableScreens.value.filter((s) => s.name?.toLowerCase().includes(search))
})

const filteredAssignedContent = computed(() => {
  if (!assignedContentFilter.value) return assignedContent.value
  const search = assignedContentFilter.value.toLowerCase()
  return assignedContent.value.filter((c) => c.title?.toLowerCase().includes(search))
})

const filteredAvailableContent = computed(() => {
  if (!availableContentFilter.value) return availableContent.value
  const search = availableContentFilter.value.toLowerCase()
  return availableContent.value.filter((c) => c.title?.toLowerCase().includes(search))
})

// Dialog-specific: receives assigned screens for the open screengroup
const handleScreenGroupScreens = (data: any) => {
  if (data && data.screens) {
    assignedScreens.value = data.screens.map((s: any) => ({
      id: s.id,
      name: s.name,
      resolution: s.resolution || 'n/a',
      is_online: s.is_online ?? false,
    }))
    const assignedIds = new Set(assignedScreens.value.map((s) => s.id))
    availableScreens.value = screensStore.screens
      .filter((s) => !assignedIds.has(s.id))
      .map((s) => ({
        id: s.id,
        name: s.name,
        resolution: s.resolution || 'n/a',
        is_online: s.attached_device?.is_online ?? false,
      }))
  }
  screensLoading.value = false
}

// Dialog-specific: receives assigned content for the open screengroup
const handleScreenGroupContent = (data: any) => {
  if (data && data.content) {
    assignedContent.value = data.content.map((c: any) => ({
      id: c.id,
      title: c.title,
      contenttype_name: c.type || c.contenttype_name,
    }))
    const assignedIds = new Set(assignedContent.value.map((c) => c.id))
    availableContent.value = contentStore.content.filter((c) => !assignedIds.has(c.id))
  }
  contentLoading.value = false
}

const handleScreenGroupCreated = (data: any) => {
  if (data.success) {
    toast.add({ severity: 'success', summary: 'Success', detail: 'Screen group created', life: 3000 })
    screengroupsStore.fetch()
  } else {
    toast.add({ severity: 'error', summary: 'Error', detail: data.error || 'Failed to create screen group', life: 5000 })
  }
}

const handleScreenGroupDeleted = (data: any) => {
  if (data.success) {
    toast.add({ severity: 'success', summary: 'Success', detail: 'Screen group deleted', life: 3000 })
    screengroupsStore.fetch()
  } else {
    toast.add({ severity: 'error', summary: 'Error', detail: data.error || 'Failed to delete screen group', life: 5000 })
  }
}

onMounted(() => {
  on('displayhive:admin:stc:screengroup_screens_data', handleScreenGroupScreens)
  on('displayhive:admin:stc:screengroup_content_data', handleScreenGroupContent)
  on('displayhive:admin:stc:screengroup_created', handleScreenGroupCreated)
  on('displayhive:admin:stc:screengroup_deleted', handleScreenGroupDeleted)
  screengroupsStore.fetch()
  screensStore.fetch()
  contentStore.fetch()
})

onUnmounted(() => {
  off('displayhive:admin:stc:screengroup_screens_data', handleScreenGroupScreens)
  off('displayhive:admin:stc:screengroup_content_data', handleScreenGroupContent)
  off('displayhive:admin:stc:screengroup_created', handleScreenGroupCreated)
  off('displayhive:admin:stc:screengroup_deleted', handleScreenGroupDeleted)
})

const refreshData = () => screengroupsStore.fetch()

const openNewDialog = () => {
  isNew.value = true
  editForm.value = { id: null, name: '' }
  showEditDialog.value = true
}

const openEditDialog = (sg: Screengroup) => {
  isNew.value = false
  editForm.value = { id: sg.id, name: sg.name }
  showEditDialog.value = true
}

const closeDialog = () => { showEditDialog.value = false }

const saveScreenGroup = (keepOpen = false) => {
  if (!editForm.value.name.trim()) {
    toast.add({ severity: 'warn', summary: 'Warning', detail: 'Name is required', life: 3000 })
    return
  }
  isSaving.value = true
  try {
    if (isNew.value) {
      screengroupsStore.createScreenGroup(editForm.value.name)
    } else {
      screengroupsStore.renameScreenGroup(editForm.value.id!, editForm.value.name)
      toast.add({ severity: 'success', summary: 'Success', detail: 'Screen group updated', life: 3000 })
      screengroupsStore.fetch()
    }
    if (!keepOpen) showEditDialog.value = false
  } finally {
    isSaving.value = false
  }
}

const deleteScreenGroup = (sg: Screengroup) => {
  confirm.require({
    message: `Are you sure you want to delete "${sg.name}"? This will only work if the group has no screens or content.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => { screengroupsStore.deleteScreenGroup(sg.id) },
  })
}

const openScreensDialog = (sg: Screengroup) => {
  selectedScreenGroup.value = sg
  assignedScreens.value = []
  availableScreens.value = []
  screensLoading.value = true
  assignedScreensFilter.value = ''
  availableScreensFilter.value = ''
  showScreensDialog.value = true
  screengroupsStore.getScreenGroupScreens(sg.id)
}

const closeScreensDialog = () => {
  showScreensDialog.value = false
  selectedScreenGroup.value = null
  assignedScreens.value = []
}

const removeScreenFromGroup = (screen: DialogScreen) => {
  if (!selectedScreenGroup.value) return
  screengroupsStore.removeScreenFromGroup(selectedScreenGroup.value.id, screen.id)
  assignedScreens.value = assignedScreens.value.filter((s) => s.id !== screen.id)
  availableScreens.value.push(screen)
  screengroupsStore.fetch()
}

const addScreenToGroup = (screen: DialogScreen) => {
  if (!selectedScreenGroup.value) return
  screengroupsStore.addScreenToGroup(selectedScreenGroup.value.id, screen.id)
  availableScreens.value = availableScreens.value.filter((s) => s.id !== screen.id)
  assignedScreens.value.push(screen)
  screengroupsStore.fetch()
}

const removeAllScreensFromGroup = () => {
  if (!selectedScreenGroup.value) return
  confirm.require({
    message: `Remove ALL screens from "${selectedScreenGroup.value.name}"?`,
    header: 'Confirm Remove All',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      screengroupsStore.removeAllScreensFromGroup(selectedScreenGroup.value!.id)
      assignedScreens.value = []
      screengroupsStore.fetch()
    },
  })
}

const openContentDialog = (sg: Screengroup) => {
  selectedScreenGroup.value = sg
  assignedContent.value = []
  availableContent.value = []
  contentLoading.value = true
  assignedContentFilter.value = ''
  availableContentFilter.value = ''
  showContentDialog.value = true
  screengroupsStore.getScreenGroupContent(sg.id)
}

const closeContentDialog = () => {
  showContentDialog.value = false
  selectedScreenGroup.value = null
  assignedContent.value = []
  availableContent.value = []
}

const removeContentFromGroup = (content: Content) => {
  if (!selectedScreenGroup.value) return
  screengroupsStore.removeContentFromGroup(selectedScreenGroup.value.id, content.id)
  assignedContent.value = assignedContent.value.filter((c) => c.id !== content.id)
  availableContent.value.push(content)
  screengroupsStore.fetch()
}

const addContentToGroup = (content: Content) => {
  if (!selectedScreenGroup.value) return
  screengroupsStore.addContentToGroup(selectedScreenGroup.value.id, content.id)
  availableContent.value = availableContent.value.filter((c) => c.id !== content.id)
  assignedContent.value.push(content)
  screengroupsStore.fetch()
}

const removeAllContentFromGroup = () => {
  if (!selectedScreenGroup.value) return
  confirm.require({
    message: `Remove ALL content from "${selectedScreenGroup.value.name}"?`,
    header: 'Confirm Remove All',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      screengroupsStore.removeAllContentFromGroup(selectedScreenGroup.value!.id)
      availableContent.value.push(...assignedContent.value)
      assignedContent.value = []
      screengroupsStore.fetch()
    },
  })
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('screengroups.page')" class="screengroups-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Screen Groups page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="screengroups-view">
    <Card>
      <template #content>
        <div class="filter-bar">
          <InputText v-model="filterText" placeholder="Filter screen groups..." class="filter-input" />
          <div class="header-actions">
            <Button v-if="canCreate" icon="pi pi-plus" label="New Screen Group" @click="openNewDialog" size="small" />
            <Button icon="pi pi-refresh" @click="refreshData" size="small" outlined />
          </div>
        </div>

        <DataTable
          :value="filteredScreenGroups"
          :loading="screengroupsStore.loading"
          sortField="name"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="filteredScreenGroups.length > 10"
          :rows="10"
        >
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="name" header="Name" sortable />
          <Column header="Screens" style="width: 120px">
            <template #body="{ data }">
              <Badge
                :value="data.screens_count"
                severity="secondary"
                class="clickable-badge"
                @click="openScreensDialog(data)"
                title="Manage screens"
              />
            </template>
          </Column>
          <Column header="Content" style="width: 120px">
            <template #body="{ data }">
              <Badge
                :value="data.content_count"
                severity="info"
                class="clickable-badge"
                @click="openContentDialog(data)"
                title="Manage content"
              />
            </template>
          </Column>
          <Column header="Actions" style="width: 150px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button v-if="canRename" icon="pi pi-pencil" @click="openEditDialog(data)" size="small" outlined title="Edit" />
                <Button
                  v-if="canDelete && data.screens_count === 0 && data.content_count === 0"
                  icon="pi pi-trash"
                  @click="deleteScreenGroup(data)"
                  size="small"
                  severity="danger"
                  outlined
                  title="Delete"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Edit/Create Dialog -->
    <Dialog
      v-model:visible="showEditDialog"
      :header="isNew ? 'New Screen Group' : 'Edit Screen Group'"
      modal
      :style="{ width: '500px' }"
    >
      <div class="dialog-content">
        <div class="field">
          <label for="sg-name">Name</label>
          <InputText id="sg-name" v-model="editForm.name" class="w-full" />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="closeDialog" text :disabled="isSaving" />
        <Button v-if="!isNew" label="Update" severity="secondary" outlined @click="saveScreenGroup(true)" :loading="isSaving" :disabled="isSaving" />
        <Button label="Save" @click="saveScreenGroup()" :loading="isSaving" :disabled="isSaving" />
      </template>
    </Dialog>

    <!-- Screens Management Dialog -->
    <Dialog
      v-model:visible="showScreensDialog"
      :header="`Screens in ${selectedScreenGroup?.name || ''}`"
      modal
      :style="{ width: '900px', maxHeight: '90vh' }"
    >
      <div class="dialog-content">
        <div v-if="screensLoading" class="loading-state">
          <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
          <p>Loading screens...</p>
        </div>
        <div v-else class="screens-container">
          <!-- Assigned Screens Section -->
          <div class="screens-section">
            <h6 class="section-title">Assigned Screens</h6>
            <InputText
              v-model="assignedScreensFilter"
              placeholder="Filter assigned screens..."
              class="w-full mb-3"
            />
            <div v-if="filteredAssignedScreens.length === 0" class="empty-state">
              <p class="text-muted">No assigned screens{{ assignedScreensFilter ? ' matching filter' : '' }}.</p>
            </div>
            <div v-else>
              <DataTable :value="filteredAssignedScreens" sortField="name" :sortOrder="1" :paginator="filteredAssignedScreens.length > screensPerPage" :rows="screensPerPage" size="small" responsiveLayout="scroll">
                <Column field="name" header="Name" />
                <Column field="resolution" header="Resolution" style="width:160px" />
                <Column header="Online" style="width:120px">
                  <template #body="{ data }">
                    <Badge :value="data.is_online ? 'Online' : 'Offline'" :severity="data.is_online ? 'success' : 'secondary'" class="online-badge" />
                  </template>
                </Column>
                <Column header="Actions" style="width:120px">
                  <template #body="{ data }">
                    <Button v-if="canManageScreens" icon="pi pi-minus" @click="removeScreenFromGroup(data)" size="small" severity="danger" text title="Remove from group" />
                  </template>
                </Column>
              </DataTable>
            </div>
          </div>

          <div class="divider"></div>

          <!-- Available Screens Section -->
          <div class="screens-section">
            <h6 class="section-title">Not Assigned Screens</h6>
            <InputText
              v-model="availableScreensFilter"
              placeholder="Filter available screens..."
              class="w-full mb-3"
            />
            <div v-if="filteredAvailableScreens.length === 0" class="empty-state">
              <p class="text-muted">No available screens{{ availableScreensFilter ? ' matching filter' : '' }}.</p>
            </div>
            <div v-else>
              <DataTable :value="filteredAvailableScreens" sortField="name" :sortOrder="1" :paginator="filteredAvailableScreens.length > screensPerPage" :rows="screensPerPage" size="small" responsiveLayout="scroll">
                <Column field="name" header="Name" />
                <Column field="resolution" header="Resolution" style="width:160px" />
                <Column header="Online" style="width:120px">
                  <template #body="{ data }">
                    <Badge :value="data.is_online ? 'Online' : 'Offline'" :severity="data.is_online ? 'success' : 'secondary'" class="online-badge" />
                  </template>
                </Column>
                <Column header="Actions" style="width:120px">
                  <template #body="{ data }">
                    <Button v-if="canManageScreens" icon="pi pi-plus" @click="addScreenToGroup(data)" size="small" severity="success" text title="Add to group" />
                  </template>
                </Column>
              </DataTable>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <Button
          v-if="canManageScreens && assignedScreens.length > 0"
          label="Remove All"
          @click="removeAllScreensFromGroup"
          severity="danger"
          outlined
          size="small"
        />
        <Button label="Close" @click="closeScreensDialog" />
      </template>
    </Dialog>

    <!-- Content Management Dialog -->
    <Dialog
      v-model:visible="showContentDialog"
      :header="`Content in ${selectedScreenGroup?.name || ''}`"
      modal
      :style="{ width: '900px', maxHeight: '90vh' }"
    >
      <div class="dialog-content">
        <div v-if="contentLoading" class="loading-state">
          <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
          <p>Loading content...</p>
        </div>
        <div v-else class="content-container">
          <!-- Assigned Content Section -->
          <div class="content-section">
            <h6 class="section-title">Assigned Content</h6>
            <InputText
              v-model="assignedContentFilter"
              placeholder="Filter assigned content..."
              class="w-full mb-3"
            />
            <div v-if="filteredAssignedContent.length === 0" class="empty-state">
              <p class="text-muted">No assigned content{{ assignedContentFilter ? ' matching filter' : '' }}.</p>
            </div>
            <div v-else>
              <DataTable :value="filteredAssignedContent" :paginator="filteredAssignedContent.length > contentPerPage" :rows="contentPerPage" size="small" responsiveLayout="scroll">
                <Column field="title" header="Title" />
                <Column field="contenttype_name" header="Type" style="width:180px" />
                <Column header="Actions" style="width:120px">
                  <template #body="{ data }">
                    <Button v-if="canManageContent" icon="pi pi-minus" @click="removeContentFromGroup(data)" size="small" severity="danger" text title="Remove from group" />
                  </template>
                </Column>
              </DataTable>
            </div>
          </div>

          <div class="divider"></div>

          <!-- Available Content Section -->
          <div class="content-section">
            <h6 class="section-title">Not Assigned Content</h6>
            <InputText
              v-model="availableContentFilter"
              placeholder="Filter available content..."
              class="w-full mb-3"
            />
            <div v-if="filteredAvailableContent.length === 0" class="empty-state">
              <p class="text-muted">No available content{{ availableContentFilter ? ' matching filter' : '' }}.</p>
            </div>
            <div v-else>
              <DataTable :value="filteredAvailableContent" :paginator="filteredAvailableContent.length > contentPerPage" :rows="contentPerPage" size="small" responsiveLayout="scroll">
                <Column field="title" header="Title" />
                <Column field="contenttype_name" header="Type" style="width:180px" />
                <Column header="Actions" style="width:120px">
                  <template #body="{ data }">
                    <Button v-if="canManageContent" icon="pi pi-plus" @click="addContentToGroup(data)" size="small" severity="success" text title="Add to group" />
                  </template>
                </Column>
              </DataTable>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <Button
          v-if="canManageContent && assignedContent.length > 0"
          label="Remove All"
          @click="removeAllContentFromGroup"
          severity="danger"
          outlined
          size="small"
        />
        <Button label="Close" @click="closeContentDialog" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.screengroups-view {
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

.screens-container {
}

.content-container {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-height: 70vh;
  overflow-y: auto;
}

.screens-section,
.content-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.section-title {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 0.5rem 0;
  color: #333;
}

.divider {
  height: 1px;
  background: #e0e0e0;
  margin: 1rem 0;
}

.screens-list,
.content-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.screen-item,
.content-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background: #f9f9f9;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
}

.screen-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 1rem;
}

.screen-main {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex: 1;
}

.screen-info,
.content-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.content-info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  gap: 1rem;
}

.content-main {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex: 1;
}

.content-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.screen-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.screen-name,
.content-title,
.content-name {
  font-weight: 600;
  font-size: 0.95rem;
}

.screen-resolution,
.content-type {
  font-size: 0.85rem;
  color: #666;
}

.online-badge {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
}

.pagination-container {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #e0e0e0;
}

.pagination-info {
  font-size: 0.875rem;
  color: #666;
}
</style>
