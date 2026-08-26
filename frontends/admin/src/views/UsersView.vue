<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useAuthStore } from '../stores/auth'
import { useRightsStore } from '../stores/rights'
import type { AdminUser, RightDefinition, RightsGroup, UserRightsRow, RightOverrideValue } from '../types/models'

import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Dialog from 'primevue/dialog'
import Card from 'primevue/card'
import ToggleSwitch from 'primevue/toggleswitch'
import Message from 'primevue/message'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import Select from 'primevue/select'
import MultiSelect from 'primevue/multiselect'
import Checkbox from 'primevue/checkbox'
import Tag from 'primevue/tag'
import Popover from 'primevue/popover'

const toast = useToast()
const confirm = useConfirm()
const authStore = useAuthStore()
const rightsStore = useRightsStore()
const { on, off, emit, emitWithAck, isConnected } = useSocket()

// --- Rights gates ---------------------------------------------------------------

const canViewUsers = computed(() => rightsStore.can('users.page'))
const canViewRights = computed(() => rightsStore.can('rights.page'))
const canManageRights = computed(() => rightsStore.can('rights.manage'))

const canCreate = computed(() => rightsStore.can('users.create'))
const canEdit = computed(() => rightsStore.can('users.edit'))
const canSetPassword = computed(() => rightsStore.can('users.set_password'))
const canDelete = computed(() => rightsStore.can('users.delete'))
const canActivate = computed(() => rightsStore.can('users.activate'))
const canManageAccountsAny = computed(
  () => canCreate.value || canEdit.value || canSetPassword.value || canDelete.value || canActivate.value,
)

const defaultTab = computed(() => (canViewUsers.value ? 'accounts' : 'groups'))

// --- Accounts: list ---------------------------------------------------------------

const users = ref<AdminUser[]>([])
const usersLoading = ref(true)

const handleUsers = (data: { users?: AdminUser[] }) => {
  users.value = data?.users || []
  usersLoading.value = false
}

const loadUsers = () => {
  if (!canViewUsers.value) {
    usersLoading.value = false
    return
  }
  usersLoading.value = true
  emit('displayhive:admin:users:cts:get_users')
}

// --- Rights: catalog / groups / per-user rights ------------------------------------

const rightsLoading = ref(true)
const catalog = ref<RightDefinition[]>([])
const groups = ref<RightsGroup[]>([])
const userRights = ref<UserRightsRow[]>([])

const categories = computed(() => {
  const seen = new Map<string, RightDefinition[]>()
  for (const r of catalog.value) {
    if (!seen.has(r.category)) seen.set(r.category, [])
    seen.get(r.category)!.push(r)
  }
  return Array.from(seen.entries()).map(([category, rights]) => ({ category, rights }))
})

const catalogByKey = computed(() => new Map(catalog.value.map((r) => [r.key, r])))
const categoryOf = (rightKey: string): string | undefined => catalogByKey.value.get(rightKey)?.category

/** The "<category>.page" right for a category, if the catalog defines one (not every category has one, e.g. "special"). */
const pageRightFor = (category: { category: string; rights: RightDefinition[] }): RightDefinition | undefined =>
  category.rights.find((r) => r.key.endsWith('.page'))

/** *group*'s ancestor chain, nearest parent first. */
const groupAncestors = (group: RightsGroup): RightsGroup[] => {
  const chain: RightsGroup[] = []
  const seen = new Set<number>([group.id])
  let parentId = group.parent_group_id
  while (parentId != null) {
    const parent = groupById.value.get(parentId)
    if (!parent || seen.has(parent.id)) break
    seen.add(parent.id)
    chain.push(parent)
    parentId = parent.parent_group_id
  }
  return chain
}

/** The nearest ancestor of the group currently open in the rights dialog that
 * grants *rightKey* — directly, or implicitly by being the Superadmin group —
 * or undefined if no ancestor grants it. Used to show "inherited from X". */
const inheritedRightSource = (rightKey: string): RightsGroup | undefined => {
  if (!editingGroup.value) return undefined
  for (const ancestor of groupAncestors(editingGroup.value)) {
    if (ancestor.is_superadmin || ancestor.rights.includes(rightKey)) return ancestor
  }
  return undefined
}

/** Whether a category's other rights should be shown in the group-rights matrix
 * — hidden until the group holds (directly or via inheritance) that category's
 * page right, since the rest are unreachable without it. Categories with no
 * page right always show everything. */
