/**
 * How a screen comes back after losing the server.
 *
 * Two layers retry, with the same timing:
 *  - Socket.IO's own reconnection (transport drops, server restarts) — configured with
 *    `reconnectionOptions()` in socket-connection.ts;
 *  - a manual retry (`reconnectDelay`) for the cases Socket.IO does not retry by itself: the
 *    server refused the connection (e.g. a deactivated device) or closed it on purpose.
 *
 * The delay doubles from 1 s up to 30 s and is randomised by ±25 %, so a few hundred screens
 * do not all hit a restarting server in the same second, yet each is back within half a minute.
 */

export const RECONNECT_BASE_MS = 1_000;
export const RECONNECT_MAX_MS = 30_000;
/** Socket.IO's `randomizationFactor`: the delay varies by ± half of this. */
export const RECONNECT_RANDOMIZATION = 0.5;

/** Options for the `io()` factory: retry forever, with the backoff above. */
export function reconnectionOptions() {
  return {
    reconnection: true,
    reconnectionAttempts: Infinity,
    reconnectionDelay: RECONNECT_BASE_MS,
    reconnectionDelayMax: RECONNECT_MAX_MS,
    randomizationFactor: RECONNECT_RANDOMIZATION,
  };
}

/**
 * Delay in ms before manual retry number *attempt* (0 = the first).
 * `random` is a number in [0, 1) (injectable for tests).
 */
export function reconnectDelay(attempt: number, random: number = Math.random()): number {
  const base = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * 2 ** Math.max(0, attempt));
  const factor = 1 - RECONNECT_RANDOMIZATION / 2 + random * RECONNECT_RANDOMIZATION;
  return Math.round(base * factor);
}
