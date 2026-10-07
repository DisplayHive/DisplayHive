import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { useSocket } from '../composables/useSocket'

const TOKEN_STORAGE_KEY = 'displayhive_admin_token'
const USERNAME_STORAGE_KEY = 'displayhive_admin_username'
// Cached copy of the DB-backed preferences, so the theme can be applied
// before login()/restore() completes its round-trip (avoids a flash of the
// wrong theme). The DB stays the source of truth; this is just a paint cache.
const PREFERENCES_STORAGE_KEY = 'displayhive_admin_preferences'
// Mirrors the server's must_change_password flag for the current session, so
// other tabs (via the `storage` event) know not to connect a socket the
// server would refuse anyway. The server stays the source of truth.
const MUST_CHANGE_PASSWORD_STORAGE_KEY = 'displayhive_admin_must_change_password'

export type UserPreferences = { theme?: 'light' | 'dark' | 'system' }

const readCachedPreferences = (): UserPreferences => {
  try {
    const raw = localStorage.getItem(PREFERENCES_STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}
// Set only while impersonating: the admin's own token/username, stashed so
// "stop impersonating" can restore it without a fresh login.
const ORIGINAL_TOKEN_STORAGE_KEY = 'displayhive_admin_original_token'
const ORIGINAL_USERNAME_STORAGE_KEY = 'displayhive_admin_original_username'

/**
 * Decode a JWT's `exp` claim (seconds since epoch) without verifying the
 * signature — purely for scheduling a client-side auto-logout timer. The
 * server is the source of truth: every authenticated request/socket connect
 * re-validates the token, so a forged/tampered `exp` here can at most make
 * the UI log out early or late, never grant access.
 */
const decodeExpiryMs = (token: string): number | null => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1] ?? ''))
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

/**
 * Admin authentication store: holds the current JWT + username, persists
 * them to localStorage, and drives login/logout against the backend.
 *
 * localStorage (rather than sessionStorage) is used deliberately so that
 * logging in or out in one tab/window is reflected in every other open
 * tab/window (via the native `storage` event, below) instead of each tab
 * carrying its own independent session. The token still expires on its own
 * — the backend issues it with a 12h TTL (see application/auth.py
 * TOKEN_TTL) that every request/socket connect re-validates — and
 * `scheduleExpiry` mirrors that TTL client-side so a stale tab logs itself
 * out proactively rather than sitting on an expired token until its next
 * API call happens to fail.
 */
