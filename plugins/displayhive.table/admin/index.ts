import type { AdminPluginHost } from '@/plugins/types'
import Editor from './Editor.vue'

const blank = () => JSON.stringify({ columns: ['Column 1', 'Column 2'], rows: [['', '']] })

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({
    id: 'table',
    label: 'Table',
    editor: Editor,
    defaults: (name) => ({ [name]: blank() }),
    blankDefault: blank,
  })
}
