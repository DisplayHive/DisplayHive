import { onMounted, onUnmounted, ref } from 'vue'
import { useSocket } from '../useSocket'
import { useAck } from '../useAck'
import { clamp, type Snapline } from '../../utils/layoutGeometry'

/**
 * Snaplines are global (shared across every Layout, not scoped to this one) — loaded once
 * here and kept live via the broadcast every save triggers, so two admins editing different
 * Layouts at once stay in sync. They are global settings (application/admin/layouts/
 * sockethandlers.py stores them via SystemSetting), so add/remove just replace-and-persist the
 * whole list; `snaplines` itself is updated by the server's broadcast once the change is
 * committed, not optimistically — one source of truth for every open Layout editor.
 */
export function useSnaplines() {
  const { on, off, emit } = useSocket()
  const { request } = useAck()

  const snaplines = ref<Snapline[]>([])
  const newSnaplineAxis = ref<'h' | 'v'>('h')
  const newSnaplinePosition = ref<number>(50)

  const handleSnaplines = (data: { snaplines?: Snapline[] }) => {
    snaplines.value = data?.snaplines || []
  }

  onMounted(() => {
    on('displayhive:admin:stc:layout_snaplines', handleSnaplines)
    emit('displayhive:admin:cts:get_layout_snaplines')
  })
  onUnmounted(() => {
    off('displayhive:admin:stc:layout_snaplines', handleSnaplines)
  })

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

  return { snaplines, newSnaplineAxis, newSnaplinePosition, addSnapline, removeSnapline }
}
