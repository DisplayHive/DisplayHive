import type { AdminPluginHost } from '@/plugins/types'
import Editor from './Editor.vue'

// A container's default is the packed {url, size, fit, mode, tags}; older ones are just the URL.
const unpack = (packed: string): Record<string, unknown> => {
  try {
    const p = JSON.parse(packed)
    if (p && typeof p === 'object' && 'url' in p) {
      return {
        default: p.url || '',
        default__size: p.size || '',
        default__fit: p.fit || '',
        default__image_mode: p.mode || 'single',
        default__image_tags: Array.isArray(p.tags) ? p.tags : [],
      }
    }
  } catch { /* a plain URL */ }
  return { default: packed }
}

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({
    id: 'image',
    label: 'Image',
    editor: Editor,
    blankDefault: () => JSON.stringify({ url: '', size: null }),
    container: {
      unpack,
      pack: (f) => JSON.stringify({
        url: f.default ?? '',
        size: f.default__size ? Number(f.default__size) : null,
        fit: f.default__fit || undefined,
        mode: f.default__image_mode && f.default__image_mode !== 'single' ? f.default__image_mode : undefined,
        tags: Array.isArray(f.default__image_tags) && f.default__image_tags.length ? f.default__image_tags : undefined,
      }),
    },
  })
}
