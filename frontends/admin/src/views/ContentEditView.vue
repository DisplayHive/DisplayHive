<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useScreensStore } from '../stores/screens'

import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import Editor from 'primevue/editor'
import Select from 'primevue/select'
import Checkbox from 'primevue/checkbox'
import Paginator from 'primevue/paginator'
import DatePicker from 'primevue/datepicker'
import Tag from 'primevue/tag'
import Card from 'primevue/card'
import PretalxTableFieldEditor from '../components/PretalxTableFieldEditor.vue'
import { blankPretalxTableValue, type PretalxTableValue } from '../utils/pretalxTable'
import IconPickerField from '../components/IconPickerField.vue'
import type { IconPickerValue } from '../utils/iconLibraries'
import { buildDesignPreviewSrcdoc, type DesignPreviewPayload, type PreviewContainer } from '../utils/designPreview'

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

interface ContentType {
  id: number
  name: string
  description?: string
  html?: string
}

interface TagConfig {
  name: string
  title?: string
  fieldHandler?: string
  description?: string
  max_length?: number
}

interface MediaItem {
  id: number
  title: string
  filename: string
  mimetype: string
  url: string
  preview_url: string
  tags: string[]
}

interface ScreengroupOption { id: number; name: string; screen_ids: number[] }

const router = useRouter()
const route = useRoute()
const goBack = () => router.push({ name: 'content' })

const toast = useToast()
const confirm = useConfirm()
const screensStore = useScreensStore()
const { on, off, emit: socketEmit } = useSocket()

// Fetched locally now (this used to receive contentTypes/allScreengroups/
// oneScreenGroups as props from ContentView.vue, back when this was a modal
// it opened) — a routed page only gets an id from the URL, so it fetches
// everything it needs itself, the same way ContentView.vue does for its own
// filter system.
const contentTypes = ref<ContentType[]>([])
const allScreengroups = ref<ScreengroupOption[]>([])
const oneScreenGroups = ref<ScreengroupOption[]>([])

const handleContentTypesList = (data: { data?: ContentType[]; contenttypes?: ContentType[] }) => {
  contentTypes.value = data.data || data.contenttypes || []
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

const showSelectContentTypeDialog = ref(false)
const showCreateContentDialog = ref(false)
const editMode = ref(false)
const pendingIsCreate = ref(false)
const pendingKeepOpen = ref(false)
const editorReady = ref(false)
const contentDetailReceived = ref(false)
const loadingContentTypeDetail = ref(false)
const selectedContentType = ref<ContentType | null>(null)
const pendingContentDetail = ref<any | null>(null)

const createForm = ref({
  id: null as number | null,
  title: '',
  duration: 10,
  start_time: null as Date | null,
  end_time: null as Date | null,
  contenttype_id: null as number | null,
  fields: {} as Record<string, string | number | boolean>
})
const tagConfigs = ref<TagConfig[]>([])

const formScreengroupIds = ref<number[]>([])
const originalScreengroupIds = ref<number[]>([])

// Screens this content element is currently live on (via its *saved*
// screengroup memberships — originalScreengroupIds, not the in-progress
// formScreengroupIds edit), so any edit here (even one that doesn't touch
// the screengroup checkboxes at all) is flagged as affecting them.
const affectedScreenNames = computed<string[]>(() => {
  const screenIds = new Set<number>()
  for (const sgId of originalScreengroupIds.value) {
    const oneScreen = oneScreenGroups.value.find(g => g.id === sgId)
    if (oneScreen) oneScreen.screen_ids.forEach(id => screenIds.add(id))
    const group = allScreengroups.value.find(g => g.id === sgId)
    if (group) group.screen_ids.forEach(id => screenIds.add(id))
  }
  return screensStore.screens
    .filter(s => screenIds.has(s.id))
    .map(s => s.name)
    .sort((a, b) => a.localeCompare(b))
})
const affectsMultipleScreens = computed(() => editMode.value && affectedScreenNames.value.length > 1)

// --- Live preview: renders the in-progress (possibly unsaved) form fields
// through the Contenttype's actual Layout + the active Design, debounced so
// it doesn't fire a server round trip on every keystroke. srcdoc assembly
// itself lives in utils/designPreview.ts, shared with ContentTable.vue's
// row-expansion preview for already-saved content. ---
interface PreviewData { design: DesignPreviewPayload; containers: Record<string, PreviewContainer> }
const previewData = ref<PreviewData | null>(null)
let previewTimer: ReturnType<typeof setTimeout> | null = null

const handleContentPreview = (data: PreviewData) => {
  previewData.value = data
}

const requestPreview = () => {
  if (!createForm.value.contenttype_id) {
    previewData.value = null
    return
  }
  socketEmit('displayhive:admin:cts:preview_content_element', {
    contenttype_id: createForm.value.contenttype_id,
    ...createForm.value.fields,
  })
}

watch(
  () => [createForm.value.contenttype_id, createForm.value.fields],
  () => {
    if (previewTimer) clearTimeout(previewTimer)
    previewTimer = setTimeout(requestPreview, 500)
  },
  { deep: true },
)

const previewSrcdoc = computed(() => buildDesignPreviewSrcdoc(previewData.value?.design, previewData.value?.containers))

const sgSearchText = ref('')
const screenSearchText = ref('')
const sgPage = ref(0)
const screenPage = ref(0)
const SG_PAGE_SIZE = 10

const showImagePickerDialog = ref(false)
const pickerTargetField = ref<string | null>(null)
const pickerMediaItems = ref<MediaItem[]>([])
const pickerSearchText = ref('')
const pickerLoading = ref(false)

const availableImageTags = ref<string[]>([])

// --- datetime_format preview ---
const previewNow = ref(new Date())
const previewTimezone = ref('UTC')
let previewInterval: ReturnType<typeof setInterval> | null = null

const FORMAT_TOKENS = [
  { token: 'YYYY',  desc: 'Year (4 digits)',        example: '2024'   },
  { token: 'YY',    desc: 'Year (2 digits)',         example: '24'     },
  { token: 'MM',    desc: 'Month (01–12)',           example: '06'     },
  { token: 'M',     desc: 'Month (1–12)',            example: '6'      },
  { token: 'DD',    desc: 'Day (01–31)',             example: '07'     },
  { token: 'D',     desc: 'Day (1–31)',              example: '7'      },
  { token: 'HH',    desc: 'Hour 24h (00–23)',        example: '14'     },
  { token: 'H',     desc: 'Hour 24h (0–23)',         example: '14'     },
  { token: 'hh',    desc: 'Hour 12h (01–12)',        example: '02'     },
  { token: 'h',     desc: 'Hour 12h (1–12)',         example: '2'      },
  { token: 'mm',    desc: 'Minute (00–59)',          example: '05'     },
  { token: 'ss',    desc: 'Second (00–59)',          example: '09'     },
  { token: 'A',     desc: 'AM / PM',                example: 'PM'     },
  { token: 'dddd',  desc: 'Weekday (full)',          example: 'Monday' },
  { token: 'ddd',   desc: 'Weekday (short)',         example: 'Mon'    },
]

function _formatDateStr(d: Date, fmt: string, timezone: string): string {
  try {
    const tz = timezone || 'UTC'
    const p = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false, weekday: 'long',
    }).formatToParts(d)
    const p12 = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, hour: 'numeric', hour12: true,
    }).formatToParts(d)
    const wdShort = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, weekday: 'short',
    }).format(d)

    const get   = (type: string) => p.find(x => x.type === type)?.value ?? ''
    const get12 = (type: string) => p12.find(x => x.type === type)?.value ?? ''

    const year   = get('year')
    const month  = get('month')
    const day    = get('day')
    const h24    = parseInt(get('hour'), 10) % 24
    const minute = get('minute')
    const second = get('second')
    const wdFull = get('weekday')
    const h12r   = parseInt(get12('hour'), 10)
    const h12    = h12r === 0 ? 12 : h12r
    const period = (get12('dayPeriod') || (h24 < 12 ? 'AM' : 'PM')).toUpperCase()

    return fmt.replace(/YYYY|YY|dddd|ddd|MM|M|DD|D|HH|H|hh|h|mm|m|ss|s|A|a/g, t => {
      switch (t) {
        case 'YYYY': return year
        case 'YY':   return year.slice(-2)
        case 'dddd': return wdFull
        case 'ddd':  return wdShort
        case 'MM':   return month
        case 'M':    return String(parseInt(month, 10))
        case 'DD':   return day
        case 'D':    return String(parseInt(day, 10))
        case 'HH':   return String(h24).padStart(2, '0')
        case 'H':    return String(h24)
        case 'hh':   return String(h12).padStart(2, '0')
        case 'h':    return String(h12)
        case 'mm':   return minute
        case 'm':    return String(parseInt(minute, 10))
        case 'ss':   return second
        case 's':    return String(parseInt(second, 10))
        case 'A':    return period
        case 'a':    return period.toLowerCase()
        default:     return t
      }
    })
  } catch {
    return fmt
  }
}

