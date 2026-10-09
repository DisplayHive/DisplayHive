import { computed, inject, provide, reactive, ref, type InjectionKey } from 'vue'
import { useEditorCore, type EditorProps } from './useEditorCore'
import { useSnaplines } from './useSnaplines'
import { useDesignPreview } from './useDesignPreview'
import { useLayoutPersistence } from './useLayoutPersistence'
import { useContainerActions } from './useContainerActions'
import { useCanvasInteraction } from './useCanvasInteraction'
import { useRatioVariations } from './useRatioVariations'
import { BASE_ASPECT_RATIO } from '../useAspectRatios'
import { DEFAULT_FIELD_HANDLER_OPTIONS } from '../../utils/containerDefaultContent'
import type { ContentContainer } from '../../types/models'

/**
 * Everything the Layout editor (components/LayoutCanvasEditor.vue and the components in
 * components/layout/) shares, built from the parts in this folder:
 *
 * - useEditorCore        selection, shown ratio, the staged edits, the settings form
 * - useSnaplines         the global snaplines
 * - useDesignPreview     the Design behind the canvas, preview toggles, Container Design styles
 * - useContainerActions  add / remove / delete / create / lock containers
 * - useCanvasInteraction drag, resize and draw on the canvas
 * - useRatioVariations   aspect-ratio variations
 * - useLayoutPersistence send / discard / revert the staged edits
 *
 * The result is reactive (read `editor.selectedId`, not `.value`) and provided to the
 * components below with provideLayoutEditor().
 */
function createLayoutEditor(props: EditorProps) {
  const core = useEditorCore(props)
  const canvasEl = ref<HTMLElement | null>(null)

  const snap = useSnaplines()
  const preview = useDesignPreview(core)
  const persistence = useLayoutPersistence(core, preview)
  const actions = useContainerActions(core, canvasEl)
  const canvas = useCanvasInteraction(core, {
    canvasEl,
    snaplines: snap.snaplines,
    hideHandlerElements: () => preview.hideHandlerElements,
    createNewContainer: actions.createNewContainer,
  })
  const ratios = useRatioVariations(core)

  // Search/filter for the two sidebar lists only — matches on name (including any in-progress
  // unsaved rename) or id. The canvas is NOT filtered, so searching never hides anything placed.
  const containerFilterText = ref('')
  const matchesContainerFilter = (c: ContentContainer) => {
    const q = containerFilterText.value.trim().toLowerCase()
    if (!q) return true
    return core.contentFor(c).name.toLowerCase().includes(q) || String(c.id).includes(q)
  }

  // Right-hand cards: collapsible. Local-only UI state (never persisted); all start expanded.
  const collapsedCards = reactive<Record<string, boolean>>({})
  const toggleCard = (key: string) => {
    collapsedCards[key] = !collapsedCards[key]
  }

  return reactive({
    // shared state
    layout: computed(() => props.layout),
    selectedId: core.selectedId,
    activeRatio: core.activeRatio,
    layoutRatioList: core.layoutRatioList,
    idsOfLayoutAt: core.idsOfLayoutAt,
    BASE_ASPECT_RATIO,
    placedContainers: core.placedContainers,
    availableContainers: core.availableContainers,
    selectedContainer: core.selectedContainer,
    isSelectedPlaced: core.isSelectedPlaced,
    canDeleteContainer: core.canDeleteContainer,
    contentFor: core.contentFor,
    hasPendingChange: core.hasPendingChange,
    hasAnyPendingChange: core.hasAnyPendingChange,
    containerEditForm: core.containerEditForm,
    changeDefaultHandler: core.changeDefaultHandler,
    DEFAULT_FIELD_HANDLER_OPTIONS,
    // canvas element, bound by LayoutCanvas.vue
    canvasEl,
    // sidebar filter and cards
    containerFilterText,
    filteredPlacedContainers: computed(() => core.placedContainers.value.filter(matchesContainerFilter)),
    filteredAvailableContainers: computed(() => core.availableContainers.value.filter(matchesContainerFilter)),
    collapsedCards, toggleCard,
    // parts
    ...snap,
    preview,
    ...persistence,
    ...actions,
    ...canvas,
    ...ratios,
  })
}

export type LayoutEditor = ReturnType<typeof createLayoutEditor>

const KEY: InjectionKey<LayoutEditor> = Symbol('layoutEditor')

/** Called once by LayoutCanvasEditor; the editor's child components inject it. */
export function provideLayoutEditor(props: EditorProps): LayoutEditor {
  const editor = createLayoutEditor(props)
  provide(KEY, editor)
  return editor
}

export function useLayoutEditor(): LayoutEditor {
  const editor = inject(KEY)
  if (!editor) throw new Error('useLayoutEditor() needs provideLayoutEditor() in a parent component')
  return editor
}
