import { addFieldHandler, addPage, addTour } from './registry'
import type { AdminPluginHost, AdminPluginModule } from './types'

const modules = import.meta.glob<AdminPluginModule>('@plugins/*/admin/index.ts', { eager: true })

/** For tests: register the admin side of every bundled plugin (what the loader does for the active ones). */
export function registerBundledPlugins(): void {
  for (const [path, module] of Object.entries(modules)) {
    const pluginId = /\/plugins\/([^/]+)\/admin\//.exec(path)![1]
    const host: AdminPluginHost = {
      pluginId,
      fieldHandlers: { add: (def) => addFieldHandler(pluginId, def) },
      pages: { add: (def) => addPage(pluginId, def) },
      tours: { add: (def) => addTour(pluginId, def) },
      lib: {},
    }
    void module.default(host)
  }
}
