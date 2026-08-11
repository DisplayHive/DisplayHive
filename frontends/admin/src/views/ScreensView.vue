<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useOnlineFilter } from '../composables/useOnlineFilter'
import { useMaximizedFilter, isWindowed, isFullscreen } from '../composables/useMaximizedFilter'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useScreensStore } from '../stores/screens'
import { useScreengroupsStore } from '../stores/screengroups'
import { useDevicesStore } from '../stores/devices'
import { useRightsStore } from '../stores/rights'
import type { Screen } from '../types/models'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import Card from 'primevue/card'
import Checkbox from 'primevue/checkbox'

const toast = useToast()
const confirm = useConfirm()
const { on, off, emit } = useSocket()
const screensStore = useScreensStore()
const screengroupsStore = useScreengroupsStore()
const devicesStore = useDevicesStore()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('screens.create'))
const canEdit = computed(() => rightsStore.can('screens.edit'))
const canDelete = computed(() => rightsStore.can('screens.delete'))
const canMonitor = computed(() => rightsStore.can('screens.monitor'))
const canResize = computed(() => rightsStore.can('screens.resize'))
const canDebug = computed(() => rightsStore.can('screens.debug'))
const canReload = computed(() => rightsStore.can('screens.reload'))
const canReloadAll = computed(() => rightsStore.can('screens.reload_all'))

const filterText = ref('')

const { showOnline, showOffline, toggleShowOnline, toggleShowOffline, applyOnlineFilter } = useOnlineFilter()
const { showWindowed, showFullscreen, toggleShowWindowed, toggleShowFullscreen, applyMaximizedFilter } = useMaximizedFilter()

const onlineCount = computed(() => screensStore.onlineCount)
const offlineCount = computed(() => screensStore.offlineCount)

// Create screen dialog
const isCreating = ref(false)
const showCreateDialog = ref(false)
const createForm = ref({
  name: '',
  width: null as string | null,
  height: null as string | null,
})

// Rename screen dialog
const isRenaming = ref(false)
const showRenameDialog = ref(false)
const renamingScreen = ref<Screen | null>(null)
const renameForm = ref({
  name: '',
  screengroup_ids: [] as number[],
})

const windowedCount = computed(() => screensStore.screens.filter(isWindowed).length)
const fullscreenCount = computed(() => screensStore.screens.filter(isFullscreen).length)

const filteredScreens = computed(() => {
  let list = screensStore.screens.slice()
  const search = (filterText.value || '').trim().toLowerCase()
  if (search) {
    list = list.filter((s) =>
      (s.name && s.name.toLowerCase().includes(search)) ||
      (s.resolution && s.resolution.toLowerCase().includes(search))
    )
  }
  list = applyOnlineFilter(list, (s) => !!s.attached_device?.is_online)
  return applyMaximizedFilter(list)
})

// Dialog-specific: receives current screengroup membership for the screen being renamed
const handleScreengroupsData = (data: { all_screengroups: any[]; current_screengroups: number[] }) => {
  if (renamingScreen.value && data.current_screengroups) {
    renameForm.value.screengroup_ids = data.current_screengroups
  }
}

const handleScreenDeleted = (data: { success: boolean; error?: string }) => {
  if (data.success) {
    toast.add({ severity: 'success', summary: 'Success', detail: 'Screen deleted', life: 3000 })
  } else {
    toast.add({ severity: 'error', summary: 'Error', detail: data.error || 'Failed to delete screen', life: 5000 })
  }
}

onMounted(() => {
  on('displayhive:screens:stc:screen_screengroups', handleScreengroupsData)
  on('displayhive:screens:stc:screen_deleted', handleScreenDeleted)
  screensStore.fetch()
  screengroupsStore.fetch()
})

onUnmounted(() => {
  off('displayhive:screens:stc:screen_screengroups', handleScreengroupsData)
  off('displayhive:screens:stc:screen_deleted', handleScreenDeleted)
})

const refreshScreens = () => screensStore.fetch()

const openCreateDialog = () => {
  createForm.value = { name: '', width: null, height: null }
  showCreateDialog.value = true
}

const createScreen = async () => {
  if (!createForm.value.name) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Name is required', life: 3000 })
    return
  }
  isCreating.value = true
  try {
    const payload: any = { name: createForm.value.name }
    if (createForm.value.width && createForm.value.height) {
      payload.width = createForm.value.width
      payload.height = createForm.value.height
    }
    screensStore.createScreen(payload)
    toast.add({ severity: 'success', summary: 'Success', detail: 'Screen created', life: 3000 })
    showCreateDialog.value = false
  } finally {
    isCreating.value = false
  }
}

const openRenameDialog = (screen: Screen) => {
  renamingScreen.value = screen
  renameForm.value = {
    name: screen.name,
    screengroup_ids: [],
  }
  emit('displayhive:screens:cts:get_screen_screengroups', { screen_id: screen.id })
  showRenameDialog.value = true
}

