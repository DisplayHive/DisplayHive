<script setup lang="ts">
import { computed, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirmAction } from '../../composables/useConfirmAction'
import { useAck, type Ack } from '../../composables/useAck'
import { useUsersPage, formatDate, isSsoAccount } from '../../composables/users/useUsersPage'
import { useAuthStore } from '../../stores/auth'
import { useRightsStore } from '../../stores/rights'
import type { AdminUser, AdminUserIdentity } from '../../types/models'
import AccountDialog from './AccountDialog.vue'
import MergeDialog from './MergeDialog.vue'
import UserRightsDialog from './UserRightsDialog.vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Message from 'primevue/message'
import Popover from 'primevue/popover'
import Tag from 'primevue/tag'
import ToggleSwitch from 'primevue/toggleswitch'

// The Accounts tab: the user table and its row actions, with the dialogs they open.
const page = useUsersPage()
const toast = useToast()
const { confirmDanger } = useConfirmAction()
const { request } = useAck()
const authStore = useAuthStore()
const rightsStore = useRightsStore()

const canMerge = computed(() => page.canEdit && page.canDelete)

// --- create / edit / merge / rights dialogs (they own their forms) ---
const showAccountDialog = ref(false)
const editingAccount = ref<AdminUser | null>(null)
const openCreateAccountDialog = () => {
  editingAccount.value = null
  showAccountDialog.value = true
}
const openEditAccountDialog = (user: AdminUser) => {
  editingAccount.value = user
  showAccountDialog.value = true
}

const showMergeDialog = ref(false)
const mergeSource = ref<AdminUser | null>(null)
const openMergeDialog = (user: AdminUser) => {
  mergeSource.value = user
  showMergeDialog.value = true
}

const showUserRightsDialog = ref(false)
const rightsUser = ref<AdminUser | null>(null)
const openUserRightsDialog = (user: AdminUser) => {
  rightsUser.value = user
  showUserRightsDialog.value = true
}

// --- activate / delete / impersonate ---
const toggleActiveUser = async (user: AdminUser, val: boolean) => {
  const previous = user.is_active
  user.is_active = val
  const ack = await request(
    'displayhive:admin:users:cts:set_active',
    { id: user.id, is_active: val },
    { success: `User ${user.username} ${val ? 'activated' : 'deactivated'}`, error: 'Update failed' },
  )
  if (!ack) user.is_active = previous
}

const deleteAccount = (user: AdminUser) => {
  confirmDanger({
    message: `Are you sure you want to delete user "${user.username}"? This cannot be undone.`,
    accept: async () => {
      const ack = await request('displayhive:admin:users:cts:delete_user', { id: user.id }, { success: 'User deleted', error: 'Delete failed' })
      if (ack) page.loadAll()
    },
  })
}

const impersonateLoading = ref(false)

const impersonate = async (user: AdminUser) => {
  impersonateLoading.value = true
  try {
    // Over HTTP, not the socket: the new session is a cookie, which only a response can set.
    const error = await authStore.startImpersonation(user.id)
    if (error) {
      toast.add({ severity: 'error', summary: 'Error', detail: error, life: 5000 })
    } else {
      toast.add({ severity: 'info', summary: 'Impersonating', detail: `Now logged in as ${user.username}`, life: 3000 })
    }
  } finally {
    impersonateLoading.value = false
  }
}

// --- recent-logins popover ---
interface LoginEntry { logged_in_at: string | null }

const loginsPopover = ref<InstanceType<typeof Popover> | null>(null)
const loginsLoading = ref(false)
const loginsForUser = ref<LoginEntry[]>([])
const loginsUsername = ref('')

const toggleLogins = async (event: Event, user: AdminUser) => {
  loginsPopover.value?.toggle(event)
  loginsUsername.value = user.username
  loginsForUser.value = []
  loginsLoading.value = true
  try {
    const ack = await request<Ack & { logins?: LoginEntry[] }>(
      'displayhive:admin:users:cts:get_user_logins',
      { id: user.id },
      { error: 'Failed to load login history' },
    )
    if (ack) loginsForUser.value = ack.logins || []
  } finally {
    loginsLoading.value = false
  }
}
</script>

