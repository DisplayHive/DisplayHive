import { ref } from 'vue'
import { io, type Socket } from 'socket.io-client'

// Test-only globals injected by Playwright fixtures (see connect() below).
interface TestWindow extends Window {
  __DISPLAYHIVE_TEST_BACKEND_URL__?: string
  __displayhive_socket__?: Socket
}

// Singleton socket instance shared across all composable calls
let socket: Socket | null = null
const isConnected = ref(false)
// Flips true once the underlying Manager gives up retrying (reconnectionAttempts
// exhausted) or the server rejects the handshake outright. Socket.IO does not
// retry on its own past that point, so without this the UI would otherwise be
// stuck on the "Disconnected" overlay forever. Callers (App.vue) watch this to
// drop back to the login screen instead of leaving the user stranded.
const reconnectFailed = ref(false)

// Queues for listeners/emits registered before the socket is available.
// Flushed automatically once the socket connects.
const pendingListeners: Array<{ event: string; callback: (...args: unknown[]) => void }> = []
const pendingEmits: Array<{ event: string; data?: unknown }> = []

/**
 * Singleton Socket.IO composable.
 *
 * All calls to `useSocket()` share the same underlying socket instance and
 * `isConnected` ref. The socket is created lazily on the first `connect()` call
 * and reused on subsequent calls.
 *
 * Listeners and emits issued before the socket is ready are queued and
 * replayed automatically on connection.
 */
