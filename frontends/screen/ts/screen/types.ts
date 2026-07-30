/**
 * Type definitions for the screen client
 */

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

