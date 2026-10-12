<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import Badge from 'primevue/badge'
import DialogTitle from '../ui/DialogTitle.vue'
import RouteLink from '../ui/RouteLink.vue'
import { links } from '../../utils/links'
import { useAck } from '../../composables/useAck'
import { useConfirmAction } from '../../composables/useConfirmAction'
import { useSocket } from '../../composables/useSocket'
import { useScreengroupsStore } from '../../stores/screengroups'
import { useScreensStore } from '../../stores/screens'
import { useRightsStore } from '../../stores/rights'
import type { Screengroup } from '../../types/models'

// "Screens in <group>" dialog of the Screen Groups page: the screens assigned
// to `group` and the ones that aren't, with add / remove / remove-all.

// Dialog-local screen shape (backend sends flat is_online, not nested in attached_device)
interface DialogScreen {
  id: number
  name: string
  resolution?: string
  is_online?: boolean
}

const props = defineProps<{ group: Screengroup | null }>()
const visible = defineModel<boolean>('visible', { default: false })

const { confirmDanger } = useConfirmAction()
const { on, off } = useSocket()
const { request } = useAck()
const screengroupsStore = useScreengroupsStore()
const screensStore = useScreensStore()
const rightsStore = useRightsStore()

const canManageScreens = computed(() => rightsStore.can('screengroups.manage_screens'))

const assignedScreens = ref<DialogScreen[]>([])
const availableScreens = ref<DialogScreen[]>([])
const screensLoading = ref(false)
const assignedScreensFilter = ref('')
const availableScreensFilter = ref('')
const screensPerPage = 10

const filteredAssignedScreens = computed(() => {
  if (!assignedScreensFilter.value) return assignedScreens.value
  const search = assignedScreensFilter.value.toLowerCase()
  return assignedScreens.value.filter((s) => s.name?.toLowerCase().includes(search))
})

const filteredAvailableScreens = computed(() => {
  if (!availableScreensFilter.value) return availableScreens.value
  const search = availableScreensFilter.value.toLowerCase()
  return availableScreens.value.filter((s) => s.name?.toLowerCase().includes(search))
})

// Dialog-specific: receives assigned screens for the open screengroup
const handleScreenGroupScreens = (data: { screens?: DialogScreen[] }) => {
  if (data && data.screens) {
    assignedScreens.value = data.screens.map((s) => ({
      id: s.id,
      name: s.name,
      resolution: s.resolution || 'n/a',
      is_online: s.is_online ?? false,
    }))
    const assignedIds = new Set(assignedScreens.value.map((s) => s.id))
    availableScreens.value = screensStore.screens
      .filter((s) => !assignedIds.has(s.id))
      .map((s) => ({
        id: s.id,
        name: s.name,
        resolution: s.resolution || 'n/a',
        is_online: s.attached_device?.is_online ?? false,
      }))
  }
  screensLoading.value = false
}

onMounted(() => {
  on('displayhive:admin:stc:screengroup_screens_data', handleScreenGroupScreens)
})

onUnmounted(() => {
  off('displayhive:admin:stc:screengroup_screens_data', handleScreenGroupScreens)
})

watch(visible, (open) => {
  if (open && props.group) {
    assignedScreens.value = []
    availableScreens.value = []
    screensLoading.value = true
    assignedScreensFilter.value = ''
    availableScreensFilter.value = ''
    screengroupsStore.getScreenGroupScreens(props.group.id)
  } else if (!open) {
    assignedScreens.value = []
  }
})

const closeScreensDialog = () => {
  visible.value = false
}

const removeScreenFromGroup = async (screen: DialogScreen) => {
  if (!props.group) return
  const ack = await request('displayhive:admin:cts:remove_screen_from_screengroup', { screengroup_id: props.group.id, screen_id: screen.id }, { error: 'Could not remove the screen' })
  if (!ack) return
  assignedScreens.value = assignedScreens.value.filter((s) => s.id !== screen.id)
  availableScreens.value.push(screen)
}

const addScreenToGroup = async (screen: DialogScreen) => {
  if (!props.group) return
  const ack = await request('displayhive:admin:cts:add_screen_to_screengroup', { screengroup_id: props.group.id, screen_id: screen.id }, { error: 'Could not add the screen' })
  if (!ack) return
  availableScreens.value = availableScreens.value.filter((s) => s.id !== screen.id)
  assignedScreens.value.push(screen)
}

