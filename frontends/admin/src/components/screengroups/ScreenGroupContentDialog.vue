<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import DialogTitle from '../ui/DialogTitle.vue'
import RouteLink from '../ui/RouteLink.vue'
import { links } from '../../utils/links'
import { useAck } from '../../composables/useAck'
import { useConfirmAction } from '../../composables/useConfirmAction'
import { useSocket } from '../../composables/useSocket'
import { useScreengroupsStore } from '../../stores/screengroups'
import { useContentStore } from '../../stores/content'
import { useRightsStore } from '../../stores/rights'
import type { Screengroup, Content } from '../../types/models'

// "Content in <group>" dialog of the Screen Groups page: the content assigned
// to `group` and the ones that aren't, with add / remove / remove-all.
const props = defineProps<{ group: Screengroup | null }>()
const visible = defineModel<boolean>('visible', { default: false })

const { confirmDanger } = useConfirmAction()
const { on, off } = useSocket()
const { request } = useAck()
const screengroupsStore = useScreengroupsStore()
const contentStore = useContentStore()
const rightsStore = useRightsStore()

const canManageContent = computed(() => rightsStore.can('screengroups.manage_content'))

const assignedContent = ref<Content[]>([])
const availableContent = ref<Content[]>([])
const contentLoading = ref(false)
const assignedContentFilter = ref('')
const availableContentFilter = ref('')
const contentPerPage = 10

const filteredAssignedContent = computed(() => {
  if (!assignedContentFilter.value) return assignedContent.value
  const search = assignedContentFilter.value.toLowerCase()
  return assignedContent.value.filter((c) => c.title?.toLowerCase().includes(search))
})

const filteredAvailableContent = computed(() => {
  if (!availableContentFilter.value) return availableContent.value
  const search = availableContentFilter.value.toLowerCase()
  return availableContent.value.filter((c) => c.title?.toLowerCase().includes(search))
})

// Dialog-specific: receives assigned content for the open screengroup
const handleScreenGroupContent = (data: { content?: Array<{ id: number; title: string; type?: string; contenttype_name?: string }> }) => {
  if (data && data.content) {
    assignedContent.value = data.content.map((c) => ({
      id: c.id,
      title: c.title,
      contenttype_name: c.type || c.contenttype_name,
    }))
    const assignedIds = new Set(assignedContent.value.map((c) => c.id))
    availableContent.value = contentStore.content.filter((c) => !assignedIds.has(c.id))
  }
  contentLoading.value = false
}

onMounted(() => {
  on('displayhive:admin:stc:screengroup_content_data', handleScreenGroupContent)
})

onUnmounted(() => {
  off('displayhive:admin:stc:screengroup_content_data', handleScreenGroupContent)
})

watch(visible, (open) => {
  if (open && props.group) {
    assignedContent.value = []
    availableContent.value = []
    contentLoading.value = true
    assignedContentFilter.value = ''
    availableContentFilter.value = ''
    screengroupsStore.getScreenGroupContent(props.group.id)
  } else if (!open) {
    assignedContent.value = []
    availableContent.value = []
  }
})

const closeContentDialog = () => {
  visible.value = false
}

const removeContentFromGroup = async (content: Content) => {
  if (!props.group) return
  const ack = await request('displayhive:admin:cts:remove_content_from_screengroup', { screengroup_id: props.group.id, content_id: content.id }, { error: 'Could not remove the content' })
  if (!ack) return
  assignedContent.value = assignedContent.value.filter((c) => c.id !== content.id)
  availableContent.value.push(content)
}

const addContentToGroup = async (content: Content) => {
  if (!props.group) return
  const ack = await request('displayhive:admin:cts:add_content_to_screengroup', { screengroup_id: props.group.id, content_id: content.id }, { error: 'Could not add the content' })
  if (!ack) return
  availableContent.value = availableContent.value.filter((c) => c.id !== content.id)
  assignedContent.value.push(content)
}

