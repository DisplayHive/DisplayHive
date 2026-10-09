<script setup lang="ts">
import PreviewFrame from './PreviewFrame.vue'
import { ref, computed, reactive, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useAck, type Ack } from '../composables/useAck'
import { useAspectRatios, BASE_ASPECT_RATIO, cssAspectRatio } from '../composables/useAspectRatios'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import type { Layout, ContentContainer } from '../types/models'

import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import Dropdown from 'primevue/dropdown'
import DatePicker from 'primevue/datepicker'
import Select from 'primevue/select'
import Editor from 'primevue/editor'
import ToggleSwitch from 'primevue/toggleswitch'
import Tag from 'primevue/tag'
import Card from 'primevue/card'
import MediaPickerDialog from './MediaPickerDialog.vue'
import PretalxTableFieldEditor from './PretalxTableFieldEditor.vue'
import { blankPretalxTableValue, type PretalxTableValue } from '../utils/pretalxTable'
import IconPickerField from './IconPickerField.vue'
import ContainerDesignFields from './ContainerDesignFields.vue'
import { useRightsStore } from '../stores/rights'
import { ALL_CONTAINER_STYLE_PROPERTIES } from '../utils/containerFontProperties'
import type { IconPickerValue } from '../utils/iconLibraries'
import type { DefaultColor } from '../types/models'
import { getEffectDefinition } from '../utils/backgroundEffects'
import { resolveIconPlaceholders, type PreviewContainer } from '../utils/designPreview'
// `?raw` inlines the pre-built bundle's source as a string at build time.
// It has to run *inside* the preview iframe's own document (own
// customElements registry), so it can't just be imported/evaluated in this
// page's JS realm — but it also can't be loaded via `<script src="...">`:
// module scripts always fetch with CORS semantics, and the iframe is
// `sandbox="allow-scripts"` *without* `allow-same-origin` (intentionally,
// so a Design's own arbitrary HTML/CSS can't reach this page's cookies/
// storage), which gives it an opaque `Origin: null` — the static asset
// server has no matching CORS header for that, so the browser silently
// blocks the fetch. Inlining the source as literal script *content*
// sidesteps the network fetch (and CORS) entirely.
import bbScriptSource from 'beautiful-backgrounds?raw'
// A `</script` appearing verbatim inside that source (e.g. in a minified
// string literal) would prematurely close our injected <script> tag when
// the HTML parser scans for it — inserting a backslash breaks that literal
// match for the parser while remaining valid (harmless) JS if it happens to
// land inside a string/regex in the source itself.
const bbScriptSourceSafe = bbScriptSource.replace(/<\/script/gi, '<\\/script')

// Same underlying problem as above, but for the wrapper tags this file writes
// around bbScriptSourceSafe (below). A closing script tag typed directly,
// verbatim, into this .vue file's own <script> block — even inside a JS
// template literal — confuses the SFC compiler's block locator: it scans the
// raw file text for that exact byte sequence without understanding it's
// sitting inside a string, and ends this file's own script block right
// there, corrupting everything parsed after it (see the build error this
// caused: a "Duplicate attribute" / "Element is missing end tag" deep in the
// unrelated code that follows). Concatenating the tag name keeps the closing
// sequence from ever appearing literally in this file's source while still
// producing the intended string at runtime.
const SCRIPT_OPEN_TAG = '<' + 'script type="module">'
const SCRIPT_CLOSE_TAG = '<' + '/script>'

interface MediaItem { id: number; url: string }

// Same arrow set as ContentEditView.vue's field picker.
const ARROW_OPTIONS = [
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
]

const props = defineProps<{
  layout: Layout
  containers: ContentContainer[]
  layouts: Layout[]
}>()

const { emit: socketEmit, on, off } = useSocket()
const { request } = useAck()
const confirm = useConfirm()
const toast = useToast()

const canvasEl = ref<HTMLElement | null>(null)
const selectedId = ref<number | null>(null)

// Staged (unsaved) drag/resize positions, keyed by container id — declared
// this early because rebuildDesignPreviewSrcdoc's watcher below also reads
// it live, so a container's default-content preview moves with it while
// dragging. See the "Staged position overlay" section further down for the
// full explanation and the rest of this mechanism (posFor, flush/discard, etc).
const draft = reactive<Record<number, { top: number; left: number; width: number; height: number }>>({})

// --- Aspect-ratio variations --------------------------------------------------
// The Layout is edited one aspect-ratio variant at a time. 16:9 is the base
// (membership = layout.container_ids, positions = the container's own
// top/left/width/height); every other ratio is a variation with its own
// member containers and per-container positions. Everything else about a
// container (name, content, design, ...) is shared across ratios. `draft`
// above always holds the staged positions of the ACTIVE ratio; those of the
// others are parked in draftsByRatio while another ratio is shown.
type Pos = { top: number; left: number; width: number; height: number }
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

// Staged settings-card edits (see "Staged settings" below); declared this early
// because the preview watcher reads it live.
interface ContentDraftEntry { name: string; default_field_handler: string; default_content: string; show_when_empty: boolean }
const contentDraft = reactive<Record<number, ContentDraftEntry>>({})

// Staged like position/settings edits: every change lands here and is
// previewed live on the canvas, but nothing is sent until
// flushPendingPositions() runs (the Layout's own Save). Holds the container's
// complete property map once touched; absent = no staged change.
const designDraft = reactive<Record<number, Record<string, string>>>({})

// --- Design preview: the active Design, rendered behind the canvas so
// containers can be positioned against how the screen will actually look.
// Same {name, html, css, background_effect} shape/CSS-layering as what
// upd_content pushes to real screens (see
// application/admin/designs/helper.py's build_design_payload) — rendered in
// an iframe (not injected inline) so a Design's own hand-written
// `body {...}` CSS and arbitrary HTML can't leak into or clash with this
// page's own styles.
interface DesignPreview {
  name: string
  html: string
  css: string
  background_effect: { name: string; settings: Record<string, unknown> } | null
  /** Active Design's color palette — offered as quick-pick swatches by the
   * container-default icon handler's color picker. */
  default_colors?: DefaultColor[]
}
const designPreview = ref<DesignPreview | null>(null)

// Local-only preview toggles — never persisted, purely control what this
// editor's own iframe renders (the real screen output is unaffected).
const disableAnimationsInPreview = ref(false)
const disableBackdropInPreview = ref(false)
const disableDefaultContentInPreview = ref(false)
// Hides everything on the canvas that never reaches a screen: container
// rectangles + handles, snaplines and the grid, leaving only the Design preview.
const hideHandlerElements = ref(false)

// Each placed container's own fallback content, already rendered through its
// default_field_handler server-side (see render_container_default /
// combine_layout_containers in application/admin/content/helper.py) — the
// same {top, left, width, height, html} shape the Content list/edit page
// previews use, so containers show what a real screen actually falls back to
// here instead of an approximated client-side render.
const layoutContainerPreviews = ref<Record<string, PreviewContainer>>({})

const handleLayoutDefaultContentPreview = (data: { layout_id?: number; aspect_ratio?: string; containers?: Record<string, PreviewContainer> }) => {
  if (data?.layout_id !== props.layout.id) return
  if ((data.aspect_ratio || BASE_ASPECT_RATIO) !== activeRatio.value) return
  layoutContainerPreviews.value = data.containers || {}
}

const fetchLayoutDefaultContentPreview = () => {
  if (!props.layout.id) return
  socketEmit('displayhive:admin:cts:get_layout_default_content_preview', { layout_id: props.layout.id, aspect_ratio: activeRatio.value })
}

// Attribute-value escaping for the effect's custom-element tag below — the
// settings values come from the backend (design's stored JSON), not from
// this page's own trusted template literals, so they need escaping same as
// any other data interpolated into an HTML string.
const escapeAttr = (v: string): string =>
  v.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')

// The effect canvas sits between the Backdrop (body's own background-color/
// image/gradients) and the Design's own HTML — same stacking as the real
// screen's #design-effect-background / #design-background (see
// frontends/screen/templates/index.html) — which is only achievable by
// rendering it inside the *same* document as the backdrop CSS, hence
// building it into this srcdoc rather than as a separate layer in the
// parent page (an iframe's own background-color would otherwise fully
// hide anything layered behind it from outside).
const effectFragment = computed(() => {
  if (disableAnimationsInPreview.value) return ''
  const effect = designPreview.value?.background_effect
  if (!effect) return ''
  const def = getEffectDefinition(effect.name)
  if (!def) return ''
  const attrs = def.params
    .map((p) => {
      const value = effect.settings[p.key] ?? p.default
      const attrValue = Array.isArray(value) ? value.join(',') : String(value)
      return `${p.key}="${escapeAttr(attrValue)}"`
    })
    .join(' ')
  return (
    `<div id="design-effect-background" style="position:absolute;inset:0;overflow:hidden;">` +
    `<${def.tag} style="display:block;width:100%;height:100%;" ${attrs}></${def.tag}></div>` +
    SCRIPT_OPEN_TAG + bbScriptSourceSafe + SCRIPT_CLOSE_TAG
  )
})

// Async because container HTML may contain 'icon' field placeholders that
// need resolving to real inline SVG first (resolveIconPlaceholders — see
// utils/designPreview.ts for why that has to happen out here rather than
// inside the sandboxed iframe itself).
const designPreviewSrcdoc = ref('')

const rebuildDesignPreviewSrcdoc = async () => {
  const p = designPreview.value
  if (!p) {
    designPreviewSrcdoc.value = ''
    return
  }
  // Backdrop (body's background-color/image/gradients) arrives already
  // merged into p.css by the backend — there's no separate field to omit it
  // from. Overriding it back out client-side is an approximation: this rule
  // wins the cascade (same `body` selector, later in source order) for
  // whatever the Backdrop itself set, but can't distinguish that from a
  // Design's own hand-authored `body{...}` background in its custom CSS,
  // since both are flattened into the same string server-side.
  const backdropOverride = disableBackdropInPreview.value
    ? 'body{background-color:transparent!important;background-image:none!important;}'
    : ''
  // Mirrors what screens do: a container is drawn if it has default content
  // or "Show when empty" is on (including a still-unstaged edit of it), so
  // its Container Design background/border is visible. "Disable default
  // content" only hides the inner content, never the box itself.
  const containersHtml = (
    await Promise.all(
      placedContainers.value.filter((container) => {
        const showEmpty = contentDraft[container.id]?.show_when_empty ?? !!container.show_when_empty
        return showEmpty || !!layoutContainerPreviews.value[String(container.id)]
      }).map(async (container) => {
        const preview = layoutContainerPreviews.value[String(container.id)]
        const html = preview && !disableDefaultContentInPreview.value
          ? await resolveIconPlaceholders(preview.html)
          : ''
        // Use the container's live (possibly still-unsaved) drag/resize
        // position rather than the server's last-saved one, so the preview
        // moves with its rect on the canvas above it.
        const pos = draft[container.id] || geometryOf(container)
        return `<div class="dh-container dh-container-${container.id}" style="position:absolute;top:${pos.top}vh;left:${pos.left}vw;width:${pos.width}vw;height:${pos.height}vh;">${html}</div>`
      }),
    )
  ).join('')
  designPreviewSrcdoc.value = `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;position:relative;}${p.css}${stagedDesignCss()}${backdropOverride}</style></head><body>${effectFragment.value}<div style="position:relative;">${p.html}</div>${containersHtml}</body></html>`
}