const formatDatePreview = (format: string): string =>
  _formatDateStr(previewNow.value, format || 'HH:mm:ss', previewTimezone.value)

const handleAdminSettingsForPreview = (data: any) => {
  const tz = data?.system_settings?.timezone
  if (tz) previewTimezone.value = tz
}
// ---

const imageModeOptions = [
  { label: 'Single Image', value: 'single' },
  { label: 'Random Image from Tags', value: 'random_tags' },
]

const durationMinutes = computed({
  get: () => Math.floor(createForm.value.duration / 60),
  set: (m: number) => {
    createForm.value.duration = (m ?? 0) * 60 + (createForm.value.duration % 60)
  },
})

const durationSeconds = computed({
  get: () => createForm.value.duration % 60,
  set: (s: number) => {
    createForm.value.duration = Math.floor(createForm.value.duration / 60) * 60 + (s ?? 0)
  },
})

const filteredScreengroups = computed(() => {
  const q = sgSearchText.value.toLowerCase()
  if (!q) return allScreengroups.value
  return allScreengroups.value.filter(sg => sg.name.toLowerCase().includes(q))
})

const filteredOneScreenGroups = computed(() => {
  const q = screenSearchText.value.toLowerCase()
  if (!q) return oneScreenGroups.value
  return oneScreenGroups.value.filter(sg => sg.name.toLowerCase().includes(q))
})

const pagedScreengroups = computed(() => {
  const start = sgPage.value * SG_PAGE_SIZE
  return filteredScreengroups.value.slice(start, start + SG_PAGE_SIZE)
})

const pagedOneScreenGroups = computed(() => {
  const start = screenPage.value * SG_PAGE_SIZE
  return filteredOneScreenGroups.value.slice(start, start + SG_PAGE_SIZE)
})

const pickerFiltered = computed(() => {
  const q = pickerSearchText.value.toLowerCase()
  const images = pickerMediaItems.value.filter((m) => m.mimetype.startsWith('image/'))
  if (!q) return images
  return images.filter(
    (m) =>
      m.title?.toLowerCase().includes(q) ||
      m.filename?.toLowerCase().includes(q) ||
      (m.tags || []).some((t) => t.toLowerCase().includes(q))
  )
})

watch(sgSearchText, () => { sgPage.value = 0 })
watch(screenSearchText, () => { screenPage.value = 0 })

const parseIsoDate = (v: string | null | undefined): Date | null => {
  if (!v) return null
  const d = new Date(v)
  return isNaN(d.getTime()) ? null : d
}

const resetCreateForm = () => {
  createForm.value = {
    id: null,
    title: '',
    duration: 10,
    start_time: null,
    end_time: null,
    contenttype_id: null,
    fields: {}
  }
  tagConfigs.value = []
  selectedContentType.value = null
  editMode.value = false
  editorReady.value = false
  contentDetailReceived.value = false
  pendingContentDetail.value = null
  formScreengroupIds.value = []
  originalScreengroupIds.value = []
  sgSearchText.value = ''
  screenSearchText.value = ''
  sgPage.value = 0
  screenPage.value = 0
  showSelectContentTypeDialog.value = false
  showCreateContentDialog.value = false
  previewData.value = null
  if (previewTimer) clearTimeout(previewTimer)
}

// Whether the currently-loading content element should be saved as a new
// copy (createForm.value.id nulled, title prefixed) once its detail arrives
// — set by initFromRoute for the 'content-copy' route, consumed in
// handleContentDetail.
const pendingIsCopy = ref(false)

/**
 * Route-driven equivalent of the old openCreate/openEdit/openCopy trio this
 * page used to expose to its parent for a `<Dialog>` to call into — now the
 * URL itself is the source of truth for what's being edited, so this runs
 * on mount and again whenever the route changes (Vue Router reuses this
 * component instance rather than remounting it if only the params differ).
 */
const initFromRoute = () => {
  resetCreateForm()

  if (route.name === 'content-new') {
    editMode.value = false
    pendingIsCopy.value = false

    const screengroupId = route.query.screengroup_id ? Number(route.query.screengroup_id) : null
    if (screengroupId) {
      formScreengroupIds.value = [screengroupId]
      originalScreengroupIds.value = [screengroupId]
    }

    const contenttypeId = route.query.contenttype_id ? Number(route.query.contenttype_id) : null
    const preselected = contenttypeId ? contentTypes.value.find(ct => ct.id === contenttypeId) : null
    if (preselected) {
      selectContentType(preselected)
    } else {
      showSelectContentTypeDialog.value = true
    }
    return
  }

  const id = Number(route.params.id)
  if (!id) {
    goBack()
    return
  }
  editMode.value = true
  pendingIsCopy.value = route.name === 'content-copy'
  loadingContentTypeDetail.value = true
  socketEmit('displayhive:admin:cts:get_content_element_detail', { content_element_id: id })
}

const selectContentType = (ct: ContentType) => {
  createForm.value.contenttype_id = ct.id
  showSelectContentTypeDialog.value = false
  loadingContentTypeDetail.value = true
  socketEmit('displayhive:admin:cts:get_contenttype', { contenttype_id: ct.id })
}

const extractTagConfigs = (html: string) => {
  const re = /{{\s*([^}]+?)\s*}}/g
  const found = new Map<string, TagConfig>()
  let m: RegExpExecArray | null
  while ((m = re.exec(html))) {
    let raw = String(m[1] ?? '').trim()
    if (!raw) continue
    const beforeFilter = (raw.split('|')[0] ?? '').toString()
    raw = ((beforeFilter.split('.')[0] ?? '') as string).trim()
    if (!raw) continue
    if (!found.has(raw)) {
      found.set(raw, { name: raw, title: raw, fieldHandler: 'textklein', description: '', max_length: 255 })
    }
  }
  tagConfigs.value = Array.from(found.values())
  createForm.value.fields = {}
  tagConfigs.value.forEach(tag => {
    if (tag.fieldHandler === 'numbers') {
      createForm.value.fields[tag.name] = 0
    } else if (tag.fieldHandler === 'checkbox') {
      createForm.value.fields[tag.name] = false
    } else if (tag.fieldHandler === 'datetime_format') {
      createForm.value.fields[tag.name] = 'HH:mm:ss'
    } else if (tag.fieldHandler === 'table') {
      createForm.value.fields[tag.name] = JSON.stringify({ columns: ['Column 1', 'Column 2'], rows: [['', '']] })
    } else {
      createForm.value.fields[tag.name] = ''
    }
  })
}

