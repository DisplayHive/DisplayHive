<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'

import Card from 'primevue/card'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import ContentTable from '../components/ContentTable.vue'
import ContentEditor from '../components/ContentEditor.vue'
import MoveContentDialog from '../components/MoveContentDialog.vue'
import { useRightsStore } from '../stores/rights'

interface Container {
  id?: number
  name: string
  title: string
  order: number
  contentCount: number
  contenttype_ids?: number[]
}

interface ContentElement {
  id: number
  title: string
  active: boolean
  duration: number
  start_time?: string | null
  end_time?: string | null
  contentcontainer: string
  contenttypeName: string
  screengroups?: Array<{ id: number; name: string }>
}

interface ContentField {
  name: string
  label: string
  value: string
  order: number
}

interface ContentType {
  id: number
  name: string
  description?: string
  html?: string
  container_ids?: number[]
}

const getContentFields = (content: any): ContentField[] => {
  if (!content) return []
  const ignore = new Set(['id', 'title', 'active', 'duration', 'contentcontainer', 'contenttypeName', 'screengroups', 'contenttype_id', 'template', '_field_metadata'])
  const fields: ContentField[] = []
  const metadata = content._field_metadata || {}

  for (const k of Object.keys(content)) {
    if (ignore.has(k)) continue
    if (k.endsWith('__image_mode') || k.endsWith('__image_tags')) continue
    const v = content[k]
    if (v === null || v === undefined || v === '') continue

    let textValue = ''
    if (typeof v === 'object') {
      try { textValue = JSON.stringify(v) } catch { continue }
    } else {
      textValue = String(v)
    }

    textValue = textValue.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()
    if (textValue) {
      if (textValue.length > 100) textValue = textValue.slice(0, 100) + '…'
      const label = metadata[k]?.label || k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
      const order = metadata[k]?.order ?? 999
      fields.push({ name: k, label, value: textValue, order })
    }
  }

  return fields.sort((a, b) => a.order - b.order)
}

const filteredContentByContainer = computed<Record<string, ContentElement[]>>(() => {
  const result: Record<string, ContentElement[]> = {}
  for (const container of containers.value) {
    const name = container.name
    const filter = (searchFilters.value[name] || '').toLowerCase()
    let items = contentByContainer.value[name] || []
    if (showActiveOnly.value) {
      items = items.filter(item => item.active)
    }
    if (selectedScreengroupFilter.value !== 0) {
      items = items.filter(item =>
        (item.screengroups || []).some(sg => sg.id === selectedScreengroupFilter.value)
      )
    }
    if (filter) {
      items = items.filter(item => {
        if (item.title?.toLowerCase().includes(filter)) return true
        return getContentFields(item).some(field => field.value.toLowerCase().includes(filter))
      })
    }
    result[name] = items
  }
  return result
})

const toast = useToast()
const confirm = useConfirm()
const { on, off, emit, emitWithAck } = useSocket()
const rightsStore = useRightsStore()
const canCreate = computed(() => rightsStore.can('content.create'))

const activeTab = ref('0')

const oneScreenGroups = ref<Array<{ id: number; name: string; screen_ids: number[] }>>([])
const contentByScreengroupId = ref<Record<number, ContentElement[]>>({})
const selectedScreenFilter = ref<number | null>(null)
const screenbasedSearch = ref('')
const screenbasedContainers = ref<Container[]>([])
const contentByScreenAndContainer = ref<Record<string, ContentElement[]>>({})

const screenbasedContent = computed(() => {
  if (selectedScreenFilter.value === null) return []
  const items = contentByScreengroupId.value[selectedScreenFilter.value] || []
  const filter = screenbasedSearch.value.toLowerCase()
  if (!filter) return items
  return items.filter(item => {
    if (item.title?.toLowerCase().includes(filter)) return true
    return getContentFields(item).some(field => field.value.toLowerCase().includes(filter))
  })
})

const filteredScreenbasedByContainer = computed<Record<string, ContentElement[]>>(() => {
  if (selectedScreenFilter.value === null) return {}
  const sgId = selectedScreenFilter.value
  const result: Record<string, ContentElement[]> = {}
  const containerList = screenbasedContainers.value.length ? screenbasedContainers.value : containers.value
  for (const container of containerList) {
    const name = container.name
    let items = contentByScreenAndContainer.value[`${sgId}:${name}`] || []
    const filter = (searchFilters.value[name] || '').toLowerCase()
    if (filter) {
      items = items.filter(item => {
        if (item.title?.toLowerCase().includes(filter)) return true
        return getContentFields(item).some(field => field.value.toLowerCase().includes(filter))
      })
    }
    result[name] = items
  }
  return result
})

