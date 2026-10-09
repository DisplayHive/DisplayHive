import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'

// The login itself is an HttpOnly cookie that only the server can read or write
// (application/session.py): no script in the page — an XSS bug included — can get at
// it. What this store keeps in localStorage is NOT a credential, just a hint that the
// browser has a session: who it is, when it ends, and whether it is an impersonation.
// The server stays the source of truth: restore() asks it on every start.
const SESSION_HINT_KEY = 'displayhive_admin_session'
// Cached copy of the DB-backed preferences, so the theme can be applied
// before login()/restore() completes its round-trip (avoids a flash of the
// wrong theme). The DB stays the source of truth; this is just a paint cache.
const PREFERENCES_STORAGE_KEY = 'displayhive_admin_preferences'
// Mirrors the server's must_change_password flag for the current session, so
// other tabs (via the `storage` event) know not to connect a socket the
// server would refuse anyway. The server stays the source of truth.
const MUST_CHANGE_PASSWORD_STORAGE_KEY = 'displayhive_admin_must_change_password'
// Keys of earlier versions, which kept the JWT itself in localStorage. Removed on
// start: a token left there is readable by any script on the page.
const LEGACY_KEYS = [
  'displayhive_admin_token',
  'displayhive_admin_username',
  'displayhive_admin_original_token',
  'displayhive_admin_original_username',
]

/** Sent with every request that changes something: the server accepts a cookie session
 * only together with this header (and a matching Origin) — see csrf_problem(). */
const REQUEST_HEADER = { 'X-DisplayHive-Request': '1' }

export type UserPreferences = { theme?: 'light' | 'dark' | 'system' }

type SessionHint = { username: string; expiresAt: number | null; impersonator: string | null }

type SessionInfo = {
  username?: string
  expires_at?: string | null
  impersonator_username?: string | null
  preferences?: UserPreferences
}

