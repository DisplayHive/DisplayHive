import type { AdminPluginHost } from '@/plugins/types'
import type { FieldValue } from '@/plugins/types'
import Editor from './Editor.vue'

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({
    id: 'icon',
    label: 'Icon',
    editor: Editor,
    defaults: (name) => ({ [name]: '', [`${name}__size`]: 5 }),
    blankDefault: () => JSON.stringify({ icon: '', size: 5, color: '' }),
    container: {
      unpack: (packed): Record<string, FieldValue> => {
        try {
          const p = JSON.parse(packed || '{}')
          if (p && typeof p === 'object' && 'icon' in p) {
            return { default: p.icon || '', default__size: p.size ?? 5, default__color: p.color || '' }
          }
        } catch { /* not JSON yet */ }
        return { default: '', default__size: 5, default__color: '' }
      },
      pack: (f) => JSON.stringify({ icon: f.default ?? '', size: Number(f.default__size) || 5, color: f.default__color ?? '' }),
    },
  })
}
