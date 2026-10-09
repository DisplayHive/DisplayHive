import { computed, reactive, ref, watch } from 'vue'
import { useAspectRatios, BASE_ASPECT_RATIO } from '../useAspectRatios'
import type { Layout, ContentContainer } from '../../types/models'
import type { Pos } from '../../utils/layoutGeometry'
import { defaultContentFor } from '../../utils/containerDefaultContent'

export interface EditorProps {
  layout: Layout
  containers: ContentContainer[]
  layouts: Layout[]
}

/** The staged (unsaved) settings-card edits of one container. */
export interface ContentDraftEntry {
  name: string
  default_field_handler: string
  default_content: string
  show_when_empty: boolean
}

/**
 * The state every part of the Layout editor shares: what is selected, which aspect ratio is
 * shown, the containers placed on / available for the Layout, and the staged (unsaved) edits.
 *
 * Staging: drags, resizes and settings-card edits only land in `draft` / `contentDraft` /
 * `designDraft` (and are previewed live); nothing is sent to the server until the Layout itself
 * is saved (see useLayoutPersistence).
 */
export function useEditorCore(props: EditorProps) {
  const selectedId = ref<number | null>(null)

  // Staged (unsaved) drag/resize positions of the ACTIVE ratio, keyed by container id.
  const draft = reactive<Record<number, Pos>>({})
  // Staged settings-card edits (name, default field handler/content, show when empty).
  const contentDraft = reactive<Record<number, ContentDraftEntry>>({})
  // Staged container designs: every change lands here and is previewed live; holds the
  // container's complete property map once touched; absent = no staged change.
  const designDraft = reactive<Record<number, Record<string, string>>>({})

  // --- Aspect-ratio variations ----------------------------------------------------
  // The Layout is edited one aspect-ratio variant at a time. 16:9 is the base
  // (membership = layout.container_ids, positions = the container's own
  // top/left/width/height); every other ratio is a variation with its own
  // member containers and per-container positions. Everything else about a
  // container (name, content, design, ...) is shared across ratios. `draft`
  // always holds the staged positions of the ACTIVE ratio; those of the
  // others are parked in draftsByRatio while another ratio is shown.
  const { ratios: designRatios } = useAspectRatios()
  const activeRatio = ref(BASE_ASPECT_RATIO)
  const draftsByRatio: Record<string, Record<number, Pos>> = {}

  const layoutRatioList = computed(() => [
    BASE_ASPECT_RATIO,
    ...(props.layout.variations || []).map((v) => v.aspect_ratio),
  ])
  const idsOfLayoutAt = (layout: Layout, ratio: string): number[] =>
    ratio === BASE_ASPECT_RATIO
      ? layout.container_ids || []
      : (layout.variations || []).find((v) => v.aspect_ratio === ratio)?.container_ids || []
  const activeContainerIds = computed(() => idsOfLayoutAt(props.layout, activeRatio.value))

  /** A container's position/size at *ratio*: its own for that ratio, else the base. */
  const geometryOf = (c: ContentContainer, ratio: string = activeRatio.value): Pos => {
    const own = ratio === BASE_ASPECT_RATIO ? undefined : c.positions?.[ratio]
    return own ? { top: own.top, left: own.left, width: own.width, height: own.height }
      : { top: c.top, left: c.left, width: c.width, height: c.height }
  }

  // Parks the active ratio's staged positions in draftsByRatio (copying, since
  // `draft` itself is cleared/reused when the ratio changes).
  const stashActiveDraft = () => {
    const copy: Record<number, Pos> = {}
    for (const [id, p] of Object.entries(draft)) copy[Number(id)] = { ...p }
    if (Object.keys(copy).length) draftsByRatio[activeRatio.value] = copy
    else delete draftsByRatio[activeRatio.value]
  }
  const clearAllPositionDrafts = () => {
    for (const idStr of Object.keys(draft)) delete draft[Number(idStr)]
    for (const r of Object.keys(draftsByRatio)) delete draftsByRatio[r]
  }

  // Containers currently assigned to this Layout (at the active ratio), vs. everything else
  // (shown in the sidebar so they can be dragged in). Also drives the canvas rects.
  const placedContainers = computed(() =>
    props.containers.filter((c) => activeContainerIds.value.includes(c.id)),
  )
  const availableContainers = computed(() =>
    props.containers.filter((c) => !activeContainerIds.value.includes(c.id)),
  )
  const selectedContainer = computed(() =>
    selectedId.value != null ? props.containers.find((c) => c.id === selectedId.value) || null : null,
  )
  // The container being edited can come from the canvas (already placed) or from the sidebar
  // (not yet part of this Layout).
  const isSelectedPlaced = computed(
    () => selectedId.value != null && activeContainerIds.value.includes(selectedId.value),
  )

  // Every OTHER Layout (besides the one open here) that also uses this
  // container — since containers are shared, standalone entities, moving one
  // or deleting it affects every Layout in this list too.
  const otherLayoutsUsing = (containerId: number): Layout[] =>
    props.layouts.filter((l) => l.id !== props.layout.id && idsOfLayoutAt(l, activeRatio.value).includes(containerId))

  const canDeleteContainer = (c: ContentContainer) => !c.in_use && otherLayoutsUsing(c.id).length === 0

  const posFor = (c: ContentContainer): Pos => draft[c.id] || geometryOf(c)

  const contentFor = (c: ContentContainer): ContentDraftEntry =>
    contentDraft[c.id] || {
      name: c.name,
      default_field_handler: c.default_field_handler || '',
      default_content: c.default_content || '',
      show_when_empty: !!c.show_when_empty,
    }

  // Whether *c* has an unsaved staged move/resize.
  const hasPendingChange = (c: ContentContainer) => draft[c.id] !== undefined
  // Whether *c* has any unsaved staged edit at all (position, settings or design).
  const hasAnyPendingChange = (c: ContentContainer) =>
    draft[c.id] !== undefined || contentDraft[c.id] !== undefined || designDraft[c.id] !== undefined

  // --- The settings card's form --------------------------------------------------------
  const containerEditForm = reactive({
    id: null as number | null,
    name: '',
    top: 0, left: 0, width: 20, height: 20,
    default_field_handler: '', default_content: '',
    show_when_empty: false,
  })

  // Populates containerEditForm from *c*, resuming any already-staged position/content drafts
  // (e.g. re-selecting a container edited earlier in this session).
  const seedEditForm = (c: ContentContainer) => {
    const p = posFor(c)
    const content = contentFor(c)
    containerEditForm.id = c.id
    containerEditForm.name = content.name
    containerEditForm.top = p.top
    containerEditForm.left = p.left
    containerEditForm.width = p.width
    containerEditForm.height = p.height
    containerEditForm.default_field_handler = content.default_field_handler
    containerEditForm.default_content = content.default_content
    containerEditForm.show_when_empty = content.show_when_empty
  }

  // Re-seeds the settings card whenever the SELECTION changes (not on every
  // props.containers refresh — a server push while the form is mid-edit must
  // not clobber it).
  watch(selectedId, (id) => {
    if (id == null) {
      containerEditForm.id = null
      return
    }
    const c = props.containers.find((x) => x.id === id)
    if (c) seedEditForm(c)
  }, { immediate: true })

  // Every containerEditForm edit is staged live (into draft/contentDraft) as
  // it's made — there's no separate "Save" in the settings card; the whole
  // Layout's staged changes (this plus any drag/resize) are only sent to the
  // server when the page itself is saved. Comparing against the *last-saved*
  // container (not the current draft) on every keystroke keeps this idempotent.
  watch(containerEditForm, () => {
    const id = containerEditForm.id
    if (id == null) return
    const c = props.containers.find((x) => x.id === id)
    if (!c) return

    const contentChanged =
      containerEditForm.name !== c.name ||
      containerEditForm.default_field_handler !== (c.default_field_handler || '') ||
      containerEditForm.default_content !== (c.default_content || '') ||
      containerEditForm.show_when_empty !== !!c.show_when_empty
    if (contentChanged) {
      contentDraft[id] = {
        name: containerEditForm.name,
        default_field_handler: containerEditForm.default_field_handler,
        default_content: containerEditForm.default_content,
        show_when_empty: containerEditForm.show_when_empty,
      }
    } else {
      delete contentDraft[id]
    }

    const saved = geometryOf(c)
    const posChanged =
      containerEditForm.top !== saved.top || containerEditForm.left !== saved.left ||
      containerEditForm.width !== saved.width || containerEditForm.height !== saved.height
    if (posChanged) {
      draft[id] = {
        top: containerEditForm.top, left: containerEditForm.left,
        width: containerEditForm.width, height: containerEditForm.height,
      }
    } else {
      delete draft[id]
    }
  }, { deep: true })

  // Switching the handler in the dropdown re-seeds default_content with a sensible starting
  // shape for that type (only on an actual user change — selecting a container sets
  // containerEditForm directly, bypassing this).
  const changeDefaultHandler = (handler: string) => {
    containerEditForm.default_field_handler = handler
    containerEditForm.default_content = defaultContentFor(handler)
  }

  return {
    props,
    selectedId, draft, contentDraft, designDraft, draftsByRatio,
    designRatios, activeRatio, layoutRatioList, idsOfLayoutAt, activeContainerIds, geometryOf,
    stashActiveDraft, clearAllPositionDrafts,
    placedContainers, availableContainers, selectedContainer, isSelectedPlaced,
    otherLayoutsUsing, canDeleteContainer,
    posFor, contentFor, hasPendingChange, hasAnyPendingChange,
    containerEditForm, seedEditForm, changeDefaultHandler,
  }
}

export type EditorCore = ReturnType<typeof useEditorCore>
