<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAck } from '../../composables/useAck'
import { useSocket } from '../../composables/useSocket'
import { useUsersPage, pageRightFor, type RightsCategory } from '../../composables/users/useUsersPage'
import type { AdminUser, UserRightsRow, RightOverrideValue } from '../../types/models'
import DialogTitle from '../DialogTitle.vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import MultiSelect from 'primevue/multiselect'
import Select from 'primevue/select'
import Tag from 'primevue/tag'

// One user's group membership and per-right overrides (allow / deny / inherit).
const props = defineProps<{ user: AdminUser | null }>()
const visible = defineModel<boolean>('visible', { required: true })

const page = useUsersPage()
const { request } = useAck()
const { emitWithAck } = useSocket()

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

watch(visible, (open) => {
  if (!open || !props.user) return
  editingUser.value = page.userRightsById.get(props.user.id) ?? emptyUserRightsRow(props.user)
  editingUserGroupIds.value = [...editingUser.value.group_ids]
})

/** Same idea as the group matrix, but keyed off the resolved effective right rather than the raw
 * override (an "inherit" override can still resolve to allowed via group membership). */
const isCategoryUnlockedForUser = (category: RightsCategory): boolean => {
  const pageRight = pageRightFor(category)
  if (!pageRight) return true
  return !!editingUser.value?.effective_rights[pageRight.key]
}

const saveUserGroups = async () => {
  if (!editingUser.value) return
  isSavingUserGroups.value = true
  try {
    const ack = await request('displayhive:admin:rights:cts:set_user_groups', {
      user_id: editingUser.value.id,
      group_ids: editingUserGroupIds.value,
    }, { success: 'Group membership updated', error: 'Update failed' })
    if (ack) {
      await page.loadRights()
      const refreshed = page.userRightsById.get(editingUser.value.id)
      if (refreshed) editingUser.value = refreshed
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
    page.userRights = usersRes.users || []
    if (editingUser.value) {
      const refreshed = page.userRightsById.get(editingUser.value.id)
      if (refreshed) editingUser.value = refreshed
    }
  }
}

const setUserRight = async (rightKey: string, value: RightOverrideValue) => {
  if (!editingUser.value) return
  const ack = await request('displayhive:admin:rights:cts:set_user_right', {
    user_id: editingUser.value.id,
    right_key: rightKey,
    value,
  }, { error: 'Update failed' })
  if (!ack) return
  await refetchUserRights()

  // If this was a category's page right and it no longer resolves to
  // allowed, clear every other override in that category too — they're
  // unreachable without page access.
  if (rightKey.endsWith('.page') && editingUser.value && !editingUser.value.effective_rights[rightKey]) {
    const category = page.categoryOf(rightKey)
    const user = editingUser.value
    const others = page.catalog
      .filter((r) => r.category === category && r.key !== rightKey && overrideValue(user, r.key) !== 'inherit')
      .map((r) => r.key)
    if (others.length) await bulkSetUserRights(others, 'inherit')
  }
}

/** Set a batch of right overrides on the user open in the dialog. */
const bulkSetUserRights = async (rightKeys: string[], value: RightOverrideValue) => {
  if (!editingUser.value || !rightKeys.length) return
  // A single batched call, not N parallel set_user_right calls — see the group matrix for why.
  await request('displayhive:admin:rights:cts:set_user_rights_bulk', {
    user_id: editingUser.value.id,
    right_keys: rightKeys,
    value,
  }, { error: 'Bulk update failed' })
  await refetchUserRights()
}
</script>

<template>
<Dialog
  v-model:visible="visible"
  modal
  :style="{ width: '576px' }"
>
  <template #header>
    <DialogTitle icon="pi-shield" :title="`Rights — ${editingUser?.username ?? ''}`" />
  </template>
  <template v-if="editingUser">
    <div class="dialog-form" data-tour="users-rights-group-membership">
      <label>Group membership</label>
      <div class="user-groups-row">
        <MultiSelect
          v-model="editingUserGroupIds"
          :options="page.groupOptions"
          option-label="label"
          option-value="value"
          display="chip"
          placeholder="No groups"
          class="flex-1"
          :disabled="!page.canManageRights"
        />
        <Button
          v-if="page.canManageRights"
          label="Save"
          size="small"
          :loading="isSavingUserGroups"
          @click="saveUserGroups"
        />
      </div>
    </div>

    <p class="muted mt-4">
      Allow/deny always win over group membership; deny cannot be overridden by any group,
      including Superadmin. "Inherit" falls through to the resolved group value shown below.
      Denying (or losing) a section's "page" right hides and clears the rest of that
      section's overrides — it's unreachable without page access.
    </p>

    <div v-if="page.canManageRights" class="rights-global-actions">
      <span class="rights-global-label">All rights</span>
      <Button label="All" size="small" text @click="bulkSetUserRights(page.catalog.map((r) => r.key), 'allow')" />
      <Button label="None" size="small" text @click="bulkSetUserRights(page.catalog.map((r) => r.key), 'inherit')" />
    </div>

    <div v-for="cat in page.categories" :key="cat.category" class="rights-category">
      <div class="rights-category-header">
        <h4>{{ cat.category }}</h4>
        <div v-if="page.canManageRights" class="rights-section-actions">
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
            :disabled="!page.canManageRights"
            @update:model-value="(val: RightOverrideValue) => setUserRight(r.key, val)"
          />
        </div>
      </template>
    </div>
  </template>
  <template #footer>
    <Button data-tour="users-rights-dialog-close" label="Close" @click="visible = false" />
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

.user-groups-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.muted {
  color: var(--p-text-muted-color, #9ca3af);
  font-size: 0.85rem;
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
</style>
