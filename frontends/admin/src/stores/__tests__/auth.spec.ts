import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '../auth'

const HINT_KEY = 'displayhive_admin_session'
const FUTURE = () => new Date(Date.now() + 3600_000).toISOString()

type Call = { url: string; init?: RequestInit }
let calls: Call[]
const at = (index: number) => calls[index] as Call
let respond: (url: string, init?: RequestInit) => { status?: number; body: unknown } | Error

const jsonResponse = (status: number, body: unknown) =>
  ({ ok: status >= 200 && status < 300, status, json: async () => body }) as Response

const headersOf = (call: Call) => (call.init?.headers ?? {}) as Record<string, string>
const bodyOf = (call: Call) => JSON.parse(String(call.init?.body ?? '{}'))

let reload: ReturnType<typeof vi.fn>
// Every store instance listens to `storage` events on the window for the life of the
// page. Tests create many stores, so take their listeners off again after each test.
let storageListeners: EventListenerOrEventListenerObject[]

beforeEach(() => {
  storageListeners = []
  const original = window.addEventListener.bind(window)
  vi.spyOn(window, 'addEventListener').mockImplementation((type: string, listener: EventListenerOrEventListenerObject, options?: boolean | AddEventListenerOptions) => {
    if (type === 'storage') storageListeners.push(listener)
    original(type, listener, options)
  })
  localStorage.clear()
  calls = []
  respond = () => ({ body: { success: true } })
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init })
      const result = respond(url, init)
      if (result instanceof Error) throw result
      return jsonResponse(result.status ?? 200, result.body)
    }),
  )
  reload = vi.fn()
  vi.stubGlobal('location', { ...window.location, reload })
  setActivePinia(createPinia())
})

afterEach(() => {
  storageListeners.forEach((listener) => window.removeEventListener('storage', listener))
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('logging in', () => {
  it('asks for a cookie session, sends the CSRF header and keeps no token anywhere', async () => {
    respond = () => ({
      body: { success: true, username: 'anna', expires_at: FUTURE(), preferences: { theme: 'dark' }, must_change_password: false },
    })
    const auth = useAuthStore()
    expect(await auth.login('anna', 'secret')).toBeNull()

    expect(bodyOf(at(0))).toEqual({ username: 'anna', password: 'secret', session: 'cookie' })
    expect(headersOf(at(0))['X-DisplayHive-Request']).toBe('1')
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.username).toBe('anna')
    expect(auth.preferences.theme).toBe('dark')
    // Nothing in storage is a credential: just who, until when.
    const stored = JSON.parse(localStorage.getItem(HINT_KEY) as string)
    expect(Object.keys(stored).sort()).toEqual(['expiresAt', 'impersonator', 'username'])
    expect(JSON.stringify({ ...localStorage })).not.toMatch(/eyJ|token/i)
  })

  it('reports a failed login without remembering anything', async () => {
    respond = () => ({ status: 401, body: { success: false, error: 'Invalid username or password' } })
    const auth = useAuthStore()
    expect(await auth.login('anna', 'wrong')).toBe('Invalid username or password')
    expect(auth.isAuthenticated).toBe(false)
    expect(localStorage.getItem(HINT_KEY)).toBeNull()
  })

  it('reports an unreachable server', async () => {
    respond = () => new Error('offline')
    expect(await useAuthStore().login('a', 'b')).toContain('Could not reach server')
  })

  it('remembers that the account must choose a new password', async () => {
    respond = () => ({ body: { success: true, username: 'admin', expires_at: FUTURE(), must_change_password: true } })
    const auth = useAuthStore()
    await auth.login('admin', 'pw')
    expect(auth.mustChangePassword).toBe(true)
    expect(auth.hasUsableSession).toBe(false)
  })
})

describe('starting up', () => {
  it('removes the tokens earlier versions left in localStorage', () => {
    localStorage.setItem('displayhive_admin_token', 'eyJ.old.token')
    localStorage.setItem('displayhive_admin_original_token', 'eyJ.other.token')
    localStorage.setItem('displayhive_admin_username', 'anna')
    useAuthStore()
    expect(localStorage.getItem('displayhive_admin_token')).toBeNull()
    expect(localStorage.getItem('displayhive_admin_original_token')).toBeNull()
    expect(localStorage.getItem('displayhive_admin_username')).toBeNull()
  })

  it('asks the server only when it believes there is a session', async () => {
    const auth = useAuthStore()
    await auth.restore()
    expect(calls).toHaveLength(0)
    expect(auth.restoring).toBe(false)
    expect(auth.isAuthenticated).toBe(false)
  })

  it('confirms a remembered session with the server and learns about impersonation', async () => {
    localStorage.setItem(HINT_KEY, JSON.stringify({ username: 'anna', expiresAt: Date.now() + 1000, impersonator: null }))
    respond = () => ({
      body: { success: true, username: 'bob', expires_at: FUTURE(), impersonator_username: 'anna', must_change_password: false },
    })
    const auth = useAuthStore()
    expect(auth.restoring).toBe(true)
    await auth.restore()

    expect(at(0).url).toBe('/admin/api/auth/me')
    expect(auth.username).toBe('bob')
    expect(auth.isImpersonating).toBe(true)
    expect(auth.originalUsername).toBe('anna')
    expect(auth.restoring).toBe(false)
  })

  it('forgets a session the server no longer accepts', async () => {
    localStorage.setItem(HINT_KEY, JSON.stringify({ username: 'anna', expiresAt: Date.now() + 1000, impersonator: null }))
    respond = () => ({ status: 401, body: { success: false } })
    const auth = useAuthStore()
    await auth.restore()
    expect(auth.isAuthenticated).toBe(false)
    expect(localStorage.getItem(HINT_KEY)).toBeNull()
  })

  it('keeps the session through a network error', async () => {
    localStorage.setItem(HINT_KEY, JSON.stringify({ username: 'anna', expiresAt: Date.now() + 1000, impersonator: null }))
    respond = () => new Error('offline')
    const auth = useAuthStore()
    await auth.restore()
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.restoring).toBe(false)
  })
})