const isCategoryUnlockedForGroup = (category: { category: string; rights: RightDefinition[] }): boolean => {
  const pageRight = pageRightFor(category)
  if (!pageRight) return true
  return editingGroupRights.value.has(pageRight.key) || !!inheritedRightSource(pageRight.key)
}

/** Same idea for the per-user override matrix, but keyed off the resolved
 * effective right rather than the raw override (an "inherit" override can
 * still resolve to allowed via group membership). */
const isCategoryUnlockedForUser = (category: { category: string; rights: RightDefinition[] }): boolean => {
  const pageRight = pageRightFor(category)
  if (!pageRight) return true
  return !!editingUser.value?.effective_rights[pageRight.key]
}

const groupById = computed(() => new Map(groups.value.map((g) => [g.id, g])))
const groupOptions = computed(() => groups.value.map((g) => ({ label: g.name, value: g.id })))
const userRightsById = computed(() => new Map(userRights.value.map((u) => [u.id, u])))

interface GroupTreeRow extends RightsGroup {
  depth: number
}

/**
 * Groups ordered depth-first (parents immediately followed by their children,
 * alphabetically among siblings) with a `depth` so the table can indent to
 * show the hierarchy instead of just listing a "Parent" name column.
 */
const orderedGroups = computed<GroupTreeRow[]>(() => {
  const byParent = new Map<number | null, RightsGroup[]>()
  for (const g of groups.value) {
    const key = g.parent_group_id
    if (!byParent.has(key)) byParent.set(key, [])
    byParent.get(key)!.push(g)
  }
  for (const siblings of byParent.values()) {
    siblings.sort((a, b) => a.name.localeCompare(b.name))
  }

  const result: GroupTreeRow[] = []
  const visited = new Set<number>()

  const visit = (parentId: number | null, depth: number) => {
    for (const g of byParent.get(parentId) || []) {
      if (visited.has(g.id)) continue // defensive: a cycle should never exist server-side
      visited.add(g.id)
      result.push({ ...g, depth })
      visit(g.id, depth + 1)
    }
  }
  visit(null, 0)

  // A group whose parent_group_id doesn't resolve (shouldn't happen, but
  // don't let it silently vanish from the table) — show it as a root.
  for (const g of groups.value) {
    if (!visited.has(g.id)) result.push({ ...g, depth: 0 })
  }

  return result
})

const parentOptions = (excludeId: number | null) => [
  { label: '-- No parent --', value: null as number | null },
  ...groups.value.filter((g) => g.id !== excludeId).map((g) => ({ label: g.name, value: g.id as number | null })),
]

const loadRights = async () => {
  if (!canViewRights.value) {
    rightsLoading.value = false
    return
  }
  // emitWithAck() rejects immediately rather than queuing when the socket
  // isn't connected yet (unlike plain emit()) — on a hard page reload this
  // component can mount before App.vue's connect() has finished its
  // handshake, so bail out here and let the isConnected watcher below retry
  // once the socket is actually up, instead of silently leaving the tables
  // empty with an unhandled rejection.
  if (!isConnected.value) return
  rightsLoading.value = true
  try {
    const [catalogRes, groupsRes, usersRes] = await Promise.all([
      emitWithAck<{ rights: RightDefinition[] }>('displayhive:admin:rights:cts:get_catalog'),
      emitWithAck<{ success: boolean; groups?: RightsGroup[]; error?: string }>('displayhive:admin:rights:cts:get_groups'),
      emitWithAck<{ success: boolean; users?: UserRightsRow[]; error?: string }>('displayhive:admin:rights:cts:get_users_rights'),
    ])
    catalog.value = catalogRes?.rights || []
    if (groupsRes?.success) groups.value = groupsRes.groups || []
    else toast.add({ severity: 'error', summary: 'Error', detail: groupsRes?.error || 'Failed to load groups', life: 5000 })
    if (usersRes?.success) userRights.value = usersRes.users || []
    else toast.add({ severity: 'error', summary: 'Error', detail: usersRes?.error || 'Failed to load user rights', life: 5000 })
  } catch {
    // Most likely the socket dropped between the isConnected check above and
    // the emit itself — the isConnected watcher will retry on the next
    // reconnect, so just surface it rather than leaving a silent rejection.
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to load rights data', life: 5000 })
  } finally {
    rightsLoading.value = false
  }
}

