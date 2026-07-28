/**
 * Socket.IO event handlers for the screen client.
 *
 * Event lifecycle:
 *   connect
 *     └─► device authenticated  → upd_deviceconfig (debug/glow/screenname)
 *                               → upd_content (full content snapshot)
 *                                   └─► device_request (fetch missing HTML)
 *                                   └─► content_updated (single item re-render)
 *     └─► adoption flow         → displayhive:devices:stc:adoption_approved
 *                                   └─► page reload with new deviceKey
 *     └─► device inactive       → showDeactivationOverlay, retry in 20 s
 *     └─► invalid key           → startAdoptionFlow
 *   disconnect                  → reconnect in 20 s (manual, reconnection=false)
 *   command (CMD=RELOAD|DEVICE_DEACTIVATED|DEVICE_REVOKED)
 */

import { log, setLoggerConnected, setLoggerSocketEmitter } from "./logger";
import type {
  SocketCommand,
  UpdDeviceConfigMessage,
  DeviceConfig,
  Scene,
  ContainerDefault,
} from "./types.js";
import { setSocketEmitter, setContainerDefaults } from "./container-manager.js";
import { startSceneRotation, patchCurrentScene } from "./content-display.js";
import { applyServerTime, setClockEmitter, startClockTicker } from "./clock.js";
import { startAdoptionFlow, hideAdoptionOverlay } from "./adopt.js";
import { setDeviceKey, clearAdoptionToken } from "./storage";
import { preloadIframesInHtml } from "./preload-iframes.js";
import { initViewportTracking, emitCurrentViewport } from "./viewport-tracker";

// Track if device is deactivated (prevents hiding overlay on reconnect)
let _isDeactivated = false;

/** Show the static deactivation overlay (defined in index.html, styled in screen.css). */
function showDeactivationOverlay(): void {
  document.getElementById("deactivated-overlay")?.classList.add("show");
}

/** Hide the deactivation overlay when the connection is restored. */
function hideDeactivationOverlay(): void {
  document.getElementById("deactivated-overlay")?.classList.remove("show");
}

// ---------------------------------------------------------------------------
// Module-level helpers
// ---------------------------------------------------------------------------

/** Schedule a manual socket reconnect after `delayMs` ms (default 20 s). */
function scheduleReconnect(socket: any, delayMs = 20_000): void {
  setTimeout(() => socket?.connect?.(), delayMs);
}

/** Clear the device ping interval if one is running. */
function stopPingInterval(): void {
  clearInterval(window.__displayhive_ping_interval ?? undefined);
  window.__displayhive_ping_interval = null;
}

/** Send an immediate ping then repeat every 30 s. Clears any existing interval first. */
function startPingInterval(socket: any): void {
  stopPingInterval();
  socket.emit("displayhive:devices:cts:ping", {});
  window.__displayhive_ping_interval = setInterval(
    () => socket.emit("displayhive:devices:cts:ping", {}),
    30_000,
  );
}

/**
 * Initialise preview-mode content when the URL contains `preview=true`.
 *
 * A previewed ContentElement is shown full-bleed as a single ad-hoc scene —
 * preview is a quick one-off look at one item's rendered output, not a real
 * position within a Layout, so container placement doesn't apply here.
 */
function handlePreviewMode(socket: any): void {
  const params = new URLSearchParams(window.location.search);
  if (params.get("preview") !== "true") return;
  const previewContentId = parseInt(params.get("content_id") || "", 10);
  if (!previewContentId) return;

  log("info", "preview", `Preview mode for content ${previewContentId}`);
  socket.emit("device_request", { type: "contentelement", id: previewContentId });
}

/** Start the device ping on connect, unless this is an impersonation session. */
function handlePingOnConnect(socket: any): void {
  if (window.__impersonate === true || !window.deviceKey) return;
  startPingInterval(socket);
}

