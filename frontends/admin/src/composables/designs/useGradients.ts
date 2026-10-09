import { computed, inject, onMounted, onUnmounted, provide, reactive, ref, type InjectionKey, type Ref } from 'vue'
import { useSocket } from '../useSocket'
import { useAck } from '../useAck'
import { useConfirmAction } from '../useConfirmAction'
import type { DefaultColor, Gradient, GradientStop } from '../../types/models'
import type { DesignForm } from '../../types/designForm'
import { combinedGradientCss, gradientCssValue } from '../../utils/gradientCss'

// Gradients: a reusable library. A Design can apply several, stacked as layered
// `background-image` values (rendered ahead of the Design's own hand-written CSS — see
// upd_content.py — so a manual CSS edit still wins).

export const GRADIENT_SHAPE_OPTIONS = [
  { label: '(default: ellipse)', value: '' },
  { label: 'Circle', value: 'circle' },
  { label: 'Ellipse', value: 'ellipse' },
]
export const GRADIENT_SIZE_OPTIONS = [
  { label: '(default: farthest-corner)', value: '' },
  { label: 'Closest Side', value: 'closest-side' },
  { label: 'Closest Corner', value: 'closest-corner' },
  { label: 'Farthest Side', value: 'farthest-side' },
  { label: 'Farthest Corner', value: 'farthest-corner' },
]

const blankGradientForm = () => ({
  id: null as number | null,
  name: 'New Gradient',
  type: 'linear' as 'linear' | 'radial' | 'conic',
  repeating: false,
  angle: 180,
  shape: '',
  size: '',
  position_x: 50,
  position_y: 50,
  stops: [
    { color: 'ffffff', position: 0, opacity: 100 },
    { color: '000000', position: 100, opacity: 100 },
  ] as GradientStop[],
})

