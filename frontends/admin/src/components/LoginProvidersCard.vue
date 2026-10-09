<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useAck, type Ack } from '../composables/useAck'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import type { AuthProvider } from '../types/models'

import Card from 'primevue/card'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import ToggleSwitch from 'primevue/toggleswitch'
import Checkbox from 'primevue/checkbox'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import Message from 'primevue/message'

// SSO login providers (OpenID Connect), shown on SettingsView for holders of
// `authproviders.manage`. The backend side is
// application/admin/authproviders/sockethandlers.py; the login flow itself is
// application/oidc.py.

const { emitWithAck } = useSocket()
const { request } = useAck()
const toast = useToast()
const confirm = useConfirm()

type Result = { success: boolean; error?: string; providers?: AuthProvider[]; public_url?: string | null }

const providers = ref<AuthProvider[]>([])
/** PUBLIC_URL of the server, when configured; else the browser's origin is used. */
const publicUrl = ref<string | null>(null)
const loading = ref(true)

const load = async () => {
  const result = await emitWithAck<Result>('displayhive:admin:authproviders:cts:get_providers')
  if (result.success) {
    providers.value = result.providers || []
    publicUrl.value = result.public_url || null
  }
  loading.value = false
}

onMounted(load)

// The callback URL an admin registers at the provider: the server's
// PUBLIC_URL when it is configured (the backend builds the same one), else the
// browser's own origin, which is what the backend sees too (behind a proxy, as
// long as TRUSTED_PROXY_COUNT is set — see docs/user/installation.md).
const redirectUriFor = (slug: string) =>
  `${publicUrl.value || window.location.origin}/admin/api/auth/oidc/${slug || '<identifier>'}/callback`

const copy = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    toast.add({ severity: 'success', summary: 'Copied', detail: 'Redirect URI copied to clipboard', life: 2000 })
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Could not copy — select and copy it manually', life: 4000 })
  }
}

// --- Add / edit dialog ---------------------------------------------------------

const showDialog = ref(false)
const saving = ref(false)
const testing = ref(false)
const testResult = ref<{ ok: boolean; text: string } | null>(null)
type ProviderForm = {
  id: number | null
  slug: string
  name: string
  issuer: string
  client_id: string
  /** Empty = keep the stored secret (it is never sent back to the browser). */
  client_secret: string
  clear_client_secret: boolean
  has_client_secret: boolean
  scopes: string
  enabled: boolean
}
const form = ref<ProviderForm>({
  id: null,
  slug: '',
  name: '',
  issuer: '',
  client_id: '',
  client_secret: '',
  clear_client_secret: false,
  has_client_secret: false,
  scopes: 'openid profile email',
  enabled: true,
})
const isNew = computed(() => form.value.id === null)

// Suggest an identifier from the name until the admin edits it themselves.
const slugTouched = ref(false)
const onNameInput = () => {
  if (!isNew.value || slugTouched.value) return
  form.value.slug = form.value.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 64)
}

const openCreate = () => {
  form.value = {
    id: null, slug: '', name: '', issuer: '', client_id: '', client_secret: '',
    clear_client_secret: false, has_client_secret: false, scopes: 'openid profile email', enabled: true,
  }
  slugTouched.value = false
  testResult.value = null
  showDialog.value = true
}

const openEdit = (p: AuthProvider) => {
  form.value = {
    id: p.id, slug: p.slug, name: p.name, issuer: p.issuer, client_id: p.client_id, client_secret: '',
    clear_client_secret: false, has_client_secret: p.has_client_secret, scopes: p.scopes, enabled: p.enabled,
  }
  testResult.value = null
  showDialog.value = true
}

const testIssuer = async () => {
  testing.value = true
  testResult.value = null
  try {
    // The outcome is shown next to the form field, not as a toast.
    const result = await request<Ack & { issuer?: string; pkce?: boolean }>(
      'displayhive:admin:authproviders:cts:test_provider',
      { issuer: form.value.issuer.trim() },
      { error: 'Test failed', onError: (text) => { testResult.value = { ok: false, text } } },
    )
    if (result) testResult.value = { ok: true, text: `Found ${result.issuer}${result.pkce ? '' : ' (note: it does not advertise PKCE support)'}` }
  } finally {
    testing.value = false
  }
}

const save = async () => {
  saving.value = true
  try {
    const result = await request<Result>('displayhive:admin:authproviders:cts:save_provider', {
      id: form.value.id,
      slug: form.value.slug,
      name: form.value.name,
      issuer: form.value.issuer,
      client_id: form.value.client_id,
      client_secret: form.value.client_secret,
      clear_client_secret: form.value.clear_client_secret,
      scopes: form.value.scopes,
      enabled: form.value.enabled,
    }, { success: `Login provider "${form.value.name}" saved`, error: 'Save failed' })
    if (result) {
      providers.value = result.providers || []
      showDialog.value = false
    }
  } finally {
    saving.value = false
  }
}

