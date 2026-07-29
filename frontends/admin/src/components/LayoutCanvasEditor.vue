<script setup lang="ts">
import { ref, computed, reactive, watch } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useConfirm } from 'primevue/useconfirm'
import { useToast } from 'primevue/usetoast'
import type { Layout, ContentContainer } from '../types/models'

import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import Dropdown from 'primevue/dropdown'
import Dialog from 'primevue/dialog'
import Editor from 'primevue/editor'
import MediaPickerDialog from './MediaPickerDialog.vue'

interface MediaItem { id: number; url: string }

// Same arrow set as ContentEditor.vue's field picker.
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

const { emit: socketEmit, emitWithAck } = useSocket()
const confirm = useConfirm()
const toast = useToast()

const canvasEl = ref<HTMLElement | null>(null)
const selectedId = ref<number | null>(null)

const clamp = (v: number, min: number, max: number) => Math.min(Math.max(v, min), max)
const round1 = (v: number) => Math.round(v * 10) / 10

// Containers currently assigned to this Layout, vs. everything else
// (shown in the sidebar so they can be dragged in).
const placedContainers = computed(() =>
  props.containers.filter((c) => (props.layout.container_ids || []).includes(c.id))
)
const availableContainers = computed(() =>
  props.containers.filter((c) => !(props.layout.container_ids || []).includes(c.id))
)

const selectedContainer = computed(() =>
  selectedId.value != null ? props.containers.find((c) => c.id === selectedId.value) || null : null
)

// Every OTHER Layout (besides the one open here) that also uses this
// container — since containers are shared, standalone entities, moving one
// or deleting it affects every Layout in this list too.
const otherLayoutsUsing = (containerId: number): Layout[] =>
  props.layouts.filter((l) => l.id !== props.layout.id && (l.container_ids || []).includes(containerId))

const canDeleteContainer = (c: ContentContainer) => !c.in_use && otherLayoutsUsing(c.id).length === 0

// --- Staged position overlay while dragging/resizing -----------------------
// Containers are standalone entities with one global position shared across
// every Layout that uses them. Moves/resizes are only staged here locally —
// nothing is sent to the server until flushPendingPositions() runs (called
// by the parent when the Layout dialog is saved/closed/switched), matching
// "changes save with the Layout, not on every drag".
const draft = reactive<Record<number, { top: number; left: number; width: number; height: number }>>({})

const posFor = (c: ContentContainer) => draft[c.id] || { top: c.top, left: c.left, width: c.width, height: c.height }

const rectStyle = (c: ContentContainer) => {
  const p = posFor(c)
  return {
    top: `${p.top}%`,
    left: `${p.left}%`,
    width: `${p.width}%`,
    height: `${p.height}%`,
  }
}

