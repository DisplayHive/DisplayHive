import { computed, inject, onMounted, onUnmounted, provide, reactive, ref, watch, type InjectionKey } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useSocket } from '../useSocket'
import { useScreengroupAssignment } from './useScreengroupAssignment'
import { useContentPreview } from './useContentPreview'
import { seedField, seedMissingField, type FieldValue } from '../../utils/contentFieldDefaults'
import type { OptionFlags } from '../../utils/optionFlags'

export interface ContentType {
  id: number
  name: string
  description?: string
  html?: string
  tagconfigs?: RawTagConfig[]
}

export interface TagConfig {
  name: string
  title?: string
  fieldHandler: string
  description?: string
  max_length?: number
  optionFlags?: OptionFlags
}

// Raw TagConfig as the backend sends it (snake_case, JSON-encoded
// option_flags/default_value) — mapped into the camelCase `TagConfig` above.
interface RawTagConfig {
  field_handler?: string
  field_name?: string
  name?: string
  field_label?: string
  title?: string
  description?: string
  max_length?: number
  option_flags?: string
  default_value?: string
}

// Raw content-element payload from get_content_element_detail: the known
// metadata fields plus arbitrary per-tag field values (indexed dynamically
// by tag name, see the merge loop in handleContentTypeDetail below).
interface RawContentDetail {
  id: number
  title: string
  duration: number
  contenttype_id: number
  screengroups?: Array<{ id: number }>
  start_time?: string | null
  end_time?: string | null
  [key: string]: unknown
}

// Text-like field handlers whose value is reasonable material for an auto-generated title
// (rendered as InputText/Textarea/rich-text — the handlers rendered by other widgets, e.g.
// numbers/checkbox/image/table, wouldn't produce sensible title text).
const TEXT_FIELD_HANDLERS = new Set(['textklein', 'textbig', 'wysiwyg'])

const parseIsoDate = (v: string | null | undefined): Date | null => {
  if (!v) return null
  const d = new Date(v)
  return isNaN(d.getTime()) ? null : d
}

