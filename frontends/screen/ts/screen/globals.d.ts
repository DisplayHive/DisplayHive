import type {
  Auth,
  DebugPanel,
  DeviceConfig,
  QRCodeConstructor,
  ScreenSocket,
  SocketOptions,
} from "./types";

declare global {
  const __GIT_COMMIT__: string;

  // Minimal hand-rolled Vite client types — this project doesn't pull in
  // the full `vite/client` type package, so only what's actually used
  // (import.meta.env.BASE_URL, read in icon-libraries.ts to resolve /icons/
  // paths correctly under this bundle's configured `base`) is declared here.
  interface ImportMetaEnv {
    readonly BASE_URL: string;
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }

  /** Every global the screen client reads or writes on `window`. */
  interface Window {
    auth?: Auth;
    socket?: ScreenSocket | null;
    /** Socket.IO client factory (assets/socket.io.min.js). */
    io?: (opts?: SocketOptions) => ScreenSocket;
    initializeSocketConnection?: () => void;
    initializeAuthentication?: () => void;
    startAdoptionFlow?: () => void;
    deviceKey?: string | null;
    /** Older spelling some deployments' pages still set. */
    devicekey?: string | null;
    adoptionToken?: string | null;
    assignedScreen?: string;
    _lastDeviceConfig?: DeviceConfig | null;
    /** Set by auth_helper.ts for URL-parameter impersonation (may arrive as "true"). */
    __impersonate?: boolean | string;
    __displayhive_ping_interval?: ReturnType<typeof setInterval> | null;
    debugPanel?: DebugPanel;
    QRCode?: QRCodeConstructor;
  }

  /** QRCode.js global (templates/index.html). */
  const QRCode: QRCodeConstructor;
}

export {};
