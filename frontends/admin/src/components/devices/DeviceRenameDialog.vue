<script setup lang="ts">
import { ref, watch } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import DialogTitle from '../DialogTitle.vue'
import DialogFooter from '../DialogFooter.vue'
import { useAck } from '../../composables/useAck'
import type { Device } from '../../types/models'

// The "Rename Device" dialog of the Devices page; fills itself from `device`
// each time it opens.
const props = defineProps<{ device: Device | null }>()
const visible = defineModel<boolean>('visible', { default: false })

const { request } = useAck()
const isSavingRename = ref(false)
const renameForm = ref({ name: '' })

watch(visible, (open) => {
  if (open) renameForm.value = { name: props.device?.name ?? '' }
})

const saveRename = async (keepOpen = false) => {
  if (!props.device) return
  isSavingRename.value = true
  try {
    const ack = await request('displayhive:devices:cts:update_device', { device_id: props.device.id, name: renameForm.value.name }, { success: 'Device renamed', error: 'Rename failed' })
    if (ack && !keepOpen) visible.value = false
  } finally {
    isSavingRename.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: '420px' }">
    <template #header>
      <DialogTitle icon="pi-pencil" title="Rename Device" />
    </template>
    <div class="dialog-content">
      <div class="field">
        <label for="rename-name">Device Name</label>
        <InputText id="rename-name" v-model="renameForm.name" class="w-full" />
      </div>
    </div>
    <template #footer>
      <DialogFooter show-update :loading="isSavingRename" :cancel-disabled="isSavingRename" @cancel="visible = false" @update="saveRename(true)" @confirm="saveRename()" />
    </template>
  </Dialog>
</template>
