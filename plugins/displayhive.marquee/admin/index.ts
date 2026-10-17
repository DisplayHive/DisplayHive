import type { AdminPluginHost } from '@/plugins/types'
import Editor from './Editor.vue'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({
    id: 'marquee',
    label: 'Lauftext (Marquee)',
    editor: Editor,
    blankDefault: () => JSON.stringify({ text: '', speed: 20 }),
    container: {
      unpack: (packed) => {
        try {
          const p = JSON.parse(packed || '{}')
          return { default: p.text || '', default__speed: p.speed ?? 20 }
        } catch {
          return { default: '', default__speed: 20 }
        }
      },
      pack: (f) => JSON.stringify({ text: f.default ?? '', speed: Number(f.default__speed) || 20 }),
    },
  })
}