watch(
  [designPreview, disableBackdropInPreview, disableDefaultContentInPreview, layoutContainerPreviews, effectFragment, draft, designDraft, contentDraft, () => props.containers, activeContainerIds, activeRatio],
  rebuildDesignPreviewSrcdoc,
  { deep: true },
)

const handleDesignPreview = (data: DesignPreview) => {
  designPreview.value = data
}

// --- Right-hand cards: collapsible ---------------------------------------
// Local-only UI state (never persisted); all start expanded.
const collapsedCards = reactive<Record<string, boolean>>({})
const toggleCard = (key: string) => {
  collapsedCards[key] = !collapsedCards[key]
}

// --- Container Design: the active Design's per-container styles ------------------
// Same DesignContainerStyle rows the Designs page's "Per-Container Styles"
// panel edits, scoped to the selected container and the active Design. Shown
// to users with designs.edit or contenttypes.edit_design; the backend
// handlers enforce the same either-right gate.
const rightsStore = useRightsStore()
const canEditContainerDesign = computed(
  () => rightsStore.can('designs.edit') || rightsStore.can('contenttypes.edit_design'),
)
// contentcontainer id -> { property: value }
const containerDesignStyles = ref<Record<number, Record<string, string>>>({})

const handleContainerDesign = (data: { data?: Record<string, Record<string, string>> }) => {
  const loaded: Record<number, Record<string, string>> = {}
  for (const [id, styles] of Object.entries(data?.data || {})) loaded[Number(id)] = { ...styles }
  containerDesignStyles.value = loaded
}

const selectedContainerDesignStyles = computed(() =>
  selectedId.value != null
    ? designDraft[selectedId.value] ?? containerDesignStyles.value[selectedId.value] ?? {}
    : {},
)

const setContainerDesignStyle = (prop: string, value: string) => {
  const id = selectedId.value
  if (id == null) return
  const next = { ...(designDraft[id] ?? containerDesignStyles.value[id]) }
  if (value) next[prop] = value
  else delete next[prop]
  const saved = containerDesignStyles.value[id] ?? {}
  const same = ALL_CONTAINER_STYLE_PROPERTIES.every((p) => (next[p.key] || '') === (saved[p.key] || ''))
  if (same) delete designDraft[id]
  else designDraft[id] = next
}

// CSS for the staged (unsaved) container designs, appended after the
// server-rendered design CSS in the preview. Properties cleared relative to
// the saved value are reset with `unset` since the saved rule is already in
// the server CSS.
const resolveStagedColor = (v: string): string => {
  if (!v.startsWith('@default:')) return v
  const id = v.slice('@default:'.length)
  return designPreview.value?.default_colors?.find((c) => c.id === id)?.hex || ''
}
const stagedDesignCss = (): string =>
  Object.entries(designDraft)
    .map(([id, styles]) => {
      const saved = containerDesignStyles.value[Number(id)] ?? {}
      const decls = ALL_CONTAINER_STYLE_PROPERTIES.map((p) => {
        const v = resolveStagedColor(styles[p.key] || '')
        if (v) return `${p.key}:${v};`
        return saved[p.key] ? `${p.key}:unset;` : ''
      }).join('')
      return decls ? `.dh-container-${id}{${decls}}` : ''
    })
    .join('')

// Snaplines are global (shared across every Layout, not scoped to this one)
// — loaded once here and kept live via the broadcast every save triggers, so
// two admins editing different Layouts at once stay in sync.
const handleLayoutSnaplines = (data: { snaplines?: Snapline[] }) => {
  snaplines.value = data?.snaplines || []
}

onMounted(() => {
  on('displayhive:admin:stc:design_preview', handleDesignPreview)
  on('displayhive:admin:stc:container_design', handleContainerDesign)
  on('displayhive:admin:stc:layout_snaplines', handleLayoutSnaplines)
  on('displayhive:admin:stc:layout_default_content_preview', handleLayoutDefaultContentPreview)
  socketEmit('displayhive:admin:cts:get_design_preview')
  if (canEditContainerDesign.value) socketEmit('displayhive:admin:cts:get_container_design')
  socketEmit('displayhive:admin:cts:get_layout_snaplines')
  fetchLayoutDefaultContentPreview()
})

onUnmounted(() => {
  off('displayhive:admin:stc:design_preview', handleDesignPreview)
  off('displayhive:admin:stc:container_design', handleContainerDesign)
  off('displayhive:admin:stc:layout_snaplines', handleLayoutSnaplines)
  off('displayhive:admin:stc:layout_default_content_preview', handleLayoutDefaultContentPreview)
})

const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), max)
const round1 = (v: number) => Math.round(v * 10) / 10

// Containers currently assigned to this Layout, vs. everything else
// (shown in the sidebar so they can be dragged in). Also drives the canvas
// rects — NOT filtered by containerFilterText, so searching the sidebar
// never hides anything already placed on the canvas.
const placedContainers = computed(() =>
  props.containers.filter((c) => activeContainerIds.value.includes(c.id))
)
const availableContainers = computed(() =>
  props.containers.filter((c) => !activeContainerIds.value.includes(c.id))
)

// Search/filter for the two sidebar lists only — matches on name (including
// any in-progress unsaved rename) or id.
const containerFilterText = ref('')
const matchesContainerFilter = (c: ContentContainer) => {
  const q = containerFilterText.value.trim().toLowerCase()
  if (!q) return true
  return contentFor(c).name.toLowerCase().includes(q) || String(c.id).includes(q)
}
const filteredPlacedContainers = computed(() => placedContainers.value.filter(matchesContainerFilter))
const filteredAvailableContainers = computed(() => availableContainers.value.filter(matchesContainerFilter))

// Re-fetch the rendered default-content preview whenever the set of placed
// containers or any container's own default content/handler changes — covers
// add/remove from the Layout and edits made via the container edit modal
// (props.containers is a fresh array from the parent on every upd_containers
// broadcast, so a shallow field comparison here is enough to detect content
// edits too).
watch(
  () => [
    props.layout.id,
    activeRatio.value,
    ...placedContainers.value.map((c) => `${c.id}:${c.default_field_handler || ''}:${c.default_content || ''}`),
  ],
  fetchLayoutDefaultContentPreview,
)

const selectedContainer = computed(() =>
  selectedId.value != null ? props.containers.find((c) => c.id === selectedId.value) || null : null
)

// Every OTHER Layout (besides the one open here) that also uses this
// container — since containers are shared, standalone entities, moving one
// or deleting it affects every Layout in this list too.
const otherLayoutsUsing = (containerId: number): Layout[] =>
  props.layouts.filter((l) => l.id !== props.layout.id && idsOfLayoutAt(l, activeRatio.value).includes(containerId))

const canDeleteContainer = (c: ContentContainer) => !c.in_use && otherLayoutsUsing(c.id).length === 0

// --- Staged position overlay while dragging/resizing -----------------------
// Containers are standalone entities with one global position shared across
// every Layout that uses them. Moves/resizes are only staged here locally —
// nothing is sent to the server until flushPendingPositions() runs (called
// by the parent when the Layout dialog is saved/closed/switched), matching
// "changes save with the Layout, not on every drag". Declared up near
// selectedId (rather than down here with the rest of this section) because
// rebuildDesignPreviewSrcdoc's watcher, defined earlier in the file, also
// reads it live so a container's default-content preview moves with it.

const posFor = (c: ContentContainer) => draft[c.id] || geometryOf(c)

const rectStyle = (c: ContentContainer) => {
  const p = posFor(c)
  return {
    top: `${p.top}%`,
    left: `${p.left}%`,
    width: `${p.width}%`,
    height: `${p.height}%`,
  }
}

// Same idea as `draft`, for the settings card's non-position fields (name,
// default field handler/content) — edited live in the card, shown live on
// the canvas (rect label), but likewise only sent to the server when the
// Layout itself is saved.

const contentFor = (c: ContentContainer): ContentDraftEntry =>
  contentDraft[c.id] || { name: c.name, default_field_handler: c.default_field_handler || '', default_content: c.default_content || '', show_when_empty: !!c.show_when_empty }

// Whether *c* has an unsaved staged move/resize — drives the "reset to
// default position" button shown on its rect.
const hasPendingChange = (c: ContentContainer) => draft[c.id] !== undefined

// Whether *c* has any unsaved staged edit at all (position or settings) —
// drives the "Revert" button in the settings card.
const hasAnyPendingChange = (c: ContentContainer) =>
  draft[c.id] !== undefined || contentDraft[c.id] !== undefined || designDraft[c.id] !== undefined

// Sends every staged (drag/resize/settings-card) change to the server and
// clears the local staging areas. Exposed so the parent can call it when the
// admin actually saves/closes the Layout dialog. If any staged container is
// also used by another Layout, warns about that once here (not while
// dragging) and lets the admin back out — returns false without sending
// anything if they cancel.
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

const flushPendingPositions = async (): Promise<boolean> => {
  stashActiveDraft()
  const ids = new Set([
    ...Object.values(draftsByRatio).flatMap((d) => Object.keys(d)),
    ...Object.keys(contentDraft), ...Object.keys(designDraft),
  ].map(Number))
  if (!ids.size) return true

  const affectedLines: string[] = []
  for (const id of ids) {
    const others = otherLayoutsUsing(id)
    if (others.length) {
      const c = props.containers.find((x) => x.id === id)
      const names = others.map((l) => l.name).join('", "')
      affectedLines.push(`"${c?.name}" also affects layout${others.length > 1 ? 's' : ''} "${names}"`)
    }
  }

  if (affectedLines.length) {
    const proceed = await new Promise<boolean>((resolve) => {
      confirm.require({
        message: `Saving these changes will also affect other layouts:\n${affectedLines.join('\n')}\nKeep the changes?`,
        header: 'Shared container',
        icon: 'pi pi-exclamation-triangle',
        acceptLabel: 'Keep',
        rejectLabel: 'Cancel',
        accept: () => resolve(true),
        reject: () => resolve(false),
      })
    })
    if (!proceed) return false
  }

  const results = await Promise.all([...ids].map((id) => {
    const content = contentDraft[id]
    const design = designDraft[id]
    const saves: Promise<Ack | null>[] = []
    const posPayload = (p: Pos) => ({ top: round1(p.top), left: round1(p.left), width: round1(p.width), height: round1(p.height) })
    // Base position travels with the shared settings; each other ratio's
    // position is its own call, tagged with that ratio.
    const baseDraft = draftsByRatio[BASE_ASPECT_RATIO]?.[id]
    if (baseDraft || content) {
      saves.push(request('displayhive:admin:cts:update_container', {
        id,
        ...(baseDraft ? posPayload(baseDraft) : {}),
        ...(content ? { name: content.name, default_field_handler: content.default_field_handler, default_content: content.default_content, show_when_empty: content.show_when_empty } : {}),
      }, { error: 'Could not save the container' }))
    }
    for (const [ratio, drafts] of Object.entries(draftsByRatio)) {
      if (ratio === BASE_ASPECT_RATIO || !drafts[id]) continue
      saves.push(request('displayhive:admin:cts:update_container', { id, aspect_ratio: ratio, ...posPayload(drafts[id]) }, { error: 'Could not save the container position' }))
    }
    if (design) {
      // Every known property is sent so cleared ones are deleted server-side.
      const styles: Record<string, string> = {}
      for (const p of ALL_CONTAINER_STYLE_PROPERTIES) styles[p.key] = design[p.key] || ''
      saves.push(request('displayhive:admin:cts:save_container_design', { contentcontainer_id: id, styles }, { error: 'Could not save the container design' }))
    }
    return Promise.all(saves)
  }))
  // A refused save was already reported; keep the staged edits so nothing is lost.
  if (results.flat().some((ack) => !ack)) return false
  for (const id of ids) {
    if (designDraft[id]) containerDesignStyles.value = { ...containerDesignStyles.value, [id]: designDraft[id] }
    delete contentDraft[id]
    delete designDraft[id]
  }
  clearAllPositionDrafts()
  return true
}

