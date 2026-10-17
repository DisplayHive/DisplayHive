import type { AdminPluginHost } from '@/plugins/types'
import TextField from '@/components/fields/TextField.vue'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({ id: 'textklein', label: 'Short Text', editor: TextField, inlineEdit: 'input', titleText: true, maxLength: 255 })
}
