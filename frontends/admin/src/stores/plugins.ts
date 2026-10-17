import { ref } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'
import router from '../router'
import { syncPlugins } from '../plugins/loader'
import type { ActivePlugin } from '../plugins/types'

/**
 * The plugins that are active on the server, and — once loaded — their admin side
 * (see plugins/loader.ts). `ready` turns true after the first load, so an editor that finds no
 * plugin for a field's handler can tell "not loaded yet" from "not active".
 */
export const usePluginsStore = defineStore('plugins', () => {
  const { emitWithAck, on } = useSocket()
  const active = ref<ActivePlugin[]>([])
  const ready = ref(false)

  const apply = async (plugins: ActivePlugin[]) => {
    active.value = plugins
    await syncPlugins(plugins, router)
    ready.value = true
  }

  on('displayhive:admin:stc:active_plugins', (data: unknown) => {
    void apply((data as { plugins?: ActivePlugin[] })?.plugins ?? [])
  })

  const fetchActive = async () => {
    try {
      const ack = await emitWithAck<{ success: boolean; plugins?: ActivePlugin[] }>('displayhive:admin:cts:get_active_plugins')
      if (ack?.success) await apply(ack.plugins ?? [])
    } catch {
      // not connected yet; the push after the next change (or the next connect) covers it
    }
  }

  const reset = () => {
    active.value = []
    ready.value = false
    void syncPlugins([], router)
  }

  return { active, ready, fetchActive, reset }
})