// Silently drops any staged (unsaved) changes without sending or warning
// about anything — used when navigating away from this Layout without
// saving (switching layouts, starting a new one). Also dismisses any "also
// affects layout Y" confirmation left open from an unfinished Save, so
// switching away never leaves that dialog on screen.
const discardPendingPositions = () => {
  clearAllPositionDrafts()
  for (const idStr of Object.keys(contentDraft)) delete contentDraft[Number(idStr)]
  for (const idStr of Object.keys(designDraft)) delete designDraft[Number(idStr)]
  confirm.close()
}

// Discards the staged move/resize for *c* only, snapping its rect back to
// the last-saved (props.containers) position — same mechanism as
// discardPendingPositions(), just scoped to one container. Settings-card
// edits (name/handler/content) are left untouched.
const resetContainerPosition = (c: ContentContainer) => {
  delete draft[c.id]
  if (containerEditForm.id === c.id) {
    const g = geometryOf(c)
    containerEditForm.top = g.top
    containerEditForm.left = g.left
    containerEditForm.width = g.width
    containerEditForm.height = g.height
  }
}

// Locking is persisted immediately (unlike position, which stages until the
// Layout is saved) — it's a discrete, deliberate toggle rather than a
// continuous drag, so there's nothing useful to "stage".
const toggleContainerLock = async (c: ContentContainer) => {
  await request('displayhive:admin:cts:update_container', { id: c.id, locked: !c.locked }, { error: 'Could not change the lock' })
}

// Belt-and-braces: whenever the Layout being edited actually changes (however
// the parent got here), wipe any staged edits itself rather than relying on
// the parent remembering to call discardPendingPositions() first — so a
// dropdown switch can never carry over a stale "also affects layout Y" warning.
watch(() => props.layout.id, () => {
  discardPendingPositions()
  selectedId.value = null
})

defineExpose({ flushPendingPositions, discardPendingPositions })

// --- Edge/center snapping: moving/resizing a container snaps its edges AND
// center to the canvas bounds+center, to the edges+centers of every other
// placed container, and to any user-defined snaplines (see below).
const SNAP_THRESHOLD = 1.5 // percent

interface Snapline { axis: 'h' | 'v'; position: number } // 'h' = horizontal line, constrains top/bottom (vTargets); 'v' = vertical line, constrains left/right (hTargets)
const snaplines = ref<Snapline[]>([])

// Snaplines are global settings (application/admin/layouts/sockethandlers.py
// stores them via SystemSetting), so add/remove just replace-and-persist the
// whole list; `snaplines.value` itself is updated by the server's broadcast
// (handleLayoutSnaplines) once the change is committed, not optimistically
// here — keeps every open Layout editor in sync off one source of truth.
const newSnaplineAxis = ref<'h' | 'v'>('h')
const newSnaplinePosition = ref<number>(50)

const saveSnaplines = async (next: Snapline[]) => {
  await request('displayhive:admin:cts:set_layout_snaplines', { snaplines: next }, { error: 'Could not save snapline' })
}

const addSnapline = () => {
  const position = clamp(newSnaplinePosition.value, 0, 100)
  saveSnaplines([...snaplines.value, { axis: newSnaplineAxis.value, position }])
}

const removeSnapline = (index: number) => {
  saveSnaplines(snaplines.value.filter((_, i) => i !== index))
}

const closestWithinThreshold = (value: number, targets: number[]): number | null => {
  let best: number | null = null
  let bestDiff = SNAP_THRESHOLD
  for (const t of targets) {
    const diff = Math.abs(value - t)
    if (diff < bestDiff) {
      bestDiff = diff
      best = t
    }
  }
  return best
}

const edgeTargets = (excludeId: number) => {
  const hTargets = [0, 50, 100]
  const vTargets = [0, 50, 100]
  for (const c of placedContainers.value) {
    if (c.id === excludeId) continue
    const p = posFor(c)
    hTargets.push(p.left, p.left + p.width, p.left + p.width / 2)
    vTargets.push(p.top, p.top + p.height, p.top + p.height / 2)
  }
  for (const line of snaplines.value) {
    if (line.axis === 'v') hTargets.push(line.position)
    else vTargets.push(line.position)
  }
  return { hTargets, vTargets }
}

// Picks whichever of {left edge, right edge, center} lands closest to a
// target, so a move can snap on center just as readily as on a side.
const snapAxis = (start: number, size: number, targets: number[]): number => {
  const startSnap = closestWithinThreshold(start, targets)
  const endSnap = closestWithinThreshold(start + size, targets)
  const centerSnap = closestWithinThreshold(start + size / 2, targets)
  const candidates: Array<{ value: number; diff: number }> = []
  if (startSnap !== null) candidates.push({ value: startSnap, diff: Math.abs(start - startSnap) })
  if (endSnap !== null) candidates.push({ value: endSnap - size, diff: Math.abs(start + size - endSnap) })
  if (centerSnap !== null) candidates.push({ value: centerSnap - size / 2, diff: Math.abs(start + size / 2 - centerSnap) })
  if (!candidates.length) return start
  candidates.sort((a, b) => a.diff - b.diff)
  return candidates[0]!.value
}

const snapMove = (left: number, top: number, width: number, height: number, excludeId: number) => {
  const { hTargets, vTargets } = edgeTargets(excludeId)
  return {
    left: snapAxis(left, width, hTargets),
    top: snapAxis(top, height, vTargets),
  }
}

// --- Move / resize existing containers via pointer drag --------------------
type Corner = 'tl' | 'tr' | 'bl' | 'br'

interface DragState {
  id: number
  mode: 'move' | 'resize'
  corner: Corner | null
  startX: number
  startY: number
  startTop: number
  startLeft: number
  startWidth: number
  startHeight: number
}
let dragState: DragState | null = null

const onRectPointerDown = (e: PointerEvent, c: ContentContainer, mode: 'move' | 'resize', corner: Corner | null = null) => {
  e.stopPropagation()
  e.preventDefault()
  selectedId.value = c.id
  if (c.locked) return
  // Start from wherever it currently is — including any not-yet-saved
  // staged position — not the last-saved value from props, or picking up an
  // already-moved container would snap it back to its original spot.
  const p = posFor(c)
  dragState = {
    id: c.id, mode, corner, startX: e.clientX, startY: e.clientY,
    startTop: p.top, startLeft: p.left, startWidth: p.width, startHeight: p.height,
  }
  window.addEventListener('pointermove', onDragPointerMove)
  window.addEventListener('pointerup', onDragPointerUp)
}

const MIN_SIZE = 4 // percent

// Resizes from *corner*, keeping the OPPOSITE corner fixed as the anchor —
// the dragged corner's own edges snap to the same target set moves use
// (other containers' edges/centers, canvas bounds/center, snaplines).
const resizeFromCorner = (
  corner: Corner, startLeft: number, startTop: number, startWidth: number, startHeight: number,
  dxPct: number, dyPct: number, excludeId: number,
) => {
  const { hTargets, vTargets } = edgeTargets(excludeId)
  const movesLeftEdge = corner === 'tl' || corner === 'bl'
  const movesTopEdge = corner === 'tl' || corner === 'tr'

  const anchorX = movesLeftEdge ? startLeft + startWidth : startLeft
  const anchorY = movesTopEdge ? startTop + startHeight : startTop

  let movingX = movesLeftEdge ? startLeft + dxPct : startLeft + startWidth + dxPct
  let movingY = movesTopEdge ? startTop + dyPct : startTop + startHeight + dyPct

  movingX = movesLeftEdge ? clamp(movingX, 0, anchorX - MIN_SIZE) : clamp(movingX, anchorX + MIN_SIZE, 100)
  movingY = movesTopEdge ? clamp(movingY, 0, anchorY - MIN_SIZE) : clamp(movingY, anchorY + MIN_SIZE, 100)

  const snappedXTarget = closestWithinThreshold(movingX, hTargets)
  const snappedYTarget = closestWithinThreshold(movingY, vTargets)
  if (snappedXTarget !== null) {
    movingX = movesLeftEdge ? clamp(snappedXTarget, 0, anchorX - MIN_SIZE) : clamp(snappedXTarget, anchorX + MIN_SIZE, 100)
  }
  if (snappedYTarget !== null) {
    movingY = movesTopEdge ? clamp(snappedYTarget, 0, anchorY - MIN_SIZE) : clamp(snappedYTarget, anchorY + MIN_SIZE, 100)
  }

  return {
    left: movesLeftEdge ? movingX : anchorX,
    top: movesTopEdge ? movingY : anchorY,
    width: movesLeftEdge ? anchorX - movingX : movingX - anchorX,
    height: movesTopEdge ? anchorY - movingY : movingY - anchorY,
  }
}

const onDragPointerMove = (e: PointerEvent) => {
  if (!dragState || !canvasEl.value) return
  const rect = canvasEl.value.getBoundingClientRect()
  const dxPct = ((e.clientX - dragState.startX) / rect.width) * 100
  const dyPct = ((e.clientY - dragState.startY) / rect.height) * 100

  if (dragState.mode === 'move') {
    let top = clamp(dragState.startTop + dyPct, 0, 100 - dragState.startHeight)
    let left = clamp(dragState.startLeft + dxPct, 0, 100 - dragState.startWidth)
    const snapped = snapMove(left, top, dragState.startWidth, dragState.startHeight, dragState.id)
    left = clamp(snapped.left, 0, 100 - dragState.startWidth)
    top = clamp(snapped.top, 0, 100 - dragState.startHeight)
    draft[dragState.id] = { top, left, width: dragState.startWidth, height: dragState.startHeight }
  } else {
    const corner = dragState.corner ?? 'br'
    const resized = resizeFromCorner(
      corner, dragState.startLeft, dragState.startTop, dragState.startWidth, dragState.startHeight,
      dxPct, dyPct, dragState.id,
    )
    draft[dragState.id] = resized
  }
}

