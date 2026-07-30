<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'

import Card from 'primevue/card'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import Select from 'primevue/select'
import ContentTable from '../components/ContentTable.vue'
import ContentEditor from '../components/ContentEditor.vue'
import { useRightsStore } from '../stores/rights'

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

interface ContentType {
  id: number
  name: string
  description?: string
}

const getContentFields = (content: any): ContentField[] => {
  if (!content) return []
  const ignore = new Set(['id', 'title', 'active', 'duration', 'contenttypeName', 'screengroups', 'contenttype_id', 'html', 'preview_css', '_field_metadata'])
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

const toast = useToast()
const confirm = useConfirm()
const { on, off, emit, emitWithAck } = useSocket()
const rightsStore = useRightsStore()
const canCreate = computed(() => rightsStore.can('content.create'))

const contentTypes = ref<ContentType[]>([])
const allContent = ref<ContentElement[]>([])
const unassignedContent = ref<ContentElement[]>([])
const loading = ref(true)

const allScreengroups = ref<Array<{ id: number; name: string }>>([])
const oneScreenGroups = ref<Array<{ id: number; name: string; screen_ids: number[] }>>([])
const oneScreenGroupIds = computed(() => oneScreenGroups.value.map(g => g.id))

const selectedScreengroupFilter = ref<number>(0)
const showActiveOnly = ref(false)
const searchFilter = ref('')

const allScreengroupOptions = computed(() => {
  const opts = allScreengroups.value
    .map(sg => ({ id: sg.id, name: sg.name }))
    .sort((a, b) => a.name.localeCompare(b.name))
  return [{ id: 0, name: 'All' }, ...opts]
})

const filteredContent = computed<ContentElement[]>(() => {
  const filter = searchFilter.value.toLowerCase()
  let items = allContent.value
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
  return items
})

const handleAllContentDetailed = (data: { content: ContentElement[] }) => {
  allContent.value = data.content || []
  loading.value = false
}

const handleUnassignedContent = (data: { content: ContentElement[] }) => {
  unassignedContent.value = data.content || []
}

const handleContentTypes = (data: { data?: ContentType[]; contenttypes?: ContentType[] }) => {
  contentTypes.value = data.data || data.contenttypes || []
}

const handleAllScreengroups = (data: any) => {
  const arr = data?.screengroups || data?.data || []
  allScreengroups.value = arr
    .filter((sg: any) => !(sg.attributes?.is_one_screen ?? sg.is_one_screen))
    .map((sg: any) => ({ id: sg.id, name: sg.attributes?.name || sg.name || '' }))
  oneScreenGroups.value = arr
    .filter((sg: any) => !!(sg.attributes?.is_one_screen ?? sg.is_one_screen))
    .map((sg: any) => ({
      id: Number(sg.id),
      name: sg.attributes?.name || sg.name || '',
      screen_ids: (sg.relationships?.screens?.data || []).map((s: any) => Number(s.id)),
    }))
}

onMounted(() => {
  on('displayhive:admin:stc:all_content_detailed', handleAllContentDetailed)
  on('displayhive:admin:stc:unassigned_content', handleUnassignedContent)
  on('displayhive:admin:stc:upd_contenttypes', handleContentTypes)
  on('displayhive:admin:stc:upd_screengroups', handleAllScreengroups)

  refreshData()
  emit('displayhive:admin:cts:get_contenttypes')
  emit('displayhive:admin:cts:get_screengroups')
})

onUnmounted(() => {
  off('displayhive:admin:stc:all_content_detailed', handleAllContentDetailed)
  off('displayhive:admin:stc:unassigned_content', handleUnassignedContent)
  off('displayhive:admin:stc:upd_contenttypes', handleContentTypes)
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

const editorRef = ref<InstanceType<typeof ContentEditor>>()

const openCreateWorkflow = () => {
  editorRef.value?.openCreate()
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
          <span>Content</span>
          <div class="header-actions">
            <Button v-if="canCreate" icon="pi pi-plus" label="New Content" @click="openCreateWorkflow" size="small" />
            <Button icon="pi pi-refresh" label="Refresh" @click="refreshData" size="small" outlined />
          </div>
        </div>
      </template>
      <template #content>
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

        <ContentTable
          :items="filteredContent"
          :totalItems="allContent.length"
          v-model:search="searchFilter"
          :oneScreenGroupIds="oneScreenGroupIds"
          emptyMessage="No content"
          @edit="openEditContent"
          @copy="copyContent"
          @preview="showInPreview"
          @delete="deleteContent"
          @toggleActive="toggleActive"
          @updateDuration="updateDuration"
          @setDuration="setDuration"
        />

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
              :oneScreenGroupIds="oneScreenGroupIds"
              emptyMessage="No unassigned content"
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

.filter-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #6b7280;
  white-space: nowrap;
}

.screengroup-filter-select {
  min-width: 200px;
}

.container-card {
  height: fit-content;
}

.unassigned-card {
  border: 2px solid #f59e0b;
  background: #fffbeb;
  margin-top: 1.5rem;
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
  .container-header {
    flex-wrap: wrap;
    gap: 0.5rem;
  }
}
</style>
