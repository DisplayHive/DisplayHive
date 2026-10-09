<script setup lang="ts">
import { ref } from 'vue'
import { useConfirmAction } from '../../composables/useConfirmAction'
import { useAck } from '../../composables/useAck'
import { useUsersPage } from '../../composables/users/useUsersPage'
import type { RightsGroup } from '../../types/models'
import GroupDialog from './GroupDialog.vue'
import GroupRightsDialog from './GroupRightsDialog.vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Column from 'primevue/column'
import DataTable from 'primevue/datatable'
import Message from 'primevue/message'
import Tag from 'primevue/tag'

// The Groups tab: the group tree and its row actions, with the dialogs they open.
const page = useUsersPage()
const { confirmDanger } = useConfirmAction()
const { request } = useAck()

const showGroupDialog = ref(false)
const editingGroupRow = ref<RightsGroup | null>(null)
const openCreateGroupDialog = () => {
  editingGroupRow.value = null
  showGroupDialog.value = true
}
const openEditGroupDialog = (group: RightsGroup) => {
  editingGroupRow.value = group
  showGroupDialog.value = true
}

const showGroupRightsDialog = ref(false)
const rightsGroup = ref<RightsGroup | null>(null)
const openGroupRightsDialog = (group: RightsGroup) => {
  rightsGroup.value = group
  showGroupRightsDialog.value = true
}

const deleteGroup = (group: RightsGroup) => {
  confirmDanger({
    message: `Delete group "${group.name}"? This cannot be undone.`,
    accept: async () => {
      const ack = await request('displayhive:admin:rights:cts:delete_group', { id: group.id }, { success: 'Group deleted', error: 'Delete failed' })
      if (ack) await page.loadRights()
    },
  })
}
</script>

<template>
    <Message v-if="!page.canManageRights" severity="warn" :closable="false" class="users-warning">
      You have read-only access to Groups — you can view groups and rights, but not change them.
    </Message>

    <Card>
      <template #title>
        <div class="card-header">
          <Button
            v-if="page.canManageRights"
            data-tour="users-add-group"
            label="Add Group"
            icon="pi pi-plus"
            size="small"
            @click="openCreateGroupDialog"
          />
        </div>
      </template>
      <template #content>
        <DataTable
          data-tour="users-groups-table"
          :value="page.orderedGroups"
          :loading="page.rightsLoading"
          data-key="id"
          stripedRows
          size="small"
          responsive-layout="scroll"
        >
          <Column field="name" header="Name">
            <template #body="{ data }">
              <span
                class="group-tree-cell"
                :style="{ paddingLeft: `${data.depth * 1.5}rem` }"
              >
                <i v-if="data.depth > 0" class="pi pi-angle-right tree-branch-icon"></i>
                <span>{{ data.name }}</span>
                <Tag v-if="data.is_superadmin" value="Superadmin" severity="danger" class="ml-2" />
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
                v-if="page.canManageRights"
                icon="pi pi-pencil"
                text
                rounded
                title="Rename / move"
                @click="openEditGroupDialog(data)"
              />
              <Button
                v-if="page.canManageRights"
                data-tour="users-row-edit-rights"
                icon="pi pi-shield"
                text
                rounded
                title="Edit rights"
                :disabled="data.is_superadmin"
                @click="openGroupRightsDialog(data)"
              />
              <Button
                v-if="page.canManageRights"
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

  <GroupDialog v-model:visible="showGroupDialog" :group="editingGroupRow" />
  <GroupRightsDialog v-model:visible="showGroupRightsDialog" :group="rightsGroup" />
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

.group-tree-cell {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.tree-branch-icon {
  color: var(--p-text-muted-color, #9ca3af);
  font-size: 0.75rem;
}
</style>