const handleScreenbasedScreengroups = (data: any) => {
  const arr = data?.screengroups || data?.data || []
  const groups = arr
    .filter((sg: any) => {
      const attrs = sg.attributes || sg
      return !!(attrs.is_one_screen ?? sg.is_one_screen)
    })
    .map((sg: any) => ({
      id: Number(sg.id),
      name: sg.attributes?.name || sg.name || '',
      screen_ids: (sg.relationships?.screens?.data || []).map((s: any) => Number(s.id))
    }))
    .sort((a: any, b: any) => a.name.localeCompare(b.name))
  oneScreenGroups.value = groups
  if (selectedScreenFilter.value === null && groups.length > 0) {
    selectedScreenFilter.value = groups[0].id
  }
  groups.forEach((sg: { id: number }) => {
    emit('displayhive:admin:cts:get_content_by_screengroup', { screengroup_id: sg.id })
  })
}

const handleContentByScreengroup = (data: { screengroup_id: number; content: ContentElement[] }) => {
  contentByScreengroupId.value[data.screengroup_id] = data.content || []
}

const handleContentBySgAndContainer = (data: { screengroup_id: number; container: string; content: ContentElement[] }) => {
  const key = `${data.screengroup_id}:${data.container}`
  contentByScreenAndContainer.value[key] = data.content || []
  decPending()
}

const handleContainersForScreen = (data: { containers: Container[] }) => {
  screenbasedContainers.value = data.containers || []
}

const fetchScreenbasedContentForContainers = (sgId: number, containerList: Container[]) => {
  containerList.forEach(c => {
    incPending()
    emit('displayhive:admin:cts:get_content_by_screengroup_and_container', {
      screengroup_id: sgId,
      container: c.name
    })
  })
}

watch(selectedScreenFilter, (sgId) => {
  screenbasedContainers.value = []
  if (sgId === null) return
  const sg = oneScreenGroups.value.find(g => g.id === sgId)
  const screenId = sg?.screen_ids?.[0] ?? null
  if (screenId !== null) {
    // Screen-specific containers are coming via handleContainersForScreen,
    // which triggers the screenbasedContainers watcher — don't fetch here too.
    emit('displayhive:admin:cts:get_containers_for_screen', { screen_id: screenId })
  } else {
    // No screen to look up: use global containers directly since
    // screenbasedContainers watcher won't fire for this case.
    const defaultContainers = containers.value
    if (defaultContainers.length > 0) {
      fetchScreenbasedContentForContainers(sgId, defaultContainers)
    }
  }
})

watch(screenbasedContainers, (containers) => {
  const sgId = selectedScreenFilter.value
  if (sgId === null || containers.length === 0) return
  fetchScreenbasedContentForContainers(sgId, containers)
})

const containers = ref<Container[]>([])
const contentByContainer = ref<Record<string, ContentElement[]>>({})
const unassignedContent = ref<ContentElement[]>([])
const searchFilters = ref<Record<string, string>>({})
const pendingRequests = ref(0)
const loading = computed(() => pendingRequests.value > 0)
// Tracks in-flight get_containers requests so spurious responses triggered
// by other views (e.g. TemplatesView) don't corrupt the pending counter.
const pendingContainerRequests = ref(0)

const incPending = () => { pendingRequests.value++ }
const decPending = () => { if (pendingRequests.value > 0) pendingRequests.value-- }

const allScreengroups = ref<Array<{ id: number; name: string }>>([])
const selectedScreengroupFilter = ref<number>(0)
const showActiveOnly = ref(false)

const allScreengroupOptions = computed(() => {
  const opts = allScreengroups.value
    .map(sg => ({ id: sg.id as number, name: sg.name }))
    .sort((a, b) => a.name.localeCompare(b.name))
  return [{ id: 0, name: 'All' }, ...opts]
})

const oneScreenGroupIds = computed(() => oneScreenGroups.value.map(g => g.id))


const contentTypes = ref<ContentType[]>([])

const moveContent = ref<ContentElement | null>(null)
const showMoveContentDialog = ref(false)
// Containers from every template (not just the default one) — the Move
// dialog needs to offer every container a content element could live in,
// regardless of which template it belongs to.
const allContainersForMove = ref<Container[]>([])