const removeAllContentFromGroup = () => {
  if (!props.group) return
  confirmDanger({
    message: `Remove ALL content from "${props.group.name}"?`,
    header: 'Confirm Remove All',
    accept: async () => {
      const ack = await request('displayhive:admin:cts:remove_all_content_from_screengroup', { screengroup_id: props.group!.id }, { error: 'Could not remove the content' })
      if (!ack) return
      availableContent.value.push(...assignedContent.value)
      assignedContent.value = []
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
      <DialogTitle icon="pi-file" :title="`Content in ${group?.name || ''}`" />
    </template>
    <div class="dialog-content">
      <div v-if="contentLoading" class="loading-state">
        <i class="pi pi-spin pi-spinner"></i>
        <p>Loading content...</p>
      </div>
      <div v-else class="content-container">
        <!-- Assigned Content Section -->
        <div class="content-section">
          <h6 class="section-title">Assigned Content</h6>
          <InputText
            v-model="assignedContentFilter"
            placeholder="Filter assigned content..."
            class="w-full mb-3"
          />
          <div v-if="filteredAssignedContent.length === 0" class="empty-state">
            <p class="text-muted">No assigned content{{ assignedContentFilter ? ' matching filter' : '' }}.</p>
          </div>
          <div v-else>
            <DataTable :value="filteredAssignedContent" stripedRows :paginator="filteredAssignedContent.length > contentPerPage" :rows="contentPerPage" size="small" responsiveLayout="scroll">
              <Column field="title" header="Title">
                <template #body="{ data }">
                  <RouteLink v-if="rightsStore.can('content.page')" :to="links.content(data.id)" title="Open this content">{{ data.title }}</RouteLink>
                  <template v-else>{{ data.title }}</template>
                </template>
              </Column>
              <Column field="contenttype_name" header="Type" style="width:180px" />
              <Column header="Actions" style="width:120px">
                <template #body="{ data }">
                  <Button v-if="canManageContent" icon="pi pi-minus" @click="removeContentFromGroup(data)" size="small" severity="danger" text title="Remove from group" />
                </template>
              </Column>
            </DataTable>
          </div>
        </div>

        <div class="divider"></div>

        <!-- Available Content Section -->
        <div class="content-section" data-tour="screengroups-available-content">
          <h6 class="section-title">Not Assigned Content</h6>
          <InputText
            v-model="availableContentFilter"
            placeholder="Filter available content..."
            class="w-full mb-3"
          />
          <div v-if="filteredAvailableContent.length === 0" class="empty-state">
            <p class="text-muted">No available content{{ availableContentFilter ? ' matching filter' : '' }}.</p>
          </div>
          <div v-else>
            <DataTable :value="filteredAvailableContent" stripedRows :paginator="filteredAvailableContent.length > contentPerPage" :rows="contentPerPage" size="small" responsiveLayout="scroll">
              <Column field="title" header="Title">
                <template #body="{ data }">
                  <RouteLink v-if="rightsStore.can('content.page')" :to="links.content(data.id)" title="Open this content">{{ data.title }}</RouteLink>
                  <template v-else>{{ data.title }}</template>
                </template>
              </Column>
              <Column field="contenttype_name" header="Type" style="width:180px" />
              <Column header="Actions" style="width:120px">
                <template #body="{ data }">
                  <Button v-if="canManageContent" icon="pi pi-plus" @click="addContentToGroup(data)" size="small" severity="success" text title="Add to group" />
                </template>
              </Column>
            </DataTable>
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <Button
        v-if="canManageContent && assignedContent.length > 0"
        label="Remove All"
        @click="removeAllContentFromGroup"
        severity="danger"
        outlined
        size="small"
      />
      <Button data-tour="screengroups-content-dialog-close" label="Close" @click="closeContentDialog" />
    </template>
  </Dialog>
</template>

<style scoped src="./groupDialogLists.css"></style>
