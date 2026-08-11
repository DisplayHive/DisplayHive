import { ref } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'

/**
 * Holds the subset of admin system settings that other parts of the shell
 * (top bar, router) need to react to — currently just `hide_demo_mode`.
 * SettingsView.vue owns the full settings form independently; this store
 * exists so App.vue and the router guard can know the flag without each
 * re-implementing the socket round trip.
 */
export const useSettingsStore = defineStore('settings', () => {
  const hideDemoMode = ref(false)
  // Width (%) of the live preview column on the Content edit page — see
  // SettingsView.vue's "Content Editor" card.
  const contentEditPreviewSize = ref(35)
  // Height (vh) of the preview frame in a content row's expanded detail
  // view (ContentTable.vue) — same card, second field.
  const contentListPreviewSize = ref(20)
  const loaded = ref(false)
  let listening = false

  const applyPayload = (data: unknown) => {
    const sys = (data as { system_settings?: Record<string, unknown> } | null)?.system_settings || {}
    hideDemoMode.value = sys.hide_demo_mode === true || sys.hide_demo_mode === 'true'
    const previewSize = Number(sys.content_edit_preview_size)
    contentEditPreviewSize.value = Number.isFinite(previewSize) && previewSize > 0 ? previewSize : 35
    const listPreviewSize = Number(sys.content_list_preview_size)
    contentListPreviewSize.value = Number.isFinite(listPreviewSize) && listPreviewSize > 0 ? listPreviewSize : 20
    loaded.value = true
  }

  const fetchSettings = () => {
    const { on, emit } = useSocket()
    if (!listening) {
      on('displayhive:admin:stc:admin_settings', applyPayload)
      listening = true
    }
    emit('displayhive:admin:cts:get_admin_settings')
  }

  return { hideDemoMode, contentEditPreviewSize, contentListPreviewSize, loaded, fetchSettings }
})