const loadAll = () => {
  loadUsers()
  loadRights()
}

onMounted(() => {
  on('displayhive:admin:users:stc:users', handleUsers)
  if (isConnected.value) loadAll()
})

// Fires on the initial connect (fresh page load) and on every reconnect, so
// data is (re-)fetched as soon as the socket is actually usable — fixes both
// tables coming up empty after a hard reload, where this component mounts
// before the socket handshake has finished (see loadRights() above).
watch(isConnected, (connected) => {
  if (connected) loadAll()
})

onUnmounted(() => {
  off('displayhive:admin:users:stc:users', handleUsers)
})

// --- Accounts: create / edit / delete / activate / impersonate ---------------------

const showAccountDialog = ref(false)
const isNewAccount = ref(false)
const isSavingAccount = ref(false)
const accountForm = ref<{ id: number | null; username: string; password: string }>({
  id: null,
  username: '',
  password: '',
})

const openCreateAccountDialog = () => {
  isNewAccount.value = true
  accountForm.value = { id: null, username: '', password: '' }
  showAccountDialog.value = true
}

const openEditAccountDialog = (user: AdminUser) => {
  isNewAccount.value = false
  accountForm.value = { id: user.id, username: user.username, password: '' }
  showAccountDialog.value = true
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
    } else {
      payload.id = accountForm.value.id
      if (accountForm.value.password) payload.password = accountForm.value.password
    }

    const result = await emitWithAck<{ success: boolean; error?: string }>(event, payload)
    if (result.success) {
      toast.add({
        severity: 'success',
        summary: 'Success',
        detail: isNewAccount.value ? 'User created' : 'User updated',
        life: 3000,
      })
      showAccountDialog.value = false
      loadUsers()
      loadRights()
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Save failed', life: 5000 })
    }
  } finally {
    isSavingAccount.value = false
  }
}

const toggleActiveUser = async (user: AdminUser, val: boolean) => {
  const previous = user.is_active
  user.is_active = val
  const result = await emitWithAck<{ success: boolean; error?: string }>(
    'displayhive:admin:users:cts:set_active',
    { id: user.id, is_active: val },
  )
  if (result.success) {
    toast.add({
      severity: 'success',
      summary: 'Updated',
      detail: `User ${user.username} ${val ? 'activated' : 'deactivated'}`,
      life: 2000,
    })
  } else {
    user.is_active = previous
    toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Update failed', life: 5000 })
  }
}

