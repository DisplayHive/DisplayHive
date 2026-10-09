import { ref } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'
import { unwrapEntity } from '../utils/entity'
import type { Screengroup } from '../types/models'

export const useScreengroupsStore = defineStore('screengroups', () => {
  const { on, emit } = useSocket()

  const screengroups = ref<Screengroup[]>([])
  const loading = ref(false)

  type RawScreengroupJsonApi = {
    id: string | number
    attributes: {
      name: string
      screensCount?: number
      contentCount?: number
      is_one_screen?: boolean
    }
  }

  type RawScreengroupFlat = {
    id: number
    name: string
    screens_count?: number
    screens?: unknown[]
    content_count?: number
    content_elements?: unknown[]
    is_one_screen?: boolean
  }

  type RawScreengroup = RawScreengroupJsonApi | RawScreengroupFlat

  const handleList = (data: { data?: RawScreengroup[]; screengroups?: RawScreengroup[] }) => {
    const list = data?.data || data?.screengroups || []
    screengroups.value = list.map((sg) => {
      // Merge both wire shapes into one record, then read fields tolerantly
      // (JSON:API uses camelCase `screensCount`; the flat shape uses
      // `screens_count` or the raw `screens`/`content_elements` arrays).
      const r = unwrapEntity(sg as RawScreengroupFlat & RawScreengroupJsonApi['attributes'])
      return {
        id: Number(r.id),
        name: r.name ?? '',
        screens_count: r.screensCount ?? r.screens_count ?? r.screens?.length ?? 0,
        content_count: r.contentCount ?? r.content_count ?? r.content_elements?.length ?? 0,
        is_one_screen: r.is_one_screen ?? false,
      }
    })
    loading.value = false
  }

  on('displayhive:admin:stc:upd_screengroups', handleList)

  const fetch = () => {
    loading.value = true
    emit('displayhive:admin:cts:get_screengroups')
  }

  const getScreenGroupScreens = (groupId: number) => {
    emit('displayhive:admin:cts:get_screengroup_screens', { screengroup_id: groupId })
  }

  const getScreenGroupContent = (groupId: number) => {
    emit('displayhive:admin:cts:get_screengroup_content', { screengroup_id: groupId })
  }

  return {
    screengroups,
    loading,
    fetch,
    getScreenGroupScreens,
    getScreenGroupContent,
  }
})
