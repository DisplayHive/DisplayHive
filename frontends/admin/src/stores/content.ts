import { ref } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'
import type { Content } from '../types/models'
import type { WeeklyWindow } from '../utils/content/recurrence'

export const useContentStore = defineStore('content', () => {
  const { on, off, emit } = useSocket()

  const content = ref<Content[]>([])
  const unassignedContent = ref<Content[]>([])
  const loading = ref(false)

  type RawContent = {
    id: number
    title: string
    contenttypeName?: string
    contenttype_name?: string
    active?: boolean
    start_time?: string | null
    end_time?: string | null
    recurrence?: WeeklyWindow[]
    updated_at?: string | null
    assigned?: boolean
  }

  const toContent = (c: RawContent): Content => ({
    id: c.id,
    title: c.title,
    contenttype_name: c.contenttypeName || c.contenttype_name,
    active: c.active,
    start_time: c.start_time,
    end_time: c.end_time,
    recurrence: c.recurrence,
    updated_at: c.updated_at,
    assigned: c.assigned,
  })

  const handleAllContent = (data: { content?: RawContent[]; data?: RawContent[] }) => {
    const arr = data?.content || data?.data || []
    content.value = arr.map(toContent)
    loading.value = false
  }

  const handleUnassignedContent = (data: { content?: RawContent[]; data?: RawContent[] }) => {
    const arr = data?.content || data?.data || []
    unassignedContent.value = arr.map(toContent)
  }

  // Remove before registering to stay idempotent if the store is re-initialized
  off('displayhive:admin:stc:all_content_element', handleAllContent)
  off('displayhive:admin:stc:unassigned_content', handleUnassignedContent)
  on('displayhive:admin:stc:all_content_element', handleAllContent)
  on('displayhive:admin:stc:unassigned_content', handleUnassignedContent)

  const fetch = () => {
    loading.value = true
    emit('displayhive:admin:cts:get_all_content_element')
    emit('displayhive:admin:cts:get_unassigned_content')
  }

  /** Forget everything held for the session that ended (logout): the next person must not see it. */
  const reset = () => {
    content.value = []
    unassignedContent.value = []
    loading.value = false
  }

  return { content, unassignedContent, loading, fetch, reset }
})
