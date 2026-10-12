<script setup lang="ts">
import { ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import DialogTitle from '../ui/DialogTitle.vue'
import DialogFooter from '../ui/DialogFooter.vue'
import { useAck } from '../../composables/useAck'

// "Add Screen" dialog of the Screens page. The server pushes the new list itself.
const visible = defineModel<boolean>('visible', { default: false })

const toast = useToast()
const { request } = useAck()
const isCreating = ref(false)
const createForm = ref({
  name: '',
})

watch(visible, (open) => {
  if (open) createForm.value = { name: '' }
})

const createScreen = async () => {
  if (!createForm.value.name) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Name is required', life: 3000 })
    return
  }
  isCreating.value = true
  try {
    const ack = await request('displayhive:screens:cts:create_screen', { name: createForm.value.name }, { success: 'Screen created', error: 'Failed to create screen' })
    if (ack) visible.value = false
  } finally {
    isCreating.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: '450px' }">
    <template #header>
      <DialogTitle icon="pi-desktop" title="Add Screen" />
    </template>
    <div class="dialog-content">
      <div class="field" data-tour="screen-name-field">
        <label for="create-name">Screen Name</label>
        <InputText id="create-name" v-model="createForm.name" class="w-full" placeholder="e.g. Lobby-Display" />
      </div>
    </div>
    <template #footer>
      <DialogFooter cancel-tour="screens-create-cancel" confirm-label="Create" :loading="isCreating" :cancel-disabled="isCreating" @cancel="visible = false" @confirm="createScreen" />
    </template>
  </Dialog>
</template>
