import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'
import type { Screen } from '../types/models'

export const useScreensStore = defineStore('screens', () => {
  const { on, off, emit } = useSocket()

  const screens = ref<Screen[]>([])
  const loading = ref(false)

  const handleScreenList = (data: { data?: Screen[] }) => {
    screens.value = data?.data || []
    loading.value = false
  }

  off('displayhive:admin:stc:upd_admin_screen', handleScreenList)
  on('displayhive:admin:stc:upd_admin_screen', handleScreenList)

  const fetch = () => {
    loading.value = true
    emit('displayhive:admin:cts:get_admin_screen')
  }

  const createScreen = (payload: {
    name: string
    width?: string | null
    height?: string | null
  }) => {
    emit('displayhive:screens:cts:create_screen', payload)
  }

  const renameScreen = (payload: {
    id: number
    old_name: string
    new_name: string
    screengroup_ids: number[]
  }) => {
    emit('displayhive:screens:cts:rename_screen', payload)
  }

  const deleteScreen = (screenId: number) => {
    emit('displayhive:screens:cts:delete_screen', { screen_id: screenId })
  }

  const toggleDebug = (screenId: number, debug: boolean) => {
    const screen = screens.value.find((s) => s.id === screenId)
    if (screen) screen.debug = debug
    emit('displayhive:screens:cts:toggle_debug', { screen_id: screenId, debug })
  }

  const reloadScreen = (name: string) => {
    emit('displayhive:screens:cts:reload_screen', { name })
  }

  const reloadAll = () => {
    emit('displayhive:screens:cts:reload_all_screens', {})
  }

  const resetScreenSize = (screenId: number) => {
    emit('displayhive:screens:cts:reset_screen_size', { screen_id: screenId })
  }

  const toggleMonitoring = (screenId: number) => {
    const screen = screens.value.find((s) => s.id === screenId)
    if (screen) screen.monitoring_enabled = !screen.monitoring_enabled
    emit('displayhive:screens:cts:toggle_monitoring', { screen_id: screenId })
  }

  const monitoredScreens = computed(() => screens.value.filter((s) => s.monitoring_enabled !== false))
  const onlineCount = computed(() => monitoredScreens.value.filter((s) => s.attached_device?.is_online).length)
  const offlineCount = computed(() => monitoredScreens.value.filter((s) => !s.attached_device?.is_online).length)
  const screensInDebug = computed(() => monitoredScreens.value.filter((s) => s.debug === true).length)

  return {
    screens,
    monitoredScreens,
    loading,
    fetch,
    createScreen,
    renameScreen,
    deleteScreen,
    toggleDebug,
    reloadScreen,
    reloadAll,
    resetScreenSize,
    toggleMonitoring,
    onlineCount,
    offlineCount,
    screensInDebug,
  }
})
