import { useContentStore } from './content'
import { useDevicesStore } from './devices'
import { useHelpStore } from './help'
import { useMediaStore } from './media'
import { useRightsStore } from './rights'
import { useScreengroupsStore } from './screengroups'
import { useScreensStore } from './screens'
import { useSettingsStore } from './settings'

/**
 * Empty every store that holds data fetched for a session. Called when the session ends (logout,
 * expiry, sign-out in another tab): the stores keep what the server sent under the previous
 * account's rights, and the next person to sign in at this tab must not see it — not even for the
 * moment before their own fetch answers, and not at all for what their rights never fetch (the
 * server sends nothing for a page they may not open, so the old numbers would simply stay).
 *
 * A store that holds session data adds its `reset()` here.
 */
export function resetSessionStores(): void {
  useContentStore().reset()
  useDevicesStore().reset()
  useHelpStore().reset()
  useMediaStore().reset()
  useRightsStore().reset()
  useScreengroupsStore().reset()
  useScreensStore().reset()
  useSettingsStore().reset()
}