describe('logging out', () => {
  it('tells the server to drop the cookie and forgets the session here', async () => {
    respond = () => ({ body: { success: true, username: 'anna', expires_at: FUTURE() } })
    const auth = useAuthStore()
    await auth.login('anna', 'pw')
    calls = []
    auth.logout()

    expect(at(0).url).toBe('/admin/api/auth/logout')
    expect(at(0).init?.method).toBe('POST')
    expect(headersOf(at(0))['X-DisplayHive-Request']).toBe('1')
    expect(auth.isAuthenticated).toBe(false)
    expect(localStorage.getItem(HINT_KEY)).toBeNull()
  })

  it('logs itself out when the session runs out', async () => {
    vi.useFakeTimers()
    respond = () => ({ body: { success: true, username: 'anna', expires_at: new Date(Date.now() + 5000).toISOString() } })
    const auth = useAuthStore()
    await auth.login('anna', 'pw')
    expect(auth.isAuthenticated).toBe(true)
    vi.advanceTimersByTime(5001)
    expect(auth.isAuthenticated).toBe(false)
  })
})

describe('changing the password', () => {
  it('carries on under the new cookie and clears the flag', async () => {
    respond = (url) =>
      url.endsWith('/login')
        ? { body: { success: true, username: 'admin', expires_at: FUTURE(), must_change_password: true } }
        : { body: { success: true, username: 'admin', expires_at: new Date(Date.now() + 7200_000).toISOString() } }
    const auth = useAuthStore()
    await auth.login('admin', 'old')
    expect(await auth.changePassword('old', 'a-new-long-password')).toBeNull()

    const call = calls.find((c) => c.url.endsWith('/me/password')) as Call
    expect(bodyOf(call)).toEqual({ current_password: 'old', new_password: 'a-new-long-password' })
    expect(headersOf(call)['X-DisplayHive-Request']).toBe('1')
    expect(auth.mustChangePassword).toBe(false)
    expect(auth.isAuthenticated).toBe(true)
  })

  it('returns the server message', async () => {
    respond = () => ({ status: 400, body: { success: false, error: 'Current password is incorrect' } })
    expect(await useAuthStore().changePassword('x', 'y')).toBe('Current password is incorrect')
  })
})