const deleteAccount = (user: AdminUser) => {
  confirm.require({
    message: `Are you sure you want to delete user "${user.username}"? This cannot be undone.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      const result = await emitWithAck<{ success: boolean; error?: string }>(
        'displayhive:admin:users:cts:delete_user',
        { id: user.id },
      )
      if (result.success) {
        toast.add({ severity: 'success', summary: 'Deleted', detail: 'User deleted', life: 3000 })
        loadUsers()
        loadRights()
      } else {
        toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Delete failed', life: 5000 })
      }
    },
  })
}

const impersonateLoading = ref(false)

const impersonate = async (user: AdminUser) => {
  impersonateLoading.value = true
  try {
    const result = await emitWithAck<{
      success: boolean
      error?: string
      token?: string
      username?: string
    }>('displayhive:admin:users:cts:impersonate', { user_id: user.id })
    if (result.success && result.token && result.username) {
      authStore.startImpersonation(result.token, result.username)
      toast.add({ severity: 'info', summary: 'Impersonating', detail: `Now logged in as ${result.username}`, life: 3000 })
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Impersonation failed', life: 5000 })
    }
  } finally {
    impersonateLoading.value = false
  }
}

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : '—')

// --- Accounts: recent-logins popover -------------------------------------------

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
    const result = await emitWithAck<{ success: boolean; logins?: LoginEntry[]; error?: string }>(
      'displayhive:admin:users:cts:get_user_logins',
      { id: user.id },
    )
    if (result.success) {
      loginsForUser.value = result.logins || []
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Failed to load login history', life: 5000 })
    }
  } finally {
    loginsLoading.value = false
  }
}

// --- Groups: create / rename / move / delete ---------------------------------

const showGroupDialog = ref(false)
const isGroupNew = ref(false)
const isSavingGroup = ref(false)
const groupForm = ref<{ id: number | null; name: string; parent_group_id: number | null }>({
  id: null,
  name: '',
  parent_group_id: null,
})

const openCreateGroupDialog = () => {
  isGroupNew.value = true
  groupForm.value = { id: null, name: '', parent_group_id: null }
  showGroupDialog.value = true
}

const openEditGroupDialog = (group: RightsGroup) => {
  isGroupNew.value = false
  groupForm.value = { id: group.id, name: group.name, parent_group_id: group.parent_group_id }
  showGroupDialog.value = true
}

const saveGroup = async () => {
  if (!groupForm.value.name.trim()) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Group name is required', life: 4000 })
    return
  }
  isSavingGroup.value = true
  try {
    const event = isGroupNew.value
      ? 'displayhive:admin:rights:cts:create_group'
      : 'displayhive:admin:rights:cts:update_group'
    const payload: Record<string, unknown> = {
      name: groupForm.value.name.trim(),
      parent_group_id: groupForm.value.parent_group_id,
    }
    if (!isGroupNew.value) payload.id = groupForm.value.id
    const result = await emitWithAck<{ success: boolean; error?: string }>(event, payload)
    if (result.success) {
      toast.add({ severity: 'success', summary: 'Success', detail: isGroupNew.value ? 'Group created' : 'Group updated', life: 3000 })
      showGroupDialog.value = false
      await loadRights()
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Save failed', life: 5000 })
    }
  } finally {
    isSavingGroup.value = false
  }
}

const deleteGroup = (group: RightsGroup) => {
  confirm.require({
    message: `Delete group "${group.name}"? This cannot be undone.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      const result = await emitWithAck<{ success: boolean; error?: string }>('displayhive:admin:rights:cts:delete_group', { id: group.id })
      if (result.success) {
        toast.add({ severity: 'success', summary: 'Deleted', detail: 'Group deleted', life: 3000 })
        await loadRights()
      } else {
        toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Delete failed', life: 5000 })
      }
    },
  })
}

// --- Groups: rights matrix -----------------------------------------------------

const showGroupRightsDialog = ref(false)
const editingGroup = ref<RightsGroup | null>(null)
const editingGroupRights = ref<Set<string>>(new Set())

const openGroupRightsDialog = (group: RightsGroup) => {
  editingGroup.value = group
  editingGroupRights.value = new Set(group.rights)
  showGroupRightsDialog.value = true
}

/** Apply a single group-right change to local state (editingGroupRights + the groups list entry). */
const applyGroupRightLocally = (rightKey: string, allow: boolean) => {
  if (allow) editingGroupRights.value.add(rightKey)
  else editingGroupRights.value.delete(rightKey)
  const group = editingGroup.value
  const g = group ? groupById.value.get(group.id) : undefined
  if (g) {
    g.rights = allow ? [...new Set([...g.rights, rightKey])] : g.rights.filter((k) => k !== rightKey)
  }
}

const toggleGroupRight = async (rightKey: string, checked: boolean) => {
  if (!editingGroup.value) return
  const group = editingGroup.value
  const result = await emitWithAck<{ success: boolean; error?: string }>('displayhive:admin:rights:cts:set_group_right', {
    group_id: group.id,
    right_key: rightKey,
    allow: checked,
  })
  if (!result.success) {
    toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Update failed', life: 5000 })
    return
  }
  applyGroupRightLocally(rightKey, checked)

  // Unsetting a category's page right also clears every other right in that
  // category — they're unreachable without page access, so leaving them
  // "granted" would be misleading. See pageRightFor()/canManageRights UI.
  if (!checked && rightKey.endsWith('.page')) {
    const category = categoryOf(rightKey)
    const others = catalog.value
      .filter((r) => r.category === category && r.key !== rightKey && editingGroupRights.value.has(r.key))
      .map((r) => r.key)
    if (others.length) await bulkSetGroupRights(others, false)
  }
}

/** Grant/revoke a batch of rights on the group currently open in the rights dialog. */
const bulkSetGroupRights = async (rightKeys: string[], allow: boolean) => {
  if (!editingGroup.value || !rightKeys.length) return
  const group = editingGroup.value
  // A single batched call, not N parallel set_group_right calls: this app runs
  // single-worker with eventlet, and N concurrent handler invocations sharing
  // one db.session can interleave and silently drop some of the N rights.
  const result = await emitWithAck<{ success: boolean; error?: string }>('displayhive:admin:rights:cts:set_group_rights_bulk', {
    group_id: group.id,
    right_keys: rightKeys,
    allow,
  })
  if (!result.success) {
    toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Bulk update failed', life: 5000 })
    return
  }
  for (const key of rightKeys) applyGroupRightLocally(key, allow)
}

