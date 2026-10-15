/** A readable reason for a failed fetch() answer: the server's own message if it sent one, else one for the status. */
export async function httpErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.clone().json()
    if (body && typeof body.error === 'string' && body.error) return body.error
  } catch {
    // not JSON (a proxy's page, an empty body) — fall through to the status
  }
  switch (response.status) {
    case 401:
      return 'Your session has expired — sign in again.'
    case 403:
      return 'Not allowed — you lack the right for this.'
    case 413:
      return 'The file is too large for the server (check the reverse proxy limit).'
    case 502:
    case 503:
    case 504:
      return 'The server is not reachable right now (is it restarting?).'
    default:
      return `The server answered with HTTP ${response.status}.`
  }
}

/** The text of a caught error, without the leading "Error: " that String(e) adds. */
export function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}
