import { computed, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'
import { useSocket } from '../useSocket'
import { useScreensStore } from '../../stores/screens'

export interface ScreengroupOption { id: number; name: string; screen_ids: number[] }

// Wire shape pushed by 'upd_screengroups' — either flat or JSON:API-style
// (attributes/relationships), depending on which backend path produced it.
interface RawScreengroup {
  id: number | string
  name?: string
  is_one_screen?: boolean
  attributes?: { name?: string; is_one_screen?: boolean }
  relationships?: { screens?: { data?: Array<{ id: number | string }> } }
}

export const SG_PAGE_SIZE = 10

/**
 * Which screen groups and screens a content element is assigned to: the lists to pick from
 * (searchable, paged), the picked ids, and the screens the element is currently live on —
 * so any edit is flagged as affecting them. (Screens are the one-screen groups.)
 */
export function useScreengroupAssignment(editMode: Ref<boolean>) {
  const { on, off, emit } = useSocket()
  const screensStore = useScreensStore()

  const allScreengroups = ref<ScreengroupOption[]>([])
  const oneScreenGroups = ref<ScreengroupOption[]>([])

  const handleAllScreengroups = (data: { screengroups?: RawScreengroup[]; data?: RawScreengroup[] }) => {
    const arr = data?.screengroups || data?.data || []
    const toOption = (sg: RawScreengroup): ScreengroupOption => ({
      id: Number(sg.id),
      name: sg.attributes?.name || sg.name || '',
      screen_ids: (sg.relationships?.screens?.data || []).map((s) => Number(s.id)),
    })
    allScreengroups.value = arr
      .filter((sg) => !(sg.attributes?.is_one_screen ?? sg.is_one_screen))
      .map(toOption)
    oneScreenGroups.value = arr
      .filter((sg) => !!(sg.attributes?.is_one_screen ?? sg.is_one_screen))
      .map(toOption)
  }

  onMounted(() => {
    on('displayhive:admin:stc:upd_screengroups', handleAllScreengroups)
    emit('displayhive:admin:cts:get_screengroups')
    screensStore.fetch()
  })
  onUnmounted(() => {
    off('displayhive:admin:stc:upd_screengroups', handleAllScreengroups)
  })

  const formScreengroupIds = ref<number[]>([])
  const originalScreengroupIds = ref<number[]>([])

  // Screens this content element is currently live on (via its *saved* screengroup memberships —
  // originalScreengroupIds, not the in-progress formScreengroupIds edit), so any edit here (even
  // one that doesn't touch the screengroup checkboxes at all) is flagged as affecting them.
  const affectedScreenNames = computed<string[]>(() => {
    const screenIds = new Set<number>()
    for (const sgId of originalScreengroupIds.value) {
      const oneScreen = oneScreenGroups.value.find((g) => g.id === sgId)
      if (oneScreen) oneScreen.screen_ids.forEach((id) => screenIds.add(id))
      const group = allScreengroups.value.find((g) => g.id === sgId)
      if (group) group.screen_ids.forEach((id) => screenIds.add(id))
    }
    return screensStore.screens
      .filter((s) => screenIds.has(s.id))
      .map((s) => s.name)
      .sort((a, b) => a.localeCompare(b))
  })
  const affectsMultipleScreens = computed(() => editMode.value && affectedScreenNames.value.length > 1)

  const assignmentSummary = computed(() => {
    const n = formScreengroupIds.value.length
    return n === 0 ? 'none selected' : `${n} selected`
  })

  const sgSearchText = ref('')
  const screenSearchText = ref('')
  const sgPage = ref(0)
  const screenPage = ref(0)

  const filteredScreengroups = computed(() => {
    const q = sgSearchText.value.toLowerCase()
    if (!q) return allScreengroups.value
    return allScreengroups.value.filter((sg) => sg.name.toLowerCase().includes(q))
  })
  const filteredOneScreenGroups = computed(() => {
    const q = screenSearchText.value.toLowerCase()
    if (!q) return oneScreenGroups.value
    return oneScreenGroups.value.filter((sg) => sg.name.toLowerCase().includes(q))
  })
  const pagedScreengroups = computed(() => {
    const start = sgPage.value * SG_PAGE_SIZE
    return filteredScreengroups.value.slice(start, start + SG_PAGE_SIZE)
  })
  const pagedOneScreenGroups = computed(() => {
    const start = screenPage.value * SG_PAGE_SIZE
    return filteredOneScreenGroups.value.slice(start, start + SG_PAGE_SIZE)
  })

  watch(sgSearchText, () => { sgPage.value = 0 })
  watch(screenSearchText, () => { screenPage.value = 0 })

  const reset = () => {
    formScreengroupIds.value = []
    originalScreengroupIds.value = []
    sgSearchText.value = ''
    screenSearchText.value = ''
    sgPage.value = 0
    screenPage.value = 0
  }

  /** Pre-assign (and remember as saved) the given group ids. */
  const assign = (ids: number[]) => {
    formScreengroupIds.value = [...ids]
    originalScreengroupIds.value = [...ids]
  }

  return {
    allScreengroups, oneScreenGroups, formScreengroupIds, originalScreengroupIds,
    affectedScreenNames, affectsMultipleScreens, assignmentSummary,
    sgSearchText, screenSearchText, sgPage, screenPage,
    filteredScreengroups, filteredOneScreenGroups, pagedScreengroups, pagedOneScreenGroups,
    reset, assign,
  }
}