const handleContainers = (data: { containers: Container[] }) => {
  // Guard against spurious fires from other views that share this event (e.g. TemplatesView)
  if (pendingContainerRequests.value <= 0) return
  pendingContainerRequests.value--
  containers.value = data.containers || []
  decPending()
  containers.value.forEach(container => {
    if (!searchFilters.value[container.name]) {
      searchFilters.value[container.name] = ''
    }
    incPending()
    emit('displayhive:admin:cts:get_content_by_container', { container: container.name })
  })
}

const handleContentList = (data: { container: string; content: ContentElement[] }) => {
  contentByContainer.value[data.container] = data.content || []
  decPending()
}

const handleUnassignedContent = (data: { content: ContentElement[] }) => {
  unassignedContent.value = data.content || []
  decPending()
}

const handleAllScreengroups = (data: any) => {
  const arr = data?.screengroups || data?.data || []
  allScreengroups.value = arr
    .filter((sg: any) => {
      const attrs = sg.attributes || sg
      return !(attrs.is_one_screen ?? sg.is_one_screen)
    })
    .map((sg: any) => ({
      id: sg.id,
      name: sg.attributes?.name || sg.name || ''
    }))
  handleScreenbasedScreengroups(data)
}

const handleContentTypes = (data: { data?: ContentType[]; contenttypes?: ContentType[] }) => {
  contentTypes.value = data.data || data.contenttypes || []
}

const handleAllContainersForMove = (data: { containers: Container[] }) => {
  allContainersForMove.value = data.containers || []
}

onMounted(() => {
  on('displayhive:admin:stc:containers', handleContainers)
  on('displayhive:admin:stc:content_list', handleContentList)
  on('displayhive:admin:stc:unassigned_content', handleUnassignedContent)
  on('displayhive:admin:stc:upd_contenttypes', handleContentTypes)
  on('displayhive:admin:stc:upd_screengroups', handleAllScreengroups)
  on('displayhive:admin:stc:content_by_screengroup', handleContentByScreengroup)
  on('displayhive:admin:stc:content_by_screengroup_and_container', handleContentBySgAndContainer)
  on('displayhive:admin:stc:containers_for_screen', handleContainersForScreen)
  on('displayhive:admin:stc:all_containers_for_picker', handleAllContainersForMove)

  pendingContainerRequests.value++
  incPending()
  emit('displayhive:admin:cts:get_containers')
  emit('displayhive:admin:cts:get_contenttypes')
  incPending()
  emit('displayhive:admin:cts:get_unassigned_content')
  emit('displayhive:admin:cts:get_screengroups')
  emit('displayhive:admin:cts:get_all_containers_for_picker')
})

onUnmounted(() => {
  off('displayhive:admin:stc:containers', handleContainers)
  off('displayhive:admin:stc:content_list', handleContentList)
  off('displayhive:admin:stc:unassigned_content', handleUnassignedContent)
  off('displayhive:admin:stc:upd_contenttypes', handleContentTypes)
  off('displayhive:admin:stc:upd_screengroups', handleAllScreengroups)
  off('displayhive:admin:stc:content_by_screengroup', handleContentByScreengroup)
  off('displayhive:admin:stc:content_by_screengroup_and_container', handleContentBySgAndContainer)
  off('displayhive:admin:stc:containers_for_screen', handleContainersForScreen)
  off('displayhive:admin:stc:all_containers_for_picker', handleAllContainersForMove)
})


const getContentForContainer = (containerName: string): ContentElement[] => {
  return contentByContainer.value[containerName] || []
}

const toggleActive = async (content: ContentElement) => {
  const newActive = content.active
  try {
    const result = await emitWithAck<{ success?: boolean; error?: string }>(
      'displayhive:admin:cts:update_content_element_active',
      { content_element_id: content.id, active: newActive }
    )
    if (result && result.success === false) {
      content.active = !newActive
      toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Could not update', life: 3000 })
    }
  } catch {
    content.active = !newActive
    toast.add({ severity: 'error', summary: 'Error', detail: 'Could not reach server', life: 3000 })
  }
}

const updateDuration = (content: ContentElement) => {
  emit('displayhive:admin:cts:update_content_element_duration', {
    content_element_id: content.id,
    duration: content.duration
  })
}

const setDuration = (content: ContentElement, val: number) => {
  content.duration = val
  updateDuration(content)
}

