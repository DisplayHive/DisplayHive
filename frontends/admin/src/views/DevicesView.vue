<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Html5Qrcode } from 'html5-qrcode'
import { useOnlineFilter } from '../composables/useOnlineFilter'
import type { Device } from '../types/models'
import { useDevicesStore } from '../stores/devices'
import { useScreensStore } from '../stores/screens'
import { useRightsStore } from '../stores/rights'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import ToggleSwitch from 'primevue/toggleswitch'
import Card from 'primevue/card'

const toast = useToast()
const confirm = useConfirm()
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

// Online/offline visibility toggles
const { showOnline, showOffline, toggleShowOnline, toggleShowOffline, applyOnlineFilter } = useOnlineFilter()

// Adopt device dialog
const isAdopting = ref(false)
const showAdoptDialog = ref(false)
const adoptForm = ref({
  name: '',
  adoptiontoken: '',
  screen_id: null as number | null,
})

// QR scanner state
const scannerActive = ref(false)
const scannerEl = ref<HTMLElement | null>(null)
let html5QrScanner: Html5Qrcode | null = null

// Rename device dialog
const isSavingRename = ref(false)
const showRenameDialog = ref(false)
const renamingDevice = ref<Device | null>(null)
const renameForm = ref({ name: '' })

// Assign-to-screen dialog
const isSavingAssign = ref(false)
const showAssignDialog = ref(false)
const assigningDevice = ref<Device | null>(null)
const assignForm = ref({ screen_id: null as number | null })

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

const screenOptions = computed(() => {
  const assigned = new Set<number>()
  devicesStore.devices.forEach((d) => { if (d.screen_id) assigned.add(d.screen_id) })
  return [
    { label: '-- No Screen --', value: null as number | null },
    ...screensStore.screens
      .filter((s) => !assigned.has(s.id))
      .map((s) => ({ label: s.name, value: s.id as number | null })),
  ]
})

const screenOptionsForAssign = computed(() => {
  const assigned = new Set<number>()
  devicesStore.devices.forEach((d) => {
    if (d.screen_id) assigned.add(d.screen_id)
  })
  const options: Array<{ label: string; value: number | null }> = [
    { label: '-- No Screen --', value: null },
  ]
  screensStore.screens.forEach((s) => {
    if (!assigned.has(s.id) || assigningDevice.value?.screen_id === s.id) {
      options.push({ label: s.name, value: s.id })
    }
  })
  return options
})

onMounted(() => {
  devicesStore.fetch()
  screensStore.fetch()
})

const refreshDevices = () => devicesStore.fetch()

const openAdoptDialog = () => {
  adoptForm.value = { name: '', adoptiontoken: '', screen_id: null }
  showAdoptDialog.value = true
}

const closeAdoptDialog = () => {
  stopQRScanner()
  showAdoptDialog.value = false
}

const startQRScanner = async () => {
  try {
    scannerActive.value = true
    await new Promise(resolve => setTimeout(resolve, 100))

    if (!scannerEl.value) {
      toast.add({ severity: 'error', summary: 'Error', detail: 'Scanner element not found', life: 3000 })
      scannerActive.value = false
      return
    }

    html5QrScanner = new Html5Qrcode('qr-reader-element')

    let cameraId: string | null = null
    try {
      const devices = await Html5Qrcode.getCameras()
      if (devices && devices.length) {
        const backCamera = devices.find((d) => /back|rear|environment/i.test(d.label))
        cameraId = backCamera?.id ?? devices[devices.length - 1]?.id ?? null
      }
    } catch (e) {
      console.warn('[DevicesView] getCameras failed', e)
    }

    await html5QrScanner.start(
      cameraId ? { deviceId: { exact: cameraId } } : { facingMode: 'environment' },
      { fps: 10, qrbox: 250 },
      (decodedText: string) => {
        adoptForm.value.adoptiontoken = decodedText
        toast.add({ severity: 'success', summary: 'QR Code Scanned', detail: 'Adoptiontoken captured', life: 2000 })
        stopQRScanner()
      },
      () => { /* ignore per-frame decode errors */ }
    )
  } catch (e) {
    console.error('[DevicesView] QR scanner error:', e)
    scannerActive.value = false
    toast.add({ severity: 'error', summary: 'Scanner Error', detail: 'Failed to start camera. Please enter key manually.', life: 5000 })
  }
}

const stopQRScanner = async () => {
  try {
    if (html5QrScanner) {
      try {
        await html5QrScanner.stop()
      } catch (e) {
        console.warn('[DevicesView] scanner stop error', e)
      }
      try {
        html5QrScanner.clear()
      } catch (e) {}
      html5QrScanner = null
    }
    scannerActive.value = false
  } catch (e) {
    console.warn('[DevicesView] stopQRScanner error', e)
  }
}

