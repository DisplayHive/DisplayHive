import { ref } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'

export interface HelpTopic {
  category: string
  context: string
  title: string | null
  body: string
  docs_url: string | null
}

/**
 * In-app contextual help content, fetched once per connection from the
 * backend (application/admin/help) instead of being hardcoded per view.
 * Keyed by topic key, e.g. "page.devices" — see application/help_content.py.
 */
export const useHelpStore = defineStore('help', () => {
  const topics = ref<Record<string, HelpTopic>>({})
  const loaded = ref(false)
  let listening = false

  const applyPayload = (data: Record<string, HelpTopic> | null) => {
    topics.value = data || {}
    loaded.value = true
  }

  const fetchHelp = (locale = 'en') => {
    const { on, emit } = useSocket()
    if (!listening) {
      on('displayhive:admin:stc:all_help', applyPayload)
      listening = true
    }
    emit('displayhive:admin:cts:get_all_help', { locale })
  }

  const helpFor = (key: string): HelpTopic | null => topics.value[key] || null

  return { topics, loaded, fetchHelp, helpFor }
})
