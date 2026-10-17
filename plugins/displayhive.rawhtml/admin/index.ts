import type { AdminPluginHost } from '@/plugins/types'
import TextAreaField from '@/components/fields/TextAreaField.vue'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({ id: 'rawhtml', label: 'HTML (raw)', editor: TextAreaField, inlineEdit: 'textarea', editorProps: { rows: 5, html: true } })
}