const removeAllScreensFromGroup = () => {
  if (!props.group) return
  confirmDanger({
    message: `Remove ALL screens from "${props.group.name}"?`,
    header: 'Confirm Remove All',
    accept: async () => {
      const ack = await request('displayhive:admin:cts:remove_all_screens_from_screengroup', { screengroup_id: props.group!.id }, { error: 'Could not remove the screens' })
      if (ack) assignedScreens.value = []
    },
  })
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: '900px', maxHeight: '90vh' }"
  >
    <template #header>
      <DialogTitle icon="pi-desktop" :title="`Screens in ${group?.name || ''}`" />
    </template>
    <div class="dialog-content">
      <div v-if="screensLoading" class="loading-state">
        <i class="pi pi-spin pi-spinner"></i>
        <p>Loading screens...</p>
      </div>
      <div v-else class="screens-container">
        <!-- Assigned Screens Section -->
        <div class="screens-section">
          <h6 class="section-title">Assigned Screens</h6>
          <InputText
            v-model="assignedScreensFilter"
            placeholder="Filter assigned screens..."
            class="w-full mb-3"
          />
          <div v-if="filteredAssignedScreens.length === 0" class="empty-state">
            <p class="text-muted">No assigned screens{{ assignedScreensFilter ? ' matching filter' : '' }}.</p>
          </div>
          <div v-else>
            <DataTable :value="filteredAssignedScreens" sortField="name" :sortOrder="1" stripedRows :paginator="filteredAssignedScreens.length > screensPerPage" :rows="screensPerPage" size="small" responsiveLayout="scroll">
              <Column field="name" header="Name">
                <template #body="{ data }">
                  <RouteLink v-if="rightsStore.can('screens.page')" :to="links.screen(data.id)" title="Open this screen">{{ data.name }}</RouteLink>
                  <template v-else>{{ data.name }}</template>
                </template>
              </Column>
              <Column field="resolution" header="Resolution" style="width:160px" />
              <Column header="Online" style="width:120px">
                <template #body="{ data }">
                  <Badge :value="data.is_online ? 'Online' : 'Offline'" :severity="data.is_online ? 'success' : 'secondary'" class="online-badge" />
                </template>
              </Column>
              <Column header="Actions" style="width:120px">
                <template #body="{ data }">
                  <Button v-if="canManageScreens" icon="pi pi-minus" @click="removeScreenFromGroup(data)" size="small" severity="danger" text title="Remove from group" />
                </template>
              </Column>
            </DataTable>
          </div>
        </div>

        <div class="divider"></div>

        <!-- Available Screens Section -->
        <div class="screens-section" data-tour="screengroups-available-screens">
          <h6 class="section-title">Not Assigned Screens</h6>
          <InputText
            v-model="availableScreensFilter"
            placeholder="Filter available screens..."
            class="w-full mb-3"
          />
          <div v-if="filteredAvailableScreens.length === 0" class="empty-state">
            <p class="text-muted">No available screens{{ availableScreensFilter ? ' matching filter' : '' }}.</p>
          </div>
          <div v-else>
            <DataTable :value="filteredAvailableScreens" sortField="name" :sortOrder="1" stripedRows :paginator="filteredAvailableScreens.length > screensPerPage" :rows="screensPerPage" size="small" responsiveLayout="scroll">
              <Column field="name" header="Name">
                <template #body="{ data }">
                  <RouteLink v-if="rightsStore.can('screens.page')" :to="links.screen(data.id)" title="Open this screen">{{ data.name }}</RouteLink>
                  <template v-else>{{ data.name }}</template>
                </template>
              </Column>
              <Column field="resolution" header="Resolution" style="width:160px" />
              <Column header="Online" style="width:120px">
                <template #body="{ data }">
                  <Badge :value="data.is_online ? 'Online' : 'Offline'" :severity="data.is_online ? 'success' : 'secondary'" class="online-badge" />
                </template>
              </Column>
              <Column header="Actions" style="width:120px">
                <template #body="{ data }">
                  <Button v-if="canManageScreens" icon="pi pi-plus" @click="addScreenToGroup(data)" size="small" severity="success" text title="Add to group" />
                </template>
              </Column>
            </DataTable>
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <Button
        v-if="canManageScreens && assignedScreens.length > 0"
        label="Remove All"
        @click="removeAllScreensFromGroup"
        severity="danger"
        outlined
        size="small"
      />
      <Button data-tour="screengroups-screens-dialog-close" label="Close" @click="closeScreensDialog" />
    </template>
  </Dialog>
</template>

<style scoped src="./groupDialogLists.css"></style>
