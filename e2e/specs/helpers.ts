import type { Page } from '@playwright/test'

/**
 * Send a socket event from the admin page and wait for its answer (the page exposes its socket for tests as
 * `window.__displayhive_socket__`). Rejects after 10 s. Used to seed data and to call the server directly.
 */
export async function emitAck<T = any>(page: Page, event: string, data: unknown): Promise<T> {
  return page.evaluate(
    ({ event, data }: { event: string; data: unknown }) =>
      new Promise<any>((resolve, reject) => {
        const socket = (window as any).__displayhive_socket__
        if (!socket) { reject(new Error('Socket not available')); return }
        const t = setTimeout(() => reject(new Error(`Timed out: ${event}`)), 10_000)
        socket.emit(event, data, (ack: any) => { clearTimeout(t); resolve(ack) })
      }),
    { event, data },
  )
}