// --- Per-user rights: group membership + right overrides ---------------------------

const showUserRightsDialog = ref(false)
const editingUser = ref<UserRightsRow | null>(null)
const editingUserGroupIds = ref<number[]>([])
const isSavingUserGroups = ref(false)

const emptyUserRightsRow = (user: AdminUser): UserRightsRow => ({
  id: user.id,
  username: user.username,
  group_ids: [],
  overrides: {},
  effective_rights: {},
})

const openUserRightsDialog = (user: AdminUser) => {
  editingUser.value = userRightsById.value.get(user.id) ?? emptyUserRightsRow(user)
  editingUserGroupIds.value = [...editingUser.value.group_ids]
  showUserRightsDialog.value = true
}

const saveUserGroups = async () => {
  if (!editingUser.value) return
  isSavingUserGroups.value = true
  try {
    const result = await emitWithAck<{ success: boolean; error?: string }>('displayhive:admin:rights:cts:set_user_groups', {
      user_id: editingUser.value.id,
      group_ids: editingUserGroupIds.value,
    })
    if (result.success) {
      toast.add({ severity: 'success', summary: 'Success', detail: 'Group membership updated', life: 3000 })
      await loadRights()
      const refreshed = userRightsById.value.get(editingUser.value.id)
      if (refreshed) editingUser.value = refreshed
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Update failed', life: 5000 })
    }
  } finally {
    isSavingUserGroups.value = false
  }
}

const overrideValue = (user: UserRightsRow, rightKey: string): RightOverrideValue =>
  user.overrides[rightKey] || 'inherit'

/** Re-fetch per-user rights from the server (the group closure that resolves
 * effective_rights lives server-side, so there's no way to recompute it
 * locally) and refresh editingUser from the new data. */
const refetchUserRights = async () => {
  const usersRes = await emitWithAck<{ success: boolean; users?: UserRightsRow[] }>('displayhive:admin:rights:cts:get_users_rights')
  if (usersRes?.success) {
    userRights.value = usersRes.users || []
    if (editingUser.value) {
      const refreshed = userRightsById.value.get(editingUser.value.id)
      if (refreshed) editingUser.value = refreshed
    }
  }
}

const setUserRight = async (rightKey: string, value: RightOverrideValue) => {
  if (!editingUser.value) return
  const result = await emitWithAck<{ success: boolean; error?: string }>('displayhive:admin:rights:cts:set_user_right', {
    user_id: editingUser.value.id,
    right_key: rightKey,
    value,
  })
  if (!result.success) {
    toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Update failed', life: 5000 })
    return
  }
  await refetchUserRights()

  // If this was a category's page right and it no longer resolves to
  // allowed, clear every other override in that category too — they're
  // unreachable without page access.
  if (rightKey.endsWith('.page') && editingUser.value && !editingUser.value.effective_rights[rightKey]) {
    const category = categoryOf(rightKey)
    const user = editingUser.value
    const others = catalog.value
      .filter((r) => r.category === category && r.key !== rightKey && overrideValue(user, r.key) !== 'inherit')
      .map((r) => r.key)
    if (others.length) await bulkSetUserRights(others, 'inherit')
  }
}

/** Set a batch of right overrides on the user currently open in the rights dialog. */
const bulkSetUserRights = async (rightKeys: string[], value: RightOverrideValue) => {
  if (!editingUser.value || !rightKeys.length) return
  const userId = editingUser.value.id
  // A single batched call, not N parallel set_user_right calls — see the
  // comment on bulkSetGroupRights for why.
  const result = await emitWithAck<{ success: boolean; error?: string }>('displayhive:admin:rights:cts:set_user_rights_bulk', {
    user_id: userId,
    right_keys: rightKeys,
    value,
  })
  if (!result.success) {
    toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Bulk update failed', life: 5000 })
  }
  await refetchUserRights()
}
</script>

