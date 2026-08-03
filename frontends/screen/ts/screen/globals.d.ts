import type { Auth, DeviceConfig } from "./types";

declare const __GIT_COMMIT__: string;

declare global {
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

  interface Window {
    auth?: Auth;
    socket?: SocketIOClient.Socket | any;
    initializeSocketConnection?: () => void;
    initializeAuthentication?: () => void;
    deviceKey?: string | null;
    adoptionToken?: string | null;
    assignedScreen?: string;
    io?: any;
    _lastDeviceConfig?: DeviceConfig | null;
    __impersonate?: boolean;
    __displayhive_ping_interval?: ReturnType<typeof setInterval> | null;
    debugPanel?: {
      push: (
        section: string,
        group: string,
        key: string,
        value: string,
      ) => void;
      markUpdContent?: () => void;
    };
  }

  // QRCode.js global (loaded via CDN in templates)
  declare const QRCode: {
    CorrectLevel: {
      L: number;
      M: number;
      Q: number;
      H: number;
    };
    new (el: HTMLElement | null, opts: any): any;
  };
}

export {};
