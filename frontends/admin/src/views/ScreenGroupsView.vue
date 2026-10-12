<script setup lang="ts">
import ScreenGroupEditDialog from '../components/screengroups/ScreenGroupEditDialog.vue'
import ScreenGroupScreensDialog from '../components/screengroups/ScreenGroupScreensDialog.vue'
import ScreenGroupContentDialog from '../components/screengroups/ScreenGroupContentDialog.vue'
import { useConfirmAction } from '../composables/useConfirmAction'
import PageActions from '../components/PageActions.vue'
import { useOpenFromQuery } from '../composables/useOpenFromQuery'
import { ref, computed, onMounted } from 'vue'
import { useAck } from '../composables/useAck'
import { useScreengroupsStore } from '../stores/screengroups'
import { useScreensStore } from '../stores/screens'
import { useContentStore } from '../stores/content'
import { useRightsStore } from '../stores/rights'
import type { Screengroup } from '../types/models'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Card from 'primevue/card'
import Badge from 'primevue/badge'

const { confirmDanger } = useConfirmAction()
const { request } = useAck()
const screengroupsStore = useScreengroupsStore()
const screensStore = useScreensStore()
const contentStore = useContentStore()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('screengroups.create'))
const canRename = computed(() => rightsStore.can('screengroups.rename'))
const canDelete = computed(() => rightsStore.can('screengroups.delete'))

const filterText = ref('')

const filteredScreenGroups = computed(() => {
  const visible = screengroupsStore.screengroups.filter((sg) => !sg.is_one_screen)
  if (!filterText.value) return visible
  const search = filterText.value.toLowerCase()
  return visible.filter((sg) => sg.name?.toLowerCase().includes(search))
})

onMounted(() => {
  screengroupsStore.fetch()
  screensStore.fetch()
  contentStore.fetch()
})

const showEditDialog = ref(false)
const showScreensDialog = ref(false)
const showContentDialog = ref(false)
// The group the edit dialog renames (null: it creates a new one) and the group the
// screens / content dialogs manage.
const editingGroup = ref<Screengroup | null>(null)
const selectedScreenGroup = ref<Screengroup | null>(null)

const openNewDialog = () => {
  editingGroup.value = null
  showEditDialog.value = true
}

const openEditDialog = (sg: Screengroup) => {
  editingGroup.value = sg
  showEditDialog.value = true
}

const deleteScreenGroup = (sg: Screengroup) => {
  confirmDanger({
    message: `Are you sure you want to delete "${sg.name}"? This will only work if the group has no screens or content.`,
    accept: async () => {
      await request('displayhive:admin:cts:delete_screengroup', { screengroup_id: sg.id }, { success: 'Screen group deleted', error: 'Failed to delete screen group' })
    },
  })
}

const openScreensDialog = (sg: Screengroup) => {
  selectedScreenGroup.value = sg
  showScreensDialog.value = true
}

const openContentDialog = (sg: Screengroup) => {
  selectedScreenGroup.value = sg
  showContentDialog.value = true
}

// Reached via a link like /screengroups?edit=<id>: open that group's dialog.
useOpenFromQuery(() => screengroupsStore.screengroups, openEditDialog, () => canRename.value)
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('screengroups.page')" class="screengroups-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Screen Groups page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="screengroups-page" class="screengroups-view">
    <PageActions
      :primary="canCreate ? { label: 'New Screen Group', icon: 'pi pi-plus', tour: 'screengroups-new', onClick: openNewDialog } : null"
    />
    <Card>
      <template #content>
        <DataTable
          data-tour="screengroups-table"
          :value="filteredScreenGroups"
          :loading="screengroupsStore.loading"
          sortField="name"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="filteredScreenGroups.length > 10"
          :rows="10"
        >
          <template #header>
            <div class="dt-header">
              <div class="dt-left">
                <InputText
                  v-model="filterText"
                  data-tour="screengroups-filter"
                  placeholder="Filter screen groups..."
                  class="filter-input"
                />
              </div>
            </div>
          </template>
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="name" header="Name" sortable />
          <Column header="Screens" style="width: 120px">
            <template #body="{ data }">
              <Badge
                :value="data.screens_count"
                data-tour="screengroups-screens-badge"
                severity="secondary"
                class="clickable-badge"
                @click="openScreensDialog(data)"
                title="Manage screens"
              />
            </template>
          </Column>
          <Column header="Content" style="width: 120px">
            <template #body="{ data }">
              <Badge
                :value="data.content_count"
                data-tour="screengroups-content-badge"
                severity="info"
                class="clickable-badge"
                @click="openContentDialog(data)"
                title="Manage content"
              />
            </template>
          </Column>
          <Column header="Actions" style="width: 150px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button v-if="canRename" icon="pi pi-pencil" @click="openEditDialog(data)" size="small" outlined title="Edit" />
                <Button
                  v-if="canDelete && data.screens_count === 0 && data.content_count === 0"
                  icon="pi pi-trash"
                  @click="deleteScreenGroup(data)"
                  size="small"
                  severity="danger"
                  outlined
                  title="Delete"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <ScreenGroupEditDialog v-model:visible="showEditDialog" :group="editingGroup" />
    <ScreenGroupScreensDialog v-model:visible="showScreensDialog" :group="selectedScreenGroup" />
    <ScreenGroupContentDialog v-model:visible="showContentDialog" :group="selectedScreenGroup" />
  </div>
</template>

<style scoped>
.screengroups-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* No title text left in the card header — keep the action buttons
   right-aligned instead of collapsing to the start. */
.card-header {
  justify-content: flex-end;
}
</style>
