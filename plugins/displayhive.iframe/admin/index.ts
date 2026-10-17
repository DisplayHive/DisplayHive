import type { AdminPluginHost } from '@/plugins/types'
import TextField from '@/components/fields/TextField.vue'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({ id: 'iframe', label: 'iFrame', editor: TextField, editorProps: { type: 'url' } })
}
