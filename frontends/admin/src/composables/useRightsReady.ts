import { watch } from 'vue'
import { useRightsStore } from '../stores/rights'

/**
 * Runs `callback` as soon as the caller's effective rights are known, and
 * again every time they become known after having been reset (e.g. a fresh
 * page load's rights fetch resolving, or a re-login).
 *
 * Any data fetch gated on `rightsStore.can(...)` needs this instead of a
 * plain `onMounted`: `rightsStore.loaded` starts false on every page
 * load/reconnect and only flips true once `fetchMyRights()` (kicked off
 * separately, in App.vue) resolves. A fetch that only checks `can()` once at
 * mount time can lose that race — it silently no-ops if it runs before rights
 * have loaded, and nothing retries it afterwards. This was the cause of the
 * Users and Magic Tags pages coming up empty on a direct/first load, fixed
 * only by navigating away and back (which remounts the component after
 * rights had already loaded).
 */
export function onRightsReady(callback: () => void) {
  const rightsStore = useRightsStore()
  watch(() => rightsStore.loaded, (loaded) => {
    if (loaded) callback()
  }, { immediate: true })
}
