import type { AdminPluginHost } from '@/plugins/types'
import Editor from './Editor.vue'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({
    id: 'arrows',
    label: 'Arrow',
    editor: Editor,
    defaults: (name) => ({ [name]: '', [`${name}_size`]: 5 }),
    blankDefault: () => JSON.stringify({ char: '', size: 5 }),
    container: {
      unpack: (packed) => {
        try {
          const p = JSON.parse(packed || '{}')
          return { default: p.char || '', default_size: p.size ?? 5 }
        } catch {
          return { default: '', default_size: 5 }
        }
      },
      pack: (f) => JSON.stringify({ char: f.default ?? '', size: Number(f.default_size) || 5 }),
    },
  })
}
