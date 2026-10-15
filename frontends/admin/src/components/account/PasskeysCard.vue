<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import { useConfirmAction } from '../../composables/useConfirmAction'
import { usePasskeys, type Passkey } from '../../composables/usePasskeys'

// "My passkeys": the signed-in person's passkeys, to add, rename and remove. A passkey is a key held
// by a device (phone, laptop, security key); with one, signing in needs no username or password.

const toast = useToast()
const { confirmDanger } = useConfirmAction()
const { passkeys, available, loading, supported, load, add, rename, remove } = usePasskeys()

const newName = ref('')
const adding = ref(false)
const editingId = ref<number | null>(null)
const editName = ref('')
const problem = ref('')

const report = (error: string | null) => {
  problem.value = error ?? ''
  return error === null
}

onMounted(async () => {
  report(await load())
})

const addPasskey = async () => {
  adding.value = true
  try {
    if (report(await add(newName.value.trim()))) {
      newName.value = ''
      toast.add({ severity: 'success', summary: 'Success', detail: 'Passkey added', life: 3000 })
    }
  } finally {
    adding.value = false
  }
}

const startRename = (passkey: Passkey) => {
  editingId.value = passkey.id
  editName.value = passkey.name
}

const saveRename = async (passkey: Passkey) => {
  if (report(await rename(passkey.id, editName.value))) editingId.value = null
}

const removePasskey = (passkey: Passkey) => {
  confirmDanger({
    message: `Remove the passkey "${passkey.name}"? You can no longer sign in with it.`,
    accept: async () => {
      if (report(await remove(passkey.id))) toast.add({ severity: 'success', summary: 'Success', detail: 'Passkey removed', life: 3000 })
    },
  })
}

const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString() : '—')
</script>

<template>
  <Card data-testid="passkeys-card">
    <template #title>
      <div class="card-header-title">
        <i class="pi pi-key card-header-icon" />
        <span>Passkeys</span>
      </div>
    </template>
    <template #content>

    <p class="passkeys-intro">
      A passkey lets you sign in with your device's fingerprint, face, PIN or a security key — no username or
      password. You can have several, for example one per device.
    </p>

    <Message v-if="problem" severity="error" :closable="false" class="passkeys-message">{{ problem }}</Message>
    <Message v-if="!supported" severity="warn" :closable="false" class="passkeys-message">
      This browser cannot use passkeys here (they need https, or localhost).
    </Message>
    <Message v-else-if="!available && !loading" severity="warn" :closable="false" class="passkeys-message">
      Passkeys are not set up for this address. The administrator needs to set <code>PUBLIC_URL</code> to the
      address people use (https).
    </Message>

    <ul v-if="passkeys.length" class="passkey-list" data-testid="passkey-list">
      <li v-for="passkey in passkeys" :key="passkey.id" class="passkey-row">
        <i class="pi pi-key passkey-icon"></i>
        <div class="passkey-main">
          <template v-if="editingId === passkey.id">
            <InputText v-model="editName" size="small" class="passkey-name-input" aria-label="Passkey name" @keydown.enter="saveRename(passkey)" />
          </template>
          <template v-else>
            <span class="passkey-name">{{ passkey.name }}</span>
            <Tag v-if="passkey.synced" value="synced" severity="secondary" title="Kept in your password manager or cloud account and available on your other devices" />
          </template>
          <small class="passkey-dates">added {{ when(passkey.created_at) }} · last used {{ when(passkey.last_used_at) }}</small>
        </div>
        <div class="passkey-actions">
          <template v-if="editingId === passkey.id">
            <Button icon="pi pi-check" size="small" text title="Save the name" @click="saveRename(passkey)" />
            <Button icon="pi pi-times" size="small" text severity="secondary" title="Cancel" @click="editingId = null" />
          </template>
          <template v-else>
            <Button icon="pi pi-pencil" size="small" text title="Rename" @click="startRename(passkey)" />
            <Button icon="pi pi-trash" size="small" text severity="danger" title="Remove this passkey" @click="removePasskey(passkey)" />
          </template>
        </div>
      </li>
    </ul>
    <p v-else-if="!loading" class="passkeys-empty">You have no passkeys yet.</p>

    <div class="passkey-add">
      <InputText v-model="newName" placeholder="Name, e.g. Work laptop" class="passkey-add-name" aria-label="Name of the new passkey" :disabled="!supported || !available" @keydown.enter="addPasskey" />
      <Button
        label="Add a passkey"
        icon="pi pi-plus"
        :loading="adding"
        :disabled="!supported || !available"
        data-testid="passkey-add"
        @click="addPasskey"
      />
    </div>
    </template>
  </Card>
</template>

<style scoped>
.passkeys-intro {
  margin: 0 0 1rem;
  color: var(--p-text-muted-color);
  font-size: 0.9rem;
}

.passkeys-message {
  margin-bottom: 0.75rem;
}

.passkey-list {
  list-style: none;
  margin: 0 0 1rem;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.passkey-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--p-content-border-color, #e5e7eb);
  border-radius: 8px;
}

.passkey-icon {
  color: var(--p-text-muted-color);
}

.passkey-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem 0.6rem;
}

.passkey-name {
  font-weight: 600;
}

.passkey-name-input {
  flex: 1;
  min-width: 10rem;
}

.passkey-dates {
  flex-basis: 100%;
  color: var(--p-text-muted-color);
}

.passkey-actions {
  display: flex;
  gap: 0.15rem;
}

.passkeys-empty {
  margin: 0 0 1rem;
  color: var(--p-text-muted-color);
}

.passkey-add {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.passkey-add-name {
  flex: 1;
  min-width: 10rem;
}
</style>
