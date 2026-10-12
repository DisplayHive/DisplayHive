<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import DialogTitle from '../DialogTitle.vue'
import DialogFooter from '../DialogFooter.vue'
import { useAck } from '../../composables/useAck'
import type { Screengroup } from '../../types/models'

// Create / rename dialog of the Screen Groups page. A `group` of null means
// "new"; otherwise the dialog renames that group. Fills itself on each open.
const props = defineProps<{ group: Screengroup | null }>()
const visible = defineModel<boolean>('visible', { default: false })

const toast = useToast()
const { request } = useAck()
const isSaving = ref(false)
const isNew = computed(() => !props.group)
const editForm = ref({ name: '' })

watch(visible, (open) => {
  if (open) editForm.value = { name: props.group?.name ?? '' }
})

const saveScreenGroup = async (keepOpen = false) => {
  if (!editForm.value.name.trim()) {
    toast.add({ severity: 'warn', summary: 'Warning', detail: 'Name is required', life: 3000 })
    return
  }
  isSaving.value = true
  try {
    const ack = isNew.value
      ? await request('displayhive:admin:cts:create_screengroup', { name: editForm.value.name }, { success: 'Screen group created', error: 'Failed to create screen group' })
      : await request('displayhive:admin:cts:rename_screengroup', { screengroup_id: props.group!.id, new_name: editForm.value.name }, { success: 'Screen group updated', error: 'Failed to rename screen group' })
    if (ack && !keepOpen) visible.value = false
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: '500px' }"
  >
    <template #header>
      <DialogTitle icon="pi-th-large" :title="isNew ? 'New Screen Group' : 'Edit Screen Group'" />
    </template>
    <div class="dialog-content">
      <div class="field" data-tour="screengroup-name-field">
        <label for="sg-name">Name</label>
        <InputText id="sg-name" v-model="editForm.name" class="w-full" />
      </div>
    </div>
    <template #footer>
      <DialogFooter cancel-tour="screengroups-create-cancel" :show-update="!isNew" :loading="isSaving" :cancel-disabled="isSaving" @cancel="visible = false" @update="saveScreenGroup(true)" @confirm="saveScreenGroup()" />
    </template>
  </Dialog>
</template>
