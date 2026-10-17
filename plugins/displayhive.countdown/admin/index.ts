import type { AdminPluginHost } from '@/plugins/types'
import Editor from './Editor.vue'

const FORMAT = 'DD:HH:mm:ss'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({
    id: 'countdown',
    label: 'Countdown',
    editor: Editor,
    blankDefault: () => JSON.stringify({ target: '', format: FORMAT, finished_text: '' }),
    container: {
      unpack: (packed) => {
        try {
          const p = JSON.parse(packed || '{}')
          return { default: p.target || '', default__format: p.format || FORMAT, default__finished_text: p.finished_text || '' }
        } catch {
          return { default: '', default__format: FORMAT, default__finished_text: '' }
        }
      },
      pack: (f) => JSON.stringify({ target: f.default ?? '', format: f.default__format || FORMAT, finished_text: f.default__finished_text ?? '' }),
    },
  })
}