// Stages *pos* for *id* — nothing is sent to the server, and no cross-layout
// warning shown, until flushPendingPositions() runs (that's where the
// "also affects layout Y" check happens, once, at save time).
const stagePositionChange = (id: number, pos: { top: number; left: number; width: number; height: number }) => {
  draft[id] = pos
}

const onDragPointerUp = () => {
  window.removeEventListener('pointermove', onDragPointerMove)
  window.removeEventListener('pointerup', onDragPointerUp)
  if (dragState) {
    const id = dragState.id
    const pos = draft[id]
    if (pos) stagePositionChange(id, pos)
  }
  dragState = null
}

// --- Draw a brand-new container on empty canvas space -----------------------
interface DrawState { startX: number; startY: number; top: number; left: number; width: number; height: number }
const drawRect = ref<DrawState | null>(null)
let drawing = false
let drawStartClientX = 0
let drawStartClientY = 0

const onCanvasPointerDown = (e: PointerEvent) => {
  if (hideHandlerElements.value) { // rects are invisible: clicking empty space only deselects, no drawing
    if (e.target === canvasEl.value) selectedId.value = null
    return
  }
  if (e.target !== canvasEl.value) return // ignore clicks that started on a rect
  if (!canvasEl.value) return
  selectedId.value = null
  drawing = true
  drawStartClientX = e.clientX
  drawStartClientY = e.clientY
  const rect = canvasEl.value.getBoundingClientRect()
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  drawRect.value = { startX: e.clientX, startY: e.clientY, top: y, left: x, width: 0, height: 0 }
  window.addEventListener('pointermove', onCanvasDrawMove)
  window.addEventListener('pointerup', onCanvasDrawUp)
}

const onCanvasDrawMove = (e: PointerEvent) => {
  if (!drawing || !drawRect.value || !canvasEl.value) return
  const rect = canvasEl.value.getBoundingClientRect()
  const curX = ((e.clientX - rect.left) / rect.width) * 100
  const curY = ((e.clientY - rect.top) / rect.height) * 100
  const startX = ((drawStartClientX - rect.left) / rect.width) * 100
  const startY = ((drawStartClientY - rect.top) / rect.height) * 100
  const left = clamp(Math.min(startX, curX), 0, 100)
  const top = clamp(Math.min(startY, curY), 0, 100)
  const width = clamp(Math.abs(curX - startX), 0, 100 - left)
  const height = clamp(Math.abs(curY - startY), 0, 100 - top)
  drawRect.value = { ...drawRect.value, top, left, width, height }
}

// Creates a brand-new ContentContainer at the given position/size and
// immediately assigns it to this Layout. Shared by draw-on-canvas and the
// sidebar's "New Container" button.
const createNewContainer = async (pos: { top: number; left: number; width: number; height: number }) => {
  const n = props.containers.length + 1
  const ack = await request<Ack & { id?: number }>(
    'displayhive:admin:cts:create_container',
    {
      name: `Container ${n}`,
      order: n,
      top: round1(pos.top), left: round1(pos.left), width: round1(pos.width), height: round1(pos.height),
    },
    { error: 'Create failed' },
  )
  if (ack?.id) {
    await addContainerToLayout(ack.id)
    selectedId.value = ack.id
  }
}

const onCanvasDrawUp = async () => {
  window.removeEventListener('pointermove', onCanvasDrawMove)
  window.removeEventListener('pointerup', onCanvasDrawUp)
  drawing = false
  const d = drawRect.value
  drawRect.value = null
  if (!d || d.width < 3 || d.height < 3) return // treat as a stray click, not a real draw
  await createNewContainer(d)
}

// "New Container" button: adds a default-sized box in the top-left free
// corner instead of requiring the admin to draw it by hand.
const addNewContainerViaButton = () => {
  createNewContainer({ top: 0, left: 0, width: 20, height: 20 })
}

const drawRectStyle = computed(() => {
  const d = drawRect.value
  if (!d) return {}
  return { top: `${d.top}%`, left: `${d.left}%`, width: `${d.width}%`, height: `${d.height}%` }
})

// --- Assign / unassign existing containers to this Layout -------------------
const addContainerToLayout = async (containerId: number) => {
  const ids = activeContainerIds.value
  if (ids.includes(containerId)) return
  await request('displayhive:admin:cts:update_layout', {
    id: props.layout.id,
    aspect_ratio: activeRatio.value,
    container_ids: [...ids, containerId],
  }, { error: 'Could not add the container to the layout' })
}

const removeFromLayout = async (containerId: number | null) => {
  if (containerId == null) return
  const ids = activeContainerIds.value.filter((id) => id !== containerId)
  const ack = await request('displayhive:admin:cts:update_layout', { id: props.layout.id, aspect_ratio: activeRatio.value, container_ids: ids }, { error: 'Could not remove the container from the layout' })
  if (ack && selectedId.value === containerId) selectedId.value = null
}

