import { useToast } from 'primevue/usetoast'
import { useSocket } from '../useSocket'
import { useAck, type Ack } from '../useAck'
import { useConfirmAction } from '../useConfirmAction'
import { round1 } from '../../utils/layoutGeometry'
import type { ContentContainer } from '../../types/models'
import type { EditorCore } from './useEditorCore'

/**
 * Changing which containers exist and which belong to this Layout (at the active ratio):
 * assign, remove, delete, create, lock, and drag in from the sidebar. These happen immediately,
 * unlike positions and settings, which are staged until the Layout is saved.
 */
export function useContainerActions(core: EditorCore, canvasEl: { value: HTMLElement | null }) {
  const { props, selectedId, activeRatio, activeContainerIds, otherLayoutsUsing, isSelectedPlaced } = core
  const { emit } = useSocket()
  const { request } = useAck()
  const { confirmDanger } = useConfirmAction()
  const toast = useToast()

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

  const toggleSelectedLayoutMembership = () => {
    if (selectedId.value == null) return
    if (isSelectedPlaced.value) removeFromLayout(selectedId.value)
    else addContainerToLayout(selectedId.value)
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
    confirmDanger({
      message: `Delete container "${c.name}"?`,
      accept: () => {
        emit('displayhive:admin:cts:delete_container', { id: containerId })
        if (selectedId.value === containerId) selectedId.value = null
      },
    })
  }

  // Locking is persisted immediately (unlike position, which stages until the Layout is saved)
  // — it's a discrete, deliberate toggle rather than a continuous drag, so there's nothing
  // useful to "stage".
  const toggleContainerLock = async (c: ContentContainer) => {
    await request('displayhive:admin:cts:update_container', { id: c.id, locked: !c.locked }, { error: 'Could not change the lock' })
  }

  // Creates a brand-new ContentContainer at the given position/size and immediately assigns it
  // to this Layout. Shared by draw-on-canvas and the sidebar's "New Container" button.
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

  // "New Container" button: adds a default-sized box in the top-left free corner instead of
  // requiring the admin to draw it by hand.
  const addNewContainerViaButton = () => {
    createNewContainer({ top: 0, left: 0, width: 20, height: 20 })
  }

  // --- Drag an existing (unassigned) container in from the sidebar ---------------------
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

    // Containers are shared, standalone entities with one global position across every Layout
    // that uses them — dropping one in here only assigns it to this Layout, it keeps whatever
    // position it already has elsewhere.
    await addContainerToLayout(containerId)
    selectedId.value = containerId
  }

  return {
    addContainerToLayout, removeFromLayout, toggleSelectedLayoutMembership, confirmDeleteContainer,
    toggleContainerLock, createNewContainer, addNewContainerViaButton, onSidebarDragStart, onCanvasDrop,
  }
}
