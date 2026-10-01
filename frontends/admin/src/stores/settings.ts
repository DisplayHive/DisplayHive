import { ref } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'

/**
 * Holds the subset of admin system settings that other parts of the shell
 * (top bar nav, TourView.vue) need to react to. SettingsView.vue owns the
 * full settings form independently; this store exists so those other
 * places can know a flag's value without each re-implementing the socket
 * round trip.
 */
export const useSettingsStore = defineStore('settings', () => {
  const hideDemoMode = ref(false)
  // Hides the "User" / "Admin Path" sections of the Guided Tour catalog
  // (TourView.vue) independently — see SettingsView.vue's "Dashboard" card.
  // The "Tour" nav entry itself (App.vue) only disappears once both are hidden.
  const hideUserTours = ref(false)
  const hideAdminTours = ref(false)
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
    hideUserTours.value = sys.hide_user_tours === true || sys.hide_user_tours === 'true'
    hideAdminTours.value = sys.hide_admin_tours === true || sys.hide_admin_tours === 'true'
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

  return {
    hideDemoMode,
    hideUserTours,
    hideAdminTours,
    contentEditPreviewSize,
    contentListPreviewSize,
    loaded,
    fetchSettings,
  }
})
