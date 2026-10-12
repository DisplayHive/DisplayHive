<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Html5Qrcode } from 'html5-qrcode'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import DialogTitle from '../ui/DialogTitle.vue'
import DialogFooter from '../ui/DialogFooter.vue'
import { useDevicesStore } from '../../stores/devices'
import { useScreensStore } from '../../stores/screens'

// The "Adopt Device" dialog of the Devices page: token (typed or scanned from
// a QR code with the camera), name and an optional screen to assign.
const visible = defineModel<boolean>('visible', { default: false })

const toast = useToast()
const devicesStore = useDevicesStore()
const screensStore = useScreensStore()

const isAdopting = ref(false)
const adoptForm = ref({
  name: '',
  adoptiontoken: '',
  screen_id: null as number | null,
})

// Screens that don't have a device yet.
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

watch(visible, (open) => {
  if (open) adoptForm.value = { name: '', adoptiontoken: '', screen_id: null }
})

// QR scanner state
const scannerActive = ref(false)
const scannerEl = ref<HTMLElement | null>(null)
let html5QrScanner: Html5Qrcode | null = null

const closeAdoptDialog = () => {
  stopQRScanner()
  visible.value = false
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
      console.warn('[DeviceAdoptDialog] getCameras failed', e)
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
    console.error('[DeviceAdoptDialog] QR scanner error:', e)
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
        console.warn('[DeviceAdoptDialog] scanner stop error', e)
      }
      try {
        html5QrScanner.clear()
      } catch {}
      html5QrScanner = null
    }
    scannerActive.value = false
  } catch (e) {
    console.warn('[DeviceAdoptDialog] stopQRScanner error', e)
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
      visible.value = false
      devicesStore.fetch()
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: result?.error || 'Failed to adopt device', life: 5000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to adopt device', life: 5000 })
  } finally {
    isAdopting.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: '600px' }" @hide="closeAdoptDialog">
    <template #header>
      <DialogTitle icon="pi-qrcode" title="Adopt Device" />
    </template>
    <div class="dialog-content">
      <div class="field" data-tour="devices-adopt-name-field">
        <label for="adopt-name">Device Name</label>
        <InputText id="adopt-name" v-model="adoptForm.name" class="w-full" />
      </div>
        <div class="field" data-tour="devices-adopt-qr">
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
      <DialogFooter cancel-tour="devices-adopt-cancel" confirm-label="Adopt" :loading="isAdopting" :cancel-disabled="isAdopting" @cancel="closeAdoptDialog" @confirm="adoptDevice" />
    </template>
  </Dialog>
</template>

<style scoped>
.scanner-container {
  margin: 1rem 0;
  padding: 1rem;
  background: var(--p-content-background, #f8f9fa);
  border-radius: 8px;
  border: 2px dashed var(--p-content-border-color, #dee2e6);
}

#qr-reader-element {
  width: 100%;
  max-width: 100%;
}
</style>
