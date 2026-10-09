import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useSocket } from '../useSocket'
import { BASE_ASPECT_RATIO } from '../useAspectRatios'
import { useRightsStore } from '../../stores/rights'
import { ALL_CONTAINER_STYLE_PROPERTIES } from '../../utils/containerFontProperties'
import { resolveIconPlaceholders, type PreviewContainer } from '../../utils/designPreview'
import {
  BACKDROP_OVERRIDE_CSS, buildPreviewSrcdoc, effectFragment, previewContainerHtml, type DesignPreview,
} from '../../utils/layoutPreviewDoc'
import type { EditorCore } from './useEditorCore'

/**
 * The active Design rendered behind the canvas, so containers can be positioned against how
 * the screen will actually look — in an iframe (not injected inline) so a Design's own
 * hand-written `body {...}` CSS and arbitrary HTML can't leak into or clash with this page's
 * own styles. Includes the live preview of staged container designs, the local preview toggles
 * and the Container Design styles of the Design.
 */
export function useDesignPreview(core: EditorCore) {
  const { props, activeRatio, draft, contentDraft, designDraft, placedContainers, activeContainerIds, geometryOf } = core
  const { emit, on, off } = useSocket()
  const rightsStore = useRightsStore()

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
  // combine_layout_containers in application/admin/content/helper.py) — so containers show
  // what a real screen actually falls back to instead of an approximated client-side render.
  const layoutContainerPreviews = ref<Record<string, PreviewContainer>>({})

  const handleLayoutDefaultContentPreview = (data: { layout_id?: number; aspect_ratio?: string; containers?: Record<string, PreviewContainer> }) => {
    if (data?.layout_id !== props.layout.id) return
    if ((data.aspect_ratio || BASE_ASPECT_RATIO) !== activeRatio.value) return
    layoutContainerPreviews.value = data.containers || {}
  }

  const fetchLayoutDefaultContentPreview = () => {
    if (!props.layout.id) return
    emit('displayhive:admin:cts:get_layout_default_content_preview', { layout_id: props.layout.id, aspect_ratio: activeRatio.value })
  }

  // --- Container Design: the active Design's per-container styles ------------------
  // Same DesignContainerStyle rows the Designs page edits, scoped to the selected container and
  // the active Design. Shown to users with designs.edit or contenttypes.edit_design; the backend
  // handlers enforce the same either-right gate.
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
    core.selectedId.value != null
      ? designDraft[core.selectedId.value] ?? containerDesignStyles.value[core.selectedId.value] ?? {}
      : {},
  )

  const setContainerDesignStyle = (prop: string, value: string) => {
    const id = core.selectedId.value
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

  // --- The srcdoc ---------------------------------------------------------------------
  const effectHtml = computed(() => effectFragment(designPreview.value, disableAnimationsInPreview.value))

  // Async because container HTML may contain 'icon' field placeholders that need resolving to
  // real inline SVG first (resolveIconPlaceholders — see utils/designPreview.ts for why that has
  // to happen out here rather than inside the sandboxed iframe itself).
  const designPreviewSrcdoc = ref('')

  const rebuildDesignPreviewSrcdoc = async () => {
    const p = designPreview.value
    if (!p) {
      designPreviewSrcdoc.value = ''
      return
    }
    // Backdrop (body's background-color/image/gradients) arrives already merged into p.css by
    // the backend — there's no separate field to omit it from. Overriding it back out
    // client-side is an approximation: this rule wins the cascade for whatever the Backdrop
    // itself set, but can't distinguish that from a Design's own hand-authored `body{...}`
    // background in its custom CSS, since both are flattened into the same string server-side.
    const backdropOverride = disableBackdropInPreview.value ? BACKDROP_OVERRIDE_CSS : ''
    // Mirrors what screens do: a container is drawn if it has default content or "Show when
    // empty" is on (including a still-unstaged edit of it), so its Container Design
    // background/border is visible. "Disable default content" only hides the inner content,
    // never the box itself.
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
          // Use the container's live (possibly still-unsaved) drag/resize position rather than
          // the server's last-saved one, so the preview moves with its rect on the canvas.
          const pos = draft[container.id] || geometryOf(container)
          return previewContainerHtml(container.id, pos, html)
        }),
      )
    ).join('')
    designPreviewSrcdoc.value = buildPreviewSrcdoc({
      preview: p,
      effectHtml: effectHtml.value,
      stagedCss: stagedDesignCss(),
      backdropOverride,
      containersHtml,
    })
  }

  watch(
    [designPreview, disableBackdropInPreview, disableDefaultContentInPreview, layoutContainerPreviews, effectHtml, draft, designDraft, contentDraft, () => props.containers, activeContainerIds, activeRatio],
    rebuildDesignPreviewSrcdoc,
    { deep: true },
  )

  // Re-fetch the rendered default-content preview whenever the set of placed containers or any
  // container's own default content/handler changes — covers add/remove from the Layout and
  // edits made in the settings card (props.containers is a fresh array from the parent on every
  // upd_containers broadcast, so a shallow field comparison here is enough).
  watch(
    () => [
      props.layout.id,
      activeRatio.value,
      ...placedContainers.value.map((c) => `${c.id}:${c.default_field_handler || ''}:${c.default_content || ''}`),
    ],
    fetchLayoutDefaultContentPreview,
  )

  const handleDesignPreview = (data: DesignPreview) => {
    designPreview.value = data
  }

  onMounted(() => {
    on('displayhive:admin:stc:design_preview', handleDesignPreview)
    on('displayhive:admin:stc:container_design', handleContainerDesign)
    on('displayhive:admin:stc:layout_default_content_preview', handleLayoutDefaultContentPreview)
    emit('displayhive:admin:cts:get_design_preview')
    if (canEditContainerDesign.value) emit('displayhive:admin:cts:get_container_design')
    fetchLayoutDefaultContentPreview()
  })

  onUnmounted(() => {
    off('displayhive:admin:stc:design_preview', handleDesignPreview)
    off('displayhive:admin:stc:container_design', handleContainerDesign)
    off('displayhive:admin:stc:layout_default_content_preview', handleLayoutDefaultContentPreview)
  })

  return reactive({
    designPreview, designPreviewSrcdoc,
    disableAnimationsInPreview, disableBackdropInPreview, disableDefaultContentInPreview, hideHandlerElements,
    canEditContainerDesign, containerDesignStyles, selectedContainerDesignStyles, setContainerDesignStyle,
  })
}
