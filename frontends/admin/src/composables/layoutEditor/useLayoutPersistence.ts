import { watch } from 'vue'
import { useConfirm } from 'primevue/useconfirm'
import { useAck, type Ack } from '../useAck'
import { BASE_ASPECT_RATIO } from '../useAspectRatios'
import { ALL_CONTAINER_STYLE_PROPERTIES } from '../../utils/containerFontProperties'
import { round1, type Pos } from '../../utils/layoutGeometry'
import type { ContentContainer } from '../../types/models'
import type { EditorCore } from './useEditorCore'
import type { useDesignPreview } from './useDesignPreview'

/**
 * Sending, discarding and reverting the staged edits. The Layout page calls
 * flushPendingPositions() when the Layout is saved and discardPendingPositions() when it is
 * left (both are exposed by LayoutCanvasEditor).
 */
export function useLayoutPersistence(core: EditorCore, preview: ReturnType<typeof useDesignPreview>) {
  const {
    props, selectedId, draft, contentDraft, designDraft, draftsByRatio, containerEditForm,
    stashActiveDraft, clearAllPositionDrafts, otherLayoutsUsing, geometryOf, selectedContainer,
  } = core
  const { request } = useAck()
  const confirm = useConfirm()

  // Sends every staged (drag/resize/settings-card) change to the server and clears the local
  // staging areas. If any staged container is also used by another Layout, warns about that
  // once here (not while dragging) and lets the admin back out — returns false without sending
  // anything if they cancel, or if the server refused a save (the staged edits are kept then).
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
      if (designDraft[id]) preview.containerDesignStyles = { ...preview.containerDesignStyles, [id]: designDraft[id] }
      delete contentDraft[id]
      delete designDraft[id]
    }
    clearAllPositionDrafts()
    return true
  }

  // Silently drops any staged (unsaved) changes without sending or warning about anything —
  // used when navigating away from this Layout without saving (switching layouts, starting a
  // new one). Also dismisses any "also affects layout Y" confirmation left open from an
  // unfinished Save, so switching away never leaves that dialog on screen.
  const discardPendingPositions = () => {
    clearAllPositionDrafts()
    for (const idStr of Object.keys(contentDraft)) delete contentDraft[Number(idStr)]
    for (const idStr of Object.keys(designDraft)) delete designDraft[Number(idStr)]
    confirm.close()
  }

  // Discards the staged move/resize for *c* only, snapping its rect back to the last-saved
  // (props.containers) position. Settings-card edits (name/handler/content) are left untouched.
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

  // Discards in-progress edits (position AND settings) back to the last-saved values.
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

  // Belt-and-braces: whenever the Layout being edited actually changes (however the parent got
  // here), wipe any staged edits itself rather than relying on the parent remembering to call
  // discardPendingPositions() first — so a dropdown switch can never carry over a stale "also
  // affects layout Y" warning.
  watch(() => props.layout.id, () => {
    discardPendingPositions()
    selectedId.value = null
  })

  return { flushPendingPositions, discardPendingPositions, resetContainerPosition, revertContainerEdit }
}