function createGradients(form: Ref<DesignForm>) {
  const { on, off, emit } = useSocket()
  const { request } = useAck()
  const { confirmDanger } = useConfirmAction()

  const gradients = ref<Gradient[]>([])

  const handleGradientsList = (data: { data?: Gradient[] }) => {
    gradients.value = data?.data || []
  }

  const handleDesignGradients = (data: { design_id?: number; gradient_ids?: number[] }) => {
    if (!data || data.design_id !== form.value.id) return
    form.value.gradient_ids = data.gradient_ids || []
  }

  onMounted(() => {
    on('displayhive:admin:stc:upd_gradients', handleGradientsList)
    on('displayhive:admin:stc:design_gradients', handleDesignGradients)
    emit('displayhive:admin:cts:get_gradients')
  })
  onUnmounted(() => {
    off('displayhive:admin:stc:upd_gradients', handleGradientsList)
    off('displayhive:admin:stc:design_gradients', handleDesignGradients)
  })

  /** Ask for the ids of the gradients the Design applies (the answer lands in `form.gradient_ids`). */
  const loadForDesign = (designId: number) => emit('displayhive:admin:cts:get_design_gradients', { design_id: designId })

  // A stop's `ref` only resolves while editing the same Design it was picked
  // in — a Gradient is a shared library entity, so `stop.color` (the fallback
  // captured at pick time) is what's used everywhere else. Mirrors
  // gradient_css_value()'s _stop_color() server-side.
  const resolveStopColorHex = (stop: GradientStop): string => {
    if (stop.ref && stop.ref.design_id === form.value.id) {
      const c = form.value.default_colors.find((c) => c.id === stop.ref!.color_id)
      if (c) return c.hex.replace(/^#/, '')
    }
    return stop.color
  }

  const cssFor = (g: Parameters<typeof gradientCssValue>[0]) => gradientCssValue(g, resolveStopColorHex)
  const combinedCss = (list: Gradient[]) => combinedGradientCss(list, resolveStopColorHex)

  const selectedGradients = computed(() =>
    form.value.gradient_ids
      .map((id) => gradients.value.find((g) => g.id === id))
      .filter((g): g is Gradient => !!g),
  )

  const setDesignGradients = (gradientIds: number[] | undefined) => {
    form.value.gradient_ids = gradientIds || []
    if (!form.value.id) return
    void request(
      'displayhive:admin:cts:set_design_gradients',
      { design_id: form.value.id, gradient_ids: form.value.gradient_ids },
      { error: 'Could not save the gradients' },
    )
  }

  // Manage (list) dialog
  const showManageDialog = ref(false)

  // Create/edit dialog
  const showEditDialog = ref(false)
  const isNew = ref(false)
  const editForm = ref(blankGradientForm())

  const openNew = () => {
    isNew.value = true
    editForm.value = blankGradientForm()
    showEditDialog.value = true
  }

  const openEdit = (g: Gradient) => {
    isNew.value = false
    editForm.value = {
      id: g.id, name: g.name, type: g.type, repeating: g.repeating, angle: g.angle,
      shape: g.shape || '', size: g.size || '', position_x: g.position_x, position_y: g.position_y,
      stops: g.stops.map((s) => ({ ...s, color: s.color.replace(/^#/, ''), opacity: s.opacity ?? 100 })),
    }
    showEditDialog.value = true
  }

  const addStop = () => {
    editForm.value.stops.push({ color: '888888', position: 50, opacity: 100 })
  }

  const removeStop = (idx: number) => {
    if (editForm.value.stops.length <= 2) return
    editForm.value.stops.splice(idx, 1)
  }

  const setStopColorRef = (stop: GradientStop, color: DefaultColor) => {
    stop.color = color.hex.replace(/^#/, '')
    stop.ref = form.value.id ? { design_id: form.value.id, color_id: color.id } : undefined
  }

  const editPreview = computed(() => cssFor(editForm.value))

  const saveEdit = async () => {
    const payload = {
      ...editForm.value,
      stops: editForm.value.stops.map((s) => ({ ...s, color: `#${s.color}` })),
    }
    const event = isNew.value ? 'displayhive:admin:cts:create_gradient' : 'displayhive:admin:cts:update_gradient'
    const ack = await request(event, payload, {
      success: isNew.value ? 'Gradient created' : 'Gradient updated',
      error: 'Could not save the gradient',
    })
    if (ack) showEditDialog.value = false
  }

  const remove = (g: Gradient) => {
    confirmDanger({
      message: `Delete gradient "${g.name}"?`,
      accept: async () => {
        await request('displayhive:admin:cts:delete_gradient', { id: g.id }, { success: 'Gradient deleted', error: 'Could not delete the gradient' })
      },
    })
  }

  // Copy: duplicates a Gradient's type/angle/position and stops (including
  // each stop's Default Color `ref`, same as any other Design using it —
  // see resolveStopColorHex's doc comment) as a brand new, independent one.
  const showCopyDialog = ref(false)
  const copySource = ref<Gradient | null>(null)
  const copyName = ref('')

  const openCopy = (g: Gradient) => {
    copySource.value = g
    copyName.value = `Copy of ${g.name}`
    showCopyDialog.value = true
  }

  const executeCopy = async () => {
    const source = copySource.value
    const name = copyName.value.trim()
    if (!source || !name) return
    const ack = await request('displayhive:admin:cts:create_gradient', {
      name,
      type: source.type,
      repeating: source.repeating,
      angle: source.angle,
      shape: source.shape,
      size: source.size,
      position_x: source.position_x,
      position_y: source.position_y,
      stops: source.stops,
    }, { success: `"${name}" created`, error: 'Could not copy the gradient' })
    if (ack) showCopyDialog.value = false
  }

  // Reactive, so a template reads `gradients.showEditDialog` (not `.value`) and can v-model it.
  return reactive({
    gradients, palette: computed(() => form.value.default_colors), selectedGradients, loadForDesign, resolveStopColorHex, cssFor, combinedCss, setDesignGradients,
    showManageDialog,
    showEditDialog, isNew, editForm, editPreview, openNew, openEdit, addStop, removeStop, setStopColorRef, saveEdit, remove,
    showCopyDialog, copyName, openCopy, executeCopy,
  })
}

export type GradientsApi = ReturnType<typeof createGradients>

const KEY: InjectionKey<GradientsApi> = Symbol('designGradients')

/** Called once by the page that owns the Design form; the panels and dialogs below inject it. */
export function provideGradients(form: Ref<DesignForm>): GradientsApi {
  const api = createGradients(form)
  provide(KEY, api)
  return api
}

export function useGradients(): GradientsApi {
  const api = inject(KEY)
  if (!api) throw new Error('useGradients() needs provideGradients() in a parent component')
  return api
}
