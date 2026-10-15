import { describe, expect, it } from 'vitest'
import { base64urlToBuffer, bufferToBase64url, creationOptionsFromJson, requestOptionsFromJson } from '../webauthn'

describe('base64url', () => {
  it('round-trips bytes, including ones that need - and _', () => {
    const bytes = new Uint8Array([0, 250, 251, 252, 253, 254, 255, 62, 63])
    const text = bufferToBase64url(bytes)
    expect(text).not.toMatch(/[+/=]/)
    expect(Array.from(new Uint8Array(base64urlToBuffer(text)))).toEqual(Array.from(bytes))
  })

  it('reads text without padding', () => {
    expect(Array.from(new Uint8Array(base64urlToBuffer('AQID')))).toEqual([1, 2, 3])
    expect(Array.from(new Uint8Array(base64urlToBuffer('AQI')))).toEqual([1, 2])
  })
})

describe('options', () => {
  it('turns the creation options from the server into buffers', () => {
    const options = creationOptionsFromJson({
      challenge: 'AQID',
      rp: { id: 'localhost', name: 'DisplayHive' },
      user: { id: 'BAUG', name: 'alex', displayName: 'alex' },
      pubKeyCredParams: [{ type: 'public-key', alg: -7 }],
      excludeCredentials: [{ id: 'BwgJ', type: 'public-key' }],
    })
    expect(Array.from(new Uint8Array(options.challenge as ArrayBuffer))).toEqual([1, 2, 3])
    expect(Array.from(new Uint8Array(options.user.id as ArrayBuffer))).toEqual([4, 5, 6])
    expect(Array.from(new Uint8Array(options.excludeCredentials![0]!.id as ArrayBuffer))).toEqual([7, 8, 9])
  })

  it('turns the sign-in options into buffers', () => {
    const options = requestOptionsFromJson({ challenge: 'AQID', rpId: 'localhost', userVerification: 'required' })
    expect(Array.from(new Uint8Array(options.challenge as ArrayBuffer))).toEqual([1, 2, 3])
    expect(options.allowCredentials).toEqual([])
  })
})