// --- pretalx_table field adapter ------------------------------------------
// The wire format (ContentElement.serialized_input / the payload sent to
// create_content_element) is flat, suffix-keyed values on createForm.fields
// (e.g. `${name}__type`, `${name}__roomname`, ...) — application/admin/
// content/helper.py's render_content_fields() reads it that shape directly.
// These two functions are the only place that shape is assembled/read, so
// the shared PretalxTableFieldEditor component never needs to know about it.
const getPretalxTableValue = (name: string): PretalxTableValue => ({
  url: String(createForm.value.fields[name] || ''),
  type: String(createForm.value.fields[name + '__type'] || 'list'),
  roomname: String(createForm.value.fields[name + '__roomname'] || ''),
  fields: String(createForm.value.fields[name + '__fields'] || ''),
  linecount: Number(createForm.value.fields[name + '__linecount'] ?? 10),
  author_under_title: !!createForm.value.fields[name + '__author_under_title'],
  tracks_by_color: !!createForm.value.fields[name + '__tracks_by_color'],
  today_only: !!createForm.value.fields[name + '__today_only'],
  separate_days: !!createForm.value.fields[name + '__separate_days'],
  day_prefix: String(createForm.value.fields[name + '__day_prefix'] || ''),
  empty_text: String(createForm.value.fields[name + '__empty_text'] || ''),
  tracklist_columns: String(createForm.value.fields[name + '__tracklist_columns'] || 'name|Name,color|Color'),
  tracklist_layout: String(createForm.value.fields[name + '__tracklist_layout'] || 'list'),
  tracklist_exclude: String(createForm.value.fields[name + '__tracklist_exclude'] || ''),
  invalid_data_text: String(createForm.value.fields[name + '__invalid_data_text'] || ''),
})

const setPretalxTableValue = (name: string, v: PretalxTableValue) => {
  createForm.value.fields[name] = v.url
  createForm.value.fields[name + '__type'] = v.type
  createForm.value.fields[name + '__roomname'] = v.roomname
  createForm.value.fields[name + '__fields'] = v.fields
  createForm.value.fields[name + '__linecount'] = v.linecount
  createForm.value.fields[name + '__author_under_title'] = v.author_under_title
  createForm.value.fields[name + '__tracks_by_color'] = v.tracks_by_color
  createForm.value.fields[name + '__today_only'] = v.today_only
  createForm.value.fields[name + '__separate_days'] = v.separate_days
  createForm.value.fields[name + '__day_prefix'] = v.day_prefix
  createForm.value.fields[name + '__empty_text'] = v.empty_text
  createForm.value.fields[name + '__tracklist_columns'] = v.tracklist_columns
  createForm.value.fields[name + '__tracklist_layout'] = v.tracklist_layout
  createForm.value.fields[name + '__tracklist_exclude'] = v.tracklist_exclude
  createForm.value.fields[name + '__invalid_data_text'] = v.invalid_data_text
}

// --- icon field adapter ----------------------------------------------------
const getIconValue = (name: string): IconPickerValue => ({
  icon: String(createForm.value.fields[name] ?? ''),
  size: Number(createForm.value.fields[name + '__size']) || 5,
})

const setIconValue = (name: string, v: IconPickerValue) => {
  createForm.value.fields[name] = v.icon
  createForm.value.fields[name + '__size'] = v.size
}

const onEditorLoad = (fieldName: string, event: { instance: any }) => {
  const quill = event.instance
  const html = String(createForm.value.fields[fieldName] || '')
  if (html && quill && quill.clipboard) {
    const delta = quill.clipboard.convert(html)
    quill.setContents(delta, 'silent')
  }
}

const getFieldValue = (tagName: string): string | number | boolean => {
  return createForm.value.fields[tagName] ?? ''
}

const setFieldValue = (tagName: string, value: string | number | boolean) => {
  createForm.value.fields[tagName] = value
}

const getImageMode = (fieldName: string): string =>
  String(createForm.value.fields[`${fieldName}__image_mode`] || 'single')

const setImageMode = (fieldName: string, mode: string) => {
  createForm.value.fields[`${fieldName}__image_mode`] = mode
  if (mode === 'random_tags' && availableImageTags.value.length === 0) {
    socketEmit('displayhive:admin:cts:get_image_tags')
  }
}

const getImageTags = (fieldName: string): string[] => {
  const v = createForm.value.fields[`${fieldName}__image_tags`]
  if (Array.isArray(v)) return v as unknown as string[]
  if (typeof v === 'string' && v) {
    try { return JSON.parse(v) } catch { return [] }
  }
  return []
}

const toggleImageTag = (fieldName: string, tag: string) => {
  const current = getImageTags(fieldName)
  const idx = current.indexOf(tag)
  const next = idx === -1 ? [...current, tag] : current.filter((t) => t !== tag)
  createForm.value.fields[`${fieldName}__image_tags`] = next as unknown as string
}

const clearImageField = (fieldName: string) => {
  setFieldValue(fieldName, '')
}

// Fixes the rendered <img>'s height (vh) regardless of its container's own
// height — blank/0 leaves it scaling to fit the container, as before.
const getImageSize = (fieldName: string): number | null => {
  const v = createForm.value.fields[`${fieldName}__size`]
  const n = Number(v)
  return v !== '' && v != null && !isNaN(n) && n > 0 ? n : null
}

const setImageSize = (fieldName: string, v: number | null) => {
  createForm.value.fields[`${fieldName}__size`] = v ?? ''
}

// ── Table fieldHandler helpers ───────────────────────────────────────────────────

interface TableData { columns: string[]; rows: string[][] }

const parseTableData = (fieldName: string): TableData => {
  try {
    const parsed = JSON.parse(String(getFieldValue(fieldName) || ''))
    if (parsed && Array.isArray(parsed.columns) && Array.isArray(parsed.rows)) return parsed
  } catch {}
  return { columns: ['Column 1', 'Column 2'], rows: [['', '']] }
}

const setTableData = (fieldName: string, data: TableData) => {
  setFieldValue(fieldName, JSON.stringify(data))
}

const updateTableHeader = (fieldName: string, ci: number, value: string) => {
  const d = parseTableData(fieldName); d.columns[ci] = value; setTableData(fieldName, d)
}

const updateTableCell = (fieldName: string, ri: number, ci: number, value: string) => {
  const d = parseTableData(fieldName)
  if (d.rows[ri]) d.rows[ri][ci] = value
  setTableData(fieldName, d)
}

const addTableRow = (fieldName: string) => {
  const d = parseTableData(fieldName)
  d.rows.push(d.columns.map(() => ''))
  setTableData(fieldName, d)
}

const removeTableRow = (fieldName: string, ri: number) => {
  const d = parseTableData(fieldName); d.rows.splice(ri, 1); setTableData(fieldName, d)
}

const addTableColumn = (fieldName: string) => {
  const d = parseTableData(fieldName)
  d.columns.push(`Column ${d.columns.length + 1}`)
  d.rows.forEach(r => r.push(''))
  setTableData(fieldName, d)
}

const removeTableColumn = (fieldName: string, ci: number) => {
  const d = parseTableData(fieldName)
  d.columns.splice(ci, 1)
  d.rows.forEach(r => r.splice(ci, 1))
  setTableData(fieldName, d)
}

const tableDragState = ref<{ fieldName: string; type: 'row' | 'col'; fromIdx: number } | null>(null)

const onTableDragStart = (fieldName: string, type: 'row' | 'col', idx: number, e: DragEvent) => {
  tableDragState.value = { fieldName, type, fromIdx: idx }
  e.dataTransfer?.setData('text/plain', '')
}

const onTableDrop = (fieldName: string, type: 'row' | 'col', toIdx: number) => {
  const s = tableDragState.value
  if (!s || s.fieldName !== fieldName || s.type !== type || s.fromIdx === toIdx) { tableDragState.value = null; return }
  const d = parseTableData(fieldName)
  if (type === 'row') {
    const row = d.rows.splice(s.fromIdx, 1)[0] ?? []
    d.rows.splice(toIdx, 0, row)
  } else {
    const hdr = d.columns.splice(s.fromIdx, 1)[0] ?? ''
    d.columns.splice(toIdx, 0, hdr)
    d.rows.forEach(r => { const cell = r.splice(s.fromIdx, 1)[0] ?? ''; r.splice(toIdx, 0, cell) })
  }
  setTableData(fieldName, d)
  tableDragState.value = null
}

const openImagePicker = (fieldName: string) => {
  pickerTargetField.value = fieldName
  pickerSearchText.value = ''
  pickerLoading.value = true
  showImagePickerDialog.value = true
  socketEmit('displayhive:admin:cts:get_media_for_picker')
}

const selectPickerImage = (item: MediaItem) => {
  if (!pickerTargetField.value) return
  setFieldValue(pickerTargetField.value, item.url)
  showImagePickerDialog.value = false
  pickerTargetField.value = null
}