const remove = (p: AuthProvider) => {
  confirm.require({
    message: `Delete login provider "${p.name}"? Its button disappears from the login page. Accounts and their SSO links stay — adding a provider for the same issuer again restores those logins.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      const result = await request<Result>('displayhive:admin:authproviders:cts:delete_provider', { id: p.id }, { success: 'Login provider deleted', error: 'Delete failed' })
      if (result) providers.value = result.providers || []
    },
  })
}
</script>

<template>
  <Card data-tour="settings-login-providers">
    <template #title>
      <div class="card-header-title">
        <i class="pi pi-id-card card-header-icon" />
        <span>Login providers (SSO)</span>
      </div>
    </template>
    <template #content>
      <p class="lp-intro">
        Let people log in with an OpenID Connect provider (Keycloak, Microsoft Entra ID, Authentik, Google, …).
        The first login creates an account without any groups; assign groups on the Users page.
      </p>

      <div v-if="loading" class="lp-muted">Loading…</div>
      <div v-else-if="!providers.length" class="lp-muted">No login providers yet.</div>
      <ul v-else class="lp-list">
        <li v-for="p in providers" :key="p.id" class="lp-item">
          <div class="lp-item-main">
            <span class="lp-item-name">{{ p.name }}</span>
            <Tag v-if="!p.enabled" value="Disabled" severity="secondary" />
            <div class="lp-muted lp-item-issuer">{{ p.issuer }}</div>
          </div>
          <Button icon="pi pi-pencil" text rounded severity="secondary" title="Edit" @click="openEdit(p)" />
          <Button icon="pi pi-trash" text rounded severity="danger" title="Delete" @click="remove(p)" />
        </li>
      </ul>

      <div class="lp-actions">
        <Button label="Add provider" icon="pi pi-plus" @click="openCreate" />
      </div>
    </template>
  </Card>

  <Dialog v-model:visible="showDialog" modal :style="{ width: '520px' }">
    <template #header>
      <div class="dialog-title">
        <span class="dialog-title-icon-badge"><i class="pi pi-id-card dialog-title-icon"></i></span>
        <span class="p-dialog-title">{{ isNew ? 'Add login provider' : 'Edit login provider' }}</span>
      </div>
    </template>

    <div class="lp-form">
      <label for="lp-name">Name (shown on the login button)</label>
      <InputText id="lp-name" v-model="form.name" autofocus placeholder="Company SSO" @input="onNameInput" />

      <label for="lp-slug">Identifier</label>
      <InputText
        id="lp-slug"
        v-model="form.slug"
        :disabled="!isNew"
        placeholder="company-sso"
        @input="slugTouched = true"
      />
      <small class="lp-muted">Part of the redirect URI, so it can't be changed later.</small>

      <label>Redirect URI (register this at the provider)</label>
      <div class="lp-inline">
        <InputText :value="redirectUriFor(form.slug)" readonly class="lp-grow" />
        <Button icon="pi pi-copy" text title="Copy" :disabled="!form.slug" @click="copy(redirectUriFor(form.slug))" />
      </div>

      <label for="lp-issuer">Issuer URL</label>
      <div class="lp-inline">
        <InputText id="lp-issuer" v-model="form.issuer" class="lp-grow" placeholder="https://login.example.com/realms/main" />
        <Button label="Test" text :loading="testing" :disabled="!form.issuer" @click="testIssuer" />
      </div>
      <Message v-if="testResult" :severity="testResult.ok ? 'success' : 'error'" :closable="false">{{ testResult.text }}</Message>

      <label for="lp-client-id">Client ID</label>
      <InputText id="lp-client-id" v-model="form.client_id" />

      <label for="lp-client-secret">Client secret</label>
      <Password
        v-model="form.client_secret"
        input-id="lp-client-secret"
        :feedback="false"
        toggle-mask
        autocomplete="off"
        :placeholder="form.has_client_secret ? 'Stored — leave empty to keep it' : 'Leave empty for a public client'"
      />
      <div v-if="form.has_client_secret" class="lp-checkbox-row">
        <Checkbox v-model="form.clear_client_secret" input-id="lp-clear-secret" binary />
        <label for="lp-clear-secret">Remove the stored secret</label>
      </div>

      <label for="lp-scopes">Scopes</label>
      <InputText id="lp-scopes" v-model="form.scopes" />
      <small class="lp-muted">"openid" is always included.</small>

      <div class="lp-checkbox-row lp-toggle-row">
        <label for="lp-enabled">Show on the login page</label>
        <ToggleSwitch v-model="form.enabled" input-id="lp-enabled" />
      </div>
    </div>

    <template #footer>
      <Button label="Cancel" text @click="showDialog = false" />
      <Button label="Save" icon="pi pi-check" :loading="saving" @click="save" />
    </template>
  </Dialog>
</template>

<style scoped>
.lp-intro {
  margin: 0 0 1rem;
  font-size: 0.9rem;
}

.lp-muted {
  color: var(--p-text-muted-color, #6b7280);
  font-size: 0.85rem;
}

.lp-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}

.lp-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--p-content-border-color, #e5e7eb);
}

.lp-item-main {
  flex: 1;
  min-width: 0;
}

.lp-item-name {
  font-weight: 600;
  margin-right: 0.5rem;
}

.lp-item-issuer {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lp-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 1rem;
}

.lp-form {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.lp-form > label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
  margin-top: 0.5rem;
}

.lp-form :deep(.p-password),
.lp-form :deep(.p-password input) {
  width: 100%;
}

.lp-inline {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.lp-grow {
  flex: 1;
  min-width: 0;
}

.lp-checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.25rem;
}

.lp-toggle-row {
  justify-content: space-between;
  margin-top: 0.75rem;
}
</style>