const adoptDevice = async () => {
  isAdopting.value = true
  const screenName = adoptForm.value.screen_id
    ? screensStore.screens.find((s) => s.id === adoptForm.value.screen_id)?.name ?? null
    : null

  try {
    const result = await devicesStore.adoptDevice({
      token: adoptForm.value.adoptiontoken,
      device_name: adoptForm.value.name,
      screen_name: screenName ?? null,
    })

    if (result?.success) {
      toast.add({ severity: 'success', summary: 'Success', detail: 'Device adopted', life: 3000 })
      showAdoptDialog.value = false
      devicesStore.fetch()
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: result?.error || 'Failed to adopt device', life: 5000 })
    }
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to adopt device', life: 5000 })
  } finally {
    isAdopting.value = false
  }
}

const openRenameDialog = (device: Device) => {
  renamingDevice.value = device
  renameForm.value = { name: device.name ?? '' }
  showRenameDialog.value = true
}

const saveRename = async (keepOpen = false) => {
  if (!renamingDevice.value) return
  isSavingRename.value = true
  try {
    devicesStore.updateDevice(renamingDevice.value.id, { name: renameForm.value.name })
    toast.add({ severity: 'success', summary: 'Success', detail: 'Device renamed', life: 3000 })
    if (!keepOpen) showRenameDialog.value = false
    devicesStore.fetch()
  } finally {
    isSavingRename.value = false
  }
}

const openAssignDialog = (device: Device) => {
  assigningDevice.value = device
  assignForm.value = { screen_id: device.screen_id ?? null }
  showAssignDialog.value = true
}

const saveAssign = async () => {
  if (!assigningDevice.value) return
  isSavingAssign.value = true
  try {
    devicesStore.assignScreen(assigningDevice.value.id, assignForm.value.screen_id ?? null)
    toast.add({ severity: 'success', summary: 'Success', detail: 'Screen assignment updated', life: 3000 })
    showAssignDialog.value = false
    devicesStore.fetch()
  } finally {
    isSavingAssign.value = false
  }
}

const toggleFind = (device: Device) => {
  devicesStore.findDevice(device.id)
}

const toggleActiveDevice = (device: Device, val: boolean) => {
  device.is_active = val
  devicesStore.updateDevice(device.id, { is_active: val })
  toast.add({ severity: 'success', summary: 'Updated', detail: `Device ${device.name} ${val ? 'activated' : 'deactivated'}`, life: 2000 })
}

// Allow overriding screen URL via Vite env `VITE_SCREEN_URL`. Otherwise:
// - In dev (`npm run dev`), the admin SPA is served by its own Vite dev
//   server (e.g. :5173), which is NOT where Flask renders the screen/
//   handles the devicekey socket auth — default to the Flask backend URL
//   instead (same fallback used for the socket connection).
// - In production, admin + screen are both served by Flask on the same
//   origin, so `window.location.origin` is correct.
const getScreenBaseUrl = (): string => {
  const env = (import.meta as any).env || {}
  return (
    (env.VITE_SCREEN_URL as string) ||
    (env.DEV ? (env.VITE_BACKEND_URL as string) || (env.VITE_SOCKET_URL as string) || 'http://localhost:5000' : window.location.origin)
  )
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
    const base = getScreenBaseUrl()
    const key = device.devicekey || ''
    const separator = base.includes('?') ? '&' : '?'
    const url = `${base}${separator}impersonate=true&devicekey=${encodeURIComponent(key)}`
    // Open in new tab/window safely
    window.open(url, '_blank', 'noopener')
  } catch (e) {
    console.error('[DevicesView] playDevice error', e)
  }
}

const copyDeviceKey = async (device: Device) => {
  const key = device.devicekey || ''
  try {
    await navigator.clipboard.writeText(key)
    toast.add({ severity: 'success', summary: 'Copied', detail: 'Device key copied to clipboard', life: 2000 })
  } catch (e) {
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
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to copy device URL', life: 3000 })
  }
}

const formatDate = (iso?: string | null) => {
  try {
    if (!iso) return '-'
    const d = new Date(iso)
    if (isNaN(d.getTime())) return '-'
    return d.toLocaleString()
  } catch (e) {
    return '-'
  }
}

