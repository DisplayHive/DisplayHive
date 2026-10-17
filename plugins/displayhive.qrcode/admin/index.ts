import type { AdminPluginHost } from '@/plugins/types'
import Editor from './Editor.vue'

// A container's default is the packed values: {"content": <the link or text>, "type": …, "<key>": …}; the editor works
// on `default` (the link / text) and `default__<key>`.
const unpack = (packed: string): Record<string, unknown> => {
  try {
    const p = JSON.parse(packed || '{}')
    if (p && typeof p === 'object' && !Array.isArray(p)) {
      const out: Record<string, unknown> = { default: String(p.content ?? ''), default__type: p.type || 'url' }
      for (const [key, value] of Object.entries(p)) if (key !== 'content' && key !== 'type') out[`default__${key}`] = value
      return out
    }
  } catch { /* a plain string: the link */ }
  return { default: packed, default__type: 'url' }
}

const pack = (fields: Record<string, unknown>): string => {
  const out: Record<string, unknown> = { content: fields.default ?? '' }
  for (const [key, value] of Object.entries(fields)) {
    if (key.startsWith('default__') && value !== '' && value !== undefined && value !== null) out[key.slice('default__'.length)] = value
  }
  // An empty background is meaningful (transparent), unlike an unset one.
  if (fields.default__bg === '') out.bg = ''
  return JSON.stringify(out)
}

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({
    id: 'qrcode',
    label: 'QR code',
    editor: Editor,
    defaults: (name) => ({ [name]: '', [`${name}__type`]: 'url' }),
    blankDefault: () => JSON.stringify({ content: '', type: 'url' }),
    container: { unpack, pack },
  })
}
