/**
 * What the screen's service worker does with a request — pure functions, no worker globals, so
 * they can be tested (see routing.test.ts) and shared with the page code.
 *
 * The caches:
 *  - `dh-screen-static-<ASSET_VERSION>`: the page (`/`) and what it is made of — the bundle, its
 *    chunks and assets, logos, icons. A new release has a new version, so its worker starts a fresh
 *    cache and deletes the old ones.
 *  - `dh-screen-media`: uploaded media and their previews/renditions, and the installed icons. A file's URL never changes
 *    its content, so this cache has no version; it is kept to MEDIA_MAX_ENTRIES (oldest out first).
 */

export type Strategy = "page" | "static" | "media" | "bypass";

export const STATIC_CACHE_PREFIX = "dh-screen-static-";
export const MEDIA_CACHE = "dh-screen-media";
export const MEDIA_MAX_ENTRIES = 300;
/** How long the page waits for the server before falling back to its cached copy. */
export const PAGE_NETWORK_TIMEOUT_MS = 4_000;

const STATIC_PREFIXES = ["/dist/screen/", "/screen/assets/"];
const STATIC_FILES = ["/logo_bl.png", "/logo_wh.png", "/favicon.ico", "/favicon-32x32.png", "/favicon-16x16.png", "/apple-touch-icon.png"];
const MEDIA_PREFIXES = ["/static/media/", "/static/media_previews/", "/static/media_renditions/", "/static/icons/"];
/** The icon libraries' index files change when one is installed or removed: always from the network. */
const ICON_INDEXES = ["/static/icons/manifest.json", "/static/icons/libraries.json"];
/** The worker script itself and Socket.IO must never be served from a cache. */
const NEVER = ["/screen-sw.js", "/socket.io/"];

export const staticCacheName = (version: string): string => `${STATIC_CACHE_PREFIX}${version}`;

export interface RequestInfo {
  method: string;
  url: string;
  /** `request.mode`: "navigate" for a page load. */
  mode: string;
  hasRange: boolean;
}

/** The query parameters of a screen page that make it show something other than the device's own content. */
const isSpecialPage = (search: string): boolean => /(^|[?&])(preview|impersonate)=/.test(search);

export function strategyFor(request: RequestInfo, origin: string): Strategy {
  if (request.method !== "GET" || request.hasRange) return "bypass";
  let url: URL;
  try {
    url = new URL(request.url);
  } catch {
    return "bypass";
  }
  if (url.origin !== origin) return "bypass";
  const path = url.pathname;
  if (NEVER.some((p) => path === p || path.startsWith(p)) || ICON_INDEXES.includes(path)) return "bypass";
  if (request.mode === "navigate") {
    return path === "/" && !isSpecialPage(url.search) ? "page" : "bypass";
  }
  if (STATIC_PREFIXES.some((p) => path.startsWith(p)) || STATIC_FILES.includes(path)) return "static";
  if (MEDIA_PREFIXES.some((p) => path.startsWith(p))) return "media";
  return "bypass";
}

/**
 * The strategy for a URL the page reports as one of its resources (the worker could not see the
 * requests that were made before it took control), or null for anything it should not store.
 */
export function strategyForResource(url: string, origin: string, isPage: boolean): Exclude<Strategy, "bypass" | "media"> | null {
  const s = strategyFor({ method: "GET", url, mode: isPage ? "navigate" : "no-cors", hasRange: false }, origin);
  return s === "page" || s === "static" ? s : null;
}
