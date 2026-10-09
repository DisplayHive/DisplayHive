import { useToast } from 'primevue/usetoast'
import { useSocket } from './useSocket'

/** What every admin socket handler answers: `{success: true, …}` or `{success: false, error}`. */
export interface Ack {
  success: boolean
  error?: string
}

export interface AckOptions<T extends Ack> {
  /** Toast text on success (a function gets the answer, e.g. to mention a count). No toast without it. */
  success?: string | ((ack: T) => string)
  /** Fallback text when the server gave no reason. */
  error?: string
  /** Show the problem yourself (e.g. inside a dialog) instead of as a toast; gets the message. */
  onError?: (message: string) => void
}

/**
 * Sends a socket event and turns the answer into a toast.
 *
 *     const { request } = useAck()
 *     const ack = await request('displayhive:admin:cts:delete_layout', { id }, { success: 'Layout deleted' })
 *     if (ack) { … }   // null: it failed, and the person has already been told
 *
 * Replaces the `try { emitWithAck … if (ack.success) toast … else toast … } catch { toast … }` block
 * every page used to repeat. A refused request, a missing answer and a socket that is not connected
 * all end the same way: `null` plus an error toast.
 */
export function useAck() {
  const toast = useToast()
  const { emitWithAck } = useSocket()

  async function request<T extends Ack = Ack>(event: string, payload?: unknown, options: AckOptions<T> = {}): Promise<T | null> {
    const fail = (detail: string) => {
      if (options.onError) options.onError(detail)
      else toast.add({ severity: 'error', summary: 'Error', detail, life: 5000 })
      return null
    }
    let ack: T | undefined
    try {
      ack = await emitWithAck<T>(event, payload)
    } catch {
      return fail('Request failed — the connection to the server is down.')
    }
    if (!ack?.success) return fail(ack?.error || options.error || 'Request failed')
    const message = typeof options.success === 'function' ? options.success(ack) : options.success
    if (message) toast.add({ severity: 'success', summary: 'Success', detail: message, life: 3000 })
    return ack
  }

  return { request }
}
