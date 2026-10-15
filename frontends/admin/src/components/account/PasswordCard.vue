<script setup lang="ts">
import { ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Message from 'primevue/message'
import Password from 'primevue/password'
import { useAuthStore } from '../../stores/auth'

// "Change password" on the My account page. The server checks the current password and signs out
// the account's other sessions; this session carries on under a new token.
const authStore = useAuthStore()
const toast = useToast()

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const saving = ref(false)

const submit = async () => {
  if (!currentPassword.value || !newPassword.value) {
    error.value = 'Current and new password are required'
    return
  }
  if (newPassword.value.length < 8) {
    error.value = 'The new password must be at least 8 characters'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    error.value = 'The new passwords do not match'
    return
  }
  error.value = ''
  saving.value = true
  try {
    const result = await authStore.changePassword(currentPassword.value, newPassword.value)
    if (result) {
      error.value = result
      return
    }
    currentPassword.value = newPassword.value = confirmPassword.value = ''
    toast.add({ severity: 'success', summary: 'Success', detail: 'Password changed. Your other sessions were signed out.', life: 4000 })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Card data-testid="password-card">
    <template #title>
      <div class="card-header-title">
        <i class="pi pi-lock card-header-icon" />
        <span>Password</span>
      </div>
    </template>
    <template #content>
      <form class="password-form" @submit.prevent="submit">
        <div class="field">
          <label for="account-password-current">Current password</label>
          <Password
            v-model="currentPassword"
            :feedback="false"
            toggle-mask
            autocomplete="current-password"
            input-id="account-password-current"
            data-testid="account-password-current"
          />
        </div>
        <div class="field">
          <label for="account-password-new">New password</label>
          <Password
            v-model="newPassword"
            :feedback="false"
            toggle-mask
            autocomplete="new-password"
            input-id="account-password-new"
            data-testid="account-password-new"
          />
        </div>
        <div class="field">
          <label for="account-password-confirm">Confirm new password</label>
          <Password
            v-model="confirmPassword"
            :feedback="false"
            toggle-mask
            autocomplete="new-password"
            input-id="account-password-confirm"
            data-testid="account-password-confirm"
          />
        </div>

        <Message v-if="error" severity="error" :closable="false" data-testid="account-password-error">{{ error }}</Message>

        <div class="field-actions">
          <Button type="submit" label="Change password" icon="pi pi-check" :loading="saving" data-testid="account-password-submit" />
        </div>
      </form>
    </template>
  </Card>
</template>

<style scoped>
.password-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.field label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.field-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
