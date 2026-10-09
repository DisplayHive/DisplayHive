/**
 * Shared logging utilities used by both screen and admin bundles.
 */

import type { LogSeverity, SocketEmitter } from "./types";

let loggerConnected = false;
let _socketEmitter: SocketEmitter | null = null;

/**
 * Inject a socket emitter so the logger does not access window.socket directly.
 * Call this once during initialisation (e.g. alongside setLoggerConnected).
 */
export function setLoggerSocketEmitter(
  emitter: SocketEmitter | null,
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
 * Always prints to the local console. With a socket emitter injected via `setLoggerSocketEmitter`
 * it also reports to the server (`displayhive:logger:cts:log_entry`), which stores the line in the
 * screen log: warnings and errors always, debug and info only while an admin watches the Logger
 * page (`setLoggerConnected`), so a screen's normal chatter does not fill the database.
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
  console.log(...actualArgs);

  // Forward to remote logger if connected
  try {
    if (_socketEmitter && (loggerConnected || severity === "warn" || severity === "error")) {
      const assigned = window.assignedScreen || "unnamed";
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