const confirmDeleteContainer = (containerId: number | null) => {
  if (containerId == null) return
  const c = props.containers.find((x) => x.id === containerId)
  if (!c) return
  if (c.in_use) {
    toast.add({
      severity: 'warn', summary: 'Cannot delete',
      detail: 'This container is used by a Contenttype field — unassign it there first.', life: 4000,
    })
    return
  }
  const others = otherLayoutsUsing(c.id)
  if (others.length) {
    toast.add({
      severity: 'warn', summary: 'Cannot delete',
      detail: `This container is also used by layout${others.length > 1 ? 's' : ''} "${others.map((l) => l.name).join('", "')}" — remove it there first.`,
      life: 5000,
    })
    return
  }
  confirm.require({
    message: `Delete container "${c.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      socketEmit('displayhive:admin:cts:delete_container', { id: containerId })
      if (selectedId.value === containerId) selectedId.value = null
    },
  })
}

// --- Drag an existing (unassigned) container in from the sidebar -----------
const onSidebarDragStart = (e: DragEvent, c: ContentContainer) => {
  e.dataTransfer?.setData('text/plain', String(c.id))
  e.dataTransfer!.effectAllowed = 'copy'
}

const onCanvasDrop = async (e: DragEvent) => {
  const raw = e.dataTransfer?.getData('text/plain')
  const containerId = raw ? parseInt(raw, 10) : NaN
  if (!containerId || !canvasEl.value) return
  const c = props.containers.find((x) => x.id === containerId)
  if (!c) return

  // Containers are shared, standalone entities with one global position
  // across every Layout that uses them — dropping one in here only assigns
  // it to this Layout, it keeps whatever position it already has elsewhere.
  await addContainerToLayout(containerId)
  selectedId.value = containerId
}

// --- Editing a container's exact fields, in a modal ------------------------
// Field handler options mirror ContentTypesView.vue's field list, plus a
// "None" option since a container's default is optional.
const defaultFieldHandlerOptions = [
  { label: 'None', value: '' },
  { label: 'Arrow', value: 'arrows' },
  { label: 'Countdown', value: 'countdown' },
  { label: 'Date / Time Format', value: 'datetime_format' },
  { label: 'HTML (raw)', value: 'rawhtml' },
  { label: 'Icon', value: 'icon' },
  { label: 'iFrame', value: 'iframe' },
  { label: 'Lauftext (Marquee)', value: 'marquee' },
  { label: 'Image', value: 'image' },
  { label: 'Link/URL', value: 'link' },
  { label: 'Long Text', value: 'textbig' },
  { label: 'Number', value: 'numbers' },
  { label: 'Pretalx Table', value: 'pretalx_table' },
  { label: 'Short Text', value: 'textklein' },
  { label: 'Table', value: 'table' },
  { label: 'WYSIWYG', value: 'wysiwyg' },
]

const showImagePickerDialog = ref(false)
const containerEditForm = reactive({
  id: null as number | null,
  name: '',
  top: 0, left: 0, width: 20, height: 20,
  default_field_handler: '', default_content: '',
  show_when_empty: false,
})

// --- 'image' handler: {url, size}, packed as JSON into default_content —
// back-compat: existing containers stored the raw URL string directly (no
// size), so a plain non-JSON value is read as that URL with size unset.
const parseImageData = (): { url: string; size: number | null } => {
  const raw = containerEditForm.default_content || ''
  try {
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object' && 'url' in parsed) {
      return { url: parsed.url || '', size: parsed.size || null }
    }
  } catch { /* not JSON — legacy plain URL string */ }
  return { url: raw, size: null }
}
const imageUrl = computed(() => parseImageData().url)
const imageSize = computed(() => parseImageData().size)
const setImageData = (data: { url: string; size: number | null }) => {
  containerEditForm.default_content = JSON.stringify(data)
}

const onDefaultImagePicked = (item: MediaItem) => {
  setImageData({ url: item.url, size: imageSize.value })
}

// --- 'icon' handler: {icon, size, color}, packed as JSON into default_content
const iconValue = computed<IconPickerValue>(() => {
  try {
    const parsed = JSON.parse(containerEditForm.default_content || '{}')
    if (parsed && typeof parsed === 'object' && 'icon' in parsed) {
      return { icon: parsed.icon || '', size: parsed.size ?? 5, color: parsed.color || '' }
    }
  } catch { /* not JSON yet */ }
  return { icon: '', size: 5, color: '' }
})
const setIconData = (v: IconPickerValue) => {
  containerEditForm.default_content = JSON.stringify(v)
}

// Populates containerEditForm from *c*, resuming any already-staged
// position/content drafts (e.g. re-selecting a container edited earlier in
// this session) — used to seed the settings card when the selection changes.
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
// not clobber it) — mirrors what opening the old edit modal used to do.
watch(selectedId, (id) => {
  if (id == null) {
    containerEditForm.id = null
    return
  }
  const c = props.containers.find((x) => x.id === id)
  if (c) seedEditForm(c)
}, { immediate: true })

// --- Ratio switching / variation management ----------------------------------
const sameShape = (a: string, b: string) => {
  const [aw = 1, ah = 1] = a.split(':').map(Number)
  const [bw = 1, bh = 1] = b.split(':').map(Number)
  return aw * bh === bw * ah
}

const selectRatio = (ratio: string) => {
  if (ratio === activeRatio.value) return
  // Park this ratio's staged positions and bring back the target's.
  stashActiveDraft()
  for (const idStr of Object.keys(draft)) delete draft[Number(idStr)]
  Object.assign(draft, draftsByRatio[ratio] ?? {})
  delete draftsByRatio[ratio]
  activeRatio.value = ratio
}

// The selection / settings card follow the ratio: a container that isn't part
// of the newly shown variation is deselected, otherwise its card is re-seeded
// with that ratio's position.
watch(activeRatio, () => {
  const c = selectedContainer.value
  if (!c) return
  if (!activeContainerIds.value.includes(c.id)) selectedId.value = null
  else seedEditForm(c)
})

// A variation just created (or removed, possibly from another tab): once the
// layout broadcast arrives, jump to the new one / fall back to the base.
const pendingRatio = ref<string | null>(null)
watch(layoutRatioList, (list) => {
  if (pendingRatio.value && list.includes(pendingRatio.value)) {
    selectRatio(pendingRatio.value)
    pendingRatio.value = null
  } else if (!list.includes(activeRatio.value)) {
    delete draftsByRatio[activeRatio.value]
    selectRatio(BASE_ASPECT_RATIO)
  }
})

const newVariationRatio = ref<string | null>(null)
const addableRatios = computed(() =>
  designRatios.value.filter((r) => !layoutRatioList.value.some((x) => sameShape(x, r))),
)

const addVariation = async () => {
  const ratio = newVariationRatio.value
  if (!ratio) return
  const ack = await request('displayhive:admin:cts:create_layout_variation', {
    layout_id: props.layout.id, aspect_ratio: ratio,
  }, { error: 'Could not add variation' })
  if (ack) {
    pendingRatio.value = ratio
    newVariationRatio.value = null
  }
}

const confirmDeleteVariation = (ratio: string) => {
  confirm.require({
    message: `Remove the ${ratio} variation of this layout? Its container selection is dropped; container positions at ${ratio} are kept.`,
    header: 'Remove variation',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      await request('displayhive:admin:cts:delete_layout_variation', {
        layout_id: props.layout.id, aspect_ratio: ratio,
      }, { error: 'Could not remove variation' })
    },
  })
}

const canvasStyle = computed(() => {
  const [w = 16, h = 9] = activeRatio.value.split(':').map(Number)
  // Keep tall (portrait) ratios from growing past ~75% of the viewport height.
  return { aspectRatio: cssAspectRatio(activeRatio.value), width: `min(100%, ${((75 * w) / h).toFixed(3)}vh)`, marginInline: 'auto' }
})

// Reached via a link like /layouts/<id>/edit?container=<cid> (e.g. from a
// content type's field): select that container, switching to the variation
// that has it if it isn't in the base. The parameter is stripped afterwards.
const route = useRoute()
const router = useRouter()
watch(
  [() => route.query.container, () => props.containers, () => props.layout.variations],
  () => {
    const raw = route.query.container
    const id = Number(Array.isArray(raw) ? raw[0] : raw)
    if (!id || !props.containers.some((c) => c.id === id)) return
    if (!activeContainerIds.value.includes(id)) {
      const ratio = layoutRatioList.value.find((r) => idsOfLayoutAt(props.layout, r).includes(id))
      if (!ratio) return
      selectRatio(ratio)
    }
    selectedId.value = id
    const rest = { ...route.query }
    delete rest.container
    router.replace({ query: rest })
  },
  { immediate: true },
)

// Every containerEditForm edit is staged live (into draft/contentDraft) as
// it's made — there's no separate "Save" in the settings card; the whole
// Layout's staged changes (this plus any drag/resize) are only sent to the
// server when the page itself is saved (flushPendingPositions, called by the
// parent). Comparing against the *last-saved* container (not the current
// draft) on every keystroke keeps this idempotent either way.
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

// Discards in-progress edits (position AND settings) back to the last-saved
// values — styled and placed alongside the other per-container actions.
const revertContainerEdit = () => {
  const c = selectedContainer.value
  if (!c) return
  const g = geometryOf(c)
  containerEditForm.name = c.name
  containerEditForm.top = g.top
  containerEditForm.left = g.left
  containerEditForm.width = g.width
  containerEditForm.height = g.height
  containerEditForm.default_field_handler = c.default_field_handler || ''
  containerEditForm.default_content = c.default_content || ''
  containerEditForm.show_when_empty = !!c.show_when_empty
  delete designDraft[c.id]
}

// Switching the handler in the dropdown re-seeds default_content with a
// sensible starting shape for that type (only on an actual user change —
// opening the modal sets containerEditForm directly, bypassing this).
const onDefaultHandlerChange = (newHandler: string) => {
  containerEditForm.default_field_handler = newHandler
  if (newHandler === 'arrows') {
    containerEditForm.default_content = JSON.stringify({ char: '', size: 5 })
  } else if (newHandler === 'image') {
    containerEditForm.default_content = JSON.stringify({ url: '', size: null })
  } else if (newHandler === 'icon') {
    containerEditForm.default_content = JSON.stringify({ icon: '', size: 5, color: '' })
  } else if (newHandler === 'table') {
    containerEditForm.default_content = JSON.stringify({ columns: ['Column 1', 'Column 2'], rows: [['', '']] })
  } else if (newHandler === 'pretalx_table') {
    containerEditForm.default_content = JSON.stringify(blankPretalxTableValue())
  } else if (newHandler === 'datetime_format') {
    containerEditForm.default_content = 'HH:mm:ss'
  } else if (newHandler === 'marquee') {
    containerEditForm.default_content = JSON.stringify({ text: '', speed: 20 })
  } else if (newHandler === 'countdown') {
    containerEditForm.default_content = JSON.stringify({ target: '', format: 'DD:HH:mm:ss', finished_text: '' })
  } else {
    containerEditForm.default_content = ''
  }
}

// --- 'arrows' handler: char + size, packed as JSON into default_content ----
const arrowChar = computed({
  get: () => {
    try { return JSON.parse(containerEditForm.default_content || '{}').char || '' } catch { return '' }
  },
  set: (v: string) => {
    let size = 5
    try { size = JSON.parse(containerEditForm.default_content || '{}').size ?? 5 } catch { /* keep default */ }
    containerEditForm.default_content = JSON.stringify({ char: v, size })
  },
})
const arrowSize = computed({
  get: () => {
    try { return JSON.parse(containerEditForm.default_content || '{}').size ?? 5 } catch { return 5 }
  },
  set: (v: number | null) => {
    let char = ''
    try { char = JSON.parse(containerEditForm.default_content || '{}').char || '' } catch { /* keep default */ }
    containerEditForm.default_content = JSON.stringify({ char, size: v ?? 5 })
  },
})

// --- 'marquee' handler: {text, speed}, packed as JSON into default_content --
const marqueeText = computed({
  get: () => {
    try { return JSON.parse(containerEditForm.default_content || '{}').text || '' } catch { return '' }
  },
  set: (v: string) => {
    let speed = 20
    try { speed = JSON.parse(containerEditForm.default_content || '{}').speed ?? 20 } catch { /* keep default */ }
    containerEditForm.default_content = JSON.stringify({ text: v, speed })
  },
})
const marqueeSpeed = computed({
  get: () => {
    try { return JSON.parse(containerEditForm.default_content || '{}').speed ?? 20 } catch { return 20 }
  },
  set: (v: number | null) => {
    let text = ''
    try { text = JSON.parse(containerEditForm.default_content || '{}').text || '' } catch { /* keep default */ }
    containerEditForm.default_content = JSON.stringify({ text, speed: v ?? 20 })
  },
})

// --- 'countdown' handler: {target, format, finished_text}, packed as JSON
// into default_content. `target` is a naive "YYYY-MM-DDTHH:mm" string (no
// timezone), parsed/formatted the same way Content's start_time/end_time
// scheduling fields are — see ContentEditView.vue's parseIsoDate/fmtDt.
const parseCountdownData = (): { target: string; format: string; finished_text: string } => {
  try {
    const parsed = JSON.parse(containerEditForm.default_content || '{}')
    return {
      target: parsed.target || '',
      format: parsed.format || 'DD:HH:mm:ss',
      finished_text: parsed.finished_text || '',
    }
  } catch {
    return { target: '', format: 'DD:HH:mm:ss', finished_text: '' }
  }
}
const setCountdownData = (data: { target: string; format: string; finished_text: string }) => {
  containerEditForm.default_content = JSON.stringify(data)
}
const fmtCountdownDt = (d: Date | null): string => {
  if (!d) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}
const countdownTargetDate = computed<Date | null>({
  get: () => {
    const raw = parseCountdownData().target
    if (!raw) return null
    const d = new Date(raw)
    return isNaN(d.getTime()) ? null : d
  },
  set: (v: Date | null) => setCountdownData({ ...parseCountdownData(), target: fmtCountdownDt(v) }),
})
const countdownFormat = computed({
  get: () => parseCountdownData().format,
  set: (v: string) => setCountdownData({ ...parseCountdownData(), format: v }),
})
const countdownFinishedText = computed({
  get: () => parseCountdownData().finished_text,
  set: (v: string) => setCountdownData({ ...parseCountdownData(), finished_text: v }),
})

// --- 'table' handler: {columns, rows}, stored directly as JSON -------------
interface TableData { columns: string[]; rows: string[][] }
const tableData = computed<TableData>(() => {
  try {
    const parsed = JSON.parse(containerEditForm.default_content || '{}')
    if (Array.isArray(parsed.columns) && Array.isArray(parsed.rows)) return parsed
  } catch { /* fall through to default shape */ }
  return { columns: ['Column 1', 'Column 2'], rows: [['', '']] }
})
const setTableData = (data: TableData) => {
  containerEditForm.default_content = JSON.stringify(data)
}
const addTableColumn = () => {
  const d = tableData.value
  setTableData({ columns: [...d.columns, `Column ${d.columns.length + 1}`], rows: d.rows.map((r) => [...r, '']) })
}
const removeTableColumn = (ci: number) => {
  const d = tableData.value
  if (d.columns.length <= 1) return
  setTableData({ columns: d.columns.filter((_, i) => i !== ci), rows: d.rows.map((r) => r.filter((_, i) => i !== ci)) })
}
const addTableRow = () => {
  const d = tableData.value
  setTableData({ columns: d.columns, rows: [...d.rows, d.columns.map(() => '')] })
}
const removeTableRow = (ri: number) => {
  const d = tableData.value
  if (d.rows.length <= 1) return
  setTableData({ columns: d.columns, rows: d.rows.filter((_, i) => i !== ri) })
}
const updateTableHeader = (ci: number, v: string) => {
  const d = tableData.value
  const columns = [...d.columns]
  columns[ci] = v
  setTableData({ columns, rows: d.rows })
}
const updateTableCell = (ri: number, ci: number, v: string) => {
  const d = tableData.value
  const rows = d.rows.map((r) => [...r])
  if (rows[ri]) rows[ri][ci] = v
  setTableData({ columns: d.columns, rows })
}

// --- 'pretalx_table' handler: full PretalxTableValue, stored as JSON -------
const pretalxTableData = computed<PretalxTableValue>(() => {
  try {
    return { ...blankPretalxTableValue(), ...JSON.parse(containerEditForm.default_content || '{}') }
  } catch {
    return blankPretalxTableValue()
  }
})
const setPretalxTableData = (v: PretalxTableValue) => {
  containerEditForm.default_content = JSON.stringify(v)
}

// The container being edited can come from the canvas (already placed) or
// from the sidebar (not yet part of this Layout) — the settings card's
// assign/remove button reflects and toggles whichever state it's currently in.
const isSelectedPlaced = computed(() =>
  selectedId.value != null && activeContainerIds.value.includes(selectedId.value)
)

const toggleSelectedLayoutMembership = () => {
  if (selectedId.value == null) return
  if (isSelectedPlaced.value) {
    removeFromLayout(selectedId.value)
  } else {
    addContainerToLayout(selectedId.value)
  }
}
</script>

<template>
  <div class="layout-editor">
    <div class="editor-left-column">
      <div class="container-filter">
        <i class="pi pi-search container-filter-icon"></i>
        <InputText v-model="containerFilterText" size="small" class="w-full" placeholder="Search containers…" />
        <button v-if="containerFilterText" type="button" class="container-filter-clear" title="Clear" @click="containerFilterText = ''">
          <i class="pi pi-times"></i>
        </button>
      </div>

      <Card class="editor-used-card">
        <template #title>
          <div class="card-header-title">
            <i class="pi pi-check-square card-header-icon" />
            <span>Used in this Layout</span>
          </div>
        </template>
        <template #content>
          <div class="sidebar-list">
            <div
              v-for="c in filteredPlacedContainers"
              :key="c.id"
              class="sidebar-item"
              :class="{ selected: selectedId === c.id }"
              @click="selectedId = c.id"
            >
              <i class="pi pi-th-large"></i>
              <span class="sidebar-item-label">{{ contentFor(c).name }} <span class="hint">#{{ c.id }}</span></span>
              <button type="button" class="sidebar-icon-btn" title="Remove from Layout" @click.stop.prevent="removeFromLayout(c.id)">
                <i class="pi pi-minus"></i>
              </button>
            </div>
            <p v-if="!placedContainers.length" class="hint">No containers placed in this layout yet.</p>
            <p v-else-if="!filteredPlacedContainers.length" class="hint">No containers match "{{ containerFilterText }}".</p>
          </div>
        </template>
      </Card>

      <Card class="editor-containers-card">
        <template #title>
          <div class="card-header-title">
            <i class="pi pi-th-large card-header-icon" />
            <span>Containers</span>
          </div>
        </template>
        <template #content>
          <Button label="New Container" icon="pi pi-plus" size="small" class="w-full" @click="addNewContainerViaButton" />
          <h4>Available Containers</h4>
          <p class="hint">Drag one onto the canvas to add it to this Layout.</p>
          <div class="sidebar-list">
            <div
              v-for="c in filteredAvailableContainers"
              :key="c.id"
              class="sidebar-item"
              :class="{ selected: selectedId === c.id }"
              draggable="true"
              @click="selectedId = c.id"
              @dragstart="onSidebarDragStart($event, c)"
            >
              <i class="pi pi-th-large"></i>
              <span class="sidebar-item-label">{{ contentFor(c).name }} <span class="hint">#{{ c.id }}</span></span>
              <button
                type="button"
                class="sidebar-icon-btn"
                :class="{ disabled: !canDeleteContainer(c) }"
                :title="canDeleteContainer(c) ? 'Delete container entirely' : 'In use — cannot delete'"
                @click.stop.prevent="confirmDeleteContainer(c.id)"
              >
                <i class="pi pi-times"></i>
              </button>
            </div>
            <p v-if="!availableContainers.length" class="hint">All containers are already in this layout.</p>
            <p v-else-if="!filteredAvailableContainers.length" class="hint">No containers match "{{ containerFilterText }}".</p>
          </div>
        </template>
      </Card>
    </div>

    <div class="editor-main">
      <div class="editor-canvas-wrap">
        <div
          ref="canvasEl"
          class="editor-canvas"
          :class="{ 'handles-hidden': hideHandlerElements }"
          :style="canvasStyle"
          @pointerdown="onCanvasPointerDown"
          @dragover.prevent
          @drop.prevent="onCanvasDrop"
        >
          <PreviewFrame
            v-if="designPreviewSrcdoc"
            class="editor-design-preview"
            :html="designPreviewSrcdoc"
            title="Active Design preview"
          />
          <div
            v-for="(line, i) in snaplines"
            :key="`snapline-${i}`"
            class="canvas-snapline"
            :class="line.axis === 'h' ? 'canvas-snapline--h' : 'canvas-snapline--v'"
            :style="line.axis === 'h' ? { top: `${line.position}%` } : { left: `${line.position}%` }"
          ></div>
          <div
            v-for="c in placedContainers"
            :key="c.id"
            class="editor-rect"
            :class="{ selected: selectedId === c.id, locked: c.locked }"
            :style="rectStyle(c)"
            @pointerdown="onRectPointerDown($event, c, 'move')"
          >
            <span class="rect-label">{{ contentFor(c).name }} <span class="rect-label-id">#{{ c.id }}</span></span>
            <div class="rect-toolbar">
              <button
                type="button"
                class="remove-handle"
                title="Remove from Layout"
                @pointerdown.stop.prevent
                @click.stop.prevent="removeFromLayout(c.id)"
              >
                <i class="pi pi-minus"></i>
              </button>
              <button
                type="button"
                class="delete-handle"
                :class="{ disabled: !canDeleteContainer(c) }"
                :title="canDeleteContainer(c) ? 'Delete container entirely' : 'In use — cannot delete'"
                @pointerdown.stop.prevent
                @click.stop.prevent="confirmDeleteContainer(c.id)"
              >
                <i class="pi pi-times"></i>
              </button>
            </div>
            <button
              type="button"
              class="lock-handle"
              :class="{ 'lock-handle--locked': c.locked }"
              :title="c.locked ? 'Unlock position' : 'Lock position'"
              @pointerdown.stop.prevent
              @click.stop.prevent="toggleContainerLock(c)"
            >
              <i :class="c.locked ? 'pi pi-lock' : 'pi pi-lock-open'"></i>
            </button>
            <template v-if="!c.locked">
              <div class="resize-handle resize-handle--tl" @pointerdown="onRectPointerDown($event, c, 'resize', 'tl')"></div>
              <div class="resize-handle resize-handle--tr" @pointerdown="onRectPointerDown($event, c, 'resize', 'tr')"></div>
              <div class="resize-handle resize-handle--bl" @pointerdown="onRectPointerDown($event, c, 'resize', 'bl')"></div>
              <div class="resize-handle resize-handle--br" @pointerdown="onRectPointerDown($event, c, 'resize', 'br')"></div>
            </template>
          </div>
          <div v-if="drawRect" class="editor-rect drawing-rect" :style="drawRectStyle"></div>
        </div>
        <p class="hint">Drag a rectangle to move it, its corner handle to resize, or click-drag empty space to draw a new container.</p>
      </div>
    <Card v-if="canEditContainerDesign" class="editor-design-card">
      <template #title>
        <div class="card-header-title card-header-collapsible" role="button" tabindex="0"
          :aria-expanded="!collapsedCards.design"
          @click="toggleCard('design')" @keydown.enter.prevent="toggleCard('design')" @keydown.space.prevent="toggleCard('design')">
          <i class="pi pi-palette card-header-icon" />
          <span>Container Design</span>
          <i class="pi card-header-chevron" :class="collapsedCards.design ? 'pi-chevron-down' : 'pi-chevron-up'" />
        </div>
      </template>
      <template #content>
        <div v-show="!collapsedCards.design">
          <div v-if="!selectedContainer" class="empty-state empty-state--compact">
            <i class="pi pi-palette"></i>
            <p>Select a container to edit its design.</p>
          </div>
          <template v-else>
            <p class="hint">Font &amp; alignment for #{{ selectedContainer.id }} in the active Design. Previewed live; saved with the layout.</p>
            <ContainerDesignFields
              :styles="selectedContainerDesignStyles"
              :palette="designPreview?.default_colors ?? []"
              @change="setContainerDesignStyle"
            />
          </template>
        </div>
      </template>
    </Card>
    </div>

    <div class="editor-right-column">
      <Card class="editor-ratio-card" data-tour="layout-aspect-ratios">
        <template #title>
          <div class="card-header-title card-header-collapsible" role="button" tabindex="0"
            :aria-expanded="!collapsedCards.ratios"
            @click="toggleCard('ratios')" @keydown.enter.prevent="toggleCard('ratios')" @keydown.space.prevent="toggleCard('ratios')">
            <i class="pi pi-arrows-h card-header-icon" />
            <span>Aspect Ratio Variations</span>
            <i class="pi card-header-chevron" :class="collapsedCards.ratios ? 'pi-chevron-down' : 'pi-chevron-up'" />
          </div>
        </template>
        <template #content>
          <div v-show="!collapsedCards.ratios">
            <div class="ratio-list">
              <div
                v-for="r in layoutRatioList"
                :key="r"
                class="ratio-row"
                :class="{ active: r === activeRatio }"
                role="button"
                tabindex="0"
                @click="selectRatio(r)"
                @keydown.enter.prevent="selectRatio(r)"
              >
                <span class="ratio-name">{{ r }}<span v-if="r === BASE_ASPECT_RATIO" class="hint"> (base)</span></span>
                <Tag :value="`${idsOfLayoutAt(layout, r).length} containers`" severity="secondary" />
                <Button
                  v-if="r !== BASE_ASPECT_RATIO"
                  icon="pi pi-trash" text size="small" severity="danger" title="Remove this variation"
                  @click.stop="confirmDeleteVariation(r)"
                />
              </div>
            </div>
            <div class="ratio-add">
              <Select
                v-model="newVariationRatio"
                :options="addableRatios"
                placeholder="Add variation…"
                :disabled="!addableRatios.length"
                class="ratio-add-select"
              />
              <Button icon="pi pi-plus" label="Add" size="small" outlined :disabled="!newVariationRatio" @click="addVariation" />
            </div>
            <p class="hint">
              A new variation starts as a copy of 16:9. Add or remove containers per variation; positions are per ratio,
              everything else about a container is shared.
              <template v-if="!addableRatios.length">More ratios are added on the Designs page.</template>
            </p>
          </div>
        </template>
      </Card>

      <Card class="editor-options-card">
        <template #title>
          <div class="card-header-title card-header-collapsible" role="button" tabindex="0"
            :aria-expanded="!collapsedCards.options"
            @click="toggleCard('options')" @keydown.enter.prevent="toggleCard('options')" @keydown.space.prevent="toggleCard('options')">
            <i class="pi pi-eye card-header-icon" />
            <span>Preview &amp; Guides</span>
            <i class="pi card-header-chevron" :class="collapsedCards.options ? 'pi-chevron-down' : 'pi-chevron-up'" />
          </div>
        </template>
        <template #content>
          <div v-show="!collapsedCards.options">
          <div class="preview-toggles">
            <div class="filter-toggle">
              <label for="disable-animations-preview">Disable animations in Preview</label>
              <ToggleSwitch id="disable-animations-preview" v-model="disableAnimationsInPreview" />
            </div>
            <div class="filter-toggle">
              <label for="disable-backdrop-preview">Disable Backdrop in Preview</label>
              <ToggleSwitch id="disable-backdrop-preview" v-model="disableBackdropInPreview" />
            </div>
            <div class="filter-toggle">
              <label for="disable-default-content-preview">Disable default content in Preview</label>
              <ToggleSwitch id="disable-default-content-preview" v-model="disableDefaultContentInPreview" />
            </div>
            <div class="filter-toggle">
              <label for="hide-handler-elements">Disable Handlerelements</label>
              <ToggleSwitch id="hide-handler-elements" v-model="hideHandlerElements" />
            </div>
          </div>

          <div class="snapline-bar">
            <Select v-model="newSnaplineAxis" :options="[{ label: 'Horizontal', value: 'h' }, { label: 'Vertical', value: 'v' }]" optionLabel="label" optionValue="value" class="snapline-axis-select" />
            <InputNumber v-model="newSnaplinePosition" :min="0" :max="100" suffix="%" class="snapline-position-input" />
            <Button label="Add Snapline" icon="pi pi-plus" size="small" outlined @click="addSnapline" />
            <div class="snapline-chip-list">
              <Tag v-for="(line, i) in snaplines" :key="i" class="snapline-chip">
                {{ line.axis === 'h' ? 'H' : 'V' }} @ {{ line.position }}%
                <i class="pi pi-times snapline-chip-remove" @click="removeSnapline(i)"></i>
              </Tag>
            </div>
          </div>
          </div>
        </template>
      </Card>

      <Card class="editor-settings-card">
        <template #title>
          <div class="card-header-title card-header-collapsible" role="button" tabindex="0"
            :aria-expanded="!collapsedCards.settings"
            @click="toggleCard('settings')" @keydown.enter.prevent="toggleCard('settings')" @keydown.space.prevent="toggleCard('settings')">
            <i class="pi pi-sliders-h card-header-icon" />
            <span>Container Settings</span>
            <i class="pi card-header-chevron" :class="collapsedCards.settings ? 'pi-chevron-down' : 'pi-chevron-up'" />
          </div>
        </template>
        <template #content>
          <div v-show="!collapsedCards.settings">
          <div v-if="!selectedContainer" class="empty-state empty-state--compact">
            <i class="pi pi-th-large"></i>
            <p>Select a container to edit its settings.</p>
          </div>
          <div v-else class="dialog-content">
        <div class="field">
          <label>Name</label>
          <InputText v-model="containerEditForm.name" size="small" class="w-full" />
        </div>
        <div class="position-grid">
          <div class="field">
            <label>Top (vh)</label>
            <InputNumber v-model="containerEditForm.top" size="small" class="w-full" :min="0" :max="100" />
          </div>
          <div class="field">
            <label>Left (vw)</label>
            <InputNumber v-model="containerEditForm.left" size="small" class="w-full" :min="0" :max="100" />
          </div>
          <div class="field">
            <label>Width (vw)</label>
            <InputNumber v-model="containerEditForm.width" size="small" class="w-full" :min="1" :max="100" />
          </div>
          <div class="field">
            <label>Height (vh)</label>
            <InputNumber v-model="containerEditForm.height" size="small" class="w-full" :min="1" :max="100" />
          </div>
        </div>
        <p class="hint">Changes here are shown live, but only saved to the server when you save this Layout.</p>

        <div class="filter-toggle">
          <label for="container-show-when-empty">Show when empty</label>
          <ToggleSwitch id="container-show-when-empty" v-model="containerEditForm.show_when_empty" />
        </div>
        <p class="hint">Off: a container with no content is not shown on screens at all. On: it is, so its Container Design background and border still appear.</p>

        <div class="field">
          <label>Default Field Handler</label>
          <Dropdown
            :model-value="containerEditForm.default_field_handler"
            :options="defaultFieldHandlerOptions"
            optionLabel="label"
            optionValue="value"
            size="small"
            class="w-full"
            @update:model-value="onDefaultHandlerChange"
          />
          <small class="hint">Shown when no active scene currently targets this container.</small>
        </div>

        <template v-if="containerEditForm.default_field_handler">
          <div v-if="['textklein', 'link'].includes(containerEditForm.default_field_handler)" class="field">
            <label>Default Content</label>
            <InputText v-model="containerEditForm.default_content" size="small" class="w-full" />
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'textbig'" class="field">
            <label>Default Content</label>
            <Textarea v-model="containerEditForm.default_content" rows="3" class="w-full" />
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'wysiwyg'" class="field">
            <label>Default Content</label>
            <Editor v-model="containerEditForm.default_content" editorStyle="height: 160px" />
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'numbers'" class="field">
            <label>Default Content</label>
            <InputNumber
              :model-value="Number(containerEditForm.default_content) || 0"
              size="small" class="w-full"
              @update:model-value="(v) => (containerEditForm.default_content = String(v ?? 0))"
            />
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'datetime_format'" class="field">
            <label>Default Content</label>
            <InputText v-model="containerEditForm.default_content" size="small" class="w-full" placeholder="HH:mm:ss" />
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'image'" class="field image-field-wrapper">
            <label>Default Content</label>
            <div v-if="imageUrl" class="image-field-preview">
              <img :src="imageUrl" class="image-field-thumb" alt="selected" />
              <div class="image-field-actions">
                <Button icon="pi pi-pencil" size="small" label="Change" outlined @click="showImagePickerDialog = true" />
                <Button icon="pi pi-times" size="small" severity="danger" outlined @click="setImageData({ url: '', size: imageSize })" />
              </div>
            </div>
            <div v-else class="image-field-empty" @click="showImagePickerDialog = true">
              <i class="pi pi-image" />
              <span>Click to select an image</span>
            </div>
            <div class="image-size-row">
              <label class="image-size-label">Size (vh)</label>
              <InputNumber
                :model-value="imageSize"
                @update:model-value="(v) => setImageData({ url: imageUrl, size: v })"
                :min="0" :max="100" :step="0.5" :max-fraction-digits="2"
                suffix=" vh"
                placeholder="auto"
                style="width: 140px"
              />
            </div>
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'icon'" class="field">
            <label>Default Content</label>
            <IconPickerField :model-value="iconValue" @update:model-value="setIconData" :palette="designPreview?.default_colors ?? []" />
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'arrows'" class="field arrow-picker-wrapper">
            <label>Default Content</label>
            <div class="arrow-grid">
              <button
                v-for="arrow in ARROW_OPTIONS"
                :key="arrow.char"
                type="button"
                :class="['arrow-btn', arrowChar === arrow.char ? 'arrow-btn--selected' : '']"
                :title="arrow.label"
                @click="arrowChar = arrow.char"
              >{{ arrow.char }}</button>
            </div>
            <div class="arrow-selected-preview" v-if="arrowChar">
              Selected: <span class="arrow-preview-char">{{ arrowChar }}</span>
              <Button icon="pi pi-times" size="small" text @click="arrowChar = ''" title="Clear" />
            </div>
            <div class="arrow-size-row">
              <label class="arrow-size-label">Größe (vh)</label>
              <InputNumber v-model="arrowSize" :min="0.1" :max="50" :step="0.1" suffix=" vh" style="width: 120px" />
            </div>
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'table'" class="field">
            <label>Default Content</label>
            <div class="default-table-editor-scroll">
              <table class="default-table-editor">
                <thead>
                  <tr>
                    <th v-for="(col, ci) in tableData.columns" :key="ci">
                      <InputText
                        :model-value="col" size="small" placeholder="Header"
                        @update:model-value="(v) => updateTableHeader(ci, String(v ?? ''))"
                      />
                      <Button icon="pi pi-trash" size="small" text severity="danger" :disabled="tableData.columns.length <= 1" @click="removeTableColumn(ci)" />
                    </th>
                    <th><Button icon="pi pi-plus" size="small" text title="Add column" @click="addTableColumn" /></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, ri) in tableData.rows" :key="ri">
                    <td v-for="(cell, ci) in row" :key="ci">
                      <InputText
                        :model-value="cell" size="small"
                        @update:model-value="(v) => updateTableCell(ri, ci, String(v ?? ''))"
                      />
                    </td>
                    <td><Button icon="pi pi-trash" size="small" text severity="danger" :disabled="tableData.rows.length <= 1" @click="removeTableRow(ri)" /></td>
                  </tr>
                </tbody>
              </table>
            </div>
            <Button label="Add Row" icon="pi pi-plus" size="small" text @click="addTableRow" />
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'pretalx_table'" class="field">
            <PretalxTableFieldEditor
              :model-value="pretalxTableData"
              @update:model-value="setPretalxTableData"
            />
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'iframe'" class="field">
            <label>iFrame URL</label>
            <InputText v-model="containerEditForm.default_content" type="url" size="small" class="w-full" placeholder="https://example.com" />
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'rawhtml'" class="field">
            <label>Default HTML</label>
            <Textarea v-model="containerEditForm.default_content" rows="5" class="w-full" placeholder="<div>…</div>" />
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'marquee'" class="field">
            <label>Lauftext</label>
            <InputText :model-value="marqueeText" size="small" class="w-full" placeholder="Dein Lauftext…" @update:model-value="(v) => (marqueeText = String(v ?? ''))" />
            <div class="arrow-size-row">
              <label class="arrow-size-label">Geschwindigkeit (s)</label>
              <InputNumber
                :model-value="marqueeSpeed"
                @update:model-value="(v) => (marqueeSpeed = v)"
                :min="1" :max="300" :step="1"
                suffix=" s"
                style="width: 130px"
              />
            </div>
            <small class="hint">Niedrigere Zahl = schnellere Laufgeschwindigkeit.</small>
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'countdown'" class="field">
            <label>Target Date &amp; Time</label>
            <DatePicker v-model="countdownTargetDate" showTime hourFormat="24" showClear dateFormat="dd.mm.yy" placeholder="Pick a date" class="w-full" />
            <label class="mt-2 d-block">Format</label>
            <InputText v-model="countdownFormat" size="small" placeholder="DD:HH:mm:ss" style="width: 160px" />
            <label class="mt-2 d-block">Finished Text</label>
            <InputText v-model="countdownFinishedText" size="small" class="w-full" placeholder="Optional text shown once the countdown ends" />
            <small class="hint">Tokens: DD/D days, HH/H hours, mm/m minutes, ss/s seconds — remaining until the target.</small>
          </div>
        </template>

        <div class="selected-actions">
          <Button
            v-if="hasPendingChange(selectedContainer)"
            label="Reset to Default Position" icon="pi pi-refresh" outlined size="small"
            @click="resetContainerPosition(selectedContainer)"
          />
          <Button
            :label="selectedContainer.locked ? 'Unlock Position' : 'Lock Position'"
            :icon="selectedContainer.locked ? 'pi pi-lock' : 'pi pi-lock-open'"
            outlined size="small"
            @click="toggleContainerLock(selectedContainer)"
          />
          <Button
            :label="isSelectedPlaced ? 'Remove from Layout' : 'Add to Layout'"
            :icon="isSelectedPlaced ? 'pi pi-eject' : 'pi pi-plus'"
            outlined size="small"
            @click="toggleSelectedLayoutMembership"
          />
          <Button
            label="Delete Container" icon="pi pi-trash" severity="danger" outlined size="small"
            :disabled="!canDeleteContainer(selectedContainer)"
            :title="canDeleteContainer(selectedContainer) ? '' : 'In use — cannot delete'"
            @click="confirmDeleteContainer(selectedId)"
          />
          <Button
            v-if="hasAnyPendingChange(selectedContainer)"
            label="Revert" icon="pi pi-undo" outlined size="small"
            @click="revertContainerEdit"
          />
        </div>
          </div>
          </div>
        </template>
      </Card>
    </div>

    <MediaPickerDialog
      v-model:visible="showImagePickerDialog"
      :selected-url="containerEditForm.default_content"
      @select="onDefaultImagePicked"
    />
  </div>
</template>

<style scoped>
.layout-editor {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.editor-left-column {
  flex: 0 0 260px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: sticky;
  top: 1rem;
}

.editor-used-card,
.editor-containers-card {
  width: 100%;
}

.container-filter {
  position: relative;
  display: flex;
  align-items: center;
}

.container-filter-icon {
  position: absolute;
  left: 0.6rem;
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #888);
  pointer-events: none;
}

.container-filter :deep(input) {
  padding-left: 1.8rem;
  padding-right: 1.8rem;
}

.container-filter-clear {
  position: absolute;
  right: 0.4rem;
  width: 18px;
  height: 18px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--p-text-muted-color, #888);
  cursor: pointer;
  font-size: 0.65rem;
  border-radius: 3px;
}

.container-filter-clear:hover {
  background: rgba(0, 0, 0, 0.08);
  color: var(--p-text-color, #333);
}

.editor-right-column {
  flex: 0 0 340px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: sticky;
  top: 1rem;
  max-height: calc(100vh - 2rem);
  overflow-y: auto;
  overflow-x: hidden;
}

.editor-ratio-card,
.editor-options-card,
.editor-settings-card,
.editor-design-card {
  width: 100%;
}

.ratio-list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-bottom: 0.75rem;
}

.ratio-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0.5rem;
  border: 1px solid var(--p-content-border-color, #ddd);
  border-radius: 6px;
  cursor: pointer;
}

.ratio-row:hover {
  background: var(--p-content-hover-background, rgba(128, 128, 128, 0.1));
}

.ratio-row.active {
  border-color: var(--p-primary-color, #6366f1);
  background: var(--p-highlight-background, rgba(99, 102, 241, 0.12));
}

.ratio-name {
  flex: 1;
  font-weight: 600;
}

.ratio-add {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}

.ratio-add-select {
  flex: 1;
  min-width: 0;
}

.card-header-collapsible {
  cursor: pointer;
  user-select: none;
}

.card-header-chevron {
  margin-left: auto;
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #6b7280);
}

.editor-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.editor-canvas-wrap {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.preview-toggles {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.filter-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.filter-toggle label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.snapline-bar {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.5rem;
}

.snapline-axis-select {
  width: 100%;
}

.snapline-position-input {
  width: 100%;
}

.snapline-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.snapline-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.snapline-chip-remove {
  cursor: pointer;
  font-size: 0.7rem;
}

/* "Disable Handlerelements": show only what ends up on a screen. */
.editor-canvas.handles-hidden {
  background: none;
}

.editor-canvas.handles-hidden .canvas-snapline,
.editor-canvas.handles-hidden .drawing-rect,
.editor-canvas.handles-hidden .rect-label,
.editor-canvas.handles-hidden .rect-toolbar,
.editor-canvas.handles-hidden .lock-handle,
.editor-canvas.handles-hidden .resize-handle {
  display: none;
}

/* Rectangles stay in place and clickable (select / drag), just invisible. */
.editor-canvas.handles-hidden .editor-rect,
.editor-canvas.handles-hidden .editor-rect.selected {
  background: transparent;
  border-color: transparent;
}

.canvas-snapline {
  position: absolute;
  background: #e11d48;
  pointer-events: none;
  z-index: 4;
}

.canvas-snapline--h {
  left: 0;
  right: 0;
  height: 1px;
}

.canvas-snapline--v {
  top: 0;
  bottom: 0;
  width: 1px;
}

.editor-canvas {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: repeating-linear-gradient(
      0deg, rgba(128, 128, 128, 0.08) 0, rgba(128, 128, 128, 0.08) 1px, transparent 1px, transparent 10%
    ),
    repeating-linear-gradient(
      90deg, rgba(128, 128, 128, 0.08) 0, rgba(128, 128, 128, 0.08) 1px, transparent 1px, transparent 10%
    );
  border: 1px solid var(--p-content-border-color, #ccc);
  border-radius: 6px;
  overflow: hidden;
  touch-action: none;
  cursor: crosshair;
}

.editor-design-preview {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  border: none;
  /* Let clicks/drags fall through to the canvas underneath — the iframe is
     a separate document, so without this it would swallow the pointer
     events that drive drawing/moving/resizing containers. */
  pointer-events: none;
}

.editor-rect {
  position: absolute;
  box-sizing: border-box;
  background: rgba(37, 99, 171, 0.15);
  border: 2px solid #2563ab;
  border-radius: 4px;
  cursor: move;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-start;
  overflow: hidden;
}

.editor-rect.selected {
  background: rgba(37, 99, 171, 0.3);
  border-color: #1e3a5f;
  z-index: 2;
}

.editor-rect.drawing-rect {
  background: rgba(76, 175, 80, 0.2);
  border: 2px dashed #4caf50;
  pointer-events: none;
}

.rect-label {
  font-size: 0.7rem;
  font-weight: 600;
  color: #1e3a5f;
  background: rgba(255, 255, 255, 0.7);
  padding: 1px 4px;
  border-radius: 3px;
  margin: 3px;
  pointer-events: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: calc(100% - 6px);
}

.rect-label-id {
  font-weight: 400;
  color: #64748b;
}

.resize-handle {
  position: absolute;
  width: 14px;
  height: 14px;
  background: #2563ab;
  border: 1px solid white;
  border-radius: 2px;
  z-index: 3;
}

.resize-handle--tl {
  top: 2px;
  left: 2px;
  cursor: nwse-resize;
}

.resize-handle--br {
  bottom: 2px;
  right: 2px;
  cursor: nwse-resize;
}

.resize-handle--tr {
  top: 2px;
  right: 2px;
  cursor: nesw-resize;
}

.resize-handle--bl {
  bottom: 2px;
  /* Offset from the true bottom-left corner (left: 2px) — that spot is
     reserved for .lock-handle, which is always rendered there. */
  left: 20px;
  cursor: nesw-resize;
}

.rect-toolbar {
  position: absolute;
  top: 2px;
  right: 2px;
  display: flex;
  gap: 2px;
  z-index: 4;
}

.remove-handle,
.delete-handle {
  width: 16px;
  height: 16px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid white;
  border-radius: 2px;
  cursor: pointer;
  font-size: 0.6rem;
  line-height: 1;
  color: white;
}

.remove-handle {
  background: #c62828;
}

.remove-handle:hover {
  background: #e53935;
}

.delete-handle {
  background: #c62828;
}

.delete-handle:hover {
  background: #e53935;
}

.delete-handle.disabled {
  background: #999;
  cursor: not-allowed;
}

.lock-handle {
  position: absolute;
  bottom: 2px;
  left: 2px;
  z-index: 4;
  width: 16px;
  height: 16px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid white;
  border-radius: 2px;
  cursor: pointer;
  font-size: 0.6rem;
  line-height: 1;
  color: white;
  background: rgba(30, 58, 95, 0.7);
}

.lock-handle:hover {
  background: #1e3a5f;
}

.lock-handle--locked {
  background: #c62828;
}

.lock-handle--locked:hover {
  background: #e53935;
}

.editor-rect.locked {
  cursor: not-allowed;
  border-style: dashed;
}

.hint {
  color: var(--p-text-muted-color, #888);
  font-size: 0.75rem;
  margin: 0;
}

.dialog-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
  overflow-x: hidden;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.field label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #666);
}

/* Two columns (Top/Left, Width/Height): four did not fit the 340px right column
   and pushed Width/Height out of view. minmax(0, 1fr) + min-width: 0 let the
   number inputs shrink instead of forcing the grid wider than the card. */
.position-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem 0.5rem;
}

.position-grid .field,
.position-grid :deep(.p-inputnumber),
.position-grid :deep(.p-inputnumber-input) {
  min-width: 0;
  width: 100%;
}

.selected-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.25rem;
}

.editor-left-column h4 {
  margin: 0;
  font-size: 0.9rem;
}

.sidebar-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.sidebar-item {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--p-content-border-color, #ddd);
  border-radius: 4px;
  cursor: grab;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--p-content-background, #fff);
}

.sidebar-item.selected {
  border-color: #2563ab;
  background: rgba(37, 99, 171, 0.08);
}

.sidebar-item:active {
  cursor: grabbing;
}

.sidebar-item-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-icon-btn {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--p-text-muted-color, #666);
  cursor: pointer;
  border-radius: 3px;
  font-size: 0.7rem;
}

.sidebar-icon-btn:hover {
  background: rgba(37, 99, 171, 0.15);
  color: #2563ab;
}

.sidebar-icon-btn.disabled {
  color: var(--p-text-muted-color, #ccc);
  cursor: not-allowed;
}

.sidebar-icon-btn.disabled:hover {
  background: transparent;
  color: var(--p-text-muted-color, #ccc);
}

/* The settings card has a fixed width — a table with many/wide columns
   scrolls inside this wrapper instead of widening the card (and the page)
   sideways. */
.default-table-editor-scroll {
  width: 100%;
  overflow-x: auto;
  margin-bottom: 0.4rem;
}

.default-table-editor {
  border-collapse: collapse;
}

.default-table-editor th,
.default-table-editor td {
  min-width: 90px;
  border: 1px solid var(--p-content-border-color, #ddd);
  padding: 0.25rem;
  text-align: left;
}

.default-table-editor th {
  display: table-cell;
}

/* Image field — mirrors ContentEditView.vue's image field widget */
.image-field-wrapper {
  width: 100%;
}

.image-field-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border: 2px dashed var(--p-content-border-color, #cbd5e1);
  border-radius: 8px;
  padding: 1.5rem;
  cursor: pointer;
  color: var(--p-text-muted-color, #94a3b8);
  font-size: 0.875rem;
  transition: border-color 0.2s, background 0.2s;
}

.image-field-empty i {
  font-size: 2rem;
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
  border: 1px solid var(--p-content-border-color, #e2e8f0);
}

.image-field-actions {
  display: flex;
  gap: 0.4rem;
}

/* Arrow picker — mirrors ContentEditView.vue's arrow field widget */
.arrow-picker-wrapper {
  width: 100%;
}

.arrow-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.5rem;
  background: var(--p-content-background, #f8fafc);
  border: 1px solid var(--p-content-border-color, #e2e8f0);
  border-radius: 8px;
}

.arrow-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.4rem;
  height: 2.4rem;
  font-size: 1.4rem;
  border: 1px solid var(--p-content-border-color, #cbd5e1);
  border-radius: 6px;
  background: var(--p-content-background, white);
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
  flex-wrap: wrap;
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
  flex-wrap: wrap;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.6rem;
}

.image-size-label {
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
  white-space: nowrap;
}
</style>