const submitCreateContent = (keepOpen = false) => {
  pendingKeepOpen.value = keepOpen
  if (!createForm.value.title.trim()) {
    toast.add({ severity: 'warn', summary: 'Validation', detail: 'Title is required', life: 3000 })
    return
  }

  if (affectsMultipleScreens.value) {
    confirm.require({
      message: `This change affects ${affectedScreenNames.value.length} screens. Proceed?`,
      header: 'Confirm Change',
      icon: 'pi pi-exclamation-triangle',
      acceptClass: 'p-button-warning',
      accept: () => doSubmitCreateContent(),
    })
    return
  }

  doSubmitCreateContent()
}

const doSubmitCreateContent = () => {
  const fmtDt = (d: Date | null | undefined): string | null => {
    if (!d) return null
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }

  if (
    createForm.value.start_time &&
    createForm.value.end_time &&
    createForm.value.end_time <= createForm.value.start_time
  ) {
    createForm.value.end_time = null
  }

  const payload: any = {
    title: createForm.value.title,
    duration: createForm.value.duration,
    start_time: fmtDt(createForm.value.start_time),
    end_time: fmtDt(createForm.value.end_time),
    contenttype_id: createForm.value.contenttype_id,
    ...createForm.value.fields
  }

  if (editMode.value && createForm.value.id) {
    payload.id = createForm.value.id
  }

  pendingIsCreate.value = !(editMode.value && createForm.value.id)
  socketEmit('displayhive:admin:cts:create_content_element', payload)

  if (editMode.value && createForm.value.id) {
    const contentId = createForm.value.id
    const added = formScreengroupIds.value.filter(id => !originalScreengroupIds.value.includes(id))
    const removed = originalScreengroupIds.value.filter(id => !formScreengroupIds.value.includes(id))
    added.forEach(sgId => socketEmit('displayhive:admin:cts:add_content_to_screengroup', { screengroup_id: sgId, content_id: contentId }))
    removed.forEach(sgId => socketEmit('displayhive:admin:cts:remove_content_from_screengroup', { screengroup_id: sgId, content_id: contentId }))
    originalScreengroupIds.value = [...formScreengroupIds.value]
  }
}

const handleContentTypeDetail = (data: { contenttype: ContentType }) => {
  loadingContentTypeDetail.value = false
  if (data.contenttype) {
    selectedContentType.value = data.contenttype
    // Fields (TagConfig) belong to the Contenttype itself — each one maps
    // directly to one of its Layout's containers.
    const serverTagConfigs: any[] = (data.contenttype as any).tagconfigs || []
    if (serverTagConfigs && serverTagConfigs.length > 0) {
      tagConfigs.value = serverTagConfigs.map((t: any) => {
        const fieldHandler = (t.field_handler as string) ?? 'textklein'
        return {
          name: t.field_name || t.name || '',
          title: t.field_label || t.title || (t.field_name || t.name || ''),
          fieldHandler,
          description: (t.description as string) || '',
          max_length: (t.max_length as number) || (fieldHandler === 'textbig' ? 5000 : 255),
        }
      })

      if (!editMode.value) {
        createForm.value.fields = {}
        tagConfigs.value.forEach(tag => {
          if (tag.fieldHandler === 'numbers') {
            createForm.value.fields[tag.name] = 0
          } else if (tag.fieldHandler === 'checkbox') {
            createForm.value.fields[tag.name] = false
          } else if (tag.fieldHandler === 'pretalx_table') {
            setPretalxTableValue(tag.name, blankPretalxTableValue())
          } else if (tag.fieldHandler === 'arrows') {
            createForm.value.fields[tag.name] = ''
            createForm.value.fields[tag.name + '_size'] = 5
          } else if (tag.fieldHandler === 'icon') {
            createForm.value.fields[tag.name] = ''
            createForm.value.fields[tag.name + '__size'] = 5
          } else if (tag.fieldHandler === 'datetime_format') {
            createForm.value.fields[tag.name] = 'HH:mm:ss'
          } else if (tag.fieldHandler === 'table') {
            createForm.value.fields[tag.name] = JSON.stringify({ columns: ['Column 1', 'Column 2'], rows: [['', '']] })
          } else if (tag.fieldHandler !== '') {
            createForm.value.fields[tag.name] = ''
          }
          // fieldHandler === '' ("None"): no input in the editor, nothing to seed —
          // always falls through to the container's own default_content.
        })
      } else {
        tagConfigs.value.forEach(tag => {
          if (!(tag.name in createForm.value.fields)) {
            if (tag.fieldHandler === 'numbers') {
              createForm.value.fields[tag.name] = 0
            } else if (tag.fieldHandler === 'checkbox') {
              createForm.value.fields[tag.name] = false
            } else if (tag.fieldHandler === 'pretalx_table') {
              setPretalxTableValue(tag.name, blankPretalxTableValue())
            } else if (tag.fieldHandler === 'arrows') {
              createForm.value.fields[tag.name] = ''
              if (!(tag.name + '_size' in createForm.value.fields)) {
                createForm.value.fields[tag.name + '_size'] = 5
              }
            } else if (tag.fieldHandler === 'icon') {
              createForm.value.fields[tag.name] = ''
              if (!(tag.name + '__size' in createForm.value.fields)) {
                createForm.value.fields[tag.name + '__size'] = 5
              }
            } else if (tag.fieldHandler === 'datetime_format') {
              createForm.value.fields[tag.name] = 'HH:mm:ss'
            } else if (tag.fieldHandler === 'table') {
              createForm.value.fields[tag.name] = JSON.stringify({ columns: ['Column 1', 'Column 2'], rows: [['', '']] })
            } else if (tag.fieldHandler !== '') {
              createForm.value.fields[tag.name] = ''
            }
          }
        })

        if (pendingContentDetail.value) {
          const pending = pendingContentDetail.value
          tagConfigs.value.forEach(tag => {
            const v = pending[tag.name]
            if (v !== undefined && v !== null) {
              createForm.value.fields[tag.name] = v
            }
          })
          // Sub-fields of a pretalx_table field (`${name}__type`, `${name}__roomname`,
          // etc.) aren't their own tagConfigs entry — copy any of those over too.
          const pendingIgnore = new Set(['id', 'title', 'active', 'duration', 'start_time', 'end_time', 'contentcontainer', 'contenttypeName', 'screengroups', 'contenttype_id', '_field_metadata'])
          for (const k of Object.keys(pending)) {
            if (!pendingIgnore.has(k) && !tagConfigs.value.some(t => t.name === k)) {
              createForm.value.fields[k] = pending[k]
            }
          }
          // start_time / end_time are not tag fields — apply them explicitly
          createForm.value.start_time = parseIsoDate(pending.start_time)
          createForm.value.end_time = parseIsoDate(pending.end_time)
          pendingContentDetail.value = null
          contentDetailReceived.value = true
        }
      }
    } else {
      extractTagConfigs((data.contenttype as any).html || '')
    }
    showCreateContentDialog.value = true
    if (!editMode.value || contentDetailReceived.value) {
      nextTick(() => {
        editorReady.value = true
      })
    }
  }
}

/**
 * Handles the response to get_content_element_detail — the entry point for
 * both edit and copy mode (initFromRoute only knows an id; everything else,
 * including which Contenttype this element uses, comes from here). Captures
 * the metadata fields directly, then defers the custom field values to
 * handleContentTypeDetail's pendingContentDetail merge once get_contenttype
 * (fired from here) resolves the field list.
 */
