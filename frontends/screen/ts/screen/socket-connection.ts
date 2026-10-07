/**
 * Shared Socket.IO connection logic.
 */

import { setupSocketHandlers } from "./socket-handlers";
import { log } from "./logger";
import { getDeviceKey, getAdoptionToken } from "./storage";
import type { SocketOptions } from "./types";

/**
 * Resolve the connection keys from window globals and localStorage.
 * Returns the first deviceKey found and (if no deviceKey) an adoptionKey.
 */
function resolveConnectionKeys(wnd: Window): {
  deviceKey: string | null;
  adoptionKey: string | null;
} {
  let deviceKey: string | null = null;
  if (typeof wnd.deviceKey !== "undefined")
    deviceKey = String(wnd.deviceKey || "") || null;
  if (!deviceKey && typeof wnd.devicekey !== "undefined")
    deviceKey = String(wnd.devicekey || "") || null;
  if (!deviceKey) deviceKey = getDeviceKey();

  let adoptionKey: string | null = null;
  if (!deviceKey) {
    if (typeof wnd.adoptionToken !== "undefined")
      adoptionKey = String(wnd.adoptionToken || "") || null;
    if (!adoptionKey) adoptionKey = getAdoptionToken();
  }

  return { deviceKey, adoptionKey };
}

/**
 * Detect whether this session is a transient URL-param impersonation.
 */
function detectImpersonation(wnd: Window): boolean {
  try {
    return !!(
      wnd.__impersonate === true ||
      String(wnd.__impersonate) === "true"
    );
  } catch {
    return false;
  }
}

/**
 * Build Socket.IO connection options for the given key type.
 * Returns null when no key is available (caller should abort).
 */
function buildSocketOptions(
  deviceKey: string | null,
  adoptionKey: string | null,
  isImpersonation: boolean,
): SocketOptions | null {
  const base: SocketOptions = {
    reconnection: false,
    timeout: 20000,
  };

  if (deviceKey) {
    const query: Record<string, string> = { devicekey: deviceKey };
    const auth: Record<string, string> = { devicekey: deviceKey };
    const extraHeaders: Record<string, string> = { devicekey: deviceKey };
    if (isImpersonation) {
      query.impersonate = "true";
      auth.impersonate = "true";
      extraHeaders.impersonate = "true";
    }
    base.query = query;
    base.auth = auth;
    base.transportOptions = { polling: { extraHeaders } };
    // Merge any URL query params so the server sees them in request.args
    try {
      const search = window.location.search || "";
      if (search.length > 1) {
        const usp = new URLSearchParams(search);
        usp.forEach((value, key) => {
          if (typeof query[key] === "undefined") query[key] = value;
        });
      }
    } catch {
      /* ignore URL parsing errors */
    }
    return base;
  }

  if (adoptionKey) {
    base.query = { adoptionkey: adoptionKey };
    base.auth = { adoptionkey: adoptionKey };
    base.transportOptions = {
      polling: { extraHeaders: { adoptionkey: adoptionKey } },
    };
    return base;
  }

  return null;
}

/**
 * Initialize Socket.IO connection with authentication and shared handlers.
 */
export function initializeSocketConnection(): void {
  log("debug", "initializeSocketConnection", "called");

  // Plain Window (not `Window & typeof globalThis`): only the globals this app declares.
  const wnd: Window = window;

  const { deviceKey, adoptionKey } = resolveConnectionKeys(wnd);
  const isImpersonation = detectImpersonation(wnd);

  if (isImpersonation) {
    log("info", "initializeSocketConnection", "Impersonation detected; client will include impersonate flag in handshake");
  }

  const socketOptionsOrNull = buildSocketOptions(deviceKey, adoptionKey, isImpersonation);

  if (!socketOptionsOrNull) {
    console.error(
      "[socket-connection] Cannot initialize socket: no deviceKey or adoptionKey found",
    );
    log(
      "error",
      "initializeSocketConnection",
      "Socket initialization blocked: no keys available",
      { hasDeviceKey: false, hasAdoptionKey: false },
    );
    return;
  }

  const socketOptions: SocketOptions = socketOptionsOrNull;

  // Log a masked key preview before connecting
  if (deviceKey) {
    const masked = deviceKey.length > 4 ? `***${deviceKey.slice(-4)}` : "***";
    log("debug", "initializeSocketConnection", "Attaching deviceKey to connection options", {
      hasDeviceKey: true,
      maskedDeviceKey: masked,
    });
  } else if (adoptionKey) {
    const masked = adoptionKey.length > 4 ? `***${adoptionKey.slice(-4)}` : "***";
    log("debug", "initializeSocketConnection", "Attaching adoptionKey to connection options", {
      hasAdoptionKey: true,
      maskedAdoptionKey: masked,
    });
  }

  if (wnd.socket && typeof wnd.socket.disconnect === "function") {
    try {
      log(
        "debug",
        "initializeSocketConnection",
        "Cleaning up existing disconnected socket",
      );
      wnd.socket.disconnect();
    } catch (err) {
      log(
        "warn",
        "initializeSocketConnection",
        "Error while disconnecting previous socket",
        err,
      );
    }
    wnd.socket = null;
  }

  // Create the socket immediately if `io` is available. Otherwise attempt
  // to load the Socket.IO client script dynamically and create the socket
  // once it becomes available. This avoids the "Socket.IO not available"
  // error on pages that don't include the `<script src="...socket.io...">`
  // tag.
  function createSocketAndSetup() {
    const created = wnd.io ? wnd.io(socketOptions) : null;
    if (!created) {
      log(
        "error",
        "initializeSocketConnection",
        "Socket.IO not available after loading client",
      );
      return;
    }
    wnd.socket = created;
    log(
      "info",
      "initializeSocketConnection",
      "Socket created, setting up handlers",
    );
    setupSocketHandlers(created);

    // Global debug hook: re-dispatch every incoming socket event as a DOM
    // event. (onAny exists in the pinned Socket.IO v4 client; the old
    // onevent monkey-patch for pre-v3 clients is gone.)
    try {
      created.onAny((event: string, ...args: unknown[]) => {
        try {
          window.dispatchEvent(new CustomEvent("socket:any", { detail: { event, args } }));
          window.dispatchEvent(new CustomEvent(`socket:${event}`, { detail: args }));
        } catch {
          // ignore
        }
      });
    } catch (e) {
      // Ensure instrumentation never prevents normal socket setup
      log(
        "warn",
        "initializeSocketConnection",
        "Failed to attach global socket debug hook",
        e as Error,
      );
    }
  }

  if (wnd.io) {
    // io is already available; create socket synchronously
    createSocketAndSetup();
    return;
  }

  // The Socket.IO client is expected to already be loaded via the pinned,
  // integrity-checked <script> tag in templates/index.html. There is no
  // CDN fallback here — loading an unpinned copy at runtime would be an
  // unverified script-injection vector.
  log(
    "error",
    "initializeSocketConnection",
    "Socket.IO client (window.io) is not available; check that the script tag in index.html loaded successfully",
  );
}