const formatDateDisplay = (d: Date | null): string => {
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d!.getDate())}.${pad(d!.getMonth() + 1)}.${d!.getFullYear()} ${pad(d!.getHours())}:${pad(d!.getMinutes())}`
}

const fmtDt = (d: Date | null | undefined): string | null => {
  if (!d) return null
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/**
 * The content edit page (/content/new, /content/:id/edit, /content/:id/copy): what is being
 * edited (decided by the URL), the form with the content type's fields, saving, and — through
 * the two helpers it builds on — the screen assignment and the live preview.
 *
 * The URL is the source of truth: initFromRoute() runs on mount and whenever the route changes
 * (Vue Router reuses the component if only the params differ).
 */
function createContentEditor() {
  const router = useRouter()
  const route = useRoute()
  const toast = useToast()
  const confirm = useConfirm()
  const { on, off, emit } = useSocket()

  const goBack = () => router.push({ name: 'content' })

  // A routed page only gets an id from the URL, so it fetches everything it needs itself.
  const contentTypes = ref<ContentType[]>([])

  const showSelectContentTypeDialog = ref(false)
  const editMode = ref(false)
  const pendingIsCreate = ref(false)
  const pendingKeepOpen = ref(false)
  const loadingContentTypeDetail = ref(false)
  const selectedContentType = ref<ContentType | null>(null)
  const pendingContentDetail = ref<RawContentDetail | null>(null)
  // Whether the currently-loading content element should be saved as a new copy (id nulled, title
  // prefixed) once its detail arrives — set by initFromRoute for the 'content-copy' route,
  // consumed in handleContentDetail.
  const pendingIsCopy = ref(false)

  const createForm = ref({
    id: null as number | null,
    title: '',
    duration: 10,
    start_time: null as Date | null,
    end_time: null as Date | null,
    contenttype_id: null as number | null,
    fields: {} as Record<string, FieldValue>,
  })
  const tagConfigs = ref<TagConfig[]>([])
  // Per-tag "does its FieldValueEditor actually render an editable control" flag, reported by
  // FieldValueEditor's `update:hasVisibleControl` — a field whose only control(s) are all hidden
  // via the per-field "hide" option flag renders nothing, so its label/description row is hidden
  // too rather than showing a bare headline over empty space. Defaults to visible so a field
  // isn't hidden before its FieldValueEditor has reported in.
  const tagHasVisibleControl = reactive<Record<string, boolean>>({})

  const assignment = useScreengroupAssignment(editMode)
  const preview = useContentPreview(createForm)

  // --- Title: filled from the first text field until the person types one themselves ---
  // Compared against the last value *we* wrote (rather than a boolean flag reset right after the
  // assignment) because watch() callbacks are batched — a flag reset synchronously would already
  // be back to `false` by the time the title-watcher actually runs, misreading our own auto-fill
  // as a manual edit after just one character.
  const titleManuallyEdited = ref(false)
  let lastAutoTitle: string | null = null
  watch(() => createForm.value.title, (val) => {
    if (val === lastAutoTitle) return
    titleManuallyEdited.value = true
  })
  watch(
    () => createForm.value.fields,
    (fields) => {
      if (titleManuallyEdited.value || createForm.value.title.trim()) return
      const source = tagConfigs.value.find(
        (t) => TEXT_FIELD_HANDLERS.has(t.fieldHandler) && String(fields[t.name] ?? '').trim(),
      )
      if (!source) return
      lastAutoTitle = String(fields[source.name]).trim().slice(0, 255)
      createForm.value.title = lastAutoTitle
    },
    { deep: true },
  )

  // --- Duration / scheduling, and the summaries shown while their sections are collapsed ---
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

  const schedulingSummary = computed(() => {
    const { start_time: start, end_time: end } = createForm.value
    if (!start && !end) return 'no restriction'
    if (start && end) return `${formatDateDisplay(start)} → ${formatDateDisplay(end)}`
    if (start) return `from ${formatDateDisplay(start)}`
    return `until ${formatDateDisplay(end)}`
  })

  const durationSummary = computed(() => {
    const m = durationMinutes.value
    const s = durationSeconds.value
    if (m === 0) return `${s}s`
    if (s === 0) return `${m}m`
    return `${m}m ${s}s`
  })

  // --- Loading what the URL names ---------------------------------------------------------
  const resetCreateForm = () => {
    createForm.value = { id: null, title: '', duration: 10, start_time: null, end_time: null, contenttype_id: null, fields: {} }
    tagConfigs.value = []
    selectedContentType.value = null
    editMode.value = false
    pendingContentDetail.value = null
    assignment.reset()
    showSelectContentTypeDialog.value = false
    preview.reset()
    titleManuallyEdited.value = false
    lastAutoTitle = null
  }

  const selectContentType = (ct: ContentType) => {
    createForm.value.contenttype_id = ct.id
    showSelectContentTypeDialog.value = false
    loadingContentTypeDetail.value = true
    emit('displayhive:admin:cts:get_contenttype', { contenttype_id: ct.id })
  }

  const handleContentTypesList = (data: { data?: ContentType[]; contenttypes?: ContentType[] }) => {
    contentTypes.value = data.data || data.contenttypes || []
    // /content/new?contenttype_id=… : the list is only fetched after this page is set up, so the
    // type named in the URL can only be picked once it has arrived.
    if (route.name === 'content-new' && !createForm.value.contenttype_id) {
      const wanted = route.query.contenttype_id ? Number(route.query.contenttype_id) : null
      const preselected = wanted ? contentTypes.value.find((ct) => ct.id === wanted) : null
      if (preselected) selectContentType(preselected)
    }
  }

  const initFromRoute = () => {
    resetCreateForm()

    if (route.name === 'content-new') {
      editMode.value = false
      pendingIsCopy.value = false

      const screengroupId = route.query.screengroup_id ? Number(route.query.screengroup_id) : null
      if (screengroupId) assignment.assign([screengroupId])

      const contenttypeId = route.query.contenttype_id ? Number(route.query.contenttype_id) : null
      const preselected = contenttypeId ? contentTypes.value.find((ct) => ct.id === contenttypeId) : null
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
    emit('displayhive:admin:cts:get_content_element_detail', { content_element_id: id })
  }

  // Legacy content types without TagConfig rows: fields are the {{ tags }} of their HTML.
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
    tagConfigs.value.forEach((tag) => seedField(createForm.value.fields, tag.fieldHandler, tag.name))
  }

  const handleContentTypeDetail = (data: { contenttype: ContentType }) => {
    loadingContentTypeDetail.value = false
    if (!data.contenttype) return
    selectedContentType.value = data.contenttype
    // Fields (TagConfig) belong to the Contenttype itself — each one maps directly to one of
    // its Layout's containers.
    const serverTagConfigs: RawTagConfig[] = data.contenttype.tagconfigs || []
    if (serverTagConfigs && serverTagConfigs.length > 0) {
      tagConfigs.value = serverTagConfigs.map((t) => {
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
        tagConfigs.value.forEach((tag) => seedField(createForm.value.fields, tag.fieldHandler, tag.name))
      } else {
        tagConfigs.value.forEach((tag) => seedMissingField(createForm.value.fields, tag.fieldHandler, tag.name))

        if (pendingContentDetail.value) {
          const pending = pendingContentDetail.value
          tagConfigs.value.forEach((tag) => {
            const v = pending[tag.name]
            if (v !== undefined && v !== null) {
              createForm.value.fields[tag.name] = v as FieldValue
            }
          })
          // Sub-fields of a pretalx_table field (`${name}__type`, `${name}__roomname`, etc.)
          // aren't their own tagConfigs entry — copy any of those over too.
          const pendingIgnore = new Set(['id', 'title', 'active', 'duration', 'start_time', 'end_time', 'contentcontainer', 'contenttypeName', 'screengroups', 'contenttype_id', '_field_metadata'])
          for (const k of Object.keys(pending)) {
            if (!pendingIgnore.has(k) && !tagConfigs.value.some((t) => t.name === k)) {
              createForm.value.fields[k] = pending[k] as FieldValue
            }
          }
          // start_time / end_time are not tag fields — apply them explicitly
          createForm.value.start_time = parseIsoDate(pending.start_time)
          createForm.value.end_time = parseIsoDate(pending.end_time)
          pendingContentDetail.value = null
        }
      }
    } else {
      extractTagConfigs(data.contenttype.html || '')
    }

    // Locked/hidden individual sub-options always show (and, when locked, get edited as) their
    // Contenttype-configured preset — merge those specific keys in last so they win over
    // whatever default/pending value was just seeded above. The backend enforces this again at
    // render time regardless of what a client actually submits (see render_content_fields), so
    // this is purely for the UI to display the right thing.
    tagConfigs.value.forEach((tag) => {
      const flags = tag.optionFlags
      if (!flags) return
      const raw = serverTagConfigs.find((t) => (t.field_name || t.name) === tag.name)?.default_value
      let preset: Record<string, unknown> = {}
      try { preset = raw ? JSON.parse(raw) : {} } catch { preset = {} }
      for (const [key, flag] of Object.entries(flags)) {
        if ((flag.locked || flag.hidden) && key in preset) {
          createForm.value.fields[key] = preset[key] as FieldValue
        }
      }
    })
  }

  // The response to get_content_element_detail — the entry point for both edit and copy mode
  // (initFromRoute only knows an id; everything else, including which Contenttype this element
  // uses, comes from here). Captures the metadata fields directly, then defers the custom field
  // values to handleContentTypeDetail's pendingContentDetail merge once get_contenttype (fired
  // from here) resolves the field list.
  const handleContentDetail = (data: { content: RawContentDetail }) => {
    if (!data.content || !editMode.value) return
    const content = data.content

    createForm.value.id = pendingIsCopy.value ? null : content.id
    createForm.value.title = pendingIsCopy.value ? `Copy of ${content.title}` : content.title
    createForm.value.duration = content.duration
    createForm.value.contenttype_id = content.contenttype_id

    assignment.assign((content.screengroups || []).map((sg) => sg.id))

    createForm.value.start_time = parseIsoDate(content.start_time)
    createForm.value.end_time = parseIsoDate(content.end_time)

    selectedContentType.value = contentTypes.value.find((ct) => ct.id === content.contenttype_id) || null

    pendingContentDetail.value = content

    if (!content.contenttype_id) {
      toast.add({ severity: 'error', summary: 'Error', detail: 'Content type not found', life: 3000 })
      return
    }
    emit('displayhive:admin:cts:get_contenttype', { contenttype_id: content.contenttype_id })
  }

  // --- Saving ----------------------------------------------------------------------------
  const submitCreateContent = (keepOpen = false) => {
    pendingKeepOpen.value = keepOpen
    if (!createForm.value.title.trim()) {
      toast.add({ severity: 'warn', summary: 'Validation', detail: 'Title is required', life: 3000 })
      return
    }

    if (assignment.affectsMultipleScreens.value) {
      confirm.require({
        message: `This change affects ${assignment.affectedScreenNames.value.length} screens. Proceed?`,
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
    if (
      createForm.value.start_time &&
      createForm.value.end_time &&
      createForm.value.end_time <= createForm.value.start_time
    ) {
      createForm.value.end_time = null
    }

    const payload: Record<string, unknown> = {
      title: createForm.value.title,
      duration: createForm.value.duration,
      start_time: fmtDt(createForm.value.start_time),
      end_time: fmtDt(createForm.value.end_time),
      contenttype_id: createForm.value.contenttype_id,
      ...createForm.value.fields,
    }

    if (editMode.value && createForm.value.id) {
      payload.id = createForm.value.id
    }

    pendingIsCreate.value = !(editMode.value && createForm.value.id)
    emit('displayhive:admin:cts:create_content_element', payload)

    if (editMode.value && createForm.value.id) {
      const contentId = createForm.value.id
      const added = assignment.formScreengroupIds.value.filter((id) => !assignment.originalScreengroupIds.value.includes(id))
      const removed = assignment.originalScreengroupIds.value.filter((id) => !assignment.formScreengroupIds.value.includes(id))
      added.forEach((sgId) => emit('displayhive:admin:cts:add_content_to_screengroup', { screengroup_id: sgId, content_id: contentId }))
      removed.forEach((sgId) => emit('displayhive:admin:cts:remove_content_from_screengroup', { screengroup_id: sgId, content_id: contentId }))
      assignment.originalScreengroupIds.value = [...assignment.formScreengroupIds.value]
    }
  }

  const handleCreateResult = (data: { success: boolean; content_element_id?: number; error?: string }) => {
    // Snapshot before any state mutation — the user may have cancelled the page between submit
    // and this callback, which would clear formScreengroupIds.
    const screenGroupIds = [...assignment.formScreengroupIds.value]
    const wasCreate = pendingIsCreate.value
    if (data.success) {
      if (wasCreate && data.content_element_id && screenGroupIds.length > 0) {
        screenGroupIds.forEach((sgId) =>
          emit('displayhive:admin:cts:add_content_to_screengroup', { screengroup_id: sgId, content_id: data.content_element_id }),
        )
      }
      toast.add({
        severity: 'success',
        summary: 'Success',
        detail: wasCreate ? 'Content created successfully' : 'Content updated successfully',
        life: 3000,
      })
      if (!pendingKeepOpen.value) {
        // ContentView.vue's own onMounted refetch covers what the list needs after a save.
        goBack()
      }
      pendingKeepOpen.value = false
    } else {
      toast.add({
        severity: 'error',
        summary: 'Error',
        detail: data.error || (wasCreate ? 'Failed to create content' : 'Failed to update content'),
        life: 5000,
      })
    }
  }

  onMounted(() => {
    on('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
    on('displayhive:admin:stc:content_element_detail', handleContentDetail)
    on('displayhive:admin:stc:create_content_element_result', handleCreateResult)
    on('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
    emit('displayhive:admin:cts:get_contenttypes')
  })

  onUnmounted(() => {
    off('displayhive:admin:stc:contenttype_detail', handleContentTypeDetail)
    off('displayhive:admin:stc:content_element_detail', handleContentDetail)
    off('displayhive:admin:stc:create_content_element_result', handleCreateResult)
    off('displayhive:admin:stc:upd_contenttypes', handleContentTypesList)
  })

  // Re-run route-driven init both on first mount and whenever the route changes without
  // unmounting this component (e.g. navigating directly between two edit URLs) — placed after
  // everything it uses is defined, since {immediate: true} runs synchronously right here.
  watch(() => route.fullPath, initFromRoute, { immediate: true })

  return reactive({
    goBack, contentTypes, showSelectContentTypeDialog, selectContentType,
    editMode, loadingContentTypeDetail, selectedContentType,
    createForm, tagConfigs, tagHasVisibleControl,
    durationMinutes, durationSeconds, schedulingSummary, durationSummary,
    submitCreateContent,
    ...assignment,
    ...preview,
  })
}

export type ContentEditor = ReturnType<typeof createContentEditor>

const KEY: InjectionKey<ContentEditor> = Symbol('contentEditor')

/** Called once by the content edit page; its parts inject it. */
export function provideContentEditor(): ContentEditor {
  const editor = createContentEditor()
  provide(KEY, editor)
  return editor
}

export function useContentEditor(): ContentEditor {
  const editor = inject(KEY)
  if (!editor) throw new Error('useContentEditor() needs provideContentEditor() in a parent component')
  return editor
}