const handleContentDetail = (data: { content: any }) => {
  if (!data.content || !editMode.value) return
  const content = data.content

  createForm.value.id = pendingIsCopy.value ? null : content.id
  createForm.value.title = pendingIsCopy.value ? `Copy of ${content.title}` : content.title
  createForm.value.duration = content.duration
  createForm.value.contenttype_id = content.contenttype_id

  const sgIds = (content.screengroups || []).map((sg: any) => sg.id)
  formScreengroupIds.value = [...sgIds]
  originalScreengroupIds.value = [...sgIds]

  createForm.value.start_time = parseIsoDate(content.start_time)
  createForm.value.end_time = parseIsoDate(content.end_time)

  selectedContentType.value = contentTypes.value.find(ct => ct.id === content.contenttype_id) || null

  const hasRandomTags = Object.keys(content).some(
    (k) => k.endsWith('__image_mode') && content[k] === 'random_tags'
  )
  if (hasRandomTags && availableImageTags.value.length === 0) {
    socketEmit('displayhive:admin:cts:get_image_tags')
  }

  pendingContentDetail.value = content
  contentDetailReceived.value = false

  if (!content.contenttype_id) {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Content type not found', life: 3000 })
    return
  }
  socketEmit('displayhive:admin:cts:get_contenttype', { contenttype_id: content.contenttype_id })
}

const handleCreateResult = (data: { success: boolean; content_element_id?: number; error?: string }) => {
  // Snapshot before any state mutation — the user may have cancelled the dialog
  // between submit and this callback, which would clear formScreengroupIds.
  const screenGroupIds = [...formScreengroupIds.value]
  const wasCreate = pendingIsCreate.value
  if (data.success) {
    if (wasCreate && data.content_element_id && screenGroupIds.length > 0) {
      screenGroupIds.forEach(sgId =>
        socketEmit('displayhive:admin:cts:add_content_to_screengroup', { screengroup_id: sgId, content_id: data.content_element_id })
      )
    }
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: wasCreate ? 'Content created successfully' : 'Content updated successfully',
      life: 3000
    })
    if (!pendingKeepOpen.value) {
      // ContentView.vue's own onMounted refetch covers what a `saved` emit
      // used to trigger in the parent when this was a modal it controlled.
      goBack()
    }
    pendingKeepOpen.value = false
  } else {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: data.error || (wasCreate ? 'Failed to create content' : 'Failed to update content'),
      life: 5000
    })
  }
}

const handleMediaForPicker = (data: { media: MediaItem[] }) => {
  pickerMediaItems.value = data.media || []
  pickerLoading.value = false
}

const handleImageTags = (data: { tags: string[] }) => {
  availableImageTags.value = data.tags || []
}

