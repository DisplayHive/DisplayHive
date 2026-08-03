<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'

import Card from 'primevue/card'
import Button from 'primevue/button'
import Select from 'primevue/select'
import SelectButton from 'primevue/selectbutton'
import ToggleSwitch from 'primevue/toggleswitch'
import ContentTable from '../components/ContentTable.vue'
import { useRightsStore } from '../stores/rights'
import { useScreensStore } from '../stores/screens'

interface ContentElement {
  id: number
  title: string
  active: boolean
  duration: number
  start_time?: string | null
  end_time?: string | null
  contenttypeName: string
  screengroups?: Array<{ id: number; name: string }>
}

interface ContentField {
  name: string
  label: string
  value: string
  order: number
}

const getContentFields = (content: any): ContentField[] => {
  if (!content) return []
  const ignore = new Set(['id', 'title', 'active', 'duration', 'contenttypeName', 'screengroups', 'contenttype_id', 'design', 'containers', '_field_metadata'])
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

const router = useRouter()
const toast = useToast()
const confirm = useConfirm()
const { on, off, emit, emitWithAck } = useSocket()
const rightsStore = useRightsStore()
const screensStore = useScreensStore()
const canCreate = computed(() => rightsStore.can('content.create'))

const allContent = ref<ContentElement[]>([])
const unassignedContent = ref<ContentElement[]>([])
const loading = ref(true)

interface ScreengroupOption { id: number; name: string; screen_ids: number[] }
const allScreengroups = ref<ScreengroupOption[]>([])
const oneScreenGroups = ref<ScreengroupOption[]>([])
const oneScreenGroupIds = computed(() => oneScreenGroups.value.map(g => g.id))

// --- New filter system: exactly one of these three modes is active at a time. ---
type FilterMode = 'screen' | 'group' | 'abandoned'
const filterModeOptions: Array<{ label: string; value: FilterMode }> = [
  { label: 'By Screen', value: 'screen' },
  { label: 'By Group', value: 'group' },
  { label: 'Abandoned', value: 'abandoned' },
]
const filterMode = ref<FilterMode>('group')

// Option 1: By Screen
const selectedScreenId = ref<number | null>(null)
const showInheritedFromGroups = ref(false)
const screenOptions = computed(() =>
  screensStore.screens.map(s => ({ id: s.id, name: s.name })).sort((a, b) => a.name.localeCompare(b.name))
)

// Option 2: By Group ('0' = "None" — show everything in some group, not narrowed to one)
const selectedGroupId = ref<number>(0)
const groupOptions = computed(() => {
  const opts = allScreengroups.value
    .map(sg => ({ id: sg.id, name: sg.name }))
    .sort((a, b) => a.name.localeCompare(b.name))
  return [{ id: 0, name: 'None' }, ...opts]
})

// Shared across all three modes.
const hideDisabled = ref(false)
const searchFilter = ref('')

const filteredContent = computed<ContentElement[]>(() => {
  const filter = searchFilter.value.toLowerCase()
  let items: ContentElement[]

  if (filterMode.value === 'screen') {
    if (selectedScreenId.value == null) {
      items = []
    } else {
      const screenId = selectedScreenId.value
      const groupIds = new Set<number>()
      const ownGroup = oneScreenGroups.value.find(g => g.screen_ids.includes(screenId))
      if (ownGroup) groupIds.add(ownGroup.id)
      if (showInheritedFromGroups.value) {
        for (const g of allScreengroups.value) {
          if (g.screen_ids.includes(screenId)) groupIds.add(g.id)
        }
      }
      items = allContent.value.filter(item => (item.screengroups || []).some(sg => groupIds.has(sg.id)))
    }
  } else if (filterMode.value === 'group') {
    if (selectedGroupId.value === 0) {
      const groupIds = new Set(allScreengroups.value.map(g => g.id))
      items = allContent.value.filter(item => (item.screengroups || []).some(sg => groupIds.has(sg.id)))
    } else {
      const groupId = selectedGroupId.value
      items = allContent.value.filter(item => (item.screengroups || []).some(sg => sg.id === groupId))
    }
  } else {
    items = unassignedContent.value
  }

  if (hideDisabled.value) {
    items = items.filter(item => item.active)
  }
  if (filter) {
    items = items.filter(item => {
      if (item.title?.toLowerCase().includes(filter)) return true
      return getContentFields(item).some(field => field.value.toLowerCase().includes(filter))
    })
  }
  return items
})

const handleAllContentDetailed = (data: { content: ContentElement[] }) => {
  allContent.value = data.content || []
  loading.value = false
}

const handleUnassignedContent = (data: { content: ContentElement[] }) => {
  unassignedContent.value = data.content || []
}

const handleAllScreengroups = (data: any) => {
  const arr = data?.screengroups || data?.data || []
  const toOption = (sg: any): ScreengroupOption => ({
    id: Number(sg.id),
    name: sg.attributes?.name || sg.name || '',
    screen_ids: (sg.relationships?.screens?.data || []).map((s: any) => Number(s.id)),
  })
  allScreengroups.value = arr
    .filter((sg: any) => !(sg.attributes?.is_one_screen ?? sg.is_one_screen))
    .map(toOption)
  oneScreenGroups.value = arr
    .filter((sg: any) => !!(sg.attributes?.is_one_screen ?? sg.is_one_screen))
    .map(toOption)
}

onMounted(() => {
  on('displayhive:admin:stc:all_content_detailed', handleAllContentDetailed)
  on('displayhive:admin:stc:unassigned_content', handleUnassignedContent)
  on('displayhive:admin:stc:upd_screengroups', handleAllScreengroups)

  refreshData()
  emit('displayhive:admin:cts:get_screengroups')
  screensStore.fetch()
})

onUnmounted(() => {
  off('displayhive:admin:stc:all_content_detailed', handleAllContentDetailed)
  off('displayhive:admin:stc:unassigned_content', handleUnassignedContent)
  off('displayhive:admin:stc:upd_screengroups', handleAllScreengroups)
})

const refreshData = () => {
  loading.value = true
  emit('displayhive:admin:cts:get_all_content_detailed')
  emit('displayhive:admin:cts:get_unassigned_content')
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

const deleteContent = (content: ContentElement) => {
  confirm.require({
    message: `Are you sure you want to delete "${content.title}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      emit('displayhive:admin:cts:delete_content_element', { content_element_id: content.id })
      allContent.value = allContent.value.filter(c => c.id !== content.id)
      unassignedContent.value = unassignedContent.value.filter(c => c.id !== content.id)
      toast.add({ severity: 'success', summary: 'Success', detail: 'Content deleted', life: 3000 })
    }
  })
}

const openCreateWorkflow = () => {
  router.push({ name: 'content-new' })
}

const openEditContent = (content: ContentElement) => {
  router.push({ name: 'content-edit', params: { id: content.id } })
}

const copyContent = (content: ContentElement) => {
  router.push({ name: 'content-copy', params: { id: content.id } })
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
          <span>Content</span>
          <div class="header-actions">
            <Button v-if="canCreate" icon="pi pi-plus" label="New Content" @click="openCreateWorkflow" size="small" />
            <Button icon="pi pi-refresh" label="Refresh" @click="refreshData" size="small" outlined />
          </div>
        </div>
      </template>
      <template #content>
        <div class="filter-bar filter-bar--modes">
          <SelectButton
            v-model="filterMode"
            :options="filterModeOptions"
            optionLabel="label"
            optionValue="value"
            :allowEmpty="false"
          />

          <template v-if="filterMode === 'screen'">
            <Select
              v-model="selectedScreenId"
              :options="screenOptions"
              optionLabel="name"
              optionValue="id"
              placeholder="Select a screen"
              class="screengroup-filter-select"
            />
            <div class="filter-toggle">
              <label for="show-inherited-groups">Also show inherited from Groups</label>
              <ToggleSwitch id="show-inherited-groups" v-model="showInheritedFromGroups" />
            </div>
          </template>

          <template v-else-if="filterMode === 'group'">
            <Select
              v-model="selectedGroupId"
              :options="groupOptions"
              optionLabel="name"
              optionValue="id"
              placeholder="None"
              class="screengroup-filter-select"
            />
          </template>

          <div class="filter-toggle">
            <label for="hide-disabled-content">Hide disabled</label>
            <ToggleSwitch id="hide-disabled-content" v-model="hideDisabled" />
          </div>
        </div>

        <ContentTable
          :items="filteredContent"
          :totalItems="allContent.length"
          v-model:search="searchFilter"
          :oneScreenGroupIds="oneScreenGroupIds"
          :emptyMessage="filterMode === 'screen' && selectedScreenId == null ? 'Select a screen to see its content' : 'No content'"
          @edit="openEditContent"
          @copy="copyContent"
          @preview="showInPreview"
          @delete="deleteContent"
          @toggleActive="toggleActive"
          @updateDuration="updateDuration"
          @setDuration="setDuration"
        />
      </template>
    </Card>
  </div>
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
  margin-bottom: 1rem;
}

.screengroup-filter-select {
  min-width: 200px;
}

.filter-bar--modes {
  flex-wrap: wrap;
}

.filter-toggle {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.filter-toggle label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #6b7280;
  white-space: nowrap;
}
</style>
