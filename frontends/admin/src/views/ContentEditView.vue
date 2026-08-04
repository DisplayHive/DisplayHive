<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useScreensStore } from '../stores/screens'

import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Paginator from 'primevue/paginator'
import DatePicker from 'primevue/datepicker'
import Tag from 'primevue/tag'
import Card from 'primevue/card'
import FieldValueEditor from '../components/FieldValueEditor.vue'
import { buildDesignPreviewSrcdoc, type DesignPreviewPayload, type PreviewContainer } from '../utils/designPreview'
import type { OptionFlags } from '../utils/optionFlags'

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
  fieldHandler: string
  description?: string
  max_length?: number
  optionFlags?: OptionFlags
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

const previewSrcdoc = ref('')
watch(
  previewData,
  async (data) => {
    const srcdoc = await buildDesignPreviewSrcdoc(data?.design, data?.containers)
    // Guard against an older (slower) resolution overwriting a newer one.
    if (previewData.value === data) previewSrcdoc.value = srcdoc
  },
  { immediate: true },
)

const sgSearchText = ref('')
const screenSearchText = ref('')
const sgPage = ref(0)
const screenPage = ref(0)
const SG_PAGE_SIZE = 10

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
          optionFlags: (() => {
            try { return t.option_flags ? JSON.parse(t.option_flags) : {} } catch { return {} }
          })(),
        }
      })

      if (!editMode.value) {
        createForm.value.fields = {}
        tagConfigs.value.forEach(tag => {
          if (tag.fieldHandler === 'numbers') {
            createForm.value.fields[tag.name] = 0
          } else if (tag.fieldHandler === 'checkbox') {
            createForm.value.fields[tag.name] = false
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

    // Locked/hidden individual sub-options always show (and, when locked,
    // get edited as) their Contenttype-configured preset — merge those
    // specific keys in last so they win over whatever default/pending value
    // was just seeded above. The backend enforces this again at render time
    // regardless of what a client actually submits (see
    // render_content_fields), so this is purely for the UI to display the
    // right thing.
    tagConfigs.value.forEach(tag => {
      const flags = tag.optionFlags
      if (!flags) return
      const raw = serverTagConfigs.find((t: any) => (t.field_name || t.name) === tag.name)?.default_value
      let preset: Record<string, any> = {}
      try { preset = raw ? JSON.parse(raw) : {} } catch { preset = {} }
      for (const [key, flag] of Object.entries(flags)) {
        if ((flag.locked || flag.hidden) && key in preset) {
          createForm.value.fields[key] = preset[key]
        }
      }
    })

    showCreateContentDialog.value = true
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

onMounted(() => {
  on('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
  on('displayhive:admin:stc:content_element_detail', handleContentDetail)
  on('displayhive:admin:stc:create_content_element_result', handleCreateResult)
  on('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
  on('displayhive:admin:stc:upd_screengroups', handleAllScreengroups)
  on('displayhive:admin:stc:content_element_preview', handleContentPreview)
  socketEmit('displayhive:admin:cts:get_contenttypes')
  socketEmit('displayhive:admin:cts:get_screengroups')
  screensStore.fetch()
})

onUnmounted(() => {
  off('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
  off('displayhive:admin:stc:content_element_detail', handleContentDetail)
  off('displayhive:admin:stc:create_content_element_result', handleCreateResult)
  off('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
  off('displayhive:admin:stc:upd_screengroups', handleAllScreengroups)
  off('displayhive:admin:stc:content_element_preview', handleContentPreview)
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
        <div
          v-for="tag in tagConfigs"
          v-show="tag.fieldHandler !== ''"
          :key="tag.name"
          class="field"
        >
          <label :for="`field-${tag.name}`">{{ tag.title || tag.name }}</label>
          <small v-if="tag.description" class="field-description">{{ tag.description }}</small>
          <FieldValueEditor :tag="tag" :fields="createForm.fields" mode="edit" :option-flags="tag.optionFlags" />
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
  top: calc(1rem + 200px);
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

</style>
