import type { AdminPluginHost } from '@/plugins/types'
import TextAreaField from '@/components/fields/TextAreaField.vue'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({ id: 'textbig', label: 'Long Text', editor: TextAreaField, editorProps: { rows: 3 }, titleText: true, maxLength: 5000 })
}
