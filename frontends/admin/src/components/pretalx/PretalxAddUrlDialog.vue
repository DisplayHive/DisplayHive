<script setup lang="ts">
import { ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import DialogTitle from '../ui/DialogTitle.vue'
import { useAck, type Ack } from '../../composables/useAck'

// "Add Pretalx API URL" dialog. The server pushes the refreshed URL list itself.
const visible = defineModel<boolean>('visible', { default: false })

const { request } = useAck()
const toast = useToast()
const newName = ref('')
const newUrl = ref('')
const addLoading = ref(false)

watch(visible, (open) => {
  if (open) {
    newName.value = ''
    newUrl.value = ''
  }
})



async function addUrl() {
  const name = newName.value.trim()
  const url = newUrl.value.trim()
  if (!name || !url) return
  addLoading.value = true
  try {
    const ack = await request<Ack & { is_valid?: boolean }>('displayhive:admin:pretalx:cts:add_url', { name, url }, { error: 'Failed to add URL' })
    visible.value = false
    if (ack?.is_valid) {
      toast.add({ severity: 'success', summary: 'Added', detail: 'URL added and returned valid JSON', life: 3000 })
    } else if (ack) {
      toast.add({ severity: 'warn', summary: 'Added', detail: 'URL saved but did not return valid JSON', life: 4000 })
    }
  } finally {
    addLoading.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: '480px' }">
    <template #header>
      <DialogTitle icon="pi-link" title="Add Pretalx API URL" />
    </template>
    <div class="edit-form" data-tour="pretalx-add-fields">
      <div class="field">
        <label>Name</label>
        <InputText v-model="newName" placeholder="e.g. Main Conference" class="w-full" autofocus />
      </div>
      <div class="field">
        <label>API URL</label>
        <InputText
          v-model="newUrl"
          placeholder="https://pretalx.example.com/api/events/conf/talks/"
          class="w-full"
          @keydown.enter="addUrl"
        />
        <small class="hint">The URL is fetched immediately — it must return JSON to be marked as valid.</small>
      </div>
    </div>
    <template #footer>
      <Button data-tour="pretalx-add-cancel" label="Cancel" severity="secondary" outlined @click="visible = false" />
      <Button
        label="Add & Validate"
        icon="pi pi-plus"
        :loading="addLoading"
        :disabled="!newName.trim() || !newUrl.trim()"
        @click="addUrl"
      />
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