/** Toggle the debug panel visibility based on `devicedebugstate` in the device config. */
function applyDebugState(cfg: DeviceConfig, prev: DeviceConfig | null): void {
  if (prev?.devicedebugstate === cfg.devicedebugstate) return;
  const dbg = cfg.devicedebugstate === "yes";
  const el = document.getElementById("debug-panel");
  if (el) el.style.display = dbg ? "flex" : "none";
  log("info", "applyDebugState", dbg ? "Debug enabled" : "Debug disabled");
}

/**
 * Update the assigned screen name from the device config.
 * Skipped in preview mode to avoid overwriting the previewed screen's name.
 */
function applyScreenName(cfg: DeviceConfig, prev: DeviceConfig | null): void {
  const newName = cfg.screenname;
  if (!newName || prev?.screenname === newName) return;
  if (new URLSearchParams(window.location.search).get("preview") === "true") {
    log("info", "applyScreenName", "Ignoring screenname update in preview mode");
    return;
  }
  window.assignedScreen = newName;
  const el = document.getElementById("debug-screen-name");
  if (el) el.textContent = newName;
  window.debugPanel?.push("Screen Info", "Screen", "Name", newName);
  log("info", "applyScreenName", "Assigned screen name:", newName);
}

/** Apply or remove the green glow border on the body from the device config. */
function applyGlowState(cfg: DeviceConfig, prev: DeviceConfig | null): void {
  if (prev?.glow === cfg.glow) return;
  const glowOn = cfg.glow === "yes";
  log("info", "applyGlowState", glowOn ? "Activating glow" : "Deactivating glow");
  if (glowOn) {
    document.body.style.border = "10px solid #00ff00";
    document.body.style.boxShadow =
      "0 0 30px 10px rgba(0, 255, 0, 0.8), inset 0 0 30px 10px rgba(0, 255, 0, 0.3)";
    (document.body.style as any).boxSizing = "border-box";
  } else {
    document.body.style.border = "";
    document.body.style.boxShadow = "";
    (document.body.style as any).boxSizing = "";
  }
}

type ConnectErrorKind = "device_inactive" | "invalid_key" | "refused" | "unknown";

/**
 * Classify a socket `connect_error` into a known kind for handler dispatch.
 * Matches only against error.message to avoid false positives from transport-layer
 * or proxy errors that happen to contain "invalid key" in their body.
 * The server exclusively uses ConnectionRefusedError('invalid_key') / ('device_inactive'),
 * so exact match on message is both sufficient and precise.
 */
function classifyConnectError(error: unknown): ConnectErrorKind {
  const msg = String((error as any)?.message ?? error ?? "").toLowerCase();
  if (msg === "invalid_key") return "invalid_key";
  if (msg === "device_inactive" || msg.includes("deactivated") || msg.includes("device inactive")) return "device_inactive";
  if (msg.includes("unauthor") || msg.includes("refus")) return "refused";
  return "unknown";
}

/**
 * Setup all socket event handlers.
 * Call once after the socket is created; the socket instance is closed over
 * by every inner handler so no globals are needed.
 */