export function useSocket() {
  /**
   * Establish the socket connection.
   *
   * The URL is resolved from (in priority order):
   * 1. `window.__DISPLAYHIVE_TEST_BACKEND_URL__` (injected by Playwright test fixtures)
   * 2. `VITE_SOCKET_URL` build-time env variable
   * 3. `window.location.origin` (same-origin fallback)
   *
   * Calling `connect()` when already connected is a no-op.
   * @returns The active Socket.IO socket instance.
   */
  const connect = () => {
    // If a socket instance already exists (connected or reconnecting), reuse it.
    // Creating a new io() during auto-reconnect would orphan all registered listeners.
    if (socket) return socket

    // Resolve socket URL from Vite env or fall back to same origin.
    // During Playwright tests (Option B), global-setup injects
    // `window.__DISPLAYHIVE_TEST_BACKEND_URL__` so each worker connects to
    // its own Flask instance with an isolated database.
    const testWindow = window as TestWindow
    const url =
      testWindow.__DISPLAYHIVE_TEST_BACKEND_URL__ ||
      (import.meta.env.VITE_SOCKET_URL as string) ||
      window.location.origin
    // JWT issued by POST /admin/api/auth/login (see stores/auth.ts, which
    // owns this same localStorage key — kept as a literal here to avoid a
    // circular import between the auth store and this composable).
    const token = localStorage.getItem('displayhive_admin_token')

    socket = io(url, {
      // Sent only in the handshake `auth` payload (not `query`) so the JWT
      // never ends up in a URL / access log.
      auth: token ? { token } : undefined,
      transports: ['polling'], //'websocket',
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
    })

    // Expose the socket on window during E2E tests so Playwright's page.evaluate
    // helpers (e.g. seedDevice in device-active.spec.ts) can emit events directly.
    // The flag is injected by the loginAsAdmin fixture via addInitScript.
    if (testWindow.__DISPLAYHIVE_TEST_BACKEND_URL__) {
      testWindow.__displayhive_socket__ = socket
    }

    // Register any listeners that were queued before the socket existed —
    // this MUST happen synchronously right here, not inside the 'connect'
    // callback below. Some server-side connect handlers (e.g. the admin
    // security_status push) emit immediately as part of the handshake, and
    // Socket.IO drops events for which no listener is attached at delivery
    // time. Waiting for the 'connect' event to register listeners lost that
    // very first emit on the initial connection (a plain reconnect worked
    // fine, since by then the listener was already attached from before).
    try {
      pendingListeners.forEach((l) => {
        socket?.on(l.event, l.callback)
      })
      pendingListeners.length = 0
    } catch (e) {
      console.warn('[useSocket] failed to register pending listeners', e)
    }

    socket.on('connect', () => {
      isConnected.value = true
      reconnectFailed.value = false
      // Client does not request to join the admins room directly. The server
      // decides admin membership based on the JWT sent in the handshake `auth`.

      // Flush pending emits
      try {
        pendingEmits.forEach((e) => {
          socket?.emit(e.event, e.data)
        })
        pendingEmits.length = 0
      } catch (e) {
        console.warn('[useSocket] failed to flush pending emits', e)
      }
    })

    socket.on('disconnect', (reason) => {
      isConnected.value = false
      // 'io server disconnect' means the server itself closed the socket
      // (e.g. rejecting a now-invalid session) — Socket.IO's built-in
      // reconnection logic deliberately does NOT retry in this case, so the
      // client must kick off a fresh connect attempt by hand. That attempt
      // either succeeds, or fails the handshake and surfaces via
      // 'connect_error' (e.g. invalid_token, handled in App.vue).
      if (reason === 'io server disconnect') {
        socket?.connect()
      }
    })

    socket.on('connect_error', (error) => {
      console.error('[useSocket] connection error:', error)
    })

    // Reconnection attempts/backoff are managed by the Manager (`socket.io`),
    // not the Socket itself — these events never fire on `socket.on(...)`.
    socket.io.on('reconnect_failed', () => {
      console.error('[useSocket] reconnection attempts exhausted, giving up')
      reconnectFailed.value = true
    })

    return socket
  }

  /** Close the socket connection and clear the singleton instance. */
  const disconnect = () => {
    if (socket) {
      socket.disconnect()
      socket = null
      isConnected.value = false
    }
    reconnectFailed.value = false
    pendingListeners.length = 0
    pendingEmits.length = 0
  }

  /**
   * Emit a socket event.
   *
   * If the socket is not yet connected the emit is queued and replayed
   * automatically once the connection is established.
   *
   * @param event - The socket event name.
   * @param data - Optional payload to send with the event.
   */
  const emit = (event: string, data?: unknown) => {
    if (socket?.connected) {
      socket.emit(event, data)
    } else {
      console.warn('[useSocket] not connected, queuing emit:', event)
      pendingEmits.push({ event, data })
    }
  }

  /**
   * Emit a socket event and wait for the server acknowledgment.
   *
   * @param event - The socket event name.
   * @param data - Optional payload to send with the event.
   * @returns A Promise that resolves with the server's acknowledgment value.
   * @throws When the socket is not connected.
   */
  const emitWithAck = <T = unknown>(event: string, data?: unknown): Promise<T> => {
    return new Promise((resolve, reject) => {
      if (!socket?.connected) {
        reject(new Error('Socket not connected'))
        return
      }
      socket.emit(event, data, (response: T) => resolve(response))
    })
  }

  /**
   * Register a listener for a socket event.
   *
   * If the socket is not yet connected the listener is queued and registered
   * automatically once the connection is established.
   *
   * @param event - The socket event name to listen for.
   * @param callback - Handler called with the event payload.
   */
  const on = <T = unknown>(event: string, callback: (data: T) => void) => {
    if (socket) {
      socket.on(event, callback as (...args: unknown[]) => void)
    } else {
      // queue listener until socket exists
      pendingListeners.push({ event, callback: callback as (...args: unknown[]) => void })
    }
  }

  /**
   * Remove a previously registered event listener.
   *
   * Also removes the listener from the pending queue if it was registered
   * before the socket connected.
   *
   * @param event - The socket event name.
   * @param callback - The exact handler reference passed to `on()`.
   */
  const off = <T = unknown>(event: string, callback?: (data: T) => void) => {
    try {
      if (socket) {
        socket.off(event, callback as ((...args: unknown[]) => void) | undefined)
      }
      // remove from pending listeners as well
      for (let i = pendingListeners.length - 1; i >= 0; i--) {
        const pl = pendingListeners[i]
        if (pl && pl.event === event && (!callback || pl.callback === (callback as (...args: unknown[]) => void))) {
          pendingListeners.splice(i, 1)
        }
      }
    } catch (e) {
      console.warn('[useSocket] error removing listener', e)
    }
  }

  /** Return the raw Socket.IO socket instance (or `null` if not yet created). */
  const getSocket = () => socket

  return {
    isConnected,
    reconnectFailed,
    connect,
    disconnect,
    emit,
    emitWithAck,
    on,
    off,
    getSocket,
  }
}
