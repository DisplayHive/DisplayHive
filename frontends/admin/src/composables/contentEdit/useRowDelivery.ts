import { computed, reactive, ref, type Ref } from 'vue'
import { useAck } from '../useAck'
import { useScreengroupAssignment, type ScreengroupOption } from './useScreengroupAssignment'
import { describeWindows, type WeeklyWindow } from '../../utils/content/recurrence'
import { cloneWindows, fmtDt, formatDateDisplay, parseIsoDate } from '../../utils/content/scheduling'

/**
 * What the delivery settings (components/contentEdit/DeliverySettings.vue) work on: when the content
 * is shown and which screen groups and screens it is assigned to. The content edit page's editor has
 * all of it; a row of the content list gets it from `useRowDelivery`.
 */
export interface DeliveryModel {
  createForm: { start_time: Date | null; end_time: Date | null; recurrence: WeeklyWindow[]; duration: number }
  durationMinutes: number
  durationSeconds: number
  durationSummary: string
  schedulingSummary: string
  addWindow: (preset?: WeeklyWindow) => void
  removeWindow: (index: number) => void
  toggleWindowDay: (window: WeeklyWindow, day: number) => void
  assignmentSummary: string
  allScreengroups: ScreengroupOption[]
  oneScreenGroups: ScreengroupOption[]
  formScreengroupIds: number[]
  sgSearchText: string
  screenSearchText: string
  sgPage: number
  screenPage: number
  filteredScreengroups: ScreengroupOption[]
  filteredOneScreenGroups: ScreengroupOption[]
  pagedScreengroups: ScreengroupOption[]
  pagedOneScreenGroups: ScreengroupOption[]
}

/** The parts of a list row the delivery settings need. */
export interface DeliveryRow {
  id: number
  duration?: number
  start_time?: string | null
  end_time?: string | null
  recurrence?: unknown
  screengroups?: Array<{ id: number }>
}

/**
 * The delivery settings of one row of the content list: its schedule and assignment, kept apart
 * from the saved values until `save()` writes them (the schedule with `update_content_delivery`, the
 * assignment with one add / remove event per screen group that changed) or `discard()` drops them.
 * The screen group lists come from the page (`groups`): every row asking the server for them made the page
 * start over, and with it every row.
 */
export function useRowDelivery(getRow: () => DeliveryRow, groups: { allScreengroups: Ref<ScreengroupOption[]>; oneScreenGroups: Ref<ScreengroupOption[]> }) {
  const { request } = useAck()
  const assignment = useScreengroupAssignment(ref(true), groups)

  const createForm = reactive<DeliveryModel['createForm']>({ start_time: null, end_time: null, recurrence: [], duration: 10 })
  const saving = ref(false)
  let saved = ''

  const snapshot = () => JSON.stringify([createForm.duration, fmtDt(createForm.start_time), fmtDt(createForm.end_time), createForm.recurrence, [...assignment.formScreengroupIds.value].sort()])

  const load = () => {
    const row = getRow()
    createForm.duration = row.duration ?? 10
    createForm.start_time = parseIsoDate(row.start_time)
    createForm.end_time = parseIsoDate(row.end_time)
    createForm.recurrence = cloneWindows(row.recurrence)
    assignment.assign((row.screengroups ?? []).map((g) => g.id))
    saved = snapshot()
  }
  load()

  const dirty = computed(() => snapshot() !== saved)

  const durationMinutes = computed({
    get: () => Math.floor(createForm.duration / 60),
    set: (m: number) => { createForm.duration = (m ?? 0) * 60 + (createForm.duration % 60) },
  })
  const durationSeconds = computed({
    get: () => createForm.duration % 60,
    set: (sec: number) => { createForm.duration = Math.floor(createForm.duration / 60) * 60 + (sec ?? 0) },
  })
  const durationSummary = computed(() => {
    const m = durationMinutes.value
    const sec = durationSeconds.value
    if (m === 0) return `${sec}s`
    return sec === 0 ? `${m}m` : `${m}m ${sec}s`
  })

  const schedulingSummary = computed(() => {
    const { start_time: start, end_time: end, recurrence } = createForm
    const range = (() => {
      if (!start && !end) return ''
      if (start && end) return `${formatDateDisplay(start)} → ${formatDateDisplay(end)}`
      if (start) return `from ${formatDateDisplay(start)}`
      return `until ${formatDateDisplay(end)}`
    })()
    const windows = recurrence.length ? describeWindows(recurrence) : ''
    if (!range && !windows) return 'no restriction'
    return [range, windows].filter(Boolean).join(', ')
  })

  const addWindow = (preset?: WeeklyWindow) => {
    createForm.recurrence.push(preset ? { days: [...preset.days], from: preset.from, to: preset.to } : { days: [1, 2, 3, 4, 5], from: '08:00', to: '18:00' })
  }
  const removeWindow = (index: number) => { createForm.recurrence.splice(index, 1) }
  const toggleWindowDay = (window: WeeklyWindow, day: number) => {
    window.days = window.days.includes(day) ? window.days.filter((d) => d !== day) : [...window.days, day].sort((a, b) => a - b)
  }

  const save = async (): Promise<boolean> => {
    const row = getRow()
    saving.value = true
    if (createForm.duration !== (row.duration ?? 10)) {
      const done = await request('displayhive:admin:cts:update_content_element_duration', { content_element_id: row.id, duration: createForm.duration },
        { error: 'Could not save the duration' })
      if (!done) { saving.value = false; return false }
    }
    const ack = await request('displayhive:admin:cts:update_content_delivery', {
      content_element_id: row.id,
      start_time: fmtDt(createForm.start_time),
      end_time: fmtDt(createForm.end_time),
      recurrence: createForm.recurrence,
    }, { error: 'Could not save the delivery settings' })
    if (ack) {
      const before = assignment.originalScreengroupIds.value
      const now = assignment.formScreengroupIds.value
      // One answer per change: the list is read again after the save, and it must see all of them.
      let assigned = true
      for (const id of now.filter((g) => !before.includes(g))) {
        assigned = !!(await request('displayhive:admin:cts:add_content_to_screengroup', { screengroup_id: id, content_id: row.id }, { error: 'Could not assign the content' })) && assigned
      }
      for (const id of before.filter((g) => !now.includes(g))) {
        assigned = !!(await request('displayhive:admin:cts:remove_content_from_screengroup', { screengroup_id: id, content_id: row.id }, { error: 'Could not remove the content from the group' })) && assigned
      }
      if (!assigned) { saving.value = false; return false }
      assignment.originalScreengroupIds.value = [...now]
      saved = snapshot()
    }
    saving.value = false
    return !!ack
  }

  const discard = () => load()

  /** Take the row's values again (it was pushed anew), unless changes are waiting. */
  const refresh = () => { if (!dirty.value) load() }

  return reactive({
    createForm, durationMinutes, durationSeconds, durationSummary, schedulingSummary, addWindow, removeWindow, toggleWindowDay,
    assignmentSummary: assignment.assignmentSummary,
    allScreengroups: assignment.allScreengroups, oneScreenGroups: assignment.oneScreenGroups,
    formScreengroupIds: assignment.formScreengroupIds,
    sgSearchText: assignment.sgSearchText, screenSearchText: assignment.screenSearchText,
    sgPage: assignment.sgPage, screenPage: assignment.screenPage,
    filteredScreengroups: assignment.filteredScreengroups, filteredOneScreenGroups: assignment.filteredOneScreenGroups,
    pagedScreengroups: assignment.pagedScreengroups, pagedOneScreenGroups: assignment.pagedOneScreenGroups,
    dirty, saving, save, discard, refresh,
  })
}
