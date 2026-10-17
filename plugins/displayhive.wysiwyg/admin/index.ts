import type { AdminPluginHost } from '@/plugins/types'
import Editor from './Editor.vue'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({ id: 'wysiwyg', label: 'WYSIWYG', editor: Editor, titleText: true, maxLength: 255 })
}
