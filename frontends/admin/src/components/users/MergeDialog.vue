<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAck } from '../../composables/useAck'
import { useUsersPage } from '../../composables/users/useUsersPage'
import type { AdminUser } from '../../types/models'
import DialogTitle from '../DialogTitle.vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'

// Merge an SSO-created account into an existing one — the admin-side way to link an SSO login
// to an existing account: an identity's `sub` is unknown until its first login, which creates a
// new account; merging moves the identity onto the real account and deletes the new one.
const props = defineProps<{ source: AdminUser | null }>()
const visible = defineModel<boolean>('visible', { required: true })

const page = useUsersPage()
const { request } = useAck()

const mergeTargetId = ref<number | null>(null)
const isMerging = ref(false)
const mergeTargetOptions = computed(() =>
  page.users
    .filter((u) => u.id !== props.source?.id)
    .map((u) => ({ label: u.username, value: u.id })),
)

watch(visible, (open) => {
  if (open) mergeTargetId.value = null
})

const mergeAccount = async () => {
  if (!props.source || !mergeTargetId.value) return
  isMerging.value = true
  try {
    const ack = await request('displayhive:admin:users:cts:merge_user', {
      source_id: props.source.id,
      target_id: mergeTargetId.value,
    }, { success: 'SSO login moved to the selected user', error: 'Merge failed' })
    if (ack) {
      visible.value = false
      page.loadAll()
    }
  } finally {
    isMerging.value = false
  }
}
</script>

<template>
<Dialog v-model:visible="visible" modal :style="{ width: '440px' }">
  <template #header>
    <DialogTitle icon="pi-arrow-right-arrow-left" title="Merge into existing user" />
  </template>
  <div class="dialog-form">
    <p class="merge-explanation">
      Moves the SSO login of <strong>{{ source?.username }}</strong> onto the user you pick, then
      <strong>deletes {{ source?.username }}</strong>. From then on, that SSO login opens the picked account,
      with its groups and settings.
    </p>
    <label for="merge-target">Merge into</label>
    <Select
      v-model="mergeTargetId"
      input-id="merge-target"
      :options="mergeTargetOptions"
      option-label="label"
      option-value="value"
      filter
      placeholder="Select a user"
    />
  </div>
  <template #footer>
    <Button label="Cancel" text @click="visible = false" />
    <Button
      label="Merge"
      icon="pi pi-check"
      severity="danger"
      :disabled="!mergeTargetId"
      :loading="isMerging"
      @click="mergeAccount"
    />
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

.merge-explanation {
  margin: 0 0 0.5rem;
  font-size: 0.9rem;
}
</style>