const deleteDevice = (device: Device) => {
  confirm.require({
    message: `Are you sure you want to delete device "${device.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      devicesStore.deleteDevice(device.id)
      toast.add({ severity: 'success', summary: 'Success', detail: 'Device deleted', life: 3000 })
      devicesStore.fetch()
    },
  })
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('device.page')" class="devices-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Devices page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="devices-view">
    <Card>
      <template #title>
        <div class="card-header">
          <span>Adopted Devices</span>
          <div class="header-actions">
            <Button
              v-if="canAdopt"
              icon="pi pi-plus"
              label="Adopt Device"
              @click="openAdoptDialog"
              size="small"
            />
            <Button
              icon="pi pi-refresh"
              @click="refreshDevices"
              size="small"
              outlined
            />
          </div>
        </div>
      </template>
      <template #content>
        <DataTable
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
                <InputText v-model="filterText" placeholder="Filter devices..." class="filter-input" />
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
          <Column v-if="canShowKey" field="devicekey" header="Device Key" sortable style="width: 220px;">
            <template #body="{ data }">
              <div class="key-cell">
                <Button class="key-button" icon="pi pi-key" size="small" outlined @click="() => copyDeviceKey(data)" :title="'Copy key'">
                </Button>
                <Button class="key-button" icon="pi pi-link" size="small" outlined @click="() => copyDeviceUrl(data)" :title="'Copy dynamic device URL'">
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
              {{ data.screen_name || '-' }}
            </template>
          </Column>
          <Column header="Actions" style="width: 200px">
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
                  icon="pi pi-pencil"
                  @click="openRenameDialog(data)"
                  size="small"
                  outlined
                  title="Rename"
                />
                <Button
                  v-if="canAssign"
                  icon="pi pi-desktop"
                  @click="openAssignDialog(data)"
                  size="small"
                  outlined
                  title="Assign to Screen"
                />
                <Button
                  v-if="data.is_online"
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

    <!-- Adopt Device Dialog -->
    <Dialog v-model:visible="showAdoptDialog" header="Adopt Device" modal :style="{ width: '600px' }" @hide="closeAdoptDialog">
      <div class="dialog-content">
        <div class="field">
          <label for="adopt-name">Device Name</label>
          <InputText id="adopt-name" v-model="adoptForm.name" class="w-full" />
        </div>
          <div class="field">
            <label for="adopt-key">Adoptiontoken</label>
            <div class="key-input-group">
              <InputText id="adopt-key" v-model="adoptForm.adoptiontoken" class="w-full" placeholder="Enter or scan adoption token" />
            <Button 
              v-if="!scannerActive"
              icon="pi pi-camera" 
              @click="startQRScanner" 
              outlined
              title="Scan QR Code"
            />
            <Button 
              v-else
              icon="pi pi-times" 
              @click="stopQRScanner" 
              severity="danger"
              outlined
              title="Stop Scanner"
            />
          </div>
        </div>
        <div v-if="scannerActive" class="scanner-container">
          <div id="qr-reader-element" ref="scannerEl"></div>
        </div>
        <div class="field">
          <label for="adopt-screen">Assign to Screen</label>
          <Select
            id="adopt-screen"
            v-model="adoptForm.screen_id"
            :options="screenOptions"
            optionLabel="label"
            optionValue="value"
            class="w-full"
          />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="closeAdoptDialog" text :disabled="isAdopting" />
        <Button label="Adopt" @click="adoptDevice" :loading="isAdopting" :disabled="isAdopting" />
      </template>
    </Dialog>

    <!-- Rename Device Dialog -->
    <Dialog v-model:visible="showRenameDialog" header="Rename Device" modal :style="{ width: '420px' }">
      <div class="dialog-content">
        <div class="field">
          <label for="rename-name">Device Name</label>
          <InputText id="rename-name" v-model="renameForm.name" class="w-full" />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="showRenameDialog = false" text :disabled="isSavingRename" />
        <Button label="Update" severity="secondary" outlined @click="saveRename(true)" :loading="isSavingRename" :disabled="isSavingRename" />
        <Button label="Save" @click="saveRename()" :loading="isSavingRename" :disabled="isSavingRename" />
      </template>
    </Dialog>

    <!-- Assign to Screen Dialog -->
    <Dialog v-model:visible="showAssignDialog" header="Assign to Screen" modal :style="{ width: '420px' }">
      <div class="dialog-content">
        <div class="field">
          <label for="assign-screen">Assign to Screen</label>
          <Select
            id="assign-screen"
            v-model="assignForm.screen_id"
            :options="screenOptionsForAssign"
            optionLabel="label"
            optionValue="value"
            class="w-full"
          />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="showAssignDialog = false" text :disabled="isSavingAssign" />
        <Button label="Save" @click="saveAssign()" :loading="isSavingAssign" :disabled="isSavingAssign" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.devices-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
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
  color: #9ca3af;
}

  .key-text {
  font-family: monospace;
  font-size: 0.8rem;
  background: #f5f5f5;
  color: #111;
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

.scanner-container {
  margin: 1rem 0;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 8px;
  border: 2px dashed #dee2e6;
}

#qr-reader-element {
  width: 100%;
  max-width: 100%;
}

.connection-cell {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.connection-cell .conn-line small {
  color: #444;
  font-size: 0.85rem;
  display: block;
}
</style>
