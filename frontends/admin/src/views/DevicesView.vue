<script setup lang="ts">
import { useConfirmAction } from '../composables/useConfirmAction'
import PageActions from '../components/PageActions.vue'
import RouteLink from '../components/RouteLink.vue'
import { links } from '../utils/links'
import { useOpenFromQuery } from '../composables/useOpenFromQuery'
import { ref, computed, onMounted } from 'vue'
import DeviceAdoptDialog from '../components/devices/DeviceAdoptDialog.vue'
import DeviceRenameDialog from '../components/devices/DeviceRenameDialog.vue'
import DeviceAssignDialog from '../components/devices/DeviceAssignDialog.vue'
import { useOnlineFilter } from '../composables/useOnlineFilter'
import { getScreenBaseUrl, openDevicePreview } from '../composables/useDevicePreview'
import type { Device } from '../types/models'
import { useDevicesStore } from '../stores/devices'
import { useScreensStore } from '../stores/screens'
import { useRightsStore } from '../stores/rights'
import { useToast } from 'primevue/usetoast'
import { useAck } from '../composables/useAck'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import ToggleSwitch from 'primevue/toggleswitch'
import Card from 'primevue/card'
import Popover from 'primevue/popover'

const { request } = useAck()
const toast = useToast()
const { confirmDanger } = useConfirmAction()
const devicesStore = useDevicesStore()
const screensStore = useScreensStore()
const rightsStore = useRightsStore()

const canEnable = computed(() => rightsStore.can('device.enable'))
const canRename = computed(() => rightsStore.can('device.rename'))
const canDelete = computed(() => rightsStore.can('device.delete'))
const canShowKey = computed(() => rightsStore.can('device.showkey'))
const canAdopt = computed(() => rightsStore.can('device.adopt'))
const canPreview = computed(() => rightsStore.can('device.preview'))
const canAssign = computed(() => rightsStore.can('device.assign'))

const filterText = ref('')

// Help popovers
const urlHelpPopover = ref<InstanceType<typeof Popover> | null>(null)
const toggleUrlHelp = (e: Event) => urlHelpPopover.value?.toggle(e)
const actionsHelpPopover = ref<InstanceType<typeof Popover> | null>(null)
const toggleActionsHelp = (e: Event) => actionsHelpPopover.value?.toggle(e)

// Online/offline visibility toggles
const { showOnline, showOffline, toggleShowOnline, toggleShowOffline, applyOnlineFilter } = useOnlineFilter()

const filteredDevices = computed(() => {
  let list = devicesStore.devices.slice()
  const search = (filterText.value || '').trim().toLowerCase()
  if (search) {
    list = list.filter((d) =>
      (d.name && d.name.toLowerCase().includes(search)) ||
      (d.devicekey && d.devicekey.toLowerCase().includes(search)) ||
      (d.screen_name && d.screen_name.toLowerCase().includes(search))
    )
  }
  return applyOnlineFilter(list, (d) => d.is_online)
})

const onlineCount = computed(() => devicesStore.onlineDevices.length)
const offlineCount = computed(() => devicesStore.devices.filter((d) => !d.is_online).length)

onMounted(() => {
  devicesStore.fetch()
  screensStore.fetch()
})


const showAdoptDialog = ref(false)
const showRenameDialog = ref(false)
const showAssignDialog = ref(false)
const renamingDevice = ref<Device | null>(null)
const assigningDevice = ref<Device | null>(null)

const openAdoptDialog = () => {
  showAdoptDialog.value = true
}

const openRenameDialog = (device: Device) => {
  renamingDevice.value = device
  showRenameDialog.value = true
}

const openAssignDialog = (device: Device) => {
  assigningDevice.value = device
  showAssignDialog.value = true
}

const toggleFind = (device: Device) => {
  devicesStore.findDevice(device.id)
}

const toggleActiveDevice = async (device: Device, val: boolean) => {
  const previous = device.is_active
  device.is_active = val
  const ack = await request('displayhive:devices:cts:update_device', { device_id: device.id, is_active: val }, {
    success: `Device ${device.name} ${val ? 'activated' : 'deactivated'}`,
    error: 'Update failed',
  })
  if (!ack) device.is_active = previous
}

const playDevice = (device: Device) => {
  if (!device.devicekey) {
    toast.add({
      severity: 'error',
      summary: 'Cannot preview',
      detail: 'Device key is not visible to this account (requires device.showkey).',
      life: 4000,
    })
    return
  }
  try {
    openDevicePreview(device.devicekey)
  } catch (e) {
    console.error('[DevicesView] playDevice error', e)
  }
}

const copyDeviceKey = async (device: Device) => {
  const key = device.devicekey || ''
  try {
    await navigator.clipboard.writeText(key)
    toast.add({ severity: 'success', summary: 'Copied', detail: 'Device key copied to clipboard', life: 2000 })
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to copy device key', life: 3000 })
  }
}