<template>
    <Message v-if="!page.canManageAccountsAny" severity="warn" :closable="false" class="users-warning">
      You have read-only access to Accounts — you can view accounts, but not create, edit, activate/deactivate, or delete them.
    </Message>
    <Message v-if="page.ssoAccountsWithoutGroups.length" severity="info" :closable="false" class="users-warning" data-testid="sso-accounts-hint">
      {{ page.ssoAccountsWithoutGroups.length === 1 ? 'An SSO login created an account' : `SSO logins created ${page.ssoAccountsWithoutGroups.length} accounts` }}
      without any groups (so without rights):
      <strong>{{ page.ssoAccountsWithoutGroups.map((u) => u.username).join(', ') }}</strong>.
      Assign groups with <i class="pi pi-shield"></i>, or — if it belongs to someone who already has an account —
      merge it into that account with <i class="pi pi-arrow-right-arrow-left"></i>.
    </Message>

    <Card>
      <template #title>
        <div class="card-header">
          <Button v-if="page.canCreate" data-tour="users-add-user" label="Add User" icon="pi pi-plus" size="small" @click="openCreateAccountDialog" />
        </div>
      </template>
      <template #content>
        <DataTable
          data-tour="users-table"
          :value="page.users"
          :loading="page.usersLoading"
          data-key="id"
          sortField="username"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="page.users.length > 10"
          :rows="10"
          responsive-layout="scroll"
        >
          <Column field="username" header="Username" sortable>
            <template #body="{ data }">
              {{ data.username }}
              <Tag
                v-if="isSsoAccount(data)"
                value="SSO"
                severity="info"
                class="ml-2"
                :title="data.identities.map((i: AdminUserIdentity) => `${i.provider_name || i.issuer}: ${i.display_name || i.subject}`).join('\n')"
              />
              <Tag
                v-if="data.must_change_password"
                value="Password reset pending"
                severity="warn"
                class="ml-2"
                title="Must choose a new password on next login"
              />
            </template>
          </Column>
          <Column field="is_active" header="Active" style="width: 6rem">
            <template #body="{ data }">
              <ToggleSwitch
                :model-value="data.is_active"
                :disabled="!page.canActivate"
                @update:model-value="(val: boolean) => toggleActiveUser(data, val)"
              />
            </template>
          </Column>
          <Column v-if="page.canViewRights" header="Groups">
            <template #body="{ data }">
              <template v-if="page.userRightsById.get(data.id)?.group_ids.length">
                <Tag
                  v-for="gid in page.userRightsById.get(data.id)!.group_ids"
                  :key="gid"
                  :value="page.groupById.get(gid)?.name || `#${gid}`"
                  :severity="page.groupById.get(gid)?.is_superadmin ? 'danger' : 'secondary'"
                  class="mr-1"
                />
              </template>
              <span v-else class="muted">none</span>
            </template>
          </Column>
          <Column field="created_at" header="Created">
            <template #body="{ data }">{{ formatDate(data.created_at) }}</template>
          </Column>
          <Column field="last_login_at" header="Last Login">
            <template #body="{ data }">{{ formatDate(data.last_login_at) }}</template>
          </Column>
          <Column header="Actions" style="width: 18rem">
            <template #body="{ data }">
              <Button
                icon="pi pi-info-circle"
                text
                rounded
                severity="secondary"
                title="Recent logins"
                @click="toggleLogins($event, data)"
              />
              <Button
                v-if="rightsStore.can('special.impersonate') && !authStore.isImpersonating && data.username !== authStore.username"
                icon="pi pi-user-edit"
                text
                rounded
                severity="warn"
                title="Impersonate"
                :disabled="!data.is_active || impersonateLoading"
                @click="impersonate(data)"
              />
              <Button
                v-if="page.canEdit || page.canSetPassword"
                icon="pi pi-pencil"
                text
                rounded
                severity="secondary"
                title="Edit account"
                @click="openEditAccountDialog(data)"
              />
              <Button
                v-if="canMerge && isSsoAccount(data) && !data.has_password && data.username !== authStore.username"
                icon="pi pi-arrow-right-arrow-left"
                text
                rounded
                severity="secondary"
                title="Merge into existing user…"
                @click="openMergeDialog(data)"
              />
              <Button
                v-if="page.canViewRights"
                data-tour="users-row-manage-rights"
                icon="pi pi-shield"
                text
                rounded
                title="Manage rights"
                @click="openUserRightsDialog(data)"
              />
              <Button
                v-if="page.canDelete"
                icon="pi pi-trash"
                text
                rounded
                severity="danger"
                title="Delete"
                :disabled="data.username === authStore.username && page.users.length <= 1"
                @click="deleteAccount(data)"
              />
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

<Popover ref="loginsPopover">
  <div class="logins-popover">
    <h4>Recent logins — {{ loginsUsername }}</h4>
    <div v-if="loginsLoading" class="logins-loading">
      <i class="pi pi-spin pi-spinner"></i>
    </div>
    <ul v-else-if="loginsForUser.length" class="logins-list">
      <li v-for="(entry, i) in loginsForUser" :key="i">
        <span>{{ formatDate(entry.logged_in_at) }}</span>
      </li>
    </ul>
    <p v-else class="muted">No recorded logins yet.</p>
  </div>
</Popover>

  <AccountDialog v-model:visible="showAccountDialog" :account="editingAccount" />
  <MergeDialog v-model:visible="showMergeDialog" :source="mergeSource" />
  <UserRightsDialog v-model:visible="showUserRightsDialog" :user="rightsUser" />
</template>

<style scoped>
.users-warning {
  margin-bottom: 1rem;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.muted {
  color: var(--p-text-muted-color, #9ca3af);
  font-size: 0.85rem;
}

.logins-popover {
  min-width: 16rem;
  max-width: 20rem;
}

.logins-popover h4 {
  margin: 0 0 0.6rem;
  font-size: 0.85rem;
}

.logins-loading {
  display: flex;
  justify-content: center;
  padding: 0.75rem 0;
}

.logins-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.logins-list li {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  font-size: 0.85rem;
}
</style>
