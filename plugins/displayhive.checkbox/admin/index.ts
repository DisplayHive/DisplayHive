import type { AdminPluginHost } from '@/plugins/types'
import CheckboxField from '@/components/fields/CheckboxField.vue'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({ id: 'checkbox', label: 'Checkbox', editor: CheckboxField, selectable: false, defaults: (name) => ({ [name]: false }) })
}
