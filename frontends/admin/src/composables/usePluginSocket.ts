import { useAck, type Ack, type AckOptions } from './useAck'
import { useSocket } from './useSocket'

/**
 * A plugin's line to its own server side (`api.events.on(...)` in its backend):
 *
 *     const { call, rawCall, onPush, offPush } = usePluginSocket('acme.demo')
 *     const ack = await call('save', { name }, { success: 'Saved' })          // toast on success and on failure
 *     const plain = await rawCall<{ rows: string[] }>('rows')                 // the answer as it is, no toasts
 *     onPush('changed', handler)                                              // what the plugin pushes: displayhive:plugin:<id>:stc:changed
 *
 * All of it goes through the one `displayhive:plugin:call` event, so plugins can come and go while the server runs.
 */
export function usePluginSocket(pluginId: string) {
  const { request } = useAck()
  const { emitWithAck, whenConnected, on, off } = useSocket()

  // A page of a plugin opens on a fresh load as often as any other: it waits for the connection instead of failing.
  const call = async <T extends Ack = Ack>(event: string, data?: unknown, options: AckOptions<T> = {}) => {
    await whenConnected()
    return request<T>('displayhive:plugin:call', { plugin: pluginId, event, data }, options)
  }

  const rawCall = async <T = Ack>(event: string, data?: unknown) => {
    await whenConnected()
    return emitWithAck<T>('displayhive:plugin:call', { plugin: pluginId, event, data })
  }

  const pushName = (name: string) => `displayhive:plugin:${pluginId}:stc:${name}`
  const onPush = (name: string, callback: (...args: never[]) => void) => on(pushName(name), callback as (...args: unknown[]) => void)
  const offPush = (name: string, callback: (...args: never[]) => void) => off(pushName(name), callback as (...args: unknown[]) => void)

  return { call, rawCall, onPush, offPush }
}