const saveRename = async (keepOpen = false) => {
  if (!renamingScreen.value) return
  isRenaming.value = true
  try {
    screensStore.renameScreen({
      id: renamingScreen.value.id,
      old_name: renamingScreen.value.name,
      new_name: renameForm.value.name,
      screengroup_ids: renameForm.value.screengroup_ids,
    })
    toast.add({ severity: 'success', summary: 'Screen saved', detail: renameForm.value.name, life: 3000 })
    if (!keepOpen) showRenameDialog.value = false
  } finally {
    isRenaming.value = false
  }
}

const toggleDebug = (screen: Screen) => {
  const next = !screen.debug
  screensStore.toggleDebug(screen.id, next)
  toast.add({ severity: 'info', summary: 'Debug Mode', detail: `Debug ${next ? 'enabled' : 'disabled'} for ${screen.name}`, life: 2000 })
}

const reloadScreen = (screen: Screen) => {
  screensStore.reloadScreen(screen.name)
  toast.add({ severity: 'info', summary: 'Reloading', detail: `Reload command sent to ${screen.name}`, life: 2000 })
}

const reloadAllScreens = () => {
  confirm.require({
    message: 'Are you sure you want to reload all screens?',
    header: 'Confirm Reload All',
    icon: 'pi pi-exclamation-triangle',
    accept: () => {
      screensStore.reloadAll()
      toast.add({ severity: 'info', summary: 'Reloading', detail: 'Reload command sent to all screens', life: 3000 })
    },
  })
}