// Sends every staged (drag/resize/modal) position change to the server and
// clears the local staging area. Exposed so the parent can call it when the
// admin actually saves/closes the Layout dialog. If any staged container is
// also used by another Layout, warns about that once here (not while
// dragging) and lets the admin back out — returns false without sending
// anything if they cancel.
const flushPendingPositions = async (): Promise<boolean> => {
  const entries = Object.entries(draft)
  if (!entries.length) return true

  const affectedLines: string[] = []
  for (const [idStr] of entries) {
    const id = Number(idStr)
    const others = otherLayoutsUsing(id)
    if (others.length) {
      const c = props.containers.find((x) => x.id === id)
      const names = others.map((l) => l.name).join('", "')
      affectedLines.push(`"${c?.title || c?.name}" also affects layout${others.length > 1 ? 's' : ''} "${names}"`)
    }
  }

  if (affectedLines.length) {
    const proceed = await new Promise<boolean>((resolve) => {
      confirm.require({
        message: `Saving these position changes will also affect other layouts:\n${affectedLines.join('\n')}\nKeep the changes?`,
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

  await Promise.all(entries.map(([idStr, pos]) =>
    emitWithAck('displayhive:admin:cts:update_container', {
      id: Number(idStr),
      top: round1(pos.top), left: round1(pos.left), width: round1(pos.width), height: round1(pos.height),
    })
  ))
  for (const idStr of Object.keys(draft)) delete draft[Number(idStr)]
  return true
}

// Silently drops any staged (unsaved) position changes without sending or
// warning about anything — used when navigating away from this Layout
// without saving (switching layouts, starting a new one). Also dismisses any
// "also affects layout Y" confirmation left open from an unfinished Save, so
// switching away never leaves that dialog on screen.
const discardPendingPositions = () => {
  for (const idStr of Object.keys(draft)) delete draft[Number(idStr)]
  confirm.close()
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

// --- Edge snapping: moving/resizing a container snaps its edges to the
// canvas bounds and to the edges of every other container already placed.
const SNAP_THRESHOLD = 1.5 // percent

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
  const hTargets = [0, 100]
  const vTargets = [0, 100]
  for (const c of placedContainers.value) {
    if (c.id === excludeId) continue
    const p = posFor(c)
    hTargets.push(p.left, p.left + p.width)
    vTargets.push(p.top, p.top + p.height)
  }
  return { hTargets, vTargets }
}

const snapMove = (left: number, top: number, width: number, height: number, excludeId: number) => {
  const { hTargets, vTargets } = edgeTargets(excludeId)

  const leftSnap = closestWithinThreshold(left, hTargets)
  const rightSnap = closestWithinThreshold(left + width, hTargets)
  let newLeft = left
  if (leftSnap !== null && (rightSnap === null || Math.abs(left - leftSnap) <= Math.abs(left + width - rightSnap))) {
    newLeft = leftSnap
  } else if (rightSnap !== null) {
    newLeft = rightSnap - width
  }

  const topSnap = closestWithinThreshold(top, vTargets)
  const bottomSnap = closestWithinThreshold(top + height, vTargets)
  let newTop = top
  if (topSnap !== null && (bottomSnap === null || Math.abs(top - topSnap) <= Math.abs(top + height - bottomSnap))) {
    newTop = topSnap
  } else if (bottomSnap !== null) {
    newTop = bottomSnap - height
  }

  return { left: newLeft, top: newTop }
}

const snapResize = (left: number, top: number, width: number, height: number, excludeId: number) => {
  const { hTargets, vTargets } = edgeTargets(excludeId)
  const rightSnap = closestWithinThreshold(left + width, hTargets)
  const bottomSnap = closestWithinThreshold(top + height, vTargets)
  return {
    width: rightSnap !== null ? rightSnap - left : width,
    height: bottomSnap !== null ? bottomSnap - top : height,
  }
}

// --- Move / resize existing containers via pointer drag --------------------
interface DragState {
  id: number
  mode: 'move' | 'resize'
  startX: number
  startY: number
  startTop: number
  startLeft: number
  startWidth: number
  startHeight: number
}
let dragState: DragState | null = null

const onRectPointerDown = (e: PointerEvent, c: ContentContainer, mode: 'move' | 'resize') => {
  e.stopPropagation()
  e.preventDefault()
  selectedId.value = c.id
  // Start from wherever it currently is — including any not-yet-saved
  // staged position — not the last-saved value from props, or picking up an
  // already-moved container would snap it back to its original spot.
  const p = posFor(c)
  dragState = {
    id: c.id, mode, startX: e.clientX, startY: e.clientY,
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
    const snapped = snapMove(left, top, dragState.startWidth, dragState.startHeight, dragState.id)
    left = clamp(snapped.left, 0, 100 - dragState.startWidth)
    top = clamp(snapped.top, 0, 100 - dragState.startHeight)
    draft[dragState.id] = { top, left, width: dragState.startWidth, height: dragState.startHeight }
  } else {
    let width = clamp(dragState.startWidth + dxPct, 4, 100 - dragState.startLeft)
    let height = clamp(dragState.startHeight + dyPct, 4, 100 - dragState.startTop)
    const snapped = snapResize(dragState.startLeft, dragState.startTop, width, height, dragState.id)
    width = clamp(snapped.width, 4, 100 - dragState.startLeft)
    height = clamp(snapped.height, 4, 100 - dragState.startTop)
    draft[dragState.id] = { top: dragState.startTop, left: dragState.startLeft, width, height }
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
  try {
    const ack = await emitWithAck<{ ok: boolean; id?: number; error?: string }>(
      'displayhive:admin:cts:create_container',
      {
        name: `container-${n}`,
        title: `Container ${n}`,
        order: n,
        top: round1(pos.top), left: round1(pos.left), width: round1(pos.width), height: round1(pos.height),
      }
    )
    if (ack?.ok && ack.id) {
      await addContainerToLayout(ack.id)
      selectedId.value = ack.id
    } else {
      toast.add({ severity: 'error', summary: 'Create failed', detail: ack?.error || 'Unknown error', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Create failed', detail: 'Could not reach the server.', life: 4000 })
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
  const ids = props.layout.container_ids || []
  if (ids.includes(containerId)) return
  await emitWithAck('displayhive:admin:cts:update_layout', {
    id: props.layout.id,
    container_ids: [...ids, containerId],
  })
}

const removeFromLayout = async (containerId: number | null) => {
  if (containerId == null) return
  const ids = (props.layout.container_ids || []).filter((id) => id !== containerId)
  await emitWithAck('displayhive:admin:cts:update_layout', { id: props.layout.id, container_ids: ids })
  if (selectedId.value === containerId) selectedId.value = null
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
    message: `Delete container "${c.title || c.name}"?`,
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
  { label: 'Date / Time Format', value: 'datetime_format' },
  { label: 'Image', value: 'image' },
  { label: 'Link/URL', value: 'link' },
  { label: 'Long Text', value: 'textbig' },
  { label: 'Number', value: 'numbers' },
  { label: 'Short Text', value: 'textklein' },
  { label: 'Table', value: 'table' },
  { label: 'WYSIWYG', value: 'wysiwyg' },
]

const showContainerEditModal = ref(false)
const showImagePickerDialog = ref(false)
const containerEditForm = reactive({
  id: null as number | null,
  name: '', title: '',
  top: 0, left: 0, width: 20, height: 20,
  default_field_handler: '', default_content: '',
})

const onDefaultImagePicked = (item: MediaItem) => {
  containerEditForm.default_content = item.url
}

const openContainerEditModal = (c: ContentContainer) => {
  selectedId.value = c.id
  const p = posFor(c)
  containerEditForm.id = c.id
  containerEditForm.name = c.name
  containerEditForm.title = c.title || ''
  containerEditForm.top = p.top
  containerEditForm.left = p.left
  containerEditForm.width = p.width
  containerEditForm.height = p.height
  containerEditForm.default_field_handler = c.default_field_handler || ''
  containerEditForm.default_content = c.default_content || ''
  showContainerEditModal.value = true
}

const closeContainerEditModal = () => {
  showContainerEditModal.value = false
}

// Switching the handler in the dropdown re-seeds default_content with a
// sensible starting shape for that type (only on an actual user change —
// opening the modal sets containerEditForm directly, bypassing this).
const onDefaultHandlerChange = (newHandler: string) => {
  containerEditForm.default_field_handler = newHandler
  if (newHandler === 'arrows') {
    containerEditForm.default_content = JSON.stringify({ char: '', size: 48 })
  } else if (newHandler === 'table') {
    containerEditForm.default_content = JSON.stringify({ columns: ['Column 1', 'Column 2'], rows: [['', '']] })
  } else if (newHandler === 'datetime_format') {
    containerEditForm.default_content = 'HH:mm:ss'
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
    let size = 48
    try { size = JSON.parse(containerEditForm.default_content || '{}').size ?? 48 } catch { /* keep default */ }
    containerEditForm.default_content = JSON.stringify({ char: v, size })
  },
})
const arrowSize = computed({
  get: () => {
    try { return JSON.parse(containerEditForm.default_content || '{}').size ?? 48 } catch { return 48 }
  },
  set: (v: number | null) => {
    let char = ''
    try { char = JSON.parse(containerEditForm.default_content || '{}').char || '' } catch { /* keep default */ }
    containerEditForm.default_content = JSON.stringify({ char, size: v ?? 48 })
  },
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

const saveContainerEditModal = () => {
  const id = containerEditForm.id
  if (id == null) return
  const c = props.containers.find((x) => x.id === id)
  if (!c) return

  if (
    containerEditForm.name !== c.name ||
    containerEditForm.title !== (c.title || '') ||
    containerEditForm.default_field_handler !== (c.default_field_handler || '') ||
    containerEditForm.default_content !== (c.default_content || '')
  ) {
    socketEmit('displayhive:admin:cts:update_container', {
      id,
      name: containerEditForm.name,
      title: containerEditForm.title,
      default_field_handler: containerEditForm.default_field_handler,
      default_content: containerEditForm.default_content,
    })
  }

  const current = posFor(c)
  const pos = {
    top: containerEditForm.top, left: containerEditForm.left,
    width: containerEditForm.width, height: containerEditForm.height,
  }
  if (pos.top !== current.top || pos.left !== current.left || pos.width !== current.width || pos.height !== current.height) {
    stagePositionChange(id, pos)
  }

  showContainerEditModal.value = false
}

// The container being edited can come from the canvas (already placed) or
// from the sidebar (not yet part of this Layout) — the modal's assign/remove
// button reflects and toggles whichever state it's currently in.
const isSelectedPlaced = computed(() =>
  selectedId.value != null && (props.layout.container_ids || []).includes(selectedId.value)
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
    <div class="editor-main">
      <div class="editor-canvas-wrap">
        <div
          ref="canvasEl"
          class="editor-canvas"
          @pointerdown="onCanvasPointerDown"
          @dragover.prevent
          @drop.prevent="onCanvasDrop"
        >
          <div
            v-for="c in placedContainers"
            :key="c.id"
            class="editor-rect"
            :class="{ selected: selectedId === c.id }"
            :style="rectStyle(c)"
            @pointerdown="onRectPointerDown($event, c, 'move')"
          >
            <span class="rect-label">{{ c.title || c.name }} <span class="rect-label-id">#{{ c.id }}</span></span>
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
                class="edit-handle"
                title="Edit container"
                @pointerdown.stop.prevent
                @click.stop.prevent="openContainerEditModal(c)"
              >
                <i class="pi pi-pencil"></i>
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
            <div class="resize-handle" @pointerdown="onRectPointerDown($event, c, 'resize')"></div>
          </div>
          <div v-if="drawRect" class="editor-rect drawing-rect" :style="drawRectStyle"></div>
        </div>
        <p class="hint">Drag a rectangle to move it, its corner handle to resize, or click-drag empty space to draw a new container.</p>
      </div>
    </div>

    <div class="editor-sidebar">
      <Button label="New Container" icon="pi pi-plus" size="small" class="w-full" @click="addNewContainerViaButton" />
      <h4>Available Containers</h4>
      <p class="hint">Drag one onto the canvas to add it to this Layout.</p>
      <div class="sidebar-list">
        <div
          v-for="c in availableContainers"
          :key="c.id"
          class="sidebar-item"
          :class="{ selected: selectedId === c.id }"
          draggable="true"
          @dragstart="onSidebarDragStart($event, c)"
        >
          <i class="pi pi-th-large"></i>
          <span class="sidebar-item-label">{{ c.title || c.name }} <span class="hint">#{{ c.id }}</span></span>
          <button type="button" class="sidebar-icon-btn" title="Edit container" @click.stop.prevent="openContainerEditModal(c)">
            <i class="pi pi-pencil"></i>
          </button>
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
      </div>
    </div>

    <!-- Container Edit Modal -->
    <Dialog v-model:visible="showContainerEditModal" :header="`Edit Container #${containerEditForm.id}`" modal :style="{ width: '480px' }">
      <div class="dialog-content">
        <div class="field">
          <label>Name</label>
          <InputText v-model="containerEditForm.name" size="small" class="w-full" />
        </div>
        <div class="field">
          <label>Title</label>
          <InputText v-model="containerEditForm.title" size="small" class="w-full" />
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
        <p class="hint">Position changes here save with this Layout too — not immediately.</p>

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
            <div v-if="containerEditForm.default_content" class="image-field-preview">
              <img :src="containerEditForm.default_content" class="image-field-thumb" alt="selected" />
              <div class="image-field-actions">
                <Button icon="pi pi-pencil" size="small" label="Change" outlined @click="showImagePickerDialog = true" />
                <Button icon="pi pi-times" size="small" severity="danger" outlined @click="containerEditForm.default_content = ''" />
              </div>
            </div>
            <div v-else class="image-field-empty" @click="showImagePickerDialog = true">
              <i class="pi pi-image" style="font-size: 2rem; color: #94a3b8" />
              <span>Click to select an image</span>
            </div>
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
              <label class="arrow-size-label">Größe (px)</label>
              <InputNumber v-model="arrowSize" :min="8" :max="512" suffix=" px" style="width: 120px" />
            </div>
          </div>

          <div v-else-if="containerEditForm.default_field_handler === 'table'" class="field">
            <label>Default Content</label>
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
            <Button label="Add Row" icon="pi pi-plus" size="small" text @click="addTableRow" />
          </div>
        </template>

        <div class="selected-actions">
          <Button
            :label="isSelectedPlaced ? 'Remove from Layout' : 'Add to Layout'"
            :icon="isSelectedPlaced ? 'pi pi-eject' : 'pi pi-plus'"
            outlined size="small"
            @click="toggleSelectedLayoutMembership"
          />
          <Button
            label="Delete Container" icon="pi pi-trash" severity="danger" outlined size="small"
            :disabled="!selectedContainer || !canDeleteContainer(selectedContainer)"
            :title="selectedContainer && canDeleteContainer(selectedContainer) ? '' : 'In use — cannot delete'"
            @click="confirmDeleteContainer(selectedId); closeContainerEditModal()"
          />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="closeContainerEditModal" text />
        <Button label="Save" @click="saveContainerEditModal" />
      </template>
    </Dialog>

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
  border: 1px solid var(--p-surface-border, #ccc);
  border-radius: 6px;
  overflow: hidden;
  touch-action: none;
  cursor: crosshair;
}

.editor-rect {
  position: absolute;
  box-sizing: border-box;
  background: rgba(37, 99, 171, 0.15);
  border: 2px solid #2563ab;
  border-radius: 4px;
  cursor: move;
  display: flex;
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
  right: 2px;
  bottom: 2px;
  width: 14px;
  height: 14px;
  background: #2563ab;
  border: 1px solid white;
  border-radius: 2px;
  cursor: nwse-resize;
  z-index: 3;
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
.edit-handle,
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

.edit-handle {
  background: #2563ab;
}

.edit-handle:hover {
  background: #1e3a5f;
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

.hint {
  color: #888;
  font-size: 0.75rem;
  margin: 0;
}

.dialog-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.field label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #666;
}

.position-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem 0.75rem;
}

.selected-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.25rem;
}

.editor-sidebar {
  width: 240px;
  flex-shrink: 0;
  border: 1px solid var(--p-surface-border, #ddd);
  border-radius: 6px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.editor-sidebar h4 {
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
  border: 1px solid var(--p-surface-border, #ddd);
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
  color: #666;
  cursor: pointer;
  border-radius: 3px;
  font-size: 0.7rem;
}

.sidebar-icon-btn:hover {
  background: rgba(37, 99, 171, 0.15);
  color: #2563ab;
}

.sidebar-icon-btn.disabled {
  color: #ccc;
  cursor: not-allowed;
}

.sidebar-icon-btn.disabled:hover {
  background: transparent;
  color: #ccc;
}

.default-table-editor {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 0.4rem;
}

.default-table-editor th,
.default-table-editor td {
  border: 1px solid var(--p-surface-border, #ddd);
  padding: 0.25rem;
  text-align: left;
}

.default-table-editor th {
  display: table-cell;
}

/* Image field — mirrors ContentEditor.vue's image field widget */
.image-field-wrapper {
  width: 100%;
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

/* Arrow picker — mirrors ContentEditor.vue's arrow field widget */
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
</style>
