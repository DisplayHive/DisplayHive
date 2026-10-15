<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Card from 'primevue/card'
import SelectButton from 'primevue/selectbutton'
import { useToast } from 'primevue/usetoast'
import PasskeysCard from '../components/account/PasskeysCard.vue'
import PasswordCard from '../components/account/PasswordCard.vue'
import { useAuthStore } from '../stores/auth'
import { useTheme } from '../composables/useTheme'

// "My account": what belongs to the signed-in person rather than to the instance — who they are,
// their look of the admin and the passkeys they sign in with. Opened by clicking the name in the
// top bar; every signed-in account can open it.
const authStore = useAuthStore()
const toast = useToast()
const { preference, setTheme } = useTheme()

const themeOptions = [
  { label: 'Light', value: 'light' },
  { label: 'Dark', value: 'dark' },
  { label: 'System', value: 'system' },
]

const theme = computed({
  get: () => preference.value,
  set: async (value: 'light' | 'dark' | 'system') => {
    const error = await setTheme(value)
    if (error) toast.add({ severity: 'error', summary: 'Error', detail: error, life: 4000 })
  },
})

// An account made by an SSO login has no password to change; the server says which kind this is.
const passwordLoginAllowed = ref(false)
onMounted(async () => {
  try {
    const response = await fetch('/admin/api/auth/me', { headers: authStore.authHeader() })
    if (response.ok) passwordLoginAllowed.value = !!(await response.json()).password_login_allowed
  } catch {
    // No password card then; everything else still works.
  }
})

const sessionEnds = computed(() => (authStore.expiresAt ? new Date(authStore.expiresAt).toLocaleString() : null))
</script>

<template>
  <div class="account-view" data-tour="account-page">
    <Card data-testid="account-card">
      <template #title>
        <div class="card-header-title">
          <i class="pi pi-user card-header-icon" />
          <span>Account</span>
        </div>
      </template>
      <template #content>
        <dl class="account-facts">
          <dt>Username</dt>
          <dd data-testid="account-username">{{ authStore.username }}</dd>
          <template v-if="sessionEnds">
            <dt>Session ends</dt>
            <dd>{{ sessionEnds }}</dd>
          </template>
          <dt>Theme</dt>
          <dd>
            <SelectButton
              v-model="theme"
              :options="themeOptions"
              option-label="label"
              option-value="value"
              :allow-empty="false"
              size="small"
              data-testid="account-theme"
            />
          </dd>
        </dl>
      </template>
    </Card>

    <PasswordCard v-if="passwordLoginAllowed && !authStore.isImpersonating" />

    <PasskeysCard v-if="!authStore.isImpersonating" />
  </div>
</template>

<style scoped>
.account-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  max-width: 640px;
}

.account-facts {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.6rem 1.25rem;
  margin: 0;
  align-items: center;
}

.account-facts dt {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.account-facts dd {
  margin: 0;
}
</style>