const deleteScreen = (screen: Screen) => {
  confirm.require({
    message: `Are you sure you want to delete screen "${screen.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      screensStore.deleteScreen(screen.id)
      toast.add({ severity: 'success', summary: 'Success', detail: 'Screen deleted', life: 3000 })
    },
  })
}

const getStatusSeverity = (screen: Screen): 'success' | 'danger' => {
  return screen.attached_device?.is_online ? 'success' : 'danger'
}

const getStatusText = (screen: Screen): string => {
  if (screen.attached_device?.is_online) return 'Online'
  return screen.timestr || 'Offline'
}

const toggleFind = (screen: Screen) => {
  if (!screen.attached_device) return
  devicesStore.findDevice(screen.attached_device.id)
}

const toggleMonitoring = (screen: Screen) => {
  screensStore.toggleMonitoring(screen.id)
}

const resetScreenSize = (screen: Screen) => {
  screensStore.resetScreenSize(screen.id)
  toast.add({ severity: 'info', summary: 'Size reset', detail: `Screen size reset for ${screen.name}`, life: 2000 })
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('screens.page')" class="screens-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Screens page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="screens-view">
    <Card>
      <template #title>
        <div class="card-header">
          <div class="header-actions">
            <Button
              v-if="canCreate"
              icon="pi pi-plus"
              label="Add Screen"
              @click="openCreateDialog"
              size="small"
            />
            <Button
              v-if="canReloadAll"
              icon="pi pi-refresh"
              label="Reload All"
              @click="reloadAllScreens"
              size="small"
              outlined
            />
            <Button
              icon="pi pi-sync"
              @click="refreshScreens"
              size="small"
              outlined
            />
          </div>
        </div>
      </template>
      <template #content>
        <DataTable
          :value="filteredScreens"
          :loading="screensStore.loading"
          sortField="name"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="filteredScreens.length > 10"
          :rows="10"
          :rowsPerPageOptions="[10, 25, 50]"
          responsiveLayout="scroll"
        >
          <template #header>
            <div class="dt-header">
              <div class="dt-left">
                <InputText v-model="filterText" placeholder="Filter screens..." class="filter-input" />
              </div>
              <div class="dt-right">
                <div class="filter-row">
                  <Tag
                    :severity="showOnline ? 'success' : 'info'"
                    :value="`Online (${onlineCount})`"
                    @click="toggleShowOnline"
                    class="clickable-tag"
                    :aria-pressed="showOnline"
                    :style="{ opacity: showOnline ? 1 : 0.5 }"
                  />
                  <Tag
                    :severity="showOffline ? 'danger' : 'info'"
                    :value="`Offline (${offlineCount})`"
                    @click="toggleShowOffline"
                    class="clickable-tag"
                    :aria-pressed="showOffline"
                    :style="{ opacity: showOffline ? 1 : 0.5 }"
                  />
                </div>
                <div class="filter-row">
                  <Tag
                    severity="warn"
                    :value="`Windowed (${windowedCount})`"
                    @click="toggleShowWindowed"
                    class="clickable-tag"
                    :aria-pressed="showWindowed"
                    :style="{ opacity: showWindowed ? 1 : 0.5 }"
                  />
                  <Tag
                    severity="success"
                    :value="`Fullscreen (${fullscreenCount})`"
                    @click="toggleShowFullscreen"
                    class="clickable-tag"
                    :aria-pressed="showFullscreen"
                    :style="{ opacity: showFullscreen ? 1 : 0.5 }"
                  />
                </div>
              </div>
            </div>
          </template>
          <Column field="name" header="Name" sortable>
            <template #body="{ data }">
              <span class="name-cell">
                <i
                  v-if="isWindowed(data) && canResize"
                  class="pi pi-exclamation-triangle not-maximized-icon"
                  title="Screen not maximized - Click to reset Screensize"
                  @click.stop="resetScreenSize(data)"
                />
                {{ data.name }}
              </span>
            </template>
          </Column>
          <Column field="resolution" header="Resolution" sortable />
          <Column header="Status" style="width: 150px">
            <template #body="{ data }">
              <Tag :severity="getStatusSeverity(data)" :value="getStatusText(data)" />
            </template>
          </Column>
          <Column header="Actions" style="width: 300px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button
                  v-if="canEdit"
                  icon="pi pi-pencil"
                  @click="openRenameDialog(data)"
                  size="small"
                  outlined
                  title="Rename"
                />
                <Button
                  v-if="canReload"
                  icon="pi pi-refresh"
                  @click="reloadScreen(data)"
                  size="small"
                  outlined
                  title="Reload Screen"
                />
                <Button
                  v-if="data.attached_device && data.attached_device.is_online"
                  icon="pi pi-map-marker"
                  @click="toggleFind(data)"
                  size="small"
                  :severity="data.attached_device.find ? 'success' : 'secondary'"
                  outlined
                  title="Locate Device"
                />
                <Button
                  v-if="canDebug"
                  icon="pi pi-wrench"
                  @click="toggleDebug(data)"
                  size="small"
                  :severity="data.debug ? 'success' : 'secondary'"
                  outlined
                  title="Toggle Debug"
                />
                <Button
                  v-if="canMonitor"
                  :icon="data.monitoring_enabled !== false ? 'pi pi-eye' : 'pi pi-eye-slash'"
                  @click="toggleMonitoring(data)"
                  size="small"
                  :severity="data.monitoring_enabled !== false ? 'secondary' : 'warn'"
                  outlined
                  :title="data.monitoring_enabled !== false ? 'Disable online monitoring' : 'Enable online monitoring'"
                />
                <Button
                  v-if="canDelete"
                  icon="pi pi-trash"
                  @click="deleteScreen(data)"
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

    <!-- Create Screen Dialog -->
    <Dialog v-model:visible="showCreateDialog" header="Add Screen" modal :style="{ width: '450px' }">
      <div class="dialog-content">
        <div class="field">
          <label for="create-name">Screen Name</label>
          <InputText id="create-name" v-model="createForm.name" class="w-full" placeholder="e.g. Lobby-Display" />
        </div>
        <div class="field">
          <label for="create-width">Width (optional)</label>
          <InputText id="create-width" v-model="createForm.width" class="w-full" placeholder="1920" type="number" />
        </div>
        <div class="field">
          <label for="create-height">Height (optional)</label>
          <InputText id="create-height" v-model="createForm.height" class="w-full" placeholder="1080" type="number" />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="showCreateDialog = false" text :disabled="isCreating" />
        <Button label="Create" @click="createScreen" :loading="isCreating" :disabled="isCreating" />
      </template>
    </Dialog>

    <!-- Rename Screen Dialog -->
    <Dialog v-model:visible="showRenameDialog" header="Rename Screen" modal :style="{ width: '600px' }">
      <div class="dialog-content">
        <div class="field">
          <label for="rename-name">Screen Name</label>
          <InputText id="rename-name" v-model="renameForm.name" class="w-full" />
        </div>
        <div class="field">
          <label>Screengroups</label>
          <div class="screengroup-checkboxes">
            <div v-for="sg in screengroupsStore.screengroups.filter(sg => !sg.is_one_screen)" :key="sg.id" class="checkbox-item">
              <Checkbox
                :inputId="`sg-${sg.id}`"
                v-model="renameForm.screengroup_ids"
                :value="sg.id"
              />
              <label :for="`sg-${sg.id}`">{{ sg.name }}</label>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="showRenameDialog = false" text :disabled="isRenaming" />
        <Button label="Update" severity="secondary" outlined @click="saveRename(true)" :loading="isRenaming" :disabled="isRenaming" />
        <Button label="Save" @click="saveRename()" :loading="isRenaming" :disabled="isRenaming" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.screens-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* No title text left in the card header — keep the action buttons
   right-aligned instead of collapsing to the start. */
.card-header {
  justify-content: flex-end;
}

.dt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.dt-left,
.dt-right {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.dt-right {
  flex-direction: column;
  align-items: flex-end;
}

.filter-row {
  display: flex;
  gap: 0.5rem;
}

.screengroup-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
  padding: 0.5rem;
  border: 1px solid #dee2e6;
  border-radius: 4px;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.checkbox-item label {
  margin: 0;
  cursor: pointer;
}

.name-cell {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.not-maximized-icon {
  color: orange;
  cursor: pointer;
  flex-shrink: 0;
}

.not-maximized-icon:hover {
  color: darkorange;
}
</style>
