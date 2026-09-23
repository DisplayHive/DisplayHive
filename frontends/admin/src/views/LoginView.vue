<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'

import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'

// use static public logo (frontends/admin/public/logo_wh.png); bound via JS
// rather than a literal template src so Vite doesn't try to resolve it as a
// module asset (same pattern as App.vue's header logo).
const Logo = '/admin/logo_wh.png'

const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const error = ref('')
const loggingIn = ref(false)

const submit = async () => {
  if (!username.value || !password.value) {
    error.value = 'Username and password are required'
    return
  }
  error.value = ''
  loggingIn.value = true
  try {
    const result = await authStore.login(username.value, password.value)
    if (result) {
      error.value = result
    } else {
      password.value = ''
    }
  } finally {
    loggingIn.value = false
  }
}
</script>

<template>
  <div class="login-view">
    <Card class="login-card">
      <template #title>
        <div class="login-title">
          <img :src="Logo" alt="DisplayHive" class="login-logo" />
          <span>Admin Login</span>
        </div>
      </template>
      <template #content>
        <form class="login-form" @submit.prevent="submit">
          <label for="login-username">Username</label>
          <InputText
            id="login-username"
            v-model="username"
            autofocus
            autocomplete="username"
            data-testid="login-username"
          />

          <label for="login-password">Password</label>
          <Password
            id="login-password"
            v-model="password"
            :feedback="false"
            toggle-mask
            autocomplete="current-password"
            input-id="login-password-input"
            data-testid="login-password"
          />

          <Message v-if="error" severity="error" :closable="false" data-testid="login-error">
            {{ error }}
          </Message>

          <Button
            type="submit"
            label="Log In"
            icon="pi pi-sign-in"
            :loading="loggingIn"
            data-testid="login-submit"
          />
        </form>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.login-view {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f8f9fa;
  padding: 1rem;
}

.login-card {
  width: 100%;
  max-width: 380px;
}

.login-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.15rem;
}

.login-logo {
  height: 40px;
  width: auto;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.login-form label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
  margin-top: 0.5rem;
}

.login-form :deep(.p-password),
.login-form :deep(input) {
  width: 100%;
}

.login-form .p-button {
  margin-top: 1rem;
}

/* Dark mode: this wrapper covers the full viewport and otherwise hides
   App.vue's own `.dark-mode body` background beneath it. useTheme() runs
   before login (system/cached preference), so the login screen needs its
   own dark background too. */
.dark-mode .login-view {
  background-color: #14181c;
}
</style>
