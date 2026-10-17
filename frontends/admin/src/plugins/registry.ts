import { computed, markRaw, reactive } from 'vue'
import type { FieldHandlerDef, PageDef } from './types'
import type { TourDefinition } from '../tour/types'

/** What the active plugins have registered. Reactive: switching a plugin on or off updates every dropdown and editor. */
const handlers = reactive(new Map<string, FieldHandlerDef & { pluginId: string }>())
const pages = reactive(new Map<string, PageDef & { pluginId: string }>())
const tours = reactive(new Map<string, TourDefinition & { pluginId: string }>())
/** Which plugins' admin modules have been loaded (and with which version). */
const loadedPlugins = reactive(new Map<string, string>())

export const pluginRegistry = { handlers, pages, tours, loadedPlugins }

export const addFieldHandler = (pluginId: string, def: FieldHandlerDef) => {
  handlers.set(def.id, markRaw({ ...def, pluginId }))
}
export const addPage = (pluginId: string, def: PageDef) => {
  pages.set(def.name, markRaw({ ...def, pluginId }))
}
export const addTour = (pluginId: string, def: TourDefinition) => {
  tours.set(def.id, markRaw({ ...def, pluginId }))
}

export const removePlugin = (pluginId: string) => {
  for (const map of [handlers, pages, tours] as Map<string, { pluginId: string }>[]) {
    for (const [key, value] of map) if (value.pluginId === pluginId) map.delete(key)
  }
  loadedPlugins.delete(pluginId)
}

export const fieldHandlerDef = (id: string) => handlers.get(id)

/** The options of a field-handler dropdown: "None" first (it means no input of its own), then A→Z. */
export const fieldHandlerOptions = computed(() => [
  { label: 'None', value: '' },
  ...[...handlers.values()].filter((h) => h.selectable !== false).map((h) => ({ label: h.label, value: h.id })).sort((a, b) => a.label.localeCompare(b.label)),
])