const showInPreview = (content: ContentElement) => {
  emit('displayhive:admin:cts:show_content_element_in_preview', { content_element_id: content.id })
  toast.add({ severity: 'info', summary: 'Preview', detail: `Showing "${content.title}" in preview`, life: 3000 })
}

const deleteContent = (content: ContentElement, containerName: string) => {
  confirm.require({
    message: `Are you sure you want to delete "${content.title}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      emit('displayhive:admin:cts:delete_content_element', { content_element_id: content.id })

      const removeById = (list: ContentElement[]) => {
        const idx = list.findIndex(c => c.id === content.id)
        if (idx > -1) list.splice(idx, 1)
      }

      const containerContent = contentByContainer.value[containerName]
      if (containerContent) removeById(containerContent)

      if (selectedScreenFilter.value !== null) {
        const key = `${selectedScreenFilter.value}:${containerName}`
        const screenContent = contentByScreenAndContainer.value[key]
        if (screenContent) removeById(screenContent)
      }

      removeById(unassignedContent.value)

      toast.add({ severity: 'success', summary: 'Success', detail: 'Content deleted', life: 3000 })
    }
  })
}

const refreshData = () => {
  pendingRequests.value = 0
  pendingContainerRequests.value = 0
  contentByContainer.value = {}
  contentByScreenAndContainer.value = {}
  unassignedContent.value = []
  pendingContainerRequests.value++
  incPending()
  emit('displayhive:admin:cts:get_containers')
  incPending()
  emit('displayhive:admin:cts:get_unassigned_content')
  if (selectedScreenFilter.value !== null) {
    const ctrs = screenbasedContainers.value.length ? screenbasedContainers.value : containers.value
    fetchScreenbasedContentForContainers(selectedScreenFilter.value, ctrs)
  }
}

const openMoveContent = (content: ContentElement) => {
  moveContent.value = content
  showMoveContentDialog.value = true
}

const editorRef = ref<InstanceType<typeof ContentEditor>>()

const openCreateWorkflow = (container: Container) => {
  editorRef.value?.openCreate(container)
}

const openCreateWorkflowForScreen = (container: Container) => {
  if (selectedScreenFilter.value !== null) {
    editorRef.value?.openCreateForScreen(container, selectedScreenFilter.value)
  }
}

const openEditContent = (content: ContentElement) => {
  editorRef.value?.openEdit(content)
}

const copyContent = (content: ContentElement) => {
  editorRef.value?.openCopy(content)
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('content.page')" class="content-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Content page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="content-view">
    <Card>
      <template #title>
        <div class="card-header">
          <span>Content Containers</span>
          <div class="header-actions">
            <Button icon="pi pi-refresh" label="Refresh" @click="refreshData" size="small" outlined />
          </div>
        </div>
      </template>
      <template #content>
    <Tabs v-model:value="activeTab">
      <TabList>
        <Tab value="0">Screenbased</Tab>
        <Tab value="1">Groupbased</Tab>
      </TabList>
      <TabPanels>

        <!-- Screenbased Tab -->
        <TabPanel value="0">
          <div class="filter-bar">
            <label class="filter-label">Screen</label>
            <Select
              v-model="selectedScreenFilter"
              :options="oneScreenGroups"
              optionLabel="name"
              optionValue="id"
              placeholder="Select a screen"
              class="screengroup-filter-select"
            />
          </div>

          <div v-if="selectedScreenFilter === null" class="empty-state" style="padding: 2rem;">
            <i class="pi pi-desktop"></i>
            <p>Select a screen above to view its content.</p>
          </div>

          <div v-else class="containers-grid" style="margin-top: 1rem;">
            <Card v-for="container in (screenbasedContainers.length ? screenbasedContainers : containers)" :key="container.name" class="container-card">
              <template #title>
                <div class="container-header">
                  <div class="container-header-left">
                    <span>{{ container.title }}</span>
                    <Tag :value="`${(filteredScreenbasedByContainer[container.name] || []).length} items`" />
                  </div>
                  <Button
                    v-if="canCreate"
                    icon="pi pi-plus"
                    label="Add"
                    @click="openCreateWorkflowForScreen(container)"
                    size="small"
                    severity="success"
                  />
                </div>
              </template>
              <template #content>
                <ContentTable
                  :items="filteredScreenbasedByContainer[container.name] || []"
                  :containerName="container.name"
                  :totalItems="(contentByScreenAndContainer[`${selectedScreenFilter}:${container.name}`] || []).length"
                  v-model:search="searchFilters[container.name]"
                  :oneScreenGroupIds="oneScreenGroupIds"
                  emptyMessage="No content in this container for this screen"
                  @edit="openEditContent"
                  @copy="copyContent"
                  @preview="showInPreview"
                  @move="openMoveContent"
                  @delete="deleteContent"
                  @toggleActive="toggleActive"
                  @updateDuration="updateDuration"
                  @setDuration="setDuration"
                />
              </template>
            </Card>
          </div>
        </TabPanel>

        <!-- Groupbased Tab -->
        <TabPanel value="1">
          <div class="filter-bar">
            <label class="filter-label">Filter by Screen Group</label>
            <Select
              v-model="selectedScreengroupFilter"
              :options="allScreengroupOptions"
              optionLabel="name"
              optionValue="id"
              placeholder="All"
              class="screengroup-filter-select"
            />
            <Button
              :label="showActiveOnly ? 'Active only' : 'All states'"
              :icon="showActiveOnly ? 'pi pi-check-circle' : 'pi pi-circle'"
              :severity="showActiveOnly ? 'success' : 'secondary'"
              size="small"
              outlined
              @click="showActiveOnly = !showActiveOnly"
            />
          </div>

          <div class="containers-grid">
            <Card v-for="container in containers" :key="container.name" class="container-card">
              <template #title>
                <div class="container-header">
                  <div class="container-header-left">
                    <span>{{ container.title }}</span>
                    <Tag :value="`${getContentForContainer(container.name).length} items`" />
                  </div>
                  <Button
                    v-if="canCreate"
                    icon="pi pi-plus"
                    label="Add"
                    @click="openCreateWorkflow(container)"
                    size="small"
                    severity="success"
                  />
                </div>
              </template>
              <template #content>
                <ContentTable
                  :items="filteredContentByContainer[container.name] || []"
                  :containerName="container.name"
                  :totalItems="(contentByContainer[container.name] || []).length"
                  v-model:search="searchFilters[container.name]"
                  :oneScreenGroupIds="oneScreenGroupIds"
                  emptyMessage="No content in this container"
                  @edit="openEditContent"
                  @copy="copyContent"
                  @preview="showInPreview"
                  @move="openMoveContent"
                  @delete="deleteContent"
                  @toggleActive="toggleActive"
                  @updateDuration="updateDuration"
                  @setDuration="setDuration"
                />
              </template>
            </Card>
          </div>

          <Card v-if="unassignedContent.length > 0" class="container-card unassigned-card">
            <template #title>
              <div class="container-header">
                <div class="container-header-left">
                  <span>Unassigned Content</span>
                  <Tag :value="`${unassignedContent.length} items`" severity="warning" />
                </div>
              </div>
            </template>
            <template #content>
              <ContentTable
                :items="unassignedContent"
                containerName=""
                :oneScreenGroupIds="oneScreenGroupIds"
                emptyMessage="No unassigned content"
                @edit="openEditContent"
                @copy="copyContent"
                @preview="showInPreview"
                @move="openMoveContent"
                @delete="deleteContent"
                @toggleActive="toggleActive"
                @updateDuration="updateDuration"
                @setDuration="setDuration"
              />
            </template>
          </Card>
        </TabPanel>
      </TabPanels>
    </Tabs>
      </template>
    </Card>
  </div>

  <ContentEditor
    ref="editorRef"
    :contentTypes="contentTypes"
    :allScreengroups="allScreengroups"
    :oneScreenGroups="oneScreenGroups"
    @saved="refreshData"
  />

  <MoveContentDialog
    v-model:visible="showMoveContentDialog"
    :content="moveContent"
    :containers="allContainersForMove"
    :contentTypes="contentTypes"
    @moved="refreshData"
  />
</template>

<style scoped>
.content-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.filter-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #6b7280;
  white-space: nowrap;
}

.screengroup-filter-select {
  min-width: 200px;
}

.containers-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 1200px), 1fr));
  gap: 1.5rem;
}

.container-card {
  height: fit-content;
}

.unassigned-card {
  border: 2px solid #f59e0b;
  background: #fffbeb;
}

.container-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.container-header-left {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

@media (max-width: 768px) {
  .containers-grid {
    grid-template-columns: 1fr;
  }

  .container-header {
    flex-wrap: wrap;
    gap: 0.5rem;
  }
}
</style>
