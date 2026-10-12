<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'
import DialogTitle from '../ui/DialogTitle.vue'
import DialogFooter from '../ui/DialogFooter.vue'
import { useAck } from '../../composables/useAck'
import { useDevicesStore } from '../../stores/devices'
import { useScreensStore } from '../../stores/screens'
import type { Device } from '../../types/models'

// The "Assign to Screen" dialog of the Devices page; fills itself from
// `device` each time it opens.
const props = defineProps<{ device: Device | null }>()
const visible = defineModel<boolean>('visible', { default: false })

const { request } = useAck()
const devicesStore = useDevicesStore()
const screensStore = useScreensStore()

const isSavingAssign = ref(false)
const assignForm = ref({ screen_id: null as number | null })

// Screens without a device, plus the one this device already has.
const screenOptionsForAssign = computed(() => {
  const assigned = new Set<number>()
  devicesStore.devices.forEach((d) => {
    if (d.screen_id) assigned.add(d.screen_id)
  })
  const options: Array<{ label: string; value: number | null }> = [
    { label: '-- No Screen --', value: null },
  ]
  screensStore.screens.forEach((s) => {
    if (!assigned.has(s.id) || props.device?.screen_id === s.id) {
      options.push({ label: s.name, value: s.id })
    }
  })
  return options
})

watch(visible, (open) => {
  if (open) assignForm.value = { screen_id: props.device?.screen_id ?? null }
})

const saveAssign = async () => {
  if (!props.device) return
  isSavingAssign.value = true
  try {
    const ack = await request('displayhive:devices:cts:assign_device_screen', { device_id: props.device.id, screen_id: assignForm.value.screen_id ?? null }, { success: 'Screen assignment updated', error: 'Assignment failed' })
    if (ack) visible.value = false
  } finally {
    isSavingAssign.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: '420px' }">
    <template #header>
      <DialogTitle icon="pi-desktop" title="Assign to Screen" />
    </template>
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
      <DialogFooter cancel-tour="devices-assign-cancel" :loading="isSavingAssign" :cancel-disabled="isSavingAssign" @cancel="visible = false" @confirm="saveAssign()" />
    </template>
  </Dialog>
</template>