const readCachedPreferences = (): UserPreferences => {
  try {
    const raw = localStorage.getItem(PREFERENCES_STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

const readHint = (raw: string | null): SessionHint | null => {
  try {
    const parsed = raw ? JSON.parse(raw) : null
    if (parsed && typeof parsed.username === 'string') {
      return {
        username: parsed.username,
        expiresAt: typeof parsed.expiresAt === 'number' ? parsed.expiresAt : null,
        impersonator: typeof parsed.impersonator === 'string' ? parsed.impersonator : null,
      }
    }
  } catch {
    // fall through: no usable hint
  }
  return null
}

const parseExpiry = (value?: string | null): number | null => {
  const ms = value ? Date.parse(value) : NaN
  return Number.isFinite(ms) ? ms : null
}

/**
 * Admin authentication store: who is signed in, when the session ends, and the
 * login/logout calls against the backend.
 *
 * The hint is kept in localStorage (rather than sessionStorage) deliberately so that
 * logging in or out in one tab/window is reflected in every other open tab (via the
 * native `storage` event, below) instead of each tab carrying its own independent
 * session — the cookie is shared by all tabs anyway. The session expires on its own
 * (the backend issues it for 12 h, see application/auth.py TOKEN_TTL) and
 * `scheduleExpiry` mirrors that client-side so a stale tab logs itself out proactively.
 */
export const useAuthStore = defineStore('auth', () => {
  LEGACY_KEYS.forEach((key) => localStorage.removeItem(key))

  const hint = readHint(localStorage.getItem(SESSION_HINT_KEY))
  const signedIn = ref(!!hint)
  const username = ref<string | null>(hint?.username ?? null)
  const expiresAt = ref<number | null>(hint?.expiresAt ?? null)
  // Who is really driving the session while impersonating (the account that started it).
  const originalUsername = ref<string | null>(hint?.impersonator ?? null)
  const preferences = ref<UserPreferences>(readCachedPreferences())
  // Starts true whenever a session hint is present so the app doesn't flash the
  // login form while `restore()` confirms with the server that it is still valid.
  const restoring = ref(!!hint)
  // Set when an SSO login came back with an error (see consumeSsoRedirect);
  // LoginView shows it.
  const ssoError = ref<string | null>(null)

  const isAuthenticated = computed(() => signedIn.value)
  // While set, the server rejects this session everywhere except the
  // password-change routes (see application/auth.py user_from_token), so App.vue
  // shows ChangePasswordView instead of the app and doesn't connect the socket.
  const mustChangePassword = ref(localStorage.getItem(MUST_CHANGE_PASSWORD_STORAGE_KEY) === '1')
  const hasUsableSession = computed(() => isAuthenticated.value && !mustChangePassword.value)
  const isImpersonating = computed(() => !!originalUsername.value)

  let expiryTimer: ReturnType<typeof setTimeout> | null = null

  const clearExpiryTimer = () => {
    if (expiryTimer !== null) {
      clearTimeout(expiryTimer)
      expiryTimer = null
    }
  }

  // Auto-logout when the session's own end passes, so an idle tab doesn't linger on
  // a dead session. setTimeout is capped at ~24.8 days internally; the 12h session
  // is well within that, so no chunking is needed here.
  const scheduleExpiry = () => {
    clearExpiryTimer()
    if (expiresAt.value === null) return
    const delay = expiresAt.value - Date.now()
    if (delay <= 0) {
      logout()
      return
    }
    expiryTimer = setTimeout(() => logout(), delay)
  }

  const cachePreferences = (newPreferences: UserPreferences) => {
    preferences.value = newPreferences
    localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(newPreferences))
  }

  const setMustChangePassword = (value: boolean) => {
    mustChangePassword.value = value
    if (value) localStorage.setItem(MUST_CHANGE_PASSWORD_STORAGE_KEY, '1')
    else localStorage.removeItem(MUST_CHANGE_PASSWORD_STORAGE_KEY)
  }

  const writeHint = () => {
    if (!signedIn.value || !username.value) return
    const value: SessionHint = {
      username: username.value,
      expiresAt: expiresAt.value,
      impersonator: originalUsername.value,
    }
    localStorage.setItem(SESSION_HINT_KEY, JSON.stringify(value))
  }

  /** Remember a session the server just confirmed (login, SSO, password change, /me). */
  const applySession = (info: SessionInfo) => {
    if (info.username) username.value = info.username
    if (info.expires_at !== undefined) expiresAt.value = parseExpiry(info.expires_at)
    if (info.impersonator_username !== undefined) originalUsername.value = info.impersonator_username
    signedIn.value = true
    // Impersonation/restore may not carry preferences — only overwrite the cache
    // when the caller actually has them.
    if (info.preferences) cachePreferences(info.preferences)
    writeHint()
    scheduleExpiry()
  }

  const clearSession = () => {
    signedIn.value = false
    username.value = null
    expiresAt.value = null
    originalUsername.value = null
    preferences.value = {}
    setMustChangePassword(false)
    localStorage.removeItem(SESSION_HINT_KEY)
    localStorage.removeItem(PREFERENCES_STORAGE_KEY)
    clearExpiryTimer()
  }

  const post = (url: string, body?: unknown) =>
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...REQUEST_HEADER },
      body: body === undefined ? undefined : JSON.stringify(body),
    })

  /**
   * Become another user (they get exactly that user's rights); the admin's own session
   * is kept by the server for stopImpersonation(). Forces a full page reload rather
   * than just reconnecting the socket: every Pinia store (media, devices, content, ...)
   * holds data fetched under the *previous* identity's rights, and a plain reconnect
   * wouldn't necessarily re-fetch all of it. A reload guarantees every store starts
   * clean and re-fetches under the new session's rights. Returns an error message, or
   * null on success.
   */
  const startImpersonation = async (userId: number): Promise<string | null> => {
    if (isImpersonating.value) return 'Already impersonating'
    try {
      const response = await post('/admin/api/auth/impersonate', { user_id: userId })
      const result = await response.json()
      if (!response.ok || !result.success) return result.error || 'Impersonation failed'
      applySession({
        username: result.username,
        expires_at: result.expires_at,
        impersonator_username: result.impersonator_username,
      })
      window.location.reload()
      return null
    } catch (e) {
      return `Could not reach server: ${e}`
    }
  }

  /**
   * Fall back from an impersonated session to the admin's own original session.
   * Also forces a full reload — see startImpersonation() for why.
   */
  const stopImpersonation = async () => {
    if (!isImpersonating.value) return
    try {
      const response = await post('/admin/api/auth/impersonate/stop')
      const result = await response.json()
      if (!response.ok || !result.success) {
        // The admin's own session has run out meanwhile: nothing to go back to.
        logout()
        return
      }
      applySession({ username: result.username, expires_at: result.expires_at, impersonator_username: null })
      window.location.reload()
    } catch {
      // Network error: stay as we are; the button can be pressed again.
    }
  }

  /**
   * Authenticate against the backend. Returns an error message on failure,
   * or null on success (matching the socket emitWithAck convention used
   * elsewhere in the SPA).
   */
  const login = async (usernameInput: string, password: string): Promise<string | null> => {
    try {
      const response = await post('/admin/api/auth/login', {
        username: usernameInput,
        password,
        session: 'cookie',
      })
      const result = await response.json()
      if (!response.ok || !result.success) {
        return result.error || 'Login failed'
      }
      // Before applySession(): its hint write is what other tabs react to, and
      // they read this flag when it lands.
      setMustChangePassword(!!result.must_change_password)
      applySession({ ...result, impersonator_username: null })
      return null
    } catch (e) {
      return `Could not reach server: ${e}`
    }
  }

  /**
   * Finish an SSO login: the backend's callback redirects to `/admin/#oidc_code=…`
   * (or `#oidc_error=…`). Swap the single-use code for a session (cookie).
   * App.vue calls this once on boot, before restore(), with the URL fragment —
   * after removing it from the URL through the router, so a reload or a
   * copied link never replays it.
   */
  const consumeSsoRedirect = async (hash: string) => {
    const params = new URLSearchParams(hash.replace(/^#/, ''))
    const code = params.get('oidc_code')
    const error = params.get('oidc_error')
    if (!code && !error) return
    if (error) {
      ssoError.value = error
      return
    }
    restoring.value = true
    try {
      const response = await post('/admin/api/auth/oidc/exchange', { code, session: 'cookie' })
      const result = await response.json()
      if (!response.ok || !result.success) {
        ssoError.value = result.error || 'SSO login failed'
        return
      }
      setMustChangePassword(false)
      applySession({ ...result, impersonator_username: null })
    } catch (e) {
      ssoError.value = `Could not reach server: ${e}`
    } finally {
      // restore() (which runs next) clears it again; without a session it
      // returns immediately, so make sure the login form shows.
      if (!signedIn.value) restoring.value = false
    }
  }

  /** End the session: tell the server to remove the cookie, forget it here, disconnect the socket. */
  const logout = () => {
    // Fire and forget: the page is leaving the session either way.
    void fetch('/admin/api/auth/logout', { method: 'POST', headers: REQUEST_HEADER, keepalive: true }).catch(() => {})
    clearSession()
    const { disconnect } = useSocket()
    disconnect()
  }

  /**
   * Ask the server whether the session this browser believes in is still valid, on
   * app boot. Clears it if it is missing/expired/invalid (e.g. the user was deleted
   * since). Without a hint there is nothing to ask about: the login form shows.
   */
  const restore = async () => {
    if (!signedIn.value) {
      restoring.value = false
      return
    }
    try {
      const response = await fetch('/admin/api/auth/me')
      if (!response.ok) {
        clearSession()
      } else {
        const result = await response.json()
        applySession(result)
        setMustChangePassword(!!result.must_change_password)
      }
    } catch {
      // Network error: keep what we have: the socket connect attempt
      // will fail/retry, and the check above will run again on reload.
    } finally {
      restoring.value = false
    }
  }

  /**
   * Persist one or more preferences (e.g. { theme: 'dark' }) to the backend
   * and update the local cache optimistically-on-success. Returns an error
   * message on failure, or null on success.
   */
  const setPreferences = async (updates: UserPreferences): Promise<string | null> => {
    try {
      const response = await fetch('/admin/api/auth/me/preferences', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ preferences: updates }),
      })
      const result = await response.json()
      if (!response.ok || !result.success) {
        return result.error || 'Failed to save preference'
      }
      cachePreferences(result.preferences)
      return null
    } catch (e) {
      return `Could not reach server: ${e}`
    }
  }

  /**
   * Change the current user's own password (required while
   * `mustChangePassword` is set). The server revokes every other session and
   * replaces this one's cookie. Returns an error message on failure, or null on success.
   */
  const changePassword = async (currentPassword: string, newPassword: string): Promise<string | null> => {
    try {
      const response = await post('/admin/api/auth/me/password', {
        current_password: currentPassword,
        new_password: newPassword,
      })
      const result = await response.json()
      if (!response.ok || !result.success) {
        return result.error || 'Failed to change password'
      }
      // Session first: other tabs reload on the session swap (see the storage
      // listener below) rather than connecting with their now-revoked session
      // the moment the flag clears.
      applySession(result)
      setMustChangePassword(false)
      return null
    } catch (e) {
      return `Could not reach server: ${e}`
    }
  }

  // Cross-tab sync: localStorage writes in one tab fire a native 'storage'
  // event in every *other* open tab (never the tab that wrote it), so this
  // is enough to mirror login/logout everywhere without polling. Each tab
  // still owns its own socket connection — logout() below disconnects this
  // tab's socket; a fresh login elsewhere flips `isAuthenticated`, which
  // App.vue's watcher picks up to connect().
  window.addEventListener('storage', (event) => {
    if (event.key === MUST_CHANGE_PASSWORD_STORAGE_KEY) {
      mustChangePassword.value = event.newValue === '1'
      return
    }
    if (event.key !== SESSION_HINT_KEY) return
    const next = readHint(event.newValue)
    if (!next) {
      // Signed out in another tab: forget it here too (the server already did).
      clearSession()
      useSocket().disconnect()
      return
    }
    if (signedIn.value) {
      // Another tab switched user, started/stopped impersonation or got a fresh session
      // (password change): this tab's socket holds the previous session, and its stores
      // the previous identity's data — see startImpersonation() for why a reconnect is
      // not enough.
      if (
        next.username !== username.value ||
        next.impersonator !== originalUsername.value ||
        next.expiresAt !== expiresAt.value
      ) {
        window.location.reload()
      }
      return
    }
    // A plain login while this tab was signed out: App.vue's isAuthenticated watcher connects.
    mustChangePassword.value = localStorage.getItem(MUST_CHANGE_PASSWORD_STORAGE_KEY) === '1'
    username.value = next.username
    expiresAt.value = next.expiresAt
    originalUsername.value = next.impersonator
    signedIn.value = true
    scheduleExpiry()
  })

  /**
   * Headers for authenticated fetch() calls: the session cookie goes along by itself;
   * this is the header the server demands next to it for requests that change something.
   */
  const authHeader = (): Record<string, string> => ({ ...REQUEST_HEADER })

  return {
    username,
    preferences,
    restoring,
    isAuthenticated,
    mustChangePassword,
    hasUsableSession,
    originalUsername,
    isImpersonating,
    startImpersonation,
    stopImpersonation,
    login,
    logout,
    restore,
    consumeSsoRedirect,
    ssoError,
    setPreferences,
    changePassword,
    authHeader,
  }
})
