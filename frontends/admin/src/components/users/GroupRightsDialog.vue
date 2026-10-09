<script setup lang="ts">
import { ref, watch } from 'vue'
import { useAck } from '../../composables/useAck'
import { useUsersPage, pageRightFor, type RightsCategory } from '../../composables/users/useUsersPage'
import type { RightsGroup } from '../../types/models'
import DialogTitle from '../DialogTitle.vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'

// The rights matrix of one group: which rights it grants (only "allow" can be set on a group),
// and which it inherits from its ancestors.
const props = defineProps<{ group: RightsGroup | null }>()
const visible = defineModel<boolean>('visible', { required: true })

const page = useUsersPage()
const { request } = useAck()

const editingGroupRights = ref<Set<string>>(new Set())

watch(visible, (open) => {
  if (open) editingGroupRights.value = new Set(props.group?.rights ?? [])
})

/** The nearest ancestor of the group that grants *rightKey* — directly, or implicitly by being
 * the Superadmin group — or undefined if no ancestor grants it. Used to show "inherited from X". */
const inheritedRightSource = (rightKey: string): RightsGroup | undefined => {
  if (!props.group) return undefined
  for (const ancestor of page.groupAncestors(props.group)) {
    if (ancestor.is_superadmin || ancestor.rights.includes(rightKey)) return ancestor
  }
  return undefined
}

/** Whether a category's other rights should be shown in the matrix — hidden until the group
 * holds (directly or via inheritance) that category's page right, since the rest are
 * unreachable without it. Categories with no page right always show everything. */
const isCategoryUnlockedForGroup = (category: RightsCategory): boolean => {
  const pageRight = pageRightFor(category)
  if (!pageRight) return true
  return editingGroupRights.value.has(pageRight.key) || !!inheritedRightSource(pageRight.key)
}

/** Apply a single group-right change to local state (editingGroupRights + the groups list entry). */
const applyGroupRightLocally = (rightKey: string, allow: boolean) => {
  if (allow) editingGroupRights.value.add(rightKey)
  else editingGroupRights.value.delete(rightKey)
  const g = props.group ? page.groupById.get(props.group.id) : undefined
  if (g) {
    g.rights = allow ? [...new Set([...g.rights, rightKey])] : g.rights.filter((k) => k !== rightKey)
  }
}

const toggleGroupRight = async (rightKey: string, checked: boolean) => {
  if (!props.group) return
  const ack = await request('displayhive:admin:rights:cts:set_group_right', {
    group_id: props.group.id,
    right_key: rightKey,
    allow: checked,
  }, { error: 'Update failed' })
  if (!ack) return
  applyGroupRightLocally(rightKey, checked)

  // Unsetting a category's page right also clears every other right in that
  // category — they're unreachable without page access, so leaving them
  // "granted" would be misleading.
  if (!checked && rightKey.endsWith('.page')) {
    const category = page.categoryOf(rightKey)
    const others = page.catalog
      .filter((r) => r.category === category && r.key !== rightKey && editingGroupRights.value.has(r.key))
      .map((r) => r.key)
    if (others.length) await bulkSetGroupRights(others, false)
  }
}

/** Grant/revoke a batch of rights on the group open in the dialog. */
const bulkSetGroupRights = async (rightKeys: string[], allow: boolean) => {
  if (!props.group || !rightKeys.length) return
  // A single batched call, not N parallel set_group_right calls: this app runs
  // single-worker, and N concurrent handler invocations sharing one db.session can
  // interleave and silently drop some of the N rights.
  const ack = await request('displayhive:admin:rights:cts:set_group_rights_bulk', {
    group_id: props.group.id,
    right_keys: rightKeys,
    allow,
  }, { error: 'Bulk update failed' })
  if (!ack) return
  for (const key of rightKeys) applyGroupRightLocally(key, allow)
}
</script>

<template>
<Dialog
  v-model:visible="visible"
  modal
  :style="{ width: '512px' }"
>
  <template #header>
    <DialogTitle icon="pi-shield" :title="`Rights — ${group?.name ?? ''}`" />
  </template>
  <p class="muted">
    Grants are additive: subgroups also hold everything granted here — rights inherited
    from a parent group are marked "inherited" and stay in effect even while unchecked
    here. Only "allow" can be set on a group — per-user overrides (allow/deny) are
    managed from the Accounts tab. Revoking a section's "page" right (with no inherited
    grant covering it) hides and clears the rest of that section, since it's unreachable
    without page access.
  </p>
  <div v-if="page.canManageRights" class="rights-global-actions" data-tour="users-rights-matrix">
    <span class="rights-global-label">All rights</span>
    <Button label="All" size="small" text @click="bulkSetGroupRights(page.catalog.map((r) => r.key), true)" />
    <Button label="None" size="small" text @click="bulkSetGroupRights(page.catalog.map((r) => r.key), false)" />
  </div>
  <div v-for="cat in page.categories" :key="cat.category" class="rights-category">
    <div class="rights-category-header">
      <h4>{{ cat.category }}</h4>
      <div v-if="page.canManageRights" class="rights-section-actions">
        <Button label="All" size="small" text @click="bulkSetGroupRights(cat.rights.map((r) => r.key), true)" />
        <Button label="None" size="small" text @click="bulkSetGroupRights(cat.rights.map((r) => r.key), false)" />
      </div>
    </div>
    <template v-for="r in cat.rights" :key="r.key">
      <div v-if="r.key.endsWith('.page') || isCategoryUnlockedForGroup(cat)" class="rights-row">
        <Checkbox
          :input-id="`gr-${r.key}`"
          binary
          :disabled="!page.canManageRights"
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
    <Button data-tour="users-rights-matrix-close" label="Close" @click="visible = false" />
  </template>
</Dialog>
</template>

<style scoped>
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
</style>
