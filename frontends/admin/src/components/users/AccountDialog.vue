<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirmAction } from '../../composables/useConfirmAction'
import { useAck } from '../../composables/useAck'
import { useUsersPage, formatDate } from '../../composables/users/useUsersPage'
import type { AdminUser, AdminUserIdentity } from '../../types/models'
import DialogTitle from '../DialogTitle.vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'

// Create (account = null) or edit an account: username, password and password policy, and
// the SSO logins that can be unlinked.
const props = defineProps<{ account: AdminUser | null }>()
const visible = defineModel<boolean>('visible', { required: true })

const page = useUsersPage()
const toast = useToast()
const { confirmDanger } = useConfirmAction()
const { request } = useAck()

const isNewAccount = computed(() => props.account === null)
const isSavingAccount = ref(false)
type AccountForm = {
  id: number | null
  username: string
  password: string
  mustChangePassword: boolean
  passwordLoginAllowed: boolean
}
const accountForm = ref<AccountForm>({ id: null, username: '', password: '', mustChangePassword: false, passwordLoginAllowed: true })

// Every time the dialog opens, start from the account (or from a blank form).
watch(visible, (open) => {
  if (!open) return
  const user = props.account
  accountForm.value = user
    ? {
        id: user.id,
        username: user.username,
        password: '',
        mustChangePassword: !!user.must_change_password,
        passwordLoginAllowed: user.password_login_allowed !== false,
      }
    : { id: null, username: '', password: '', mustChangePassword: false, passwordLoginAllowed: true }
})

// The live row for the account being edited, so its SSO identity list
// refreshes when an unlink comes back through the users broadcast.
const editingAccount = computed(() => page.users.find((u) => u.id === accountForm.value.id))

// A password reset only means something for an account that logs in with a
// password; typing a new password switches password login on (server-side too).
const passwordLoginWillBeAllowed = computed(
  () => isNewAccount.value || accountForm.value.passwordLoginAllowed || !!accountForm.value.password,
)

const unlinkIdentity = (identity: AdminUserIdentity) => {
  confirmDanger({
    message: `Unlink the SSO login "${identity.display_name || identity.subject}"? Its next SSO login creates a new, separate account.`,
    header: 'Unlink SSO login',
    accept: async () => {
      const ack = await request('displayhive:admin:users:cts:unlink_identity', { id: identity.id }, { success: 'SSO login unlinked', error: 'Unlink failed' })
      if (ack) page.loadUsers()
    },
  })
}

const saveAccount = async () => {
  if (!accountForm.value.username.trim()) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Username is required', life: 4000 })
    return
  }
  if (isNewAccount.value && accountForm.value.password.length < 8) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Password must be at least 8 characters', life: 4000 })
    return
  }

  isSavingAccount.value = true
  try {
    const event = isNewAccount.value
      ? 'displayhive:admin:users:cts:create_user'
      : 'displayhive:admin:users:cts:update_user'
    const payload: Record<string, unknown> = { username: accountForm.value.username.trim() }
    if (isNewAccount.value) {
      payload.password = accountForm.value.password
      payload.must_change_password = accountForm.value.mustChangePassword
    } else {
      payload.id = accountForm.value.id
      if (accountForm.value.password) payload.password = accountForm.value.password
      // Gated by users.set_password server-side, same as the password itself.
      if (page.canSetPassword) {
        payload.password_login_allowed = passwordLoginWillBeAllowed.value
        payload.must_change_password = passwordLoginWillBeAllowed.value && accountForm.value.mustChangePassword
      }
    }

    const ack = await request(event, payload, { success: isNewAccount.value ? 'User created' : 'User updated', error: 'Save failed' })
    if (ack) {
      visible.value = false
      page.loadAll()
    }
  } finally {
    isSavingAccount.value = false
  }
}
</script>

<template>
<Dialog
  v-model:visible="visible"
  modal
  :style="{ width: '420px' }"
>
  <template #header>
    <DialogTitle icon="pi-user" :title="isNewAccount ? 'Add User' : 'Edit User'" />
  </template>
  <div class="dialog-form" data-tour="users-account-fields">
    <label for="user-username">Username</label>
    <InputText id="user-username" v-model="accountForm.username" autofocus :disabled="!isNewAccount && !page.canEdit" />

    <template v-if="isNewAccount || page.canSetPassword">
      <label for="user-password">
        {{
          isNewAccount
            ? 'Password'
            : editingAccount?.has_password
              ? 'New Password (leave blank to keep current)'
              : 'Password (none set yet — setting one allows password login)'
        }}
      </label>
      <Password id="user-password" v-model="accountForm.password" :feedback="false" toggle-mask />

      <div v-if="!isNewAccount" class="must-change-password-row">
        <Checkbox
          v-model="accountForm.passwordLoginAllowed"
          input-id="user-password-login-allowed"
          binary
          :disabled="!!accountForm.password"
        />
        <label for="user-password-login-allowed">Allow login with username and password</label>
      </div>

      <div v-if="passwordLoginWillBeAllowed" class="must-change-password-row">
        <Checkbox v-model="accountForm.mustChangePassword" input-id="user-must-change-password" binary />
        <label for="user-must-change-password">Force user to reset password on next login</label>
      </div>
    </template>

    <template v-if="!isNewAccount && editingAccount?.identities?.length">
      <label>SSO logins</label>
      <ul class="identity-list">
        <li v-for="identity in editingAccount.identities" :key="identity.id" class="identity-item">
          <div class="identity-main">
            <span class="identity-name">{{ identity.display_name || identity.subject }}</span>
            <small class="muted">
              {{ identity.provider_name || identity.issuer }} · last login {{ formatDate(identity.last_login_at) }}
            </small>
          </div>
          <Button
            v-if="page.canEdit"
            icon="pi pi-link"
            text
            rounded
            severity="danger"
            title="Unlink this SSO login"
            @click="unlinkIdentity(identity)"
          />
        </li>
      </ul>
    </template>
  </div>

  <template #footer>
    <Button data-tour="users-account-cancel" label="Cancel" text @click="visible = false" />
    <Button label="Save" icon="pi pi-check" :loading="isSavingAccount" @click="saveAccount" />
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

.identity-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.identity-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0;
}

.identity-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.identity-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.must-change-password-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.must-change-password-row label {
  margin-top: 0;
  font-weight: 400;
  color: inherit;
}

.muted {
  color: var(--p-text-muted-color, #9ca3af);
  font-size: 0.85rem;
}
</style>
