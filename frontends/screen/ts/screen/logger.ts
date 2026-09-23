/**
 * Shared logging utilities used by both screen and admin bundles.
 */

import type { LogSeverity } from "./types";

let loggerConnected = false;
let _socketEmitter: ((event: string, payload?: any) => void) | null = null;

/**
 * Inject a socket emitter so the logger does not access window.socket directly.
 * Call this once during initialisation (e.g. alongside setLoggerConnected).
 */
export function setLoggerSocketEmitter(
  emitter: ((event: string, payload?: any) => void) | null,
): void {
  _socketEmitter = emitter;
}

/**
 * Mark whether the remote logger (server-side) is currently connected.
 * @param connected - true when the logger endpoint is available
 */
export function setLoggerConnected(connected: boolean): void {
  loggerConnected = connected;
}

/**
 * Log wrapper that forwards messages to the server logger when connected.
 *
 * It preserves the original behaviour: always prints to the local console,
 * and if a socket emitter has been injected via `setLoggerSocketEmitter` and
 * the logger is connected it will emit a `screen_log` event with a simple payload.
 */
export function log(
  severity: LogSeverity,
  functionName: string | null,
  ...args: unknown[]
): void {
  // Determine message parts
  let actualFunction: string | null = null;
  let actualArgs: unknown[] = args;

  if (typeof functionName === "string" && args.length > 0) {
    actualFunction = functionName;
  } else if (functionName !== null && functionName !== undefined) {
    actualArgs = [functionName, ...args];
  }

  // Always log locally
  console.log(...(actualArgs as any));

  // Forward to remote logger if connected
  try {
    if (loggerConnected && _socketEmitter) {
      const assigned = (window as any).assignedScreen || "unnamed";
      const logPayload = {
        screen: assigned,
        severity,
        function: actualFunction || "",
        message: String(actualArgs.join(" ")),
        timestamp: new Date().toISOString(),
      };

      _socketEmitter("displayhive:logger:cts:log_entry", logPayload);
    }
  } catch (err) {
    // Swallow logging errors to avoid affecting runtime
    console.warn("log: failed to forward to remote logger", err);
  }
}
