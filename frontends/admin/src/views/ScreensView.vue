<script setup lang="ts">
import ScreenCreateDialog from '../components/screens/ScreenCreateDialog.vue'
import ScreenEditDialog from '../components/screens/ScreenEditDialog.vue'
import PageActions from '../components/ui/PageActions.vue'
import RouteLink from '../components/ui/RouteLink.vue'
import { links } from '../utils/links'
import { useOpenFromQuery } from '../composables/useOpenFromQuery'
import { ref, computed, onMounted } from 'vue'
import { useAck } from '../composables/useAck'
import { useOnlineFilter } from '../composables/useOnlineFilter'
import { openDevicePreview } from '../composables/useDevicePreview'
import { useMaximizedFilter, isWindowed, isFullscreen } from '../composables/useMaximizedFilter'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useConfirmAction } from '../composables/useConfirmAction'
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
import Tag from 'primevue/tag'
import Card from 'primevue/card'
import { useRoute, useRouter } from 'vue-router'

const toast = useToast()
const confirm = useConfirm()
const { confirmDanger } = useConfirmAction()
const { request } = useAck()
const screensStore = useScreensStore()
const screengroupsStore = useScreengroupsStore()
const devicesStore = useDevicesStore()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('screens.create'))
const canEdit = computed(() => rightsStore.can('screens.edit'))
const canDelete = computed(() => rightsStore.can('screens.delete'))
const canMonitor = computed(() => rightsStore.can('screens.monitor'))
const canPreview = computed(() => rightsStore.can('device.preview'))
const canResize = computed(() => rightsStore.can('screens.resize'))
const canDebug = computed(() => rightsStore.can('screens.debug'))
const canReload = computed(() => rightsStore.can('screens.reload'))
const canReloadAll = computed(() => rightsStore.can('screens.reload_all'))

const filterText = ref('')

// ?filter=find|debug (from the dashboard tiles) narrows the list to screens in
// that state; the chip above the table clears it again.
const route = useRoute()
const router = useRouter()
const statusFilter = computed<'find' | 'debug' | null>(() => {
  const f = route.query.filter
  return f === 'find' || f === 'debug' ? f : null
})
const clearStatusFilter = () => {
  const rest = { ...route.query }
  delete rest.filter
  router.replace({ query: rest })
}

const { showOnline, showOffline, toggleShowOnline, toggleShowOffline, applyOnlineFilter } = useOnlineFilter()
const { showWindowed, showFullscreen, toggleShowWindowed, toggleShowFullscreen, applyMaximizedFilter } = useMaximizedFilter()

const onlineCount = computed(() => screensStore.onlineCount)
const offlineCount = computed(() => screensStore.offlineCount)

const showCreateDialog = ref(false)
const showRenameDialog = ref(false)
const renamingScreen = ref<Screen | null>(null)

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
  if (statusFilter.value === 'find') list = list.filter((s) => !!s.attached_device?.find)
  if (statusFilter.value === 'debug') list = list.filter((s) => !!s.debug && s.monitoring_enabled !== false)
  list = applyOnlineFilter(list, (s) => !!s.attached_device?.is_online)
  return applyMaximizedFilter(list)
})

onMounted(() => {
  screensStore.fetch()
  screengroupsStore.fetch()
})


const openCreateDialog = () => {
  showCreateDialog.value = true
}

const openRenameDialog = (screen: Screen) => {
  renamingScreen.value = screen
  showRenameDialog.value = true
}

const toggleDebug = async (screen: Screen) => {
  const next = !screen.debug
  const previous = screen.debug
  screen.debug = next
  const ack = await request('displayhive:screens:cts:toggle_debug', { screen_id: screen.id, debug: next }, {
    success: `Debug ${next ? 'enabled' : 'disabled'} for ${screen.name}`,
    error: 'Could not change debug mode',
  })
  if (!ack) screen.debug = previous
}

const reloadScreen = async (screen: Screen) => {
  await request('displayhive:screens:cts:reload_screen', { name: screen.name }, { success: `Reload command sent to ${screen.name}`, error: 'Could not reload the screen' })
}

// A screen previews via its attached device's live connection — content is
// only ever pushed to a screen's actual devices (see _emit_to_screen in
// application/socketio_handlers/upd_content.py), there's no standalone
// "preview a screen with no device" delivery path. So this is disabled,
// not hidden, whenever that device or its key isn't available — hiding it
// would look like Screens can't be previewed at all, when really it's
// just this one screen's setup.
const previewUnavailableReason = (screen: Screen): string | null => {
  if (!screen.attached_device) return 'No device is attached to this screen'
  if (!screen.attached_device.devicekey) return 'Device key is not visible to this account (requires device.showkey)'
  return null
}