onMounted(() => {
  on('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
  on('displayhive:admin:stc:content_element_detail', handleContentDetail)
  on('displayhive:admin:stc:create_content_element_result', handleCreateResult)
  on('displayhive:admin:stc:media_for_picker', handleMediaForPicker)
  on('displayhive:admin:stc:image_tags', handleImageTags)
  on('displayhive:admin:stc:admin_settings', handleAdminSettingsForPreview)
  on('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
  on('displayhive:admin:stc:upd_screengroups', handleAllScreengroups)
  on('displayhive:admin:stc:content_element_preview', handleContentPreview)
  socketEmit('displayhive:admin:cts:get_admin_settings')
  socketEmit('displayhive:admin:cts:get_contenttypes')
  socketEmit('displayhive:admin:cts:get_screengroups')
  screensStore.fetch()
  previewInterval = setInterval(() => { previewNow.value = new Date() }, 1000)
})

onUnmounted(() => {
  off('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
  off('displayhive:admin:stc:content_element_detail', handleContentDetail)
  off('displayhive:admin:stc:create_content_element_result', handleCreateResult)
  off('displayhive:admin:stc:media_for_picker', handleMediaForPicker)
  off('displayhive:admin:stc:image_tags', handleImageTags)
  off('displayhive:admin:stc:admin_settings', handleAdminSettingsForPreview)
  off('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
  off('displayhive:admin:stc:upd_screengroups', handleAllScreengroups)
  off('displayhive:admin:stc:content_element_preview', handleContentPreview)
  if (previewInterval) clearInterval(previewInterval)
  if (previewTimer) clearTimeout(previewTimer)
})

// Re-run route-driven init both on first mount and whenever the route
// changes without unmounting this component (e.g. navigating directly
// between two edit URLs) — placed after every function/ref it uses is
// already defined, since {immediate: true} runs synchronously right here.
watch(() => route.fullPath, initFromRoute, { immediate: true })
</script>

<template>
  <!-- Step 1: Select Content Type -->
  <Dialog
    v-model:visible="showSelectContentTypeDialog"
    header="Select Content Type"
    modal
    :style="{ width: '600px' }"
  >
    <div class="contenttype-list">
      <Card
        v-for="ct in contentTypes"
        :key="ct.id"
        class="contenttype-card"
        @click="selectContentType(ct)"
      >
        <template #title>{{ ct.name }}</template>
        <template #content>
          <p v-if="ct.description" class="text-muted">{{ ct.description }}</p>
        </template>
      </Card>
      <div v-if="contentTypes.length === 0" class="empty-state">
        <i class="pi pi-inbox"></i>
        <p>No content types available</p>
      </div>
    </div>
    <template #footer>
      <Button label="Cancel" @click="goBack" text />
    </template>
  </Dialog>

  <div class="content-edit-page">
    <div class="content-edit-page-header">
      <h2>{{ editMode ? (createForm.id ? 'Edit Content' : 'Copy Content') : 'Create Content' }}</h2>
      <Button label="Back to Content" icon="pi pi-arrow-left" text @click="goBack" />
    </div>

    <div v-if="loadingContentTypeDetail" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
      <p>Loading content type...</p>
    </div>
    <div v-else class="content-edit-columns">
    <div class="content-edit-form">
    <div class="dialog-content">
      <div v-if="affectsMultipleScreens" class="multi-screen-warning">
        <i class="pi pi-exclamation-triangle"></i>
        <div>
          <p>
            This content element is shown on multiple screens via direct assignment or a group.
            If you edit it you will affect the following screens:
          </p>
          <div class="multi-screen-warning-list">
            <Tag v-for="name in affectedScreenNames" :key="name" :value="name" severity="warn" />
          </div>
        </div>
      </div>

      <div class="field">
        <label for="create-title">Title *</label>
        <InputText id="create-title" v-model="createForm.title" class="w-full" />
      </div>

      <div class="field">
        <label>Duration</label>
        <div class="flex align-items-center gap-2">
          <InputNumber v-model="durationMinutes" :min="0" :max="99" placeholder="0" />
          <span class="duration-unit-label">minutes</span>
          <InputNumber v-model="durationSeconds" :min="0" :max="59" :use-grouping="false" placeholder="00" />
          <span class="duration-unit-label">seconds</span>
        </div>
      </div>

      <div v-if="tagConfigs.length > 0" class="tag-fields-section">
        <h4>Content Fields</h4>
        <div v-for="tag in tagConfigs" v-show="tag.fieldHandler !== ''" :key="tag.name" class="field">
          <label :for="`field-${tag.name}`">{{ tag.title || tag.name }}</label>
          <small v-if="tag.description" class="field-description">{{ tag.description }}</small>

          <PretalxTableFieldEditor
            v-if="tag.fieldHandler === 'pretalx_table'"
            :model-value="getPretalxTableValue(tag.name)"
            @update:model-value="(v) => setPretalxTableValue(tag.name, v)"
          />

          <IconPickerField
            v-else-if="tag.fieldHandler === 'icon'"
            :model-value="getIconValue(tag.name)"
            @update:model-value="(v) => setIconValue(tag.name, v)"
          />

          <Textarea
            v-else-if="tag.fieldHandler === 'textbig'"
            :id="`field-${tag.name}`"
            :modelValue="String(getFieldValue(tag.name))"
            @update:modelValue="(v: string | undefined) => setFieldValue(tag.name, v ?? '')"
            rows="3"
            :maxlength="tag.max_length"
            class="w-full"
          />
          <InputNumber
            v-else-if="tag.fieldHandler === 'numbers'"
            :id="`field-${tag.name}`"
            :modelValue="Number(getFieldValue(tag.name))"
            @update:modelValue="(v: number | null) => setFieldValue(tag.name, v ?? 0)"
            class="w-full"
          />
          <InputText
            v-else-if="tag.fieldHandler === 'link'"
            :id="`field-${tag.name}`"
            :modelValue="String(getFieldValue(tag.name))"
            @update:modelValue="(v: string | undefined) => setFieldValue(tag.name, v ?? '')"
            type="url"
            placeholder="https://example.com"
            :maxlength="tag.max_length"
            class="w-full"
          />
          <Editor
            v-else-if="tag.fieldHandler === 'wysiwyg' && editorReady"
            :id="`field-${tag.name}`"
            :modelValue="String(createForm.fields[tag.name] || '')"
            @update:modelValue="(v: string | undefined) => setFieldValue(tag.name, v ?? '')"
            editorStyle="height: 220px"
            @load="(e: any) => onEditorLoad(tag.name, e)"
          />

          <!-- Image picker -->
          <div v-else-if="tag.fieldHandler === 'image'" class="image-field-wrapper">
            <div class="image-mode-select">
              <Select
                :modelValue="getImageMode(tag.name)"
                @update:modelValue="(v: string) => setImageMode(tag.name, v)"
                :options="imageModeOptions"
                optionLabel="label"
                optionValue="value"
                class="w-full"
              />
            </div>

            <template v-if="getImageMode(tag.name) === 'single'">
              <div v-if="getFieldValue(tag.name)" class="image-field-preview">
                <img :src="String(getFieldValue(tag.name))" class="image-field-thumb" alt="selected" />
                <div class="image-field-actions">
                  <Button icon="pi pi-pencil" size="small" label="Change" outlined @click="openImagePicker(tag.name)" />
                  <Button icon="pi pi-times" size="small" severity="danger" outlined @click="clearImageField(tag.name)" />
                </div>
              </div>
              <div v-else class="image-field-empty" @click="openImagePicker(tag.name)">
                <i class="pi pi-image" style="font-size: 2rem; color: #94a3b8" />
                <span>Click to select an image</span>
              </div>
            </template>

            <template v-else-if="getImageMode(tag.name) === 'random_tags'">
              <div class="image-tags-cloud">
                <p class="image-tags-hint">Select one or more tags — a random matching image will be shown on each display refresh.</p>
                <div v-if="availableImageTags.length === 0" class="image-tags-empty">
                  <i class="pi pi-spin pi-spinner" /> Loading tags…
                </div>
                <div v-else class="image-tags-list">
                  <button
                    v-for="tag2 in availableImageTags"
                    :key="tag2"
                    type="button"
                    :class="['image-tag-chip', getImageTags(tag.name).includes(tag2) ? 'image-tag-chip--selected' : '']"
                    @click="toggleImageTag(tag.name, tag2)"
                  >{{ tag2 }}</button>
                </div>
                <small v-if="getImageTags(tag.name).length > 0" class="image-tags-selected-summary">
                  Selected: {{ getImageTags(tag.name).join(', ') }}
                </small>
              </div>
            </template>

            <div class="image-size-row">
              <label :for="`field-${tag.name}-size`" class="image-size-label">Size (vh)</label>
              <InputNumber
                :id="`field-${tag.name}-size`"
                :modelValue="getImageSize(tag.name)"
                @update:modelValue="(v: number | null) => setImageSize(tag.name, v)"
                :min="0" :max="100" :step="0.5" :max-fraction-digits="2"
                suffix=" vh"
                placeholder="auto"
                style="width: 140px"
              />
            </div>
          </div>

          <!-- Arrow picker -->
          <div v-else-if="tag.fieldHandler === 'arrows'" class="arrow-picker-wrapper">
            <div class="arrow-grid">
              <button
                v-for="arrow in [
                  { char: '←', label: 'Left' },
                  { char: '→', label: 'Right' },
                  { char: '↑', label: 'Up' },
                  { char: '↓', label: 'Down' },
                  { char: '↖', label: 'Up-Left' },
                  { char: '↗', label: 'Up-Right' },
                  { char: '↙', label: 'Down-Left' },
                  { char: '↘', label: 'Down-Right' },
                  { char: '↔', label: 'Left-Right' },
                  { char: '↕', label: 'Up-Down' },
                  { char: '⇐', label: 'Double Left' },
                  { char: '⇒', label: 'Double Right' },
                  { char: '⇑', label: 'Double Up' },
                  { char: '⇓', label: 'Double Down' },
                  { char: '⇖', label: 'Double Up-Left' },
                  { char: '⇗', label: 'Double Up-Right' },
                  { char: '⇙', label: 'Double Down-Left' },
                  { char: '⇘', label: 'Double Down-Right' },
                  { char: '⇔', label: 'Double Left-Right' },
                  { char: '⇕', label: 'Double Up-Down' },
                ]"
                :key="arrow.char"
                type="button"
                :class="['arrow-btn', getFieldValue(tag.name) === arrow.char ? 'arrow-btn--selected' : '']"
                :title="arrow.label"
                @click="setFieldValue(tag.name, arrow.char)"
              >{{ arrow.char }}</button>
            </div>
            <div class="arrow-selected-preview" v-if="getFieldValue(tag.name)">
              Selected: <span class="arrow-preview-char">{{ getFieldValue(tag.name) }}</span>
              <Button icon="pi pi-times" size="small" text @click="setFieldValue(tag.name, '')" title="Clear" />
            </div>
            <div class="arrow-size-row">
              <label :for="`field-${tag.name}-size`" class="arrow-size-label">Größe (vh)</label>
              <InputNumber
                :id="`field-${tag.name}-size`"
                :modelValue="Number(getFieldValue(tag.name + '_size')) || 5"
                @update:modelValue="(v: number | null) => setFieldValue(tag.name + '_size', v ?? 5)"
                :min="0.1"
                :max="50"
                :step="0.1"
                suffix=" vh"
                style="width: 120px"
              />
            </div>
          </div>

          <Checkbox
            v-else-if="tag.fieldHandler === 'checkbox'"
            :inputId="`field-${tag.name}`"
            :binary="true"
            :modelValue="!!getFieldValue(tag.name)"
            @update:modelValue="(v: boolean) => setFieldValue(tag.name, v)"
          />

          <!-- Table editor -->
          <div v-else-if="tag.fieldHandler === 'table'" class="table-editor-wrapper">
            <div class="table-editor-scroll">
              <table class="table-editor-tbl">
                <thead>
                  <tr>
                    <th class="table-editor-handle-cell"></th>
                    <th
                      v-for="(col, ci) in parseTableData(tag.name).columns"
                      :key="ci"
                      class="table-editor-col-th"
                      draggable="true"
                      @dragstart="onTableDragStart(tag.name, 'col', ci, $event)"
                      @dragover.prevent
                      @drop.prevent="onTableDrop(tag.name, 'col', ci)"
                    >
                      <div class="table-editor-col-header">
                        <span class="table-editor-drag-icon pi pi-bars"></span>
                        <InputText
                          :modelValue="col"
                          @update:modelValue="(v: string | undefined) => updateTableHeader(tag.name, ci, v ?? '')"
                          size="small"
                          class="table-editor-header-input"
                          placeholder="Header"
                        />
                        <Button
                          icon="pi pi-trash"
                          size="small"
                          text
                          severity="danger"
                          :disabled="parseTableData(tag.name).columns.length <= 1"
                          @click="removeTableColumn(tag.name, ci)"
                        />
                      </div>
                    </th>
                    <th class="table-editor-add-col-cell">
                      <Button icon="pi pi-plus" size="small" text title="Add column" @click="addTableColumn(tag.name)" />
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="(row, ri) in parseTableData(tag.name).rows"
                    :key="ri"
                    draggable="true"
                    @dragstart="onTableDragStart(tag.name, 'row', ri, $event)"
                    @dragover.prevent
                    @drop.prevent="onTableDrop(tag.name, 'row', ri)"
                  >
                    <td class="table-editor-handle-cell">
                      <span class="table-editor-drag-icon pi pi-bars"></span>
                    </td>
                    <td v-for="(cell, ci) in row" :key="ci" class="table-editor-cell">
                      <InputText
                        :modelValue="cell"
                        @update:modelValue="(v: string | undefined) => updateTableCell(tag.name, ri, ci, v ?? '')"
                        size="small"
                        class="w-full"
                      />
                    </td>
                    <td class="table-editor-add-col-cell">
                      <Button
                        icon="pi pi-trash"
                        size="small"
                        text
                        severity="danger"
                        :disabled="parseTableData(tag.name).rows.length <= 1"
                        @click="removeTableRow(tag.name, ri)"
                      />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <Button label="Add Row" icon="pi pi-plus" size="small" text @click="addTableRow(tag.name)" style="margin-top:0.4rem;" />
          </div>

          <!-- Date / Time format picker -->
          <div v-else-if="tag.fieldHandler === 'datetime_format'" class="datetime-format-wrapper">
            <InputText
              :id="`field-${tag.name}`"
              :modelValue="String(getFieldValue(tag.name) || 'HH:mm:ss')"
              @update:modelValue="(v: string | undefined) => setFieldValue(tag.name, v ?? '')"
              class="w-full"
              placeholder="HH:mm:ss"
            />
            <div class="datetime-preview">
              <span class="datetime-preview-label">Preview</span>
              <span class="datetime-preview-value">{{ formatDatePreview(String(getFieldValue(tag.name) || 'HH:mm:ss')) }}</span>
              <span class="datetime-preview-tz">({{ previewTimezone }})</span>
            </div>
            <div class="datetime-tokens">
              <p class="datetime-tokens-title">Format tokens</p>
              <table class="token-table">
                <thead>
                  <tr><th>Token</th><th>Description</th><th>Example</th></tr>
                </thead>
                <tbody>
                  <tr v-for="t in FORMAT_TOKENS" :key="t.token">
                    <td><code>{{ t.token }}</code></td>
                    <td>{{ t.desc }}</td>
                    <td>{{ t.example }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <InputText
            v-else
            :id="`field-${tag.name}`"
            :modelValue="String(getFieldValue(tag.name))"
            @update:modelValue="(v: string | undefined) => setFieldValue(tag.name, v ?? '')"
            :maxlength="tag.max_length"
            class="w-full"
          />
        </div>
      </div>

      <!-- Scheduling -->
      <details class="scheduling-collapsible">
        <summary class="scheduling-summary">Scheduling <small class="text-muted">(optional — restrict when this content is shown)</small></summary>
        <div class="scheduling-fields">
          <div class="field">
            <label for="create-start-time">Start Time</label>
            <DatePicker
              id="create-start-time"
              v-model="createForm.start_time"
              showTime
              hourFormat="24"
              showClear
              dateFormat="dd.mm.yy"
              placeholder="No start restriction"
              class="w-full"
            />
          </div>
          <div class="field">
            <label for="create-end-time">End Time</label>
            <DatePicker
              id="create-end-time"
              v-model="createForm.end_time"
              showTime
              hourFormat="24"
              showClear
              dateFormat="dd.mm.yy"
              placeholder="No end restriction"
              class="w-full"
            />
          </div>
        </div>
      </details>

      <!-- Screengroup assignment -->
      <div class="screengroup-assignment-section">
        <h4>Screen Groups</h4>
        <p v-if="allScreengroups.length === 0" class="text-muted">No screen groups available.</p>
        <template v-else>
          <InputText v-model="sgSearchText" placeholder="Search screen groups…" class="screengroup-search" />
          <div class="screengroup-checkboxes">
            <div v-for="sg in pagedScreengroups" :key="sg.id" class="screengroup-checkbox-row">
              <Checkbox :inputId="`sg-${sg.id}`" :value="sg.id" v-model="formScreengroupIds" />
              <label :for="`sg-${sg.id}`" class="screengroup-checkbox-label">{{ sg.name }}</label>
            </div>
            <p v-if="filteredScreengroups.length === 0" class="text-muted">No results.</p>
          </div>
          <Paginator
            v-if="filteredScreengroups.length > SG_PAGE_SIZE"
            :rows="SG_PAGE_SIZE"
            :totalRecords="filteredScreengroups.length"
            :first="sgPage * SG_PAGE_SIZE"
            @page="(e: any) => sgPage = e.page"
            class="sg-paginator"
          />
        </template>
      </div>

      <!-- Screens assignment (is_one_screen groups only) -->
      <div class="screengroup-assignment-section" v-if="oneScreenGroups.length > 0">
        <h4>Screens</h4>
        <InputText v-model="screenSearchText" placeholder="Search screens…" class="screengroup-search" />
        <div class="screengroup-checkboxes">
          <div v-for="sg in pagedOneScreenGroups" :key="sg.id" class="screengroup-checkbox-row">
            <Checkbox :inputId="`screen-${sg.id}`" :value="sg.id" v-model="formScreengroupIds" />
            <label :for="`screen-${sg.id}`" class="screengroup-checkbox-label">{{ sg.name }}</label>
          </div>
          <p v-if="filteredOneScreenGroups.length === 0" class="text-muted">No results.</p>
        </div>
        <Paginator
          v-if="filteredOneScreenGroups.length > SG_PAGE_SIZE"
          :rows="SG_PAGE_SIZE"
          :totalRecords="filteredOneScreenGroups.length"
          :first="screenPage * SG_PAGE_SIZE"
          @page="(e: any) => screenPage = e.page"
          class="sg-paginator"
        />
      </div>
    </div>

    <div class="content-edit-form-actions">
      <Button label="Cancel" @click="goBack" text />
      <Button v-if="editMode && createForm.id" label="Update" severity="secondary" outlined @click="submitCreateContent(true)" :disabled="loadingContentTypeDetail" />
      <Button :label="editMode && createForm.id ? 'Save' : 'Create'" @click="submitCreateContent()" :disabled="loadingContentTypeDetail" />
    </div>
    </div>

    <div class="content-edit-preview">
      <h4>Preview</h4>
      <div v-if="!previewSrcdoc" class="content-edit-preview-empty">
        <i class="pi pi-eye" style="font-size: 2rem"></i>
        <p>Preview will appear here once a content type is selected.</p>
      </div>
      <iframe
        v-else
        :srcdoc="previewSrcdoc"
        sandbox="allow-scripts"
        class="content-edit-preview-iframe"
        title="Content preview"
      ></iframe>
    </div>
    </div>
  </div>

  <!-- Image Picker Dialog -->
  <Dialog
    v-model:visible="showImagePickerDialog"
    header="Select Image"
    modal
    :style="{ width: '860px', maxWidth: '95vw' }"
  >
    <div class="picker-toolbar">
      <InputText v-model="pickerSearchText" placeholder="Search images…" class="picker-search" />
      <Tag :value="`${pickerFiltered.length} images`" />
    </div>
    <div v-if="pickerLoading" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem" />
      <p>Loading media…</p>
    </div>
    <div v-else-if="pickerFiltered.length === 0" class="empty-state">
      <i class="pi pi-images" style="font-size: 3rem" />
      <p>No images found</p>
    </div>
    <div v-else class="picker-grid">
      <div
        v-for="item in pickerFiltered"
        :key="item.id"
        class="picker-item"
        :class="{ 'picker-item--selected': pickerTargetField && String(getFieldValue(pickerTargetField)) === item.url }"
        @click="selectPickerImage(item)"
      >
        <div class="picker-thumb">
          <img :src="item.preview_url || item.url" :alt="item.title" />
        </div>
        <div class="picker-label">{{ item.title || item.filename }}</div>
      </div>
    </div>
    <template #footer>
      <Button label="Cancel" text @click="showImagePickerDialog = false" />
    </template>
  </Dialog>
</template>

<style scoped>
.content-edit-page {
  padding: 1.5rem;
  max-width: 1600px;
  margin: 0 auto;
}

.content-edit-page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.content-edit-page-header h2 {
  margin: 0;
}

/* Two-column layout, mirroring LayoutCanvasEditor.vue's main+sidebar split
   (.layout-editor) — here both sides are flexible instead of one fixed. */
.content-edit-columns {
  display: flex;
  gap: 1.5rem;
  align-items: flex-start;
}

.content-edit-form {
  flex: 1;
  min-width: 0;
}

.content-edit-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.25rem;
}

.content-edit-preview {
  flex: 1;
  min-width: 0;
  position: sticky;
  top: 1rem;
}

.content-edit-preview h4 {
  margin-top: 0;
}

.content-edit-preview-iframe {
  width: 100%;
  aspect-ratio: 16 / 9;
  border: 1px solid var(--p-surface-border, #ccc);
  border-radius: 6px;
}

.content-edit-preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  aspect-ratio: 16 / 9;
  border: 1px dashed var(--p-surface-border, #ccc);
  border-radius: 6px;
  color: var(--p-text-muted-color, #6b7280);
}

.multi-screen-warning {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  background: #fef3c7;
  border: 2px solid #f59e0b;
  border-radius: 8px;
  padding: 1.25rem;
  margin-bottom: 1.25rem;
}

.multi-screen-warning > i {
  font-size: 2.5rem;
  color: #b45309;
  flex-shrink: 0;
}

.multi-screen-warning p {
  margin: 0 0 0.75rem 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: #78350f;
}

.multi-screen-warning-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.duration-unit-label {
  font-size: 0.875rem;
  color: var(--p-text-muted-color, #888);
  white-space: nowrap;
}

.contenttype-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
  max-height: 400px;
  overflow-y: auto;
}

.contenttype-card {
  cursor: pointer;
  transition: all 0.2s;
}

.contenttype-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}

.table-editor-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.table-editor-scroll {
  overflow-x: auto;
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  border-radius: 6px;
}

.table-editor-tbl {
  border-collapse: collapse;
  min-width: 100%;
}

.table-editor-tbl th,
.table-editor-tbl td {
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  padding: 4px;
  vertical-align: middle;
  white-space: nowrap;
}

.table-editor-tbl th {
  background: var(--p-surface-100, #f3f4f6);
}

.table-editor-handle-cell {
  width: 24px;
  text-align: center;
  cursor: grab;
}

.table-editor-add-col-cell {
  width: 32px;
  text-align: center;
  border: none !important;
  background: transparent !important;
}

.table-editor-col-th {
  cursor: grab;
}

.table-editor-col-header {
  display: flex;
  align-items: center;
  gap: 4px;
}

.table-editor-header-input {
  flex: 1;
  min-width: 80px;
}

.table-editor-drag-icon {
  color: var(--p-text-muted-color, #9ca3af);
  font-size: 0.75rem;
  cursor: grab;
}

.table-editor-cell {
  min-width: 100px;
}

.tag-fields-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #ddd;
}

.tag-fields-section h4 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
}

.field-description {
  color: #666;
  font-size: 0.75rem;
  margin-top: -0.25rem;
}

.scheduling-collapsible {
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  border-radius: 6px;
  margin-bottom: 1rem;
}

.scheduling-summary {
  padding: 0.6rem 0.75rem;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  list-style: none;
  user-select: none;
}

.scheduling-summary::-webkit-details-marker { display: none; }

.scheduling-summary::before {
  content: '▶';
  display: inline-block;
  margin-right: 0.5rem;
  font-size: 0.7rem;
  transition: transform 0.2s;
}

details[open] .scheduling-summary::before {
  transform: rotate(90deg);
}

.scheduling-fields {
  padding: 0.75rem;
  border-top: 1px solid var(--p-inputtext-border-color, #d1d5db);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.scheduling-fields .field {
  margin: 0;
}

.screengroup-assignment-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid #ddd;
}

.screengroup-assignment-section h4 {
  margin: 0 0 0.75rem 0;
  font-size: 1rem;
}

.screengroup-search {
  width: 100%;
  margin-bottom: 0.5rem;
}

.screengroup-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.screengroup-checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.screengroup-checkbox-label {
  cursor: pointer;
  font-size: 0.9rem;
}

/* Image field */
.image-field-wrapper {
  width: 100%;
}

.image-mode-select {
  margin-bottom: 0.75rem;
}

.image-field-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border: 2px dashed #cbd5e1;
  border-radius: 8px;
  padding: 1.5rem;
  cursor: pointer;
  color: #94a3b8;
  font-size: 0.875rem;
  transition: border-color 0.2s, background 0.2s;
}

.image-field-empty:hover {
  border-color: var(--p-primary-color, #3b82f6);
  background: rgba(59, 130, 246, 0.04);
}

.image-field-preview {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.image-field-thumb {
  width: 80px;
  height: 60px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.image-field-actions {
  display: flex;
  gap: 0.4rem;
}

.image-tags-cloud {
  border: 1px solid var(--p-surface-200, #e2e8f0);
  border-radius: 8px;
  padding: 0.75rem;
  background: var(--p-surface-50, #f8fafc);
}

.image-tags-hint {
  font-size: 0.8rem;
  color: #64748b;
  margin: 0 0 0.6rem;
}

.image-tags-empty {
  color: #94a3b8;
  font-size: 0.85rem;
}

.image-tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}

.image-tag-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  border: 1px solid var(--p-surface-300, #cbd5e1);
  background: white;
  font-size: 0.8rem;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.image-tag-chip:hover {
  border-color: var(--p-primary-color, #3b82f6);
  background: var(--p-primary-50, #eff6ff);
}

.image-tag-chip--selected {
  background: var(--p-primary-color, #3b82f6);
  border-color: var(--p-primary-color, #3b82f6);
  color: white;
}

.image-tag-chip--selected:hover {
  background: var(--p-primary-600, #2563eb);
}

.image-tags-selected-summary {
  font-size: 0.78rem;
  color: #475569;
  display: block;
  margin-top: 0.25rem;
}

/* Arrow picker */
.arrow-picker-wrapper {
  width: 100%;
}

.arrow-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.5rem;
  background: var(--p-surface-50, #f8fafc);
  border: 1px solid var(--p-surface-200, #e2e8f0);
  border-radius: 8px;
}

.arrow-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.4rem;
  height: 2.4rem;
  font-size: 1.4rem;
  border: 1px solid var(--p-surface-300, #cbd5e1);
  border-radius: 6px;
  background: white;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  line-height: 1;
}

.arrow-btn:hover {
  background: var(--p-primary-50, #eff6ff);
  border-color: var(--p-primary-color, #3b82f6);
}

.arrow-btn--selected {
  background: var(--p-primary-color, #3b82f6);
  border-color: var(--p-primary-color, #3b82f6);
  color: white;
}

.arrow-selected-preview {
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
}

.arrow-preview-char {
  font-size: 2rem;
  line-height: 1;
}

.arrow-size-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.6rem;
}

.arrow-size-label {
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
  white-space: nowrap;
}

.image-size-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.6rem;
}

.image-size-label {
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
  white-space: nowrap;
}

/* Image picker dialog */
.picker-toolbar {
  display: flex;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1rem;
}

.picker-search {
  flex: 1;
  max-width: 320px;
}

.picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.75rem;
  max-height: 460px;
  overflow-y: auto;
  padding: 0.25rem;
}

.picker-item {
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.picker-item:hover {
  border-color: var(--p-primary-color, #3b82f6);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
}

.picker-item--selected {
  border-color: var(--p-primary-color, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
}

.picker-thumb {
  width: 100%;
  height: 90px;
  background: #f1f5f9;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.picker-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.picker-label {
  padding: 0.3rem 0.4rem;
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: white;
}

.datetime-format-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.datetime-preview {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.45rem 0.75rem;
  background: var(--p-surface-100, #f3f4f6);
  border-radius: 6px;
  font-family: monospace;
}

.datetime-preview-label {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--p-text-muted-color, #6b7280);
}

.datetime-preview-value {
  font-size: 1rem;
  font-weight: 600;
}

.datetime-preview-tz {
  margin-left: auto;
  font-size: 0.7rem;
  color: var(--p-text-muted-color, #9ca3af);
}

.datetime-tokens {
  margin-top: 0.1rem;
}

.datetime-tokens-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
  margin: 0 0 0.35rem;
}

.token-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
}

.token-table th {
  text-align: left;
  padding: 0.2rem 0.5rem;
  border-bottom: 1px solid var(--p-surface-300, #d1d5db);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.token-table td {
  padding: 0.18rem 0.5rem;
  border-bottom: 1px solid var(--p-surface-200, #e5e7eb);
}

.token-table td code {
  background: var(--p-surface-200, #e5e7eb);
  padding: 0 0.3rem;
  border-radius: 3px;
  font-size: 0.74rem;
}

</style>
