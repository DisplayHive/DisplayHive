import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSocket } from './useSocket'
import { useAuthStore } from '../stores/auth'
import { useSettingsStore } from '../stores/settings'
import { useRightsStore } from '../stores/rights'
import { useHelpStore } from '../stores/help'

/**
 * Ties the admin page's session to its socket connection (used once, by App.vue):
 *
 * - restores the session on load (and finishes an SSO login that came back in the URL),
 * - connects when there is a usable session, resets when it ends,
 * - loads settings, rights and help once connected,
 * - reloads the page after a longer outage (the server may have been updated meanwhile),
 * - drops back to the login screen when the connection is refused or given up on,
 * - leaves a hidden page (Demo Mode, Tour) when an admin turns it off.
 */
export function useSessionLifecycle() {
  const router = useRouter()
  const route = useRoute()
  const { connect, isConnected, reconnectFailed, on } = useSocket()
  const authStore = useAuthStore()
  const settingsStore = useSettingsStore()
  const rightsStore = useRightsStore()
  const helpStore = useHelpStore()

  on('connect_error', (err: unknown) => {
    const message = (err as { message?: string } | null)?.message
    if (message === 'invalid_token') {
      authStore.logout()
    }
  })

  // Socket.IO gives up retrying after its configured reconnection attempts are
  // exhausted and never tries again on its own. Without this, a prolonged
  // outage (or being logged out server-side while offline) would leave the
  // user stuck on the greyed-out "Disconnected" overlay indefinitely. Drop
  // back to the login screen instead so they have a way forward.
  watch(reconnectFailed, (failed) => {
    if (failed) {
      authStore.logout()
    }
  })

  const hasEverConnected = ref(false)
  let disconnectTimer: ReturnType<typeof setTimeout> | null = null
  let shouldReloadOnReconnect = false

  watch(isConnected, (connected) => {
    if (connected) {
      if (disconnectTimer !== null) {
        clearTimeout(disconnectTimer)
        disconnectTimer = null
      }
      if (shouldReloadOnReconnect) {
        shouldReloadOnReconnect = false
        window.location.reload()
      }
      hasEverConnected.value = true
      settingsStore.fetchSettings()
      rightsStore.fetchMyRights()
      helpStore.fetchHelp()
    } else if (hasEverConnected.value) {
      // Only reload on reconnect if the disconnect lasts longer than the grace
      // period — brief polling hiccups (~1 s) must not trigger a page reload.
      disconnectTimer = setTimeout(() => {
        disconnectTimer = null
        shouldReloadOnReconnect = true
      }, 3_000)
    }
  })

  // Connect (or reset reload tracking) whenever auth state flips. Driven off
  // the store directly rather than a `login-success` event from LoginView:
  // setSession() flips `isAuthenticated` synchronously, which Vue's reactivity
  // flush picks up and unmounts LoginView *before* the awaited login() call in
  // LoginView resumes and emits — so a child-emitted event fires after LoginView
  // is already gone and is silently dropped. Watching the store here has no
  // such race. Watches hasUsableSession, not isAuthenticated: a session that
  // still has to change its password is refused by the socket server anyway.
  watch(
    () => authStore.hasUsableSession,
    (authenticated) => {
      if (authenticated) {
        connect()
      } else {
        // Reset the "reload on reconnect" tracking on logout — an intentional
        // disconnect from logging out is not the kind of unexpected drop this
        // mechanism exists to recover from, so it must not trigger a reload the
        // next time the user connects (e.g. right after logging back in).
        hasEverConnected.value = false
        shouldReloadOnReconnect = false
        rightsStore.reset()
        if (disconnectTimer !== null) {
          clearTimeout(disconnectTimer)
          disconnectTimer = null
        }
      }
    },
  )

  watch(
    () => [settingsStore.hideDemoMode, route.name] as const,
    ([hidden, name]) => {
      if (hidden && name === 'demo') {
        router.replace('/')
      }
    },
  )

  watch(
    () => [settingsStore.hideUserTours, settingsStore.hideAdminTours, route.name] as const,
    ([hideUser, hideAdmin, name]) => {
      if (hideUser && hideAdmin && name === 'tour') {
        router.replace('/')
      }
    },
  )

  onMounted(async () => {
    // An SSO login comes back as /admin/#oidc_code=… (see stores/auth.ts).
    // Strip it via the router once its initial navigation is done — doing it
    // with history.replaceState earlier gets undone when that navigation
    // finishes and writes the original URL back.
    await router.isReady()
    const ssoHash = route.hash
    if (/oidc_(code|error)=/.test(ssoHash)) {
      await router.replace({ path: route.path, query: route.query, hash: '' })
      await authStore.consumeSsoRedirect(ssoHash)
    }
    await authStore.restore()
    if (authStore.hasUsableSession) {
      connect()
    }
  })
}
