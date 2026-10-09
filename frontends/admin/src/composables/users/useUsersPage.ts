import { computed, inject, onMounted, onUnmounted, provide, reactive, ref, watch, type InjectionKey } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useSocket } from '../useSocket'
import { onRightsReady } from '../useRightsReady'
import { useRightsStore } from '../../stores/rights'
import type { AdminUser, RightDefinition, RightsGroup, UserRightsRow } from '../../types/models'

export interface RightsCategory { category: string; rights: RightDefinition[] }
export interface GroupTreeRow extends RightsGroup { depth: number }

export const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : '—')
export const isSsoAccount = (user: AdminUser) => (user.identities?.length ?? 0) > 0

/** The "<category>.page" right of a category, if it has one (not every category does, e.g. "special"). */
export const pageRightFor = (category: RightsCategory): RightDefinition | undefined =>
  category.rights.find((r) => r.key.endsWith('.page'))

/**
 * What the Users & Rights page and its dialogs share: what the person may do, the account list,
 * and the rights data (catalog, groups, per-user rights) with the maps derived from it. Loads
 * everything once the socket and the person's own rights are ready, and again after a reconnect.
 */
function createUsersPage() {
  const toast = useToast()
  const rightsStore = useRightsStore()
  const { on, off, emit, emitWithAck, isConnected } = useSocket()

  // --- Rights gates --------------------------------------------------------------
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

  // --- Accounts: list --------------------------------------------------------------
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

  // --- Rights: catalog / groups / per-user rights -----------------------------------
  const rightsLoading = ref(true)
  const catalog = ref<RightDefinition[]>([])
  const groups = ref<RightsGroup[]>([])
  const userRights = ref<UserRightsRow[]>([])

  const categories = computed<RightsCategory[]>(() => {
    const seen = new Map<string, RightDefinition[]>()
    for (const r of catalog.value) {
      if (!seen.has(r.category)) seen.set(r.category, [])
      seen.get(r.category)!.push(r)
    }
    return Array.from(seen.entries()).map(([category, rights]) => ({ category, rights }))
  })

  const catalogByKey = computed(() => new Map(catalog.value.map((r) => [r.key, r])))
  const categoryOf = (rightKey: string): string | undefined => catalogByKey.value.get(rightKey)?.category

  const groupById = computed(() => new Map(groups.value.map((g) => [g.id, g])))
  const groupOptions = computed(() => groups.value.map((g) => ({ label: g.name, value: g.id })))
  const userRightsById = computed(() => new Map(userRights.value.map((u) => [u.id, u])))

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

  // SSO logins create accounts without groups (= no rights) and without a password. List those
  // so an admin notices, and either assigns groups or merges them. "No password" tells them
  // apart from a local account that merely had an SSO login merged into it. Only knowable with
  // the rights view, which carries the group memberships.
  const ssoAccountsWithoutGroups = computed(() =>
    canViewRights.value
      ? users.value.filter(
          (u) => isSsoAccount(u) && !u.has_password && !(userRightsById.value.get(u.id)?.group_ids.length),
        )
      : [],
  )

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

  // Fires on the initial connect (fresh page load) and on every reconnect, so data is
  // (re-)fetched as soon as the socket is actually usable — fixes both tables coming up empty
  // after a hard reload, where this page mounts before the socket handshake has finished.
  watch(isConnected, (connected) => {
    if (connected) loadAll()
  })

  // loadUsers()/loadRights() also gate on canViewUsers/canViewRights (rightsStore.can()), which
  // stays false until rightsStore.loaded resolves — its own async round trip, so it can still be
  // pending when the watcher above fires. See useRightsReady for why this needs its own retry.
  onRightsReady(loadAll)

  onUnmounted(() => {
    off('displayhive:admin:users:stc:users', handleUsers)
  })

  // Reactive, so components read `page.users` (not `.value`) and can v-model its fields.
  return reactive({
    canViewUsers, canViewRights, canManageRights, canCreate, canEdit, canSetPassword, canDelete, canActivate,
    canManageAccountsAny, defaultTab,
    users, usersLoading, loadUsers,
    rightsLoading, catalog, groups, userRights, categories, categoryOf, groupById, groupOptions, userRightsById,
    groupAncestors, orderedGroups, parentOptions, ssoAccountsWithoutGroups, loadRights, loadAll,
  })
}

export type UsersPage = ReturnType<typeof createUsersPage>

const KEY: InjectionKey<UsersPage> = Symbol('usersPage')

/** Called once by the Users page; its tabs and dialogs inject it. */
export function provideUsersPage(): UsersPage {
  const page = createUsersPage()
  provide(KEY, page)
  return page
}

export function useUsersPage(): UsersPage {
  const page = inject(KEY)
  if (!page) throw new Error('useUsersPage() needs provideUsersPage() in a parent component')
  return page
}