// Builds a one-time screen URL carrying the device key in the URL fragment
// (`#devicekey=...`) rather than the query string, so it's never sent to a
// server in an access log or Referer header. The screen client reads it,
// uses it for this session only, and scrubs the fragment from the URL/
// history on load - it is never written to that device's localStorage.
const copyDeviceUrl = async (device: Device) => {
  if (!device.devicekey) {
    toast.add({
      severity: 'error',
      summary: 'Cannot copy',
      detail: 'Device key is not visible to this account (requires device.showkey).',
      life: 4000,
    })
    return
  }
  try {
    const base = getScreenBaseUrl()
    const key = device.devicekey || ''
    const url = `${base}#devicekey=${encodeURIComponent(key)}`
    await navigator.clipboard.writeText(url)
    toast.add({ severity: 'success', summary: 'Copied', detail: 'Dynamic device URL copied to clipboard', life: 2000 })
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to copy device URL', life: 3000 })
  }
}

const formatDate = (iso?: string | null) => {
  try {
    if (!iso) return '-'
    const d = new Date(iso)
    if (isNaN(d.getTime())) return '-'
    return d.toLocaleString()
  } catch {
    return '-'
  }
}

const deleteDevice = (device: Device) => {
  confirmDanger({
    message: `Are you sure you want to delete device "${device.name}"?`,
    accept: async () => {
      // The server pushes the new list to every admin once the device is gone; a fetch() right
      // behind the delete can be answered first and put the deleted row back.
      await request('displayhive:devices:cts:delete_device', { device_id: device.id }, { success: 'Device deleted', error: 'Delete failed' })
    },
  })
}

