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

  const monitoredScreens = computed(() => screens.value.filter((s) => s.monitoring_enabled !== false))
  const onlineCount = computed(() => monitoredScreens.value.filter((s) => s.attached_device?.is_online).length)
  const offlineCount = computed(() => monitoredScreens.value.filter((s) => !s.attached_device?.is_online).length)
  const screensInDebug = computed(() => monitoredScreens.value.filter((s) => s.debug === true).length)

  return {
    screens,
    monitoredScreens,
    loading,
    fetch,
    onlineCount,
    offlineCount,
    screensInDebug,
  }
})
