import { describe, expect, it } from 'vitest'
import { errorText, httpErrorMessage } from '../httpError'

const answer = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status })

describe('httpErrorMessage', () => {
  it('uses the message the server sent', async () => {
    expect(await httpErrorMessage(answer(500, { success: false, error: 'Boom (reference ab12cd34)' }))).toBe(
      'Boom (reference ab12cd34)',
    )
  })

  it('explains the usual statuses when there is no message', async () => {
    expect(await httpErrorMessage(answer(401))).toMatch(/session has expired/)
    expect(await httpErrorMessage(answer(403))).toMatch(/Not allowed/)
    expect(await httpErrorMessage(answer(413))).toMatch(/too large/)
    expect(await httpErrorMessage(answer(502))).toMatch(/not reachable/)
  })

  it('names the status otherwise', async () => {
    expect(await httpErrorMessage(answer(500))).toBe('The server answered with HTTP 500.')
  })
})

describe('errorText', () => {
  it('drops the "Error: " prefix', () => {
    expect(errorText(new Error('nope'))).toBe('nope')
    expect(errorText('plain')).toBe('plain')
  })
})
