import type { AdminPluginHost } from '@/plugins/types'
import Editor from './Editor.vue'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({
    id: 'datetime_format',
    label: 'Date / Time Format',
    editor: Editor,
    defaults: (name) => ({ [name]: 'HH:mm:ss' }),
    blankDefault: () => 'HH:mm:ss',
  })
}
