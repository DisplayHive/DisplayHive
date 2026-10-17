import type { AdminPluginHost } from '@/plugins/types'
import type { PageDef } from '@/plugins/types'
import Editor from './Editor.vue'
import { blankPretalxTableValue } from './pretalxTable'
import { pretalxTour } from './tour'

// The packed default is the table value ({url, type, …}); the editor works on `default`, `default__type` …
const unpack = (packed: string): Record<string, unknown> => {
  let parsed: Record<string, unknown> = {}
  try { parsed = JSON.parse(packed || '{}') } catch { /* blank */ }
  const value = { ...blankPretalxTableValue(), ...parsed } as Record<string, unknown>
  const out: Record<string, unknown> = {}
  for (const [key, v] of Object.entries(value)) out[key === 'url' ? 'default' : `default__${key}`] = v
  return out
}

const pack = (fields: Record<string, unknown>): string => {
  const value: Record<string, unknown> = {}
  for (const key of Object.keys(blankPretalxTableValue())) value[key] = fields[key === 'url' ? 'default' : `default__${key}`]
  return JSON.stringify(value)
}

const page: PageDef = {
  path: '/pretalx',
  name: 'pretalx',
  component: () => import('./View.vue'),
  title: 'Pretalx',
  icon: 'pi pi-calendar',
  right: 'displayhive.pretalx.page',
  menu: { group: 'Integrations', label: 'Pretalx' },
}

export default (host: AdminPluginHost) => {
  host.fieldHandlers.add({
    id: 'pretalx_table',
    label: 'Pretalx Table',
    editor: Editor,
    blankDefault: () => JSON.stringify(blankPretalxTableValue()),
    container: { unpack, pack },
  })
  host.pages.add(page)
  host.tours.add(pretalxTour)
}
