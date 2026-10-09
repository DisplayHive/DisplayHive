<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useAck } from '../../composables/useAck'
import { useUsersPage } from '../../composables/users/useUsersPage'
import type { RightsGroup } from '../../types/models'
import DialogTitle from '../DialogTitle.vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'

// Create (group = null) or edit a group: its name and parent.
const props = defineProps<{ group: RightsGroup | null }>()
const visible = defineModel<boolean>('visible', { required: true })

const page = useUsersPage()
const toast = useToast()
const { request } = useAck()

const isNew = computed(() => props.group === null)
const isSavingGroup = ref(false)
const groupForm = ref<{ id: number | null; name: string; parent_group_id: number | null }>({
  id: null,
  name: '',
  parent_group_id: null,
})

watch(visible, (open) => {
  if (!open) return
  const g = props.group
  groupForm.value = g
    ? { id: g.id, name: g.name, parent_group_id: g.parent_group_id }
    : { id: null, name: '', parent_group_id: null }
})

const saveGroup = async () => {
  if (!groupForm.value.name.trim()) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Group name is required', life: 4000 })
    return
  }
  isSavingGroup.value = true
  try {
    const event = isNew.value
      ? 'displayhive:admin:rights:cts:create_group'
      : 'displayhive:admin:rights:cts:update_group'
    const payload: Record<string, unknown> = {
      name: groupForm.value.name.trim(),
      parent_group_id: groupForm.value.parent_group_id,
    }
    if (!isNew.value) payload.id = groupForm.value.id
    const ack = await request(event, payload, { success: isNew.value ? 'Group created' : 'Group updated', error: 'Save failed' })
    if (ack) {
      visible.value = false
      await page.loadRights()
    }
  } finally {
    isSavingGroup.value = false
  }
}
</script>

<template>
<Dialog v-model:visible="visible" modal :style="{ width: '420px' }">
  <template #header>
    <DialogTitle icon="pi-users" :title="isNew ? 'Add Group' : 'Edit Group'" />
  </template>
  <div class="dialog-form" data-tour="users-group-fields">
    <label for="group-name">Name</label>
    <InputText id="group-name" v-model="groupForm.name" autofocus />
    <label for="group-parent">Parent group</label>
    <Select
      id="group-parent"
      v-model="groupForm.parent_group_id"
      :options="page.parentOptions(groupForm.id)"
      option-label="label"
      option-value="value"
    />
  </div>
  <template #footer>
    <Button data-tour="users-group-cancel" label="Cancel" text @click="visible = false" />
    <Button label="Save" icon="pi pi-check" :loading="isSavingGroup" @click="saveGroup" />
  </template>
</Dialog>
</template>

<style scoped>
.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.dialog-form label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
  margin-top: 0.5rem;
}

.dialog-form :deep(.p-password),
.dialog-form :deep(input) {
  width: 100%;
}
</style>
