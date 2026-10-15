import { ref } from 'vue'
import { useAuthStore } from '../stores/auth'
import {
  creationOptionsFromJson,
  credentialToJson,
  passkeyErrorMessage,
  passkeysSupported,
} from '../utils/webauthn'

export interface Passkey {
  id: number
  name: string
  created_at: string | null
  last_used_at: string | null
  synced: boolean
}

/**
 * The signed-in person's own passkeys (application/security/passkeys.py): list, add, rename, remove.
 * Every function that can fail returns an error text, or null on success.
 */
export function usePasskeys() {
  const auth = useAuthStore()
  const passkeys = ref<Passkey[]>([])
  const available = ref(false)
  const loading = ref(false)
  const supported = passkeysSupported()

  const call = async (url: string, method: string, body?: unknown) => {
    const response = await fetch(url, {
      method,
      headers: { ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...auth.authHeader() },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    const result = await response.json().catch(() => ({}))
    return { ok: response.ok && !!result.success, result }
  }

  const load = async (): Promise<string | null> => {
    loading.value = true
    try {
      const { ok, result } = await call('/admin/api/auth/me/passkeys', 'GET')
      if (!ok) return result.error || 'Could not load your passkeys'
      passkeys.value = result.passkeys
      available.value = !!result.available
      return null
    } catch (e) {
      return `Could not reach server: ${e}`
    } finally {
      loading.value = false
    }
  }

  const add = async (name: string): Promise<string | null> => {
    if (!supported) return 'This browser does not support passkeys (they need https or localhost).'
    try {
      const started = await call('/admin/api/auth/me/passkeys/options', 'POST', {})
      if (!started.ok) return started.result.error || 'Could not start adding a passkey'
      let credential: PublicKeyCredential | null
      try {
        credential = (await navigator.credentials.create({ publicKey: creationOptionsFromJson(started.result.options) })) as PublicKeyCredential | null
      } catch (e) {
        return passkeyErrorMessage(e)
      }
      if (!credential) return 'No passkey was created.'
      const finished = await call('/admin/api/auth/me/passkeys/verify', 'POST', {
        challenge_id: started.result.challenge_id,
        credential: credentialToJson(credential),
        name,
      })
      if (!finished.ok) return finished.result.error || 'The passkey could not be saved'
      return await load()
    } catch (e) {
      return `Could not reach server: ${e}`
    }
  }

  const rename = async (id: number, name: string): Promise<string | null> => {
    try {
      const { ok, result } = await call(`/admin/api/auth/me/passkeys/${id}`, 'PATCH', { name })
      if (!ok) return result.error || 'Could not rename the passkey'
      return await load()
    } catch (e) {
      return `Could not reach server: ${e}`
    }
  }

  const remove = async (id: number): Promise<string | null> => {
    try {
      const { ok, result } = await call(`/admin/api/auth/me/passkeys/${id}`, 'DELETE')
      if (!ok) return result.error || 'Could not remove the passkey'
      return await load()
    } catch (e) {
      return `Could not reach server: ${e}`
    }
  }

  return { passkeys, available, loading, supported, load, add, rename, remove }
}
