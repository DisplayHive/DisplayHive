import type { AdminPluginHost } from '@/plugins/types'
import NumberField from '@/components/fields/NumberField.vue'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({ id: 'numbers', label: 'Number', editor: NumberField, defaults: (name) => ({ [name]: 0 }) })
}