describe('impersonation', () => {
  const signedInAs = async (name: string) => {
    respond = () => ({ body: { success: true, username: name, expires_at: FUTURE() } })
    const auth = useAuthStore()
    await auth.login(name, 'pw')
    calls = []
    return auth
  }

  it('starts over HTTP, remembers who is really driving and reloads the page', async () => {
    const auth = await signedInAs('boss')
    respond = () => ({ body: { success: true, username: 'target', impersonator_username: 'boss', expires_at: FUTURE() } })
    expect(await auth.startImpersonation(7)).toBeNull()

    expect(at(0).url).toBe('/admin/api/auth/impersonate')
    expect(bodyOf(at(0))).toEqual({ user_id: 7 })
    expect(auth.username).toBe('target')
    expect(auth.originalUsername).toBe('boss')
    expect(auth.isImpersonating).toBe(true)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('reports why it could not start and does not reload', async () => {
    const auth = await signedInAs('boss')
    respond = () => ({ status: 400, body: { success: false, error: 'Cannot impersonate yourself' } })
    expect(await auth.startImpersonation(1)).toBe('Cannot impersonate yourself')
    expect(reload).not.toHaveBeenCalled()
    expect(auth.isImpersonating).toBe(false)
  })

  it('stops by going back to the original session', async () => {
    const auth = await signedInAs('target')
    auth.originalUsername = 'boss' as never
    respond = () => ({ body: { success: true, username: 'boss', expires_at: FUTURE() } })
    await auth.stopImpersonation()
    expect(at(0).url).toBe('/admin/api/auth/impersonate/stop')
    expect(auth.username).toBe('boss')
    expect(auth.isImpersonating).toBe(false)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('logs out when the original session has expired', async () => {
    const auth = await signedInAs('target')
    auth.originalUsername = 'boss' as never
    respond = (url) => (url.endsWith('/stop') ? { status: 401, body: { success: false } } : { body: { success: true } })
    await auth.stopImpersonation()
    expect(auth.isAuthenticated).toBe(false)
    expect(reload).not.toHaveBeenCalled()
  })
})

describe('single sign-on', () => {
  it('swaps the one-time code for a cookie session', async () => {
    respond = () => ({ body: { success: true, username: 'sso-user', expires_at: FUTURE() } })
    const auth = useAuthStore()
    await auth.consumeSsoRedirect('#oidc_code=abc123')
    expect(at(0).url).toBe('/admin/api/auth/oidc/exchange')
    expect(bodyOf(at(0))).toEqual({ code: 'abc123', session: 'cookie' })
    expect(auth.username).toBe('sso-user')
    expect(auth.mustChangePassword).toBe(false)
  })

  it('shows an error from the provider without calling the server', async () => {
    const auth = useAuthStore()
    await auth.consumeSsoRedirect('#oidc_error=Denied')
    expect(calls).toHaveLength(0)
    expect(auth.ssoError).toBe('Denied')
  })
})

describe('headers for requests that change something', () => {
  it('are only the CSRF header — there is no token to send', () => {
    expect(useAuthStore().authHeader()).toEqual({ 'X-DisplayHive-Request': '1' })
  })
})

describe('other tabs', () => {
  const hint = (over: Record<string, unknown> = {}) =>
    JSON.stringify({ username: 'anna', expiresAt: Date.now() + 10_000, impersonator: null, ...over })
  const storage = (newValue: string | null) =>
    window.dispatchEvent(new StorageEvent('storage', { key: HINT_KEY, newValue }))

  it('mirrors a logout', () => {
    localStorage.setItem(HINT_KEY, hint())
    const auth = useAuthStore()
    storage(null)
    expect(auth.isAuthenticated).toBe(false)
  })

  it('picks up a login made while this tab was signed out', () => {
    const auth = useAuthStore()
    storage(hint({ username: 'carla' }))
    expect(auth.isAuthenticated).toBe(true)
    expect(auth.username).toBe('carla')
  })

  it('reloads when the user, the impersonation or the session changed', () => {
    const expiresAt = Date.now() + 10_000
    localStorage.setItem(HINT_KEY, hint({ expiresAt }))
    useAuthStore()
    storage(hint({ expiresAt, username: 'someone-else' }))
    storage(hint({ expiresAt, impersonator: 'boss' }))
    storage(hint({ expiresAt: expiresAt + 5000 }))
    expect(reload).toHaveBeenCalledTimes(3)
  })

  it('leaves an identical session alone', () => {
    const expiresAt = Date.now() + 10_000
    localStorage.setItem(HINT_KEY, hint({ expiresAt }))
    useAuthStore()
    storage(hint({ expiresAt }))
    expect(reload).not.toHaveBeenCalled()
  })
})