export function setupSocketHandlers(socket: any): void {
  log("debug", "setupSocketHandlers", "Initializing socket event handlers");

  // Share a single safe-emit wrapper with both container-manager and logger
  // so neither module needs a direct reference to the socket.
  const safeEmit = (event: string, payload?: any): void => {
    try { socket.emit(event, payload); } catch { /* swallow emit errors */ }
  };
  setSocketEmitter(safeEmit);
  setLoggerSocketEmitter(safeEmit);
  setClockEmitter(safeEmit);
  initViewportTracking(safeEmit);
  startClockTicker();

  socket.on("connect", () => {
    log("info", "socket.connect", "Connected to server", { deviceKey: window.deviceKey });
    if (!_isDeactivated) hideDeactivationOverlay();
    handlePreviewMode(socket);
    handlePingOnConnect(socket);
  });

  // Handle adoption approval from server (during adoption flow)
  socket.on("displayhive:devices:stc:adoption_approved", (data: any) => {
    log("info", "socket.adoption_approved", "Server approved adoption", data);
    const devicekey = data?.devicekey;
    if (!devicekey) return;

    // Persist the new device key, clear the adoption token, and reload so
    // the full auth flow restarts with the permanent key.
    setDeviceKey(String(devicekey));
    window.deviceKey = String(devicekey);
    clearAdoptionToken();
    window.adoptionToken = null;
    hideAdoptionOverlay();
    stopPingInterval();
    socket.disconnect();
    setTimeout(() => window.location.reload(), 500);
  });

  // Successful authentication means the device is active — clear deactivation state.
  socket.on("displayhive:devices:stc:device_authenticated", (_data: any) => {
    _isDeactivated = false;
    hideDeactivationOverlay();
    emitCurrentViewport();
  });

  // Explicit rejection from server (critical for polling transports where connect_error may not fire).
  socket.on("displayhive:devices:stc:connection_rejected", (data: any) => {
    const reason = String(data?.reason || "").toLowerCase();
    const message = String(data?.message || "").toLowerCase();
    if (!reason.includes("device_inactive") && !message.includes("deactiv")) return;
    log("warn", "socket.on(connection_rejected)", "Device inactive", data);
    _isDeactivated = true;
    hideAdoptionOverlay();
    showDeactivationOverlay();
    socket.disconnect();
    scheduleReconnect(socket);
  });

  socket.on("connect_error", (error: any) => {
    log("error", "socket.connect_error", "Connection error: " + error);
    const kind = classifyConnectError(error);

    if (kind === "device_inactive") {
      log("error", "socket.connect_error", "Device deactivated by admin");
      _isDeactivated = true;
      showDeactivationOverlay();
      hideAdoptionOverlay();
      scheduleReconnect(socket);
      return;
    }

    if (kind === "invalid_key") {
      log("error", "socket.connect_error", "Invalid key, starting adoption", String(error));
      setDeviceKey(null);
      clearAdoptionToken();
      window.deviceKey = null;
      window.adoptionToken = null;
      startAdoptionFlow();
      return;
    }

    if (kind === "refused") {
      log("warn", "socket.connect_error", "Connection refused, retrying in 20 s");
      scheduleReconnect(socket);
      return;
    }

    // Server unreachable (e.g. "xhr poll error") — keep the retry loop alive so
    // the device recovers automatically when the server comes back up, regardless
    // of whether it is in adoption or deactivated state.
    log("warn", "socket.connect_error", "Transient network error, retrying in 20 s");
    scheduleReconnect(socket);
  });

  // Handle disconnect events
  socket.on("disconnect", (reason: string) => {
    log("warn", "socket.disconnect", "Socket disconnected", { reason });
    stopPingInterval();
    // "io client disconnect" means we called socket.disconnect() ourselves (e.g.
    // during adoption-flow cleanup or after adoption approval before page reload).
    // Those paths schedule their own reconnect or reload, so skip here.
    if (reason === "io client disconnect") return;
    // For all other drops — including while deactivated — keep retrying so the
    // device recovers when the server comes back or the admin re-enables it.
    scheduleReconnect(socket);
  });

  // Listen for logger connection status
  socket.on("logger_active", () => {
    setLoggerConnected(true);
    log("info", "socket.on(logger_active)", "Logger is now active");
  });

  socket.on("logger_inactive", () => {
    setLoggerConnected(false);
  });

  // Note: debug_mode and screen_rename are both handled via `upd_deviceconfig`

  // Unified device config push from backend
  socket.on("upd_deviceconfig", (msg: UpdDeviceConfigMessage) => {
    const cfg: DeviceConfig | null = msg?.deviceconfig ?? null;
    if (!cfg) return;
    log("info", "socket.on(upd_deviceconfig)", "Received device config", JSON.stringify(cfg));
    const prev: DeviceConfig | null = window._lastDeviceConfig ?? null;
    applyDebugState(cfg, prev);
    applyScreenName(cfg, prev);
    applyGlowState(cfg, prev);
    window._lastDeviceConfig = cfg;
  });

  // Listen for generic command events from admin (payload must include a 'CMD' field)
  socket.on("command", (msg: SocketCommand) => {
    log("info", "socket.on(command)", "Received command", JSON.stringify(msg));
    if (!msg?.CMD) {
      log("warn", "socket.on(command)", "Ignoring command without CMD field");
      return;
    }
    const cmd = String(msg.CMD).toUpperCase();

    if (cmd === "RELOAD") {
      window.location.reload();
      return;
    }

    if (cmd === "DEVICE_DEACTIVATED") {
      log("warn", "socket.on(command)", "Device deactivated by admin");
      _isDeactivated = true;
      hideAdoptionOverlay();
      showDeactivationOverlay();
      return;
    }

    if (cmd === "DEVICE_REVOKED" || cmd === "DEVICE_REVOKE") {
      // Admin revoked this device key — clear stored key and reload into adoption flow.
      try { localStorage.removeItem("deviceKey"); } catch { /* ignore */ }
      socket.disconnect();
      setTimeout(() => window.location.reload(), 500);
      return;
    }

    log("info", "socket.on(command)", "Unhandled CMD:", cmd);
  });

  // Listen for playlist response (IDs and durations only)
  // Unified full content snapshot pushed by server after deviceconfig
  socket.on("upd_content", (msg: any, cb?: () => void) => {
    try {
      try {
        if (
          window.debugPanel &&
          typeof window.debugPanel.markUpdContent === "function"
        ) {
          window.debugPanel.markUpdContent();
        }
      } catch (_) {}

      if (msg.server_time) applyServerTime(String(msg.server_time));

      const design = msg.design || null;
      const scenes: Scene[] = msg.scenes || [];
      const containerDefaults: Record<string, ContainerDefault> = msg.container_defaults || {};

      log("debug", "socket.on(upd_content)", "Received content snapshot", {
        sceneCount: scenes.length,
      });

      // Must be set before startSceneRotation() below, which synchronously
      // renders the first active scene and needs these to fall back on.
      setContainerDefaults(containerDefaults);
      for (const def of Object.values(containerDefaults)) {
        if (def.html) preloadIframesInHtml(def.html);
      }

      // Apply the Design background (a single global skin — see
      // #design-background in index.html, kept separate from
      // #scene-containers so re-rendering scenes never touches it).
      if (design) {
        window.debugPanel?.push(
          "Screen Info",
          "Design",
          "Name",
          typeof design.name === "string" && design.name ? design.name : "—",
        );
        if (typeof design.html === "string") {
          const backgroundEl = document.getElementById("design-background");
          if (backgroundEl) backgroundEl.innerHTML = design.html;
        }
        if (typeof design.css === "string") {
          const styleEl = document.getElementById("template-css");
          if (styleEl) styleEl.textContent = design.css;
        }
      }

      // Preload any iframes embedded in scene HTML so they're warm by the
      // time each scene's turn comes up in the rotation.
      for (const scene of scenes) {
        for (const container of Object.values(scene.containers)) {
          if (container.html) preloadIframesInHtml(container.html);
        }
      }

      startSceneRotation(scenes);

      if (cb) cb();
    } catch (e) {
      log(
        "error",
        "socket.on(upd_content)",
        "Error processing upd_content:",
        String(e),
      );
      if (cb) cb();
    }
  });

  // Server-time resync response (triggered every 30 min by clock.ts)
  socket.on("displayhive:screen:stc:server_time", (msg: any) => {
    if (msg?.server_time) applyServerTime(String(msg.server_time));
  });

  // Receive freshly re-rendered HTML for a scene's containers (e.g. a random
  // image refresh). If that scene is currently showing, patch its container
  // elements in place — the rotation timer keeps running unaffected.
  socket.on("displayhive:screen:stc:content_updated", (msg: any) => {
    log("debug", "socket.on(content_updated)", "Received content_updated", msg);
    const id: number = parseInt(msg?.id, 10);
    const containers: Record<string, string> | undefined = msg?.containers;
    if (!id || !containers) return;
    for (const html of Object.values(containers)) {
      if (typeof html === "string") preloadIframesInHtml(html);
    }
    patchCurrentScene(id, containers);
  });
}
