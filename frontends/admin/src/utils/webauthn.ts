/**
 * The browser side of passkeys (WebAuthn). The server speaks JSON with base64url strings
 * (application/security/passkeys.py); `navigator.credentials` wants ArrayBuffers. These helpers
 * convert in both directions and keep the calls out of the components.
 */

export function bufferToBase64url(buffer: ArrayBuffer | Uint8Array): string {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer)
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

export function base64urlToBuffer(text: string): ArrayBuffer {
  const padded = text.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(text.length / 4) * 4, '=')
  const binary = atob(padded)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes.buffer
}

interface DescriptorJson {
  id: string
  type: PublicKeyCredentialType
  transports?: AuthenticatorTransport[]
}

export interface CreationOptionsJson extends Omit<PublicKeyCredentialCreationOptions, 'challenge' | 'user' | 'excludeCredentials'> {
  challenge: string
  user: { id: string; name: string; displayName: string }
  excludeCredentials?: DescriptorJson[]
}

export interface RequestOptionsJson extends Omit<PublicKeyCredentialRequestOptions, 'challenge' | 'allowCredentials'> {
  challenge: string
  allowCredentials?: DescriptorJson[]
}

const descriptor = (d: DescriptorJson): PublicKeyCredentialDescriptor => ({ ...d, id: base64urlToBuffer(d.id) })

export function creationOptionsFromJson(json: CreationOptionsJson): PublicKeyCredentialCreationOptions {
  return {
    ...json,
    challenge: base64urlToBuffer(json.challenge),
    user: { ...json.user, id: base64urlToBuffer(json.user.id) },
    excludeCredentials: (json.excludeCredentials ?? []).map(descriptor),
  }
}

export function requestOptionsFromJson(json: RequestOptionsJson): PublicKeyCredentialRequestOptions {
  return {
    ...json,
    challenge: base64urlToBuffer(json.challenge),
    allowCredentials: (json.allowCredentials ?? []).map(descriptor),
  }
}

/** The credential the browser made or used, as the JSON the server expects. */
export function credentialToJson(credential: PublicKeyCredential): Record<string, unknown> {
  const response = credential.response
  const base = {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment ?? undefined,
    clientExtensionResults: credential.getClientExtensionResults(),
  }
  if ('attestationObject' in response) {
    const attestation = response as AuthenticatorAttestationResponse
    return {
      ...base,
      response: {
        clientDataJSON: bufferToBase64url(attestation.clientDataJSON),
        attestationObject: bufferToBase64url(attestation.attestationObject),
        transports: typeof attestation.getTransports === 'function' ? attestation.getTransports() : [],
      },
    }
  }
  const assertion = response as AuthenticatorAssertionResponse
  return {
    ...base,
    response: {
      clientDataJSON: bufferToBase64url(assertion.clientDataJSON),
      authenticatorData: bufferToBase64url(assertion.authenticatorData),
      signature: bufferToBase64url(assertion.signature),
      userHandle: assertion.userHandle ? bufferToBase64url(assertion.userHandle) : undefined,
    },
  }
}

/** Does this browser (in a secure context) offer passkeys at all? */
export function passkeysSupported(): boolean {
  return typeof window !== 'undefined' && window.isSecureContext && typeof window.PublicKeyCredential === 'function' && !!navigator.credentials
}

/** A readable reason for a failed or cancelled browser ceremony. */
export function passkeyErrorMessage(e: unknown): string {
  const name = e instanceof DOMException ? e.name : ''
  if (name === 'NotAllowedError' || name === 'AbortError') return 'Cancelled, or no passkey was chosen.'
  if (name === 'InvalidStateError') return 'This device already has a passkey for this account.'
  if (name === 'SecurityError') return 'Passkeys do not work at this address (it needs https or localhost).'
  if (name === 'NotSupportedError') return 'This device cannot create a passkey that unlocks with a PIN, fingerprint or face.'
  return e instanceof Error ? e.message : String(e)
}
