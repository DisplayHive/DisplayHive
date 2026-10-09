import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAck } from '../useAck'
import { useConfirmAction } from '../useConfirmAction'
import { BASE_ASPECT_RATIO, cssAspectRatio } from '../useAspectRatios'
import { sameShape } from '../../utils/layoutGeometry'
import type { EditorCore } from './useEditorCore'

/**
 * Switching between, adding and removing the Layout's aspect-ratio variations, and the canvas
 * shape that follows the shown ratio. Also selects a container named in the URL
 * (`?container=<id>`, e.g. from a content type's field), switching to a variation that has it.
 */
export function useRatioVariations(core: EditorCore) {
  const {
    props, selectedId, draft, draftsByRatio, activeRatio, layoutRatioList, idsOfLayoutAt, activeContainerIds,
    designRatios, stashActiveDraft, selectedContainer, seedEditForm,
  } = core
  const { request } = useAck()
  const { confirmDanger } = useConfirmAction()

  const selectRatio = (ratio: string) => {
    if (ratio === activeRatio.value) return
    // Park this ratio's staged positions and bring back the target's.
    stashActiveDraft()
    for (const idStr of Object.keys(draft)) delete draft[Number(idStr)]
    Object.assign(draft, draftsByRatio[ratio] ?? {})
    delete draftsByRatio[ratio]
    activeRatio.value = ratio
  }

  // The selection / settings card follow the ratio: a container that isn't part of the newly
  // shown variation is deselected, otherwise its card is re-seeded with that ratio's position.
  watch(activeRatio, () => {
    const c = selectedContainer.value
    if (!c) return
    if (!activeContainerIds.value.includes(c.id)) selectedId.value = null
    else seedEditForm(c)
  })

  // A variation just created (or removed, possibly from another tab): once the layout
  // broadcast arrives, jump to the new one / fall back to the base.
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
    // Set before asking: the server pushes the changed Layout before it answers, and that push
    // is what makes the new variation appear and be selected (see the watcher above).
    pendingRatio.value = ratio
    const ack = await request('displayhive:admin:cts:create_layout_variation', {
      layout_id: props.layout.id, aspect_ratio: ratio,
    }, { error: 'Could not add variation' })
    if (ack) newVariationRatio.value = null
    else pendingRatio.value = null
  }

  const confirmDeleteVariation = (ratio: string) => {
    confirmDanger({
      message: `Remove the ${ratio} variation of this layout? Its container selection is dropped; container positions at ${ratio} are kept.`,
      header: 'Remove variation',
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

  // Reached via a link like /layouts/<id>/edit?container=<cid>: select that container,
  // switching to the variation that has it if it isn't in the base. The parameter is stripped
  // afterwards.
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

  return { selectRatio, newVariationRatio, addableRatios, addVariation, confirmDeleteVariation, canvasStyle }
}