export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem(TOKEN_STORAGE_KEY))
  const username = ref<string | null>(localStorage.getItem(USERNAME_STORAGE_KEY))
  const preferences = ref<UserPreferences>(readCachedPreferences())
  // Starts true whenever a token is present so the app doesn't flash the
  // login form while `restore()` confirms the token is still valid.
  const restoring = ref(!!token.value)
  // Set when an SSO login came back with an error (see consumeSsoRedirect);
  // LoginView shows it.
  const ssoError = ref<string | null>(null)

  const isAuthenticated = computed(() => !!token.value)
  // While set, the server rejects this session everywhere except the
  // password-change routes (see application/auth.py user_from_token), so App.vue
  // shows ChangePasswordView instead of the app and doesn't connect the socket.
  const mustChangePassword = ref(localStorage.getItem(MUST_CHANGE_PASSWORD_STORAGE_KEY) === '1')
  const hasUsableSession = computed(() => isAuthenticated.value && !mustChangePassword.value)

  const originalToken = ref<string | null>(localStorage.getItem(ORIGINAL_TOKEN_STORAGE_KEY))
  const originalUsername = ref<string | null>(localStorage.getItem(ORIGINAL_USERNAME_STORAGE_KEY))
  const isImpersonating = computed(() => !!originalToken.value)

  let expiryTimer: ReturnType<typeof setTimeout> | null = null

  const clearExpiryTimer = () => {
    if (expiryTimer !== null) {
      clearTimeout(expiryTimer)
      expiryTimer = null
    }
  }

  // Auto-logout when the token's own `exp` passes, so an idle tab doesn't
  // linger on a dead session. setTimeout is capped at ~24.8 days internally;
  // the 12h token TTL is well within that, so no chunking is needed here.
  const scheduleExpiry = (forToken: string) => {
    clearExpiryTimer()
    const expiresAt = decodeExpiryMs(forToken)
    if (expiresAt === null) return
    const delay = expiresAt - Date.now()
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

  const setSession = (newToken: string, newUsername: string, newPreferences?: UserPreferences) => {
    token.value = newToken
    username.value = newUsername
    localStorage.setItem(TOKEN_STORAGE_KEY, newToken)
    localStorage.setItem(USERNAME_STORAGE_KEY, newUsername)
    // Impersonation/restore may not carry preferences (e.g. /auth/me on a
    // stale tab) — only overwrite the cache when the caller actually has them.
    if (newPreferences) cachePreferences(newPreferences)
    scheduleExpiry(newToken)
  }

  const clearOriginalSession = () => {
    originalToken.value = null
    originalUsername.value = null
    localStorage.removeItem(ORIGINAL_TOKEN_STORAGE_KEY)
    localStorage.removeItem(ORIGINAL_USERNAME_STORAGE_KEY)
  }

  const clearSession = () => {
    token.value = null
    username.value = null
    preferences.value = {}
    setMustChangePassword(false)
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    localStorage.removeItem(USERNAME_STORAGE_KEY)
    localStorage.removeItem(PREFERENCES_STORAGE_KEY)
    clearExpiryTimer()
    // A full logout always ends any impersonation too — there is no "original"
    // session left to fall back to once the whole thing is logged out.
    clearOriginalSession()
  }

  /**
   * Switch the active session to *newToken* (an impersonation token returned by
   * displayhive:admin:users:cts:impersonate), stashing the admin's own
   * session so stopImpersonation() can restore it. No-op if already
   * impersonating — the backend refuses to chain impersonation anyway.
   *
   * Forces a full page reload rather than just reconnecting the socket: every
   * Pinia store (media, devices, content, ...) holds data fetched under the
   * *previous* identity's rights, and a plain reconnect wouldn't necessarily
   * re-fetch all of it. A reload guarantees every store starts clean and
   * re-fetches under the new session's rights.
   */
  const startImpersonation = (newToken: string, newUsername: string) => {
    if (isImpersonating.value || !token.value || !username.value) return
    originalToken.value = token.value
    originalUsername.value = username.value
    localStorage.setItem(ORIGINAL_TOKEN_STORAGE_KEY, token.value)
    localStorage.setItem(ORIGINAL_USERNAME_STORAGE_KEY, username.value)
    setSession(newToken, newUsername)
    window.location.reload()
  }

  /**
   * Fall back from an impersonated session to the admin's own original session.
   * Also forces a full reload — see startImpersonation() for why.
   */
  const stopImpersonation = () => {
    if (!isImpersonating.value || !originalToken.value || !originalUsername.value) return
    const restoreToken = originalToken.value
    const restoreUsername = originalUsername.value
    clearOriginalSession()
    setSession(restoreToken, restoreUsername)
    window.location.reload()
  }

  /**
   * Authenticate against the backend. Returns an error message on failure,
   * or null on success (matching the socket emitWithAck convention used
   * elsewhere in the SPA).
   */
  const login = async (usernameInput: string, password: string): Promise<string | null> => {
    try {
      const response = await fetch('/admin/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: usernameInput, password }),
      })
      const result = await response.json()
      if (!response.ok || !result.success) {
        return result.error || 'Login failed'
      }
      // Before setSession(): its token write is what other tabs react to, and
      // they read this flag when it lands.
      setMustChangePassword(!!result.must_change_password)
      setSession(result.token, result.username, result.preferences || {})
      return null
    } catch (e) {
      return `Could not reach server: ${e}`
    }
  }

  /**
   * Finish an SSO login: the backend's callback redirects to `/admin/#oidc_code=…`
   * (or `#oidc_error=…`). Swap the single-use code for a session token.
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
      const response = await fetch('/admin/api/auth/oidc/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      })
      const result = await response.json()
      if (!response.ok || !result.success) {
        ssoError.value = result.error || 'SSO login failed'
        return
      }
      setMustChangePassword(false)
      setSession(result.token, result.username, result.preferences || {})
    } catch (e) {
      ssoError.value = `Could not reach server: ${e}`
    } finally {
      // restore() (which runs next) clears it again; without a token it
      // returns immediately, so make sure the login form shows.
      if (!token.value) restoring.value = false
    }
  }

  /** Clear the session and disconnect the socket. */
  const logout = () => {
    clearSession()
    const { disconnect } = useSocket()
    disconnect()
  }

  /**
   * Validate a stored token against the backend on app boot. Clears the
   * session if the token is missing/expired/invalid (e.g. the user was
   * deleted since the token was issued).
   */
  const restore = async () => {
    if (!token.value) {
      restoring.value = false
      return
    }
    try {
      const response = await fetch('/admin/api/auth/me', {
        headers: { Authorization: `Bearer ${token.value}` },
      })
      if (!response.ok) {
        clearSession()
      } else {
        const result = await response.json()
        if (result.username) username.value = result.username
        if (result.preferences) cachePreferences(result.preferences)
        setMustChangePassword(!!result.must_change_password)
        scheduleExpiry(token.value)
      }
    } catch {
      // Network error: keep the stored token: the socket connect attempt
      // will fail/retry, and the header check above will run again on reload.
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
   * returns a fresh token for this one. Returns an error message on failure,
   * or null on success.
   */
  const changePassword = async (currentPassword: string, newPassword: string): Promise<string | null> => {
    try {
      const response = await fetch('/admin/api/auth/me/password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      })
      const result = await response.json()
      if (!response.ok || !result.success) {
        return result.error || 'Failed to change password'
      }
      // Token first: other tabs reload on the token swap (see the storage
      // listener below) rather than connecting with their now-revoked token
      // the moment the flag clears.
      setSession(result.token, result.username)
      setMustChangePassword(false)
      return null
    } catch (e) {
      return `Could not reach server: ${e}`
    }
  }

  // Cross-tab sync: localStorage writes in one tab fire a native 'storage'
  // event in every *other* open tab (never the tab that wrote it), so this
  // is enough to mirror login/logout everywhere without polling or a
  // BroadcastChannel. Each tab still owns its own socket connection —
  // logout() below disconnects this tab's socket; a fresh login elsewhere
  // flips `isAuthenticated`, which App.vue's watcher picks up to connect().
  window.addEventListener('storage', (event) => {
    if (event.key === ORIGINAL_TOKEN_STORAGE_KEY) {
      originalToken.value = event.newValue
      originalUsername.value = event.newValue ? localStorage.getItem(ORIGINAL_USERNAME_STORAGE_KEY) : null
      return
    }
    if (event.key === MUST_CHANGE_PASSWORD_STORAGE_KEY) {
      mustChangePassword.value = event.newValue === '1'
      return
    }
    if (event.key !== TOKEN_STORAGE_KEY) return
    if (event.newValue) {
      const wasAuthenticated = !!token.value
      // A plain login-while-logged-out is picked up by App.vue's isAuthenticated
      // watcher, which calls connect(). A token swap on an *already*
      // authenticated tab (e.g. another tab started/stopped impersonation)
      // needs a full reload instead — see startImpersonation() for why a
      // reconnect alone isn't enough to refresh every store's data.
      if (wasAuthenticated) {
        window.location.reload()
        return
      }
      mustChangePassword.value = localStorage.getItem(MUST_CHANGE_PASSWORD_STORAGE_KEY) === '1'
      token.value = event.newValue
      username.value = localStorage.getItem(USERNAME_STORAGE_KEY)
      scheduleExpiry(event.newValue)
    } else {
      logout()
    }
  })

  /** Returns an `Authorization` header object for authenticated fetch() calls. */
  const authHeader = (): Record<string, string> =>
    token.value ? { Authorization: `Bearer ${token.value}` } : {}

  return {
    token,
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
