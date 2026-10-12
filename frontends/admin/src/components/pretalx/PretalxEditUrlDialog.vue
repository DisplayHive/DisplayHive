<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import DialogTitle from '../ui/DialogTitle.vue'
import { useAck } from '../../composables/useAck'
import type { PretalxUrl } from './types'

// "Edit Pretalx API URL" dialog: name and polling interval of `url` (the URL
// itself is fixed after creation). Fills itself on each open.
const props = defineProps<{ url: PretalxUrl | null }>()
const visible = defineModel<boolean>('visible', { default: false })

const { request } = useAck()
const editName = ref('')
const editUrl = ref('')
const editInterval = ref(300)
const editLoading = ref(false)

watch(visible, (open) => {
  if (open && props.url) {
    editName.value = props.url.name
    editUrl.value = props.url.url
    editInterval.value = props.url.polling_interval
  }
})

async function saveEdit(keepOpen = false) {
  if (!props.url || !editName.value.trim()) return
  editLoading.value = true
  try {
    const ack = await request('displayhive:admin:pretalx:cts:update_url', {
      id: props.url!.id,
      name: editName.value.trim(),
      polling_interval: editInterval.value,
    }, { success: 'URL updated', error: 'Update failed' })
    if (ack && !keepOpen) visible.value = false
  } finally {
    editLoading.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: '480px' }">
    <template #header>
      <DialogTitle icon="pi-link" title="Edit Pretalx API URL" />
    </template>
    <div class="edit-form">
      <div class="field">
        <label>Name</label>
        <InputText v-model="editName" class="w-full" autofocus />
      </div>
      <div class="field">
        <label>API URL</label>
        <InputText v-model="editUrl" class="w-full" disabled />
        <small class="hint">URL cannot be changed after creation. Delete and re-add to use a different URL.</small>
      </div>
      <div class="field">
        <label>Polling Interval (seconds)</label>
        <InputNumber v-model="editInterval" :min="30" :max="86400" class="w-full" />
      </div>
    </div>
    <template #footer>
      <Button label="Cancel" severity="secondary" outlined @click="visible = false" />
      <Button label="Update" severity="secondary" outlined :loading="editLoading" :disabled="!editName.trim()" @click="saveEdit(true)" />
      <Button label="Save" icon="pi pi-check" :loading="editLoading" :disabled="!editName.trim()" @click="saveEdit()" />
    </template>
  </Dialog>
</template>

<style scoped src="./shared.css"></style>
<style scoped>
.edit-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding-top: 0.5rem;
}

.hint {
  font-size: 0.78rem;
  color: var(--p-text-muted-color, #9ca3af);
}
</style>
