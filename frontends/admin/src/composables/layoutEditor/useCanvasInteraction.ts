import { computed, onUnmounted, ref } from 'vue'
import {
  clamp, edgeTargets as collectEdgeTargets, resizeFromCorner, snapMove, type Corner, type Pos, type Snapline,
} from '../../utils/layoutGeometry'
import type { ContentContainer } from '../../types/models'
import type { EditorCore } from './useEditorCore'

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

interface DrawState { startX: number; startY: number; top: number; left: number; width: number; height: number }

/**
 * Pointer handling on the canvas: move / resize an existing container (with edge snapping),
 * and draw a brand-new one on empty space. Moves and resizes are only staged into `draft`;
 * a drawn rectangle is handed to `createNewContainer`.
 */
export function useCanvasInteraction(
  core: EditorCore,
  deps: {
    canvasEl: { value: HTMLElement | null }
    snaplines: { value: Snapline[] }
    hideHandlerElements: () => boolean
    createNewContainer: (pos: Pos) => Promise<void>
  },
) {
  const { selectedId, draft, placedContainers, posFor } = core
  const { canvasEl } = deps

  const rectStyle = (c: ContentContainer) => {
    const p = posFor(c)
    return { top: `${p.top}%`, left: `${p.left}%`, width: `${p.width}%`, height: `${p.height}%` }
  }

  // Where an edge may snap to while moving/resizing *excludeId*: canvas bounds and centre, the
  // other placed containers (at their live positions) and the user's snaplines.
  const targetsFor = (excludeId: number) =>
    collectEdgeTargets(
      placedContainers.value.filter((c) => c.id !== excludeId).map((c) => posFor(c)),
      deps.snaplines.value,
    )

  // --- Move / resize existing containers via pointer drag ------------------------------
  let dragState: DragState | null = null

  const onRectPointerDown = (e: PointerEvent, c: ContentContainer, mode: 'move' | 'resize', corner: Corner | null = null) => {
    e.stopPropagation()
    e.preventDefault()
    selectedId.value = c.id
    if (c.locked) return
    // Start from wherever it currently is — including any not-yet-saved staged position — not
    // the last-saved value from props, or picking up an already-moved container would snap it
    // back to its original spot.
    const p = posFor(c)
    dragState = {
      id: c.id, mode, corner, startX: e.clientX, startY: e.clientY,
      startTop: p.top, startLeft: p.left, startWidth: p.width, startHeight: p.height,
    }
    window.addEventListener('pointermove', onDragPointerMove)
    window.addEventListener('pointerup', onDragPointerUp)
  }

  const onDragPointerMove = (e: PointerEvent) => {
    if (!dragState || !canvasEl.value) return
    const rect = canvasEl.value.getBoundingClientRect()
    const dxPct = ((e.clientX - dragState.startX) / rect.width) * 100
    const dyPct = ((e.clientY - dragState.startY) / rect.height) * 100

    if (dragState.mode === 'move') {
      let top = clamp(dragState.startTop + dyPct, 0, 100 - dragState.startHeight)
      let left = clamp(dragState.startLeft + dxPct, 0, 100 - dragState.startWidth)
      const snapped = snapMove(left, top, dragState.startWidth, dragState.startHeight, targetsFor(dragState.id))
      left = clamp(snapped.left, 0, 100 - dragState.startWidth)
      top = clamp(snapped.top, 0, 100 - dragState.startHeight)
      draft[dragState.id] = { top, left, width: dragState.startWidth, height: dragState.startHeight }
    } else {
      draft[dragState.id] = resizeFromCorner(
        dragState.corner ?? 'br',
        { left: dragState.startLeft, top: dragState.startTop, width: dragState.startWidth, height: dragState.startHeight },
        dxPct, dyPct, targetsFor(dragState.id),
      )
    }
  }

  const stopDragListeners = () => {
    window.removeEventListener('pointermove', onDragPointerMove)
    window.removeEventListener('pointerup', onDragPointerUp)
  }

  // The staged position stays in `draft` — nothing is sent to the server, and no cross-layout
  // warning shown, until the Layout is saved (that's where the "also affects layout Y" check
  // happens, once).
  const onDragPointerUp = () => {
    stopDragListeners()
    dragState = null
  }

  // --- Draw a brand-new container on empty canvas space ---------------------------------
  const drawRect = ref<DrawState | null>(null)
  let drawing = false
  let drawStartClientX = 0
  let drawStartClientY = 0

  const onCanvasPointerDown = (e: PointerEvent) => {
    if (deps.hideHandlerElements()) { // rects are invisible: clicking empty space only deselects, no drawing
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

  const stopDrawListeners = () => {
    window.removeEventListener('pointermove', onCanvasDrawMove)
    window.removeEventListener('pointerup', onCanvasDrawUp)
  }

  const onCanvasDrawUp = async () => {
    stopDrawListeners()
    drawing = false
    const d = drawRect.value
    drawRect.value = null
    if (!d || d.width < 3 || d.height < 3) return // treat as a stray click, not a real draw
    await deps.createNewContainer(d)
  }

  const drawRectStyle = computed(() => {
    const d = drawRect.value
    if (!d) return {}
    return { top: `${d.top}%`, left: `${d.left}%`, width: `${d.width}%`, height: `${d.height}%` }
  })

  // A page left in the middle of a gesture must not keep listening to the whole window.
  onUnmounted(() => {
    stopDragListeners()
    stopDrawListeners()
  })

  return { rectStyle, onRectPointerDown, onCanvasPointerDown, drawRect, drawRectStyle }
}
