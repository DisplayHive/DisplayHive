import type { Router } from 'vue-router'
import * as Vue from 'vue'
import { useFieldContext } from '../composables/fields/useFieldContext'
import { useSocket } from '../composables/useSocket'
import FieldSlot from '../components/fields/FieldSlot.vue'
import TextField from '../components/fields/TextField.vue'
import TextAreaField from '../components/fields/TextAreaField.vue'
import NumberField from '../components/fields/NumberField.vue'
import CheckboxField from '../components/fields/CheckboxField.vue'
import { addFieldHandler, addPage, addTour, pluginRegistry, removePlugin } from './registry'
import type { ActivePlugin, AdminPluginHost, AdminPluginModule } from './types'

/**
 * Loads the admin side of the plugins the server says are active, and takes it back when one is
 * switched off — while the page stays open.
 *
 * Plugins bundled with DisplayHive keep their admin code in `plugins/<id>/admin/index.ts`; the build
 * turns each into a chunk of its own that is fetched only when the plugin is active. Installed plugins
 * ship a finished ES module (`admin/index.js`) that the server hands out under
 * `/api/plugins/<id>/assets/<version>/…`; it gets the host's building blocks through `host.lib`
 * instead of bundling its own Vue.
 */
const bundled = import.meta.glob<AdminPluginModule>('@plugins/*/admin/index.ts')

const bundledLoader = (id: string) => {
  const key = Object.keys(bundled).find((k) => k.includes(`/plugins/${id}/admin/`))
  return key ? bundled[key] : undefined
}

const lib = {
  vue: Vue,
  useFieldContext,
  useSocket,
  components: { FieldSlot, TextField, TextAreaField, NumberField, CheckboxField },
}

let router: Router | null = null
let syncing: Promise<void> = Promise.resolve()

const hostFor = (pluginId: string): AdminPluginHost => ({
  pluginId,
  fieldHandlers: { add: (def) => addFieldHandler(pluginId, def) },
  pages: {
    add: (def) => {
      addPage(pluginId, def)
      if (router && !router.hasRoute(def.name)) {
        router.addRoute({ path: def.path, name: def.name, component: def.component, meta: { plugin: pluginId, right: def.right } })
        // Opened by its address (a bookmark, a reload) before the plugin was loaded: the router found no page.
        const current = router.currentRoute.value
        if (current.matched.length === 0 && current.path === def.path) void router.replace(current.fullPath)
      }
    },
  },
  tours: { add: (def) => addTour(pluginId, def) },
  lib,
})

const unregister = (pluginId: string) => {
  for (const [name, page] of pluginRegistry.pages) {
    if (page.pluginId === pluginId && router?.hasRoute(name)) router.removeRoute(name)
  }
  removePlugin(pluginId)
}

const importModule = async (plugin: ActivePlugin): Promise<AdminPluginModule | null> => {
  if (plugin.source === 'bundled') {
    const load = bundledLoader(plugin.id)
    return load ? await load() : null
  }
  if (!plugin.admin) return null
  const url = `${window.location.origin}/api/plugins/${plugin.id}/assets/${plugin.version}/${plugin.admin}`
  return (await import(/* @vite-ignore */ url)) as AdminPluginModule
}

async function loadOne(plugin: ActivePlugin) {
  try {
    const module = await importModule(plugin)
    if (module) await module.default(hostFor(plugin.id))
    pluginRegistry.loadedPlugins.set(plugin.id, plugin.version)
  } catch (error) {
    console.error(`The admin part of the plugin ${plugin.id} could not be loaded`, error)
    unregister(plugin.id)
  }
}

/** Make the registered plugins match *active*: load what is new or changed, drop what is gone. */
export function syncPlugins(active: ActivePlugin[], appRouter?: Router): Promise<void> {
  if (appRouter) router = appRouter
  syncing = syncing.then(async () => {
    const wanted = new Map(active.map((p) => [p.id, p]))
    for (const [id, version] of pluginRegistry.loadedPlugins) {
      const now = wanted.get(id)
      if (!now || now.version !== version) unregister(id)
    }
    for (const plugin of active) {
      if (!pluginRegistry.loadedPlugins.has(plugin.id)) await loadOne(plugin)
    }
  })
  return syncing
}