// Reached via a link like /devices?edit=<id>: open that device's dialog.
useOpenFromQuery(() => devicesStore.devices, openRenameDialog, () => canRename.value)
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('device.page')" class="devices-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Devices page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="devices-page" class="devices-view">
    <PageActions
      :primary="canAdopt ? { label: 'Adopt Device', icon: 'pi pi-plus', tour: 'devices-adopt', onClick: openAdoptDialog } : null"
    />
    <Card>
      <template #content>
        <DataTable
          data-tour="devices-table"
          :value="filteredDevices"
          :loading="devicesStore.loading"
          sortField="name"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="filteredDevices.length > 10"
          :rows="10"
          :rowsPerPageOptions="[10, 25, 50]"
          responsiveLayout="scroll"
        >
          <template #header>
            <div class="dt-header">
              <div class="dt-left">
                <InputText
                  v-model="filterText"
                  data-tour="devices-filter"
                  placeholder="Filter devices..."
                  class="filter-input"
                />
              </div>
              <div class="dt-right">
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
          </template>
          <Column field="is_active" header="Active" style="width: 80px">
            <template #body="{ data }">
              <ToggleSwitch
                v-model="data.is_active"
                :disabled="!canEnable"
                @update:modelValue="(val) => toggleActiveDevice(data, val)"
              />
            </template>
          </Column>
          <Column field="name" header="Name" sortable />
          <Column v-if="canShowKey" field="devicekey" sortable style="width: 220px;">
            <template #header>
              <span class="col-header-with-help">
                Device Key
                <i
                  class="pi pi-question-circle col-help-icon"
                  role="button"
                  tabindex="0"
                  aria-label="Help: Dynamic device URL"
                  @click.stop="toggleUrlHelp"
                  @keydown.enter.stop="toggleUrlHelp"
                ></i>
              </span>
              <Popover ref="urlHelpPopover">
                <p class="col-help-text">
                  The <i class="pi pi-key"></i> button copies the device's raw key.
                  The <i class="pi pi-share-alt"></i> button copies a dynamic device URL instead —
                  a one-time link with the key embedded that opens this device's screen when visited.
                  It's safe to share since it never gets written to that device's browser storage.
                </p>
              </Popover>
            </template>
            <template #body="{ data }">
              <div class="key-cell" data-tour="devices-key-column">
                <Button class="key-button" icon="pi pi-key" size="small" outlined @click="() => copyDeviceKey(data)" :title="'Copy key'">
                </Button>
                <Button class="key-button" icon="pi pi-share-alt" size="small" outlined @click="() => copyDeviceUrl(data)" :title="'Copy dynamic device URL'">
                </Button>
                <span class="key-text">{{ data.devicekey }}</span>
              </div>
            </template>
          </Column>
          <Column field="is_online" header="Status" style="width: 100px">
            <template #body="{ data }">
              <Tag :severity="data.is_online ? 'success' : 'danger'" :value="data.is_online ? 'Online' : 'Offline'" />
            </template>
          </Column>
          <Column header="Connection" style="width: 220px">
            <template #body="{ data }">
              <div class="connection-cell">
                <div class="conn-line"><small>Created: {{ formatDate(data.created_at) }}</small></div>
                <div class="conn-line"><small>Last: {{ formatDate(data.last_connected_at) }}</small></div>
              </div>
            </template>
          </Column>
          <Column field="screen_name" header="Screen" sortable>
            <template #body="{ data }">
              <RouteLink v-if="data.screen_id && data.screen_name && rightsStore.can('screens.page')" :to="links.screen(data.screen_id)" title="Open this screen">{{ data.screen_name }}</RouteLink>
              <template v-else>{{ data.screen_name || '-' }}</template>
            </template>
          </Column>
          <Column style="width: 200px">
            <template #header>
              <span class="col-header-with-help">
                Actions
                <i
                  class="pi pi-question-circle col-help-icon"
                  role="button"
                  tabindex="0"
                  aria-label="Help: Actions"
                  @click.stop="toggleActionsHelp"
                  @keydown.enter.stop="toggleActionsHelp"
                ></i>
              </span>
              <Popover ref="actionsHelpPopover">
                <ul class="col-help-list">
                  <li><i class="pi pi-play"></i> Play — open a live preview of what this device is showing.</li>
                  <li><i class="pi pi-pencil"></i> Rename — change the device's display name.</li>
                  <li><i class="pi pi-desktop"></i> Assign to Screen — attach this device to a screen.</li>
                  <li><i class="pi pi-map-marker"></i> Locate Device — flash an on-screen marker to find it physically (only while online).</li>
                  <li><i class="pi pi-trash"></i> Delete — remove the device and its adoption.</li>
                </ul>
              </Popover>
            </template>
            <template #body="{ data }">
              <div class="action-buttons">
                <Button
                  v-if="canPreview"
                  icon="pi pi-play"
                  @click="() => playDevice(data)"
                  size="small"
                  outlined
                  title="Play"
                />
                <Button
                  v-if="canRename"
                  data-tour="devices-row-rename"
                  icon="pi pi-pencil"
                  @click="openRenameDialog(data)"
                  size="small"
                  outlined
                  title="Rename"
                />
                <Button
                  v-if="canAssign"
                  data-tour="devices-row-assign"
                  icon="pi pi-desktop"
                  @click="openAssignDialog(data)"
                  size="small"
                  outlined
                  title="Assign to Screen"
                />
                <Button
                  v-if="data.is_online"
                  data-tour="devices-row-locate"
                  icon="pi pi-map-marker"
                  @click="toggleFind(data)"
                  size="small"
                  :severity="data.find ? 'success' : 'secondary'"
                  outlined
                  title="Locate Device"
                />
                <Button
                  v-if="canDelete"
                  icon="pi pi-trash"
                  @click="deleteDevice(data)"
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

    <DeviceAdoptDialog v-model:visible="showAdoptDialog" />
    <DeviceRenameDialog v-model:visible="showRenameDialog" :device="renamingDevice" />
    <DeviceAssignDialog v-model:visible="showAssignDialog" :device="assigningDevice" />
  </div>
</template>

<style scoped>
.devices-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* No title text left in the card header now — keep the action buttons
   right-aligned instead of collapsing to the start with nothing to space
   against. */
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

.key-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  position: relative;
}

.key-button {
  padding: 0.25rem;
}

.key-hidden {
  color: var(--p-text-muted-color, #9ca3af);
}

  .key-text {
  font-family: monospace;
  font-size: 0.8rem;
  background: var(--p-content-background, #f5f5f5);
  color: var(--p-text-color, #111);
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  position: absolute;
  left: calc(100% + 8px);
  top: 50%;
  transform: translateY(-50%);
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
  z-index: 30;
  visibility: hidden;
  opacity: 0;
  transition: opacity 120ms ease, visibility 120ms ease;
  max-width: 360px;
  pointer-events: none;
}

.key-cell:hover .key-text {
  visibility: visible;
  opacity: 1;
}

.connection-cell {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.connection-cell .conn-line small {
  color: var(--p-text-muted-color, #444);
  font-size: 0.85rem;
  display: block;
}

.col-header-with-help {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}

.col-help-icon {
  font-size: 0.85rem;
  color: var(--p-text-muted-color, #9ca3af);
  cursor: pointer;
}

.col-help-text {
  max-width: 300px;
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
}

.col-help-text i {
  font-size: 0.8rem;
}

.col-help-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
  font-size: 0.85rem;
  line-height: 1.4;
}

.col-help-list li {
  display: flex;
  align-items: baseline;
  gap: 0.5rem;
}

.col-help-list i {
  flex-shrink: 0;
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #6b7280);
}
</style>