<template>
  <div v-if="rightsStore.loaded && !canViewUsers && !canViewRights" class="users-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Users &amp; Rights page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="users-view">
    <Tabs :value="defaultTab">
      <TabList>
        <Tab v-if="canViewUsers" value="accounts">Accounts</Tab>
        <Tab v-if="canViewRights" value="groups">Groups</Tab>
      </TabList>
      <TabPanels>
        <!-- Accounts -->
        <TabPanel v-if="canViewUsers" value="accounts">
          <Message v-if="!canManageAccountsAny" severity="warn" :closable="false" class="users-warning">
            You have read-only access to Accounts — you can view accounts, but not create, edit, activate/deactivate, or delete them.
          </Message>

          <Card>
            <template #title>
              <div class="card-header">
                <Button v-if="canCreate" label="Add User" icon="pi pi-plus" size="small" @click="openCreateAccountDialog" />
              </div>
            </template>
            <template #content>
              <DataTable :value="users" :loading="usersLoading" data-key="id" responsive-layout="scroll">
                <Column field="username" header="Username" sortable />
                <Column field="is_active" header="Active" style="width: 6rem">
                  <template #body="{ data }">
                    <ToggleSwitch
                      :model-value="data.is_active"
                      :disabled="!canActivate"
                      @update:model-value="(val: boolean) => toggleActiveUser(data, val)"
                    />
                  </template>
                </Column>
                <Column v-if="canViewRights" header="Groups">
                  <template #body="{ data }">
                    <template v-if="userRightsById.get(data.id)?.group_ids.length">
                      <Tag
                        v-for="gid in userRightsById.get(data.id)!.group_ids"
                        :key="gid"
                        :value="groupById.get(gid)?.name || `#${gid}`"
                        :severity="groupById.get(gid)?.is_superadmin ? 'danger' : 'secondary'"
                        style="margin-right: 0.3rem"
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
                <Column header="Actions" style="width: 15rem">
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
                      v-if="canEdit || canSetPassword"
                      icon="pi pi-pencil"
                      text
                      rounded
                      severity="secondary"
                      title="Edit account"
                      @click="openEditAccountDialog(data)"
                    />
                    <Button
                      v-if="canViewRights"
                      icon="pi pi-shield"
                      text
                      rounded
                      title="Manage rights"
                      @click="openUserRightsDialog(data)"
                    />
                    <Button
                      v-if="canDelete"
                      icon="pi pi-trash"
                      text
                      rounded
                      severity="danger"
                      title="Delete"
                      :disabled="data.username === authStore.username && users.length <= 1"
                      @click="deleteAccount(data)"
                    />
                  </template>
                </Column>
              </DataTable>
            </template>
          </Card>
        </TabPanel>

        <!-- Groups -->
        <TabPanel v-if="canViewRights" value="groups">
          <Message v-if="!canManageRights" severity="warn" :closable="false" class="users-warning">
            You have read-only access to Groups — you can view groups and rights, but not change them.
          </Message>

          <Card>
            <template #title>
              <div class="card-header">
                <Button
                  v-if="canManageRights"
                  label="Add Group"
                  icon="pi pi-plus"
                  size="small"
                  @click="openCreateGroupDialog"
                />
              </div>
            </template>
            <template #content>
              <DataTable :value="orderedGroups" :loading="rightsLoading" data-key="id" responsive-layout="scroll">
                <Column field="name" header="Name">
                  <template #body="{ data }">
                    <span
                      class="group-tree-cell"
                      :style="{ paddingLeft: `${data.depth * 1.5}rem` }"
                    >
                      <i v-if="data.depth > 0" class="pi pi-angle-right tree-branch-icon"></i>
                      <span>{{ data.name }}</span>
                      <Tag v-if="data.is_superadmin" value="Superadmin" severity="danger" style="margin-left: 0.4rem" />
                    </span>
                  </template>
                </Column>
                <Column header="Rights">
                  <template #body="{ data }">
                    <span v-if="data.is_superadmin" class="muted">everything</span>
                    <span v-else>{{ data.rights.length }} granted</span>
                  </template>
                </Column>
                <Column header="Actions" style="width: 12rem">
                  <template #body="{ data }">
                    <Button
                      v-if="canManageRights"
                      icon="pi pi-pencil"
                      text
                      rounded
                      title="Rename / move"
                      @click="openEditGroupDialog(data)"
                    />
                    <Button
                      v-if="canManageRights"
                      icon="pi pi-shield"
                      text
                      rounded
                      title="Edit rights"
                      :disabled="data.is_superadmin"
                      @click="openGroupRightsDialog(data)"
                    />
                    <Button
                      v-if="canManageRights"
                      icon="pi pi-trash"
                      text
                      rounded
                      severity="danger"
                      title="Delete"
                      :disabled="data.is_superadmin"
                      @click="deleteGroup(data)"
                    />
                  </template>
                </Column>
              </DataTable>
            </template>
          </Card>
        </TabPanel>
      </TabPanels>
    </Tabs>

    <!-- Recent logins popover -->
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

    <!-- Create/Edit account dialog -->
    <Dialog
      v-model:visible="showAccountDialog"
      :header="isNewAccount ? 'Add User' : 'Edit User'"
      modal
      style="width: 26rem"
    >
      <div class="dialog-form">
        <label for="user-username">Username</label>
        <InputText id="user-username" v-model="accountForm.username" autofocus :disabled="!isNewAccount && !canEdit" />

        <template v-if="isNewAccount || canSetPassword">
          <label for="user-password">
            {{ isNewAccount ? 'Password' : 'New Password (leave blank to keep current)' }}
          </label>
          <Password id="user-password" v-model="accountForm.password" :feedback="false" toggle-mask />
        </template>
      </div>

      <template #footer>
        <Button label="Cancel" text @click="showAccountDialog = false" />
        <Button label="Save" icon="pi pi-check" :loading="isSavingAccount" @click="saveAccount" />
      </template>
    </Dialog>

    <!-- Create/Rename group dialog -->
    <Dialog v-model:visible="showGroupDialog" :header="isGroupNew ? 'Add Group' : 'Edit Group'" modal style="width: 26rem">
      <div class="dialog-form">
        <label for="group-name">Name</label>
        <InputText id="group-name" v-model="groupForm.name" autofocus />
        <label for="group-parent">Parent group</label>
        <Select
          id="group-parent"
          v-model="groupForm.parent_group_id"
          :options="parentOptions(groupForm.id)"
          option-label="label"
          option-value="value"
        />
      </div>
      <template #footer>
        <Button label="Cancel" text @click="showGroupDialog = false" />
        <Button label="Save" icon="pi pi-check" :loading="isSavingGroup" @click="saveGroup" />
      </template>
    </Dialog>

    <!-- Group rights matrix dialog -->
    <Dialog
      v-model:visible="showGroupRightsDialog"
      :header="`Rights — ${editingGroup?.name ?? ''}`"
      modal
      style="width: 32rem"
    >
      <p class="muted">
        Grants are additive: subgroups also hold everything granted here — rights inherited
        from a parent group are marked "inherited" and stay in effect even while unchecked
        here. Only "allow" can be set on a group — per-user overrides (allow/deny) are
        managed from the Accounts tab. Revoking a section's "page" right (with no inherited
        grant covering it) hides and clears the rest of that section, since it's unreachable
        without page access.
      </p>
      <div v-if="canManageRights" class="rights-global-actions">
        <span class="rights-global-label">All rights</span>
        <Button label="All" size="small" text @click="bulkSetGroupRights(catalog.map((r) => r.key), true)" />
        <Button label="None" size="small" text @click="bulkSetGroupRights(catalog.map((r) => r.key), false)" />
      </div>
      <div v-for="cat in categories" :key="cat.category" class="rights-category">
        <div class="rights-category-header">
          <h4>{{ cat.category }}</h4>
          <div v-if="canManageRights" class="rights-section-actions">
            <Button label="All" size="small" text @click="bulkSetGroupRights(cat.rights.map((r) => r.key), true)" />
            <Button label="None" size="small" text @click="bulkSetGroupRights(cat.rights.map((r) => r.key), false)" />
          </div>
        </div>
        <template v-for="r in cat.rights" :key="r.key">
          <div v-if="r.key.endsWith('.page') || isCategoryUnlockedForGroup(cat)" class="rights-row">
            <Checkbox
              :input-id="`gr-${r.key}`"
              binary
              :disabled="!canManageRights"
              :model-value="editingGroupRights.has(r.key)"
              @update:model-value="(val: boolean) => toggleGroupRight(r.key, val)"
            />
            <label :for="`gr-${r.key}`">{{ r.label }}</label>
            <Tag
              v-if="!editingGroupRights.has(r.key) && inheritedRightSource(r.key)"
              :value="`inherited: ${inheritedRightSource(r.key)!.name}`"
              severity="info"
              class="rights-inherited-tag"
            />
          </div>
        </template>
      </div>
      <template #footer>
        <Button label="Close" @click="showGroupRightsDialog = false" />
      </template>
    </Dialog>

    <!-- Per-user rights dialog -->
    <Dialog
      v-model:visible="showUserRightsDialog"
      :header="`Rights — ${editingUser?.username ?? ''}`"
      modal
      style="width: 36rem"
    >
      <template v-if="editingUser">
        <div class="dialog-form">
          <label>Group membership</label>
          <div class="user-groups-row">
            <MultiSelect
              v-model="editingUserGroupIds"
              :options="groupOptions"
              option-label="label"
              option-value="value"
              display="chip"
              placeholder="No groups"
              style="flex: 1"
              :disabled="!canManageRights"
            />
            <Button
              v-if="canManageRights"
              label="Save"
              size="small"
              :loading="isSavingUserGroups"
              @click="saveUserGroups"
            />
          </div>
        </div>

        <p class="muted" style="margin-top: 1rem">
          Allow/deny always win over group membership; deny cannot be overridden by any group,
          including Superadmin. "Inherit" falls through to the resolved group value shown below.
          Denying (or losing) a section's "page" right hides and clears the rest of that
          section's overrides — it's unreachable without page access.
        </p>

        <div v-if="canManageRights" class="rights-global-actions">
          <span class="rights-global-label">All rights</span>
          <Button label="All" size="small" text @click="bulkSetUserRights(catalog.map((r) => r.key), 'allow')" />
          <Button label="None" size="small" text @click="bulkSetUserRights(catalog.map((r) => r.key), 'inherit')" />
        </div>

        <div v-for="cat in categories" :key="cat.category" class="rights-category">
          <div class="rights-category-header">
            <h4>{{ cat.category }}</h4>
            <div v-if="canManageRights" class="rights-section-actions">
              <Button label="All" size="small" text @click="bulkSetUserRights(cat.rights.map((r) => r.key), 'allow')" />
              <Button label="None" size="small" text @click="bulkSetUserRights(cat.rights.map((r) => r.key), 'inherit')" />
            </div>
          </div>
          <template v-for="r in cat.rights" :key="r.key">
            <div v-if="r.key.endsWith('.page') || isCategoryUnlockedForUser(cat)" class="rights-row rights-row--user">
              <span class="rights-row-label">{{ r.label }}</span>
              <Tag
                :value="editingUser.effective_rights[r.key] ? 'allowed' : 'denied'"
                :severity="editingUser.effective_rights[r.key] ? 'success' : 'secondary'"
              />
              <Select
                :model-value="overrideValue(editingUser, r.key)"
                :options="[
                  { label: 'Inherit', value: 'inherit' },
                  { label: 'Allow', value: 'allow' },
                  { label: 'Deny', value: 'deny' },
                ]"
                option-label="label"
                option-value="value"
                :disabled="!canManageRights"
                @update:model-value="(val: RightOverrideValue) => setUserRight(r.key, val)"
              />
            </div>
          </template>
        </div>
      </template>
      <template #footer>
        <Button label="Close" @click="showUserRightsDialog = false" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.users-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.users-warning {
  margin-bottom: 1rem;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.dialog-form {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.dialog-form label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-color-secondary);
  margin-top: 0.5rem;
}

.dialog-form :deep(.p-password),
.dialog-form :deep(input) {
  width: 100%;
}

.user-groups-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.muted {
  color: var(--p-text-muted-color, #9ca3af);
  font-size: 0.85rem;
}

.group-tree-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.tree-branch-icon {
  color: var(--p-text-muted-color, #9ca3af);
  font-size: 0.75rem;
}

.rights-category {
  margin-top: 1rem;
}

.rights-category-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.rights-category h4,
.rights-category-header h4 {
  margin: 0 0 0.4rem;
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color, #9ca3af);
}

.rights-section-actions {
  display: flex;
  gap: 0.25rem;
  margin-bottom: 0.4rem;
}

.rights-global-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0;
  border-bottom: 1px solid var(--p-content-border-color, #e5e7eb);
}

.rights-global-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #9ca3af);
  margin-right: auto;
}

.rights-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0;
}

.rights-inherited-tag {
  font-size: 0.7rem;
}

.rights-row--user {
  justify-content: space-between;
}

.rights-row-label {
  flex: 1;
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
