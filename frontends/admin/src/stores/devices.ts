import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'
import type { Device } from '../types/models'

export const useDevicesStore = defineStore('devices', () => {
  const { on, emit, emitWithAck } = useSocket()

  const devices = ref<Device[]>([])
  const loading = ref(false)

  const handleDeviceList = (data: { devices?: Device[] }) => {
    devices.value = data?.devices || []
    loading.value = false
  }

  on('displayhive:devices:stc:devices_list', handleDeviceList)
  on('displayhive:devices:stc:devices_upd_devicelist', handleDeviceList)

  const fetch = () => {
    loading.value = true
    emit('displayhive:devices:cts:get_devices')
  }

  const findDevice = (deviceId: number) => {
    emit('displayhive:devices:cts:find_device', { device_id: deviceId })
  }

  const adoptDevice = (payload: { token: string; device_name: string; screen_name: string | null }) => {
    return new Promise<{ success: boolean; error?: string }>((resolve, reject) => {
      let timedOut = false
      const t = setTimeout(() => {
        timedOut = true
        reject(new Error('ack timeout'))
      }, 10000)

      emitWithAck<{ success: boolean; error?: string }>('displayhive:devices:cts:approve_registration', payload)
        .then((res) => {
          if (timedOut) return
          clearTimeout(t)
          resolve(res)
        })
        .catch((err) => {
          if (timedOut) return
          clearTimeout(t)
          reject(err)
        })
    })
  }

  const onlineDevices = computed(() => devices.value.filter((d) => d.is_online))
  const activeDevices = computed(() => devices.value.filter((d) => d.is_active))

  return {
    devices,
    loading,
    fetch,
    findDevice,
    adoptDevice,
    onlineDevices,
    activeDevices,
  }
})
