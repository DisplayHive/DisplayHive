/**
 * Type definitions for the screen client
 */

import type { ManagerOptions, Socket, SocketOptions as SocketIoOptions } from "socket.io-client";

/** One container's rendered fragment within a Scene, positioned in vh/vw. */
export interface SceneContainer {
  name: string;
  top: number;
  left: number;
  width: number;
  height: number;
  html: string;
  css: string;
}

/**
 * A Scene is one ContentElement's turn in the shared screen-wide rotation.
 * `containers` already includes every container in the scene's own
 * Contenttype Layout — ones with real field content plus any of that same
 * Layout's containers falling back to their own default_content server-side
 * (see upd_content.py). Any container id not present here goes blank while
 * this Scene is showing, even if it belongs to a different Layout used by
 * another scene in the rotation.
 */
export interface Scene {
  id: number;
  title?: string;
  duration: number;
  /** When true, the client should request a fresh re-render after showing this scene. */
  update_after_show?: boolean;
  /** ISO 8601 datetime string — scene must not be shown before this time. */
  start_time?: string;
  /** ISO 8601 datetime string — scene must not be shown after this time. */
  end_time?: string;
  /** Keyed by ContentContainer id (string). */
  containers: Record<string, SceneContainer>;
}

/**
 * Generic socket command payload sent from server to screen clients.
 *
 * Required fields:
 * - `CMD`: short command name (e.g. "RELOAD").
 *
 * Additional command-specific fields may be present and are typed as unknown
 * so callers must validate/parse before use.
 */
export interface SocketCommand {
  CMD: string;
  [key: string]: unknown;
}

/** Device configuration pushed from server to a device client */
export interface DeviceConfig {
  // `devicekey` is sent by the server; keep `key` for compatibility if present.
  devicekey?: string | null;
  key?: string | null;
  name: string | null;
  screenname: string | null;
  devicedebugstate: "yes" | "no";
  glow: "yes" | "no";
  /** Clockwise rotation of the whole stage in degrees: 0, 90, 180 or 270. */
  rotation?: number;
  /** Show the status dot (status-indicator.ts)? Missing means yes. */
  statusindicator?: "yes" | "no";
  /** Daily reload time "HH:MM" in `timezone`; empty = off (scheduled-reload.ts). */
  reloadat?: string;
  /** The instance's time zone (IANA name). */
  timezone?: string;
}

export interface UpdDeviceConfigMessage {
  deviceconfig: DeviceConfig;
}

export type LogSeverity = "debug" | "info" | "warn" | "error";

export interface Auth {
  generateQRCode(text: string): void;
  showAdoptionOverlay(): void;
  hideAdoptionOverlay(): void;
  startAdoptionFlow(): void;
  initializeAuthentication(): void;
  getDeviceKey(): string | null;
}


// ---------------------------------------------------------------------------
// Socket.IO
// ---------------------------------------------------------------------------

/**
 * The Socket.IO v4 client types come from the `socket.io-client` package (a dev dependency, type
 * imports only — nothing of it is bundled). The client itself is a pinned script
 * (assets/socket.io.min.js, loaded by templates/index.html) that provides `window.io`; keep the
 * package version in line with the version of that script.
 */
export type ScreenSocket = Socket;

/** Options passed to the global `io()` factory. */
export type SocketOptions = Partial<ManagerOptions & SocketIoOptions>;

/** Fire-and-forget emit, injected into modules that must not hold the socket. */
export type SocketEmitter = (event: string, payload?: unknown) => void;

// ---------------------------------------------------------------------------
// Server → screen payloads
// ---------------------------------------------------------------------------

/** The active Design, part of `upd_content`. */
export interface DesignPayload {
  name?: string;
  html?: string;
  css?: string;
  /** Validated by indicator.ts's own normalize(). */
  indicator?: unknown;
  background_effect?: { name: string; settings: Record<string, unknown> } | null;
}

/** `upd_content`: the full content snapshot for this screen. */
export interface UpdContentMessage {
  server_time?: string;
  design?: DesignPayload | null;
  scenes?: Scene[];
}

/** `displayhive:screen:stc:content_updated`: freshly re-rendered containers of one element. */
export interface ContentUpdatedMessage {
  id?: number | string;
  containers?: Record<string, string>;
}

/** `displayhive:screen:stc:server_time` */
export interface ServerTimeMessage {
  server_time?: string;
}

/** `displayhive:devices:stc:adoption_approved` */
export interface AdoptionApprovedMessage {
  devicekey?: string;
}

/** `displayhive:devices:stc:connection_rejected` */
export interface ConnectionRejectedMessage {
  reason?: string;
  message?: string;
}

// ---------------------------------------------------------------------------
// window.debugPanel (debug-panel.ts) and the QRCode.js global
// ---------------------------------------------------------------------------

export interface DebugPlaylistItem {
  id: number;
  title?: string;
  duration: number;
}

export interface DebugLayoutContainer {
  id: string;
  name: string;
  top: number;
  left: number;
  width: number;
  height: number;
  hasContent: boolean;
}

/**
 * The debug overlay's API on `window.debugPanel`. Filled in from two sides —
 * debug-panel.ts provides the push* methods, index.ts the rotation controls —
 * so every member is optional.
 */
export interface DebugPanel {
  push?: (section: string, group: string, key: string, value: string) => void;
  pushPlaylist?: (
    containerName: string,
    items: DebugPlaylistItem[],
    currentId: number | null,
    startTime?: number | null,
    stopped?: boolean,
  ) => void;
  pushLayout?: (sceneTitle: string, containers: DebugLayoutContainer[]) => void;
  markUpdContent?: () => void;
  jumpToScene?: (id: number) => void;
  stopSceneRotation?: () => void;
  resumeSceneRotation?: () => void;
}

export interface QRCodeOptions {
  text: string;
  width?: number;
  height?: number;
  colorDark?: string;
  colorLight?: string;
  correctLevel?: number;
}

/** QRCode.js (loaded by templates/index.html as a global script). */
export interface QRCodeConstructor {
  new (el: HTMLElement | null, opts: QRCodeOptions): unknown;
  CorrectLevel: { L: number; M: number; Q: number; H: number };
}
