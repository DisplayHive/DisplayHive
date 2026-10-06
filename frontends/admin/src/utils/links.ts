/**
 * Route locations for cross-page links ("this screen's device", "the content
 * type of this content" …). Pages that edit in a dialog take `?edit=<id>`
 * (handled by composables/useOpenFromQuery.ts); layouts and content have
 * routes of their own.
 */
import type { RouteLocationRaw } from 'vue-router'

const edit = (path: string, id: number | string): RouteLocationRaw => ({ path, query: { edit: String(id) } })

export const links = {
  // Plain list pages — an overview, without opening an item's dialog.
  screensPage: (): RouteLocationRaw => ({ path: '/screens' }),
  screengroupsPage: (): RouteLocationRaw => ({ path: '/screengroups' }),
  contentType: (id: number) => edit('/contenttypes', id),
  screen: (id: number) => edit('/screens', id),
  device: (id: number) => edit('/devices', id),
  screengroup: (id: number) => edit('/screengroups', id),
  design: (id: number) => edit('/designs', id),
  content: (id: number): RouteLocationRaw => ({ name: 'content-edit', params: { id } }),
  layout: (id: number, containerId?: number): RouteLocationRaw => ({
    name: 'layout-edit',
    params: { id },
    ...(containerId != null ? { query: { container: String(containerId) } } : {}),
  }),
  settings: (): RouteLocationRaw => ({ path: '/settings' }),
  screensFiltered: (filter: 'find' | 'debug'): RouteLocationRaw => ({ path: '/screens', query: { filter } }),
}