const previewScreen = (screen: Screen) => {
  const reason = previewUnavailableReason(screen)
  if (reason) {
    toast.add({ severity: 'error', summary: 'Cannot preview', detail: reason, life: 4000 })
    return
  }
  try {
    openDevicePreview(screen.attached_device!.devicekey!)
  } catch (e) {
    console.error('[ScreensView] previewScreen error', e)
  }
}

const reloadAllScreens = () => {
  confirm.require({
    message: 'Are you sure you want to reload all screens?',
    header: 'Confirm Reload All',
    icon: 'pi pi-exclamation-triangle',
    accept: async () => {
      await request('displayhive:screens:cts:reload_all_screens', {}, { success: 'Reload command sent to all screens', error: 'Could not reload the screens' })
    },
  })
}

const deleteScreen = (screen: Screen) => {
  confirmDanger({
    message: `Are you sure you want to delete screen "${screen.name}"?`,
    accept: async () => {
      await request('displayhive:screens:cts:delete_screen', { screen_id: screen.id }, { success: 'Screen deleted', error: 'Failed to delete screen' })
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

const toggleMonitoring = async (screen: Screen) => {
  await request('displayhive:screens:cts:toggle_monitoring', { screen_id: screen.id }, { error: 'Could not change monitoring' })
}

const resetScreenSize = async (screen: Screen) => {
  await request('displayhive:screens:cts:reset_screen_size', { screen_id: screen.id }, { success: `Screen size reset for ${screen.name}`, error: 'Could not reset the size' })
}

// Reached via a link like /screens?edit=<id>: open that screen's dialog.
useOpenFromQuery(() => screensStore.screens, openRenameDialog, () => canEdit.value)
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('screens.page')" class="screens-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Screens page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="screens-page" class="screens-view">
    <PageActions
      :primary="canCreate ? { label: 'Add Screen', icon: 'pi pi-plus', tour: 'screens-new', onClick: openCreateDialog } : null"
      :secondary="[canReloadAll && { label: 'Reload All', icon: 'pi pi-refresh', tour: 'screens-reload-all', title: 'Reload every connected screen', onClick: reloadAllScreens }]"
    />
    <Card>
      <template #content>
        <DataTable
          data-tour="screens-table"
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
                <InputText
                  v-model="filterText"
                  data-tour="screens-filter"
                  placeholder="Filter screens..."
                  class="filter-input"
                />
                <Tag
                  v-if="statusFilter"
                  severity="info"
                  class="clickable-tag"
                  :value="statusFilter === 'find' ? 'Only screens in find mode ✕' : 'Only screens in debug mode ✕'"
                  title="Show all screens"
                  @click="clearStatusFilter"
                />
              </div>
              <div class="dt-right" data-tour="screens-status-filters">
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
          <Column field="aspect_ratio" header="Ratio" sortable />
          <Column header="Status" style="width: 150px">
            <template #body="{ data }">
              <RouteLink v-if="data.attached_device && rightsStore.can('device.page')" :to="links.device(data.attached_device.id)" title="Open this screen's device">
                <Tag :severity="getStatusSeverity(data)" :value="getStatusText(data)" />
              </RouteLink>
              <Tag v-else :severity="getStatusSeverity(data)" :value="getStatusText(data)" />
            </template>
          </Column>
          <Column header="Actions" style="width: 340px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button
                  v-if="canPreview"
                  data-tour="screens-preview-button"
                  icon="pi pi-play"
                  @click="previewScreen(data)"
                  size="small"
                  outlined
                  :disabled="!!previewUnavailableReason(data)"
                  :title="previewUnavailableReason(data) || 'Preview'"
                />
                <Button
                  v-if="canEdit"
                  data-tour="screens-row-rename"
                  icon="pi pi-pencil"
                  @click="openRenameDialog(data)"
                  size="small"
                  outlined
                  title="Rename"
                />
                <Button
                  v-if="canReload"
                  data-tour="screens-row-reload"
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
                  data-tour="screens-row-debug"
                  icon="pi pi-wrench"
                  @click="toggleDebug(data)"
                  size="small"
                  :severity="data.debug ? 'success' : 'secondary'"
                  outlined
                  title="Toggle Debug"
                />
                <Button
                  v-if="canMonitor"
                  data-tour="screens-row-monitor"
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

    <ScreenCreateDialog v-model:visible="showCreateDialog" />
    <ScreenEditDialog v-model:visible="showRenameDialog" :screen="renamingScreen" />
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
  /* Windowed/Fullscreen sits left of Online/Offline, with a wider gap
     between the two groups than the 0.5rem used within each group
     (.filter-row) — keeps the two filter groups visually distinct. */
  gap: 1.5rem;
}

.filter-row {
  display: flex;
  gap: 0.5rem;
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
