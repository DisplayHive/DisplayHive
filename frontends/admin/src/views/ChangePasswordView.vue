<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'

import Card from 'primevue/card'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'

// Shown by App.vue in place of the whole app while the logged-in account is
// flagged must_change_password (set by an admin on the Users page). The
// server refuses every other request from this session until it succeeds.

// Same static logo as LoginView.vue — see there for why it's bound via JS.
const Logo = '/admin/logo_wh.png'

const authStore = useAuthStore()

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
    error.value = 'Password must be at least 8 characters'
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
    if (result) error.value = result
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="change-password-view">
    <Card class="change-password-card">
      <template #title>
        <div class="change-password-title">
          <img :src="Logo" alt="DisplayHive" class="change-password-logo" />
          <span>Choose a New Password</span>
        </div>
      </template>
      <template #content>
        <form class="change-password-form" @submit.prevent="submit">
          <p class="change-password-hint">
            An administrator requires <strong>{{ authStore.username }}</strong> to set a new password before continuing.
          </p>

          <label for="change-password-current-input">Current Password</label>
          <Password
            v-model="currentPassword"
            :feedback="false"
            toggle-mask
            autocomplete="current-password"
            input-id="change-password-current-input"
            data-testid="change-password-current"
          />

          <label for="change-password-new-input">New Password</label>
          <Password
            v-model="newPassword"
            :feedback="false"
            toggle-mask
            autocomplete="new-password"
            input-id="change-password-new-input"
            data-testid="change-password-new"
          />

          <label for="change-password-confirm-input">Confirm New Password</label>
          <Password
            v-model="confirmPassword"
            :feedback="false"
            toggle-mask
            autocomplete="new-password"
            input-id="change-password-confirm-input"
            data-testid="change-password-confirm"
          />

          <Message v-if="error" severity="error" :closable="false" data-testid="change-password-error">
            {{ error }}
          </Message>

          <Button
            type="submit"
            label="Set Password"
            icon="pi pi-check"
            :loading="saving"
            data-testid="change-password-submit"
          />
          <Button type="button" label="Log Out" icon="pi pi-sign-out" text severity="secondary" @click="authStore.logout()" />
        </form>
      </template>
    </Card>
  </div>
</template>

<style scoped>
/* Mirrors LoginView.vue's layout — the two screens are shown back to back. */
.change-password-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f8f9fa;
  padding: 1rem;
}

.change-password-card {
  width: 100%;
  max-width: 380px;
}

.change-password-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.15rem;
}

.change-password-logo {
  height: 40px;
  width: auto;
}

.change-password-form {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.change-password-hint {
  margin: 0 0 0.25rem;
  font-size: 0.9rem;
}

.change-password-form label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
  margin-top: 0.5rem;
}

.change-password-form :deep(.p-password),
.change-password-form :deep(input) {
  width: 100%;
}

.change-password-form .p-button {
  margin-top: 1rem;
}

.change-password-form .p-button + .p-button {
  margin-top: 0;
}

/* Dark mode: same reason as LoginView.vue — this wrapper covers the full
   viewport and hides App.vue's own dark body background. */
.dark-mode .change-password-view {
  background-color: #14181c;
}
</style>
