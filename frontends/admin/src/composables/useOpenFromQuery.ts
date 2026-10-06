import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * Opens an item's edit dialog when the page is reached through a link like
 * `/screens?edit=12` (see `links.ts`) — most admin pages edit in a dialog on
 * the list page rather than on a route of their own.
 *
 * Waits until the item has actually loaded, then calls `open(item)` once and
 * strips the query parameter, so closing the dialog or refreshing the page
 * doesn't reopen it. An unknown id is left alone. Call it *after* `open` is
 * defined (it runs immediately).
 *
 * @param items   getter for the loaded list (re-checked whenever it changes)
 * @param open    opens the item's dialog
 * @param enabled optional guard, e.g. the user's edit right
 * @param param   query parameter name (default `edit`)
 */
export function useOpenFromQuery<T extends { id: number }>(
  items: () => T[],
  open: (item: T) => void,
  enabled: () => boolean = () => true,
  param = 'edit',
) {
  const route = useRoute()
  const router = useRouter()

  watch(
    [() => route.query[param], () => items(), enabled],
    () => {
      const raw = route.query[param]
      const id = Number(Array.isArray(raw) ? raw[0] : raw)
      if (!id || !enabled()) return
      const item = items().find((i) => i.id === id)
      if (!item) return
      open(item)
      const rest = { ...route.query }
      delete rest[param]
      router.replace({ query: rest })
    },
    { immediate: true },
  )
}
