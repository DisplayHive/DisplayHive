/**
 * Service worker of the screen page: lets a screen start and keep showing its last content while
 * the server is unreachable. What is cached how is decided in routing.ts.
 *
 *  - the page (`/`): network first (4 s), then the last copy;
 *  - the bundle, assets, logos, icons: cache first, in a cache named for the release's ASSET_VERSION
 *    (given as `?v=` on this script's URL, so a new release is a new worker with a new cache);
 *  - uploaded media: cache first, bounded;
 *  - everything else (Socket.IO, /admin, API) goes straight to the network.
 *
 * Loaded by the page as `/screen-sw.js?v=<ASSET_VERSION>` (see sw-register.ts).
 *
 * This file is type-checked with the DOM library like the rest of the screen client, so the few
 * worker-only parts of the API are described here instead of pulling in the `webworker` library.
 */

import {
  MEDIA_CACHE,
  MEDIA_MAX_ENTRIES,
  PAGE_NETWORK_TIMEOUT_MS,
  STATIC_CACHE_PREFIX,
  staticCacheName,
  strategyFor,
  strategyForResource,
} from "./routing";

interface ExtendableEventLike extends Event {
  waitUntil(promise: Promise<unknown>): void;
}
interface FetchEventLike extends ExtendableEventLike {
  request: Request;
  respondWith(response: Promise<Response> | Response): void;
}
interface MessageEventLike extends ExtendableEventLike {
  data: unknown;
}
interface WorkerScope {
  location: Location;
  skipWaiting(): Promise<void>;
  clients: { claim(): Promise<void> };
  addEventListener(type: string, listener: (event: never) => void): void;
}

const sw = self as unknown as WorkerScope;
const version = new URL(sw.location.href).searchParams.get("v") || "dev";
const STATIC = staticCacheName(version);
const origin = sw.location.origin;

sw.addEventListener("install", ((event: ExtendableEventLike) => {
  // A new release takes over at once; the page itself is reloaded by the screen client (or the
  // next scheduled reload).
  event.waitUntil(sw.skipWaiting());
}) as (event: never) => void);

sw.addEventListener("activate", ((event: ExtendableEventLike) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(names.filter((n) => n.startsWith(STATIC_CACHE_PREFIX) && n !== STATIC).map((n) => caches.delete(n)));
      await sw.clients.claim();
    })(),
  );
}) as (event: never) => void);

/** Keep the media cache at its limit: the entries stored first go first. */
async function trimMedia(cache: Cache): Promise<void> {
  const keys = await cache.keys();
  for (const key of keys.slice(0, Math.max(0, keys.length - MEDIA_MAX_ENTRIES))) await cache.delete(key);
}

const storable = (response: Response): boolean => response.status === 200 && response.type === "basic";

async function cacheFirst(request: Request, cacheName: string, trim: boolean): Promise<Response> {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(request);
  if (hit) return hit;
  const response = await fetch(request);
  if (storable(response)) {
    await cache.put(request, response.clone());
    if (trim) await trimMedia(cache);
  }
  return response;
}

async function networkFirstPage(request: Request): Promise<Response> {
  const cache = await caches.open(STATIC);
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), PAGE_NETWORK_TIMEOUT_MS);
    try {
      const response = await fetch(request, { signal: controller.signal });
      if (storable(response)) await cache.put(request, response.clone());
      return response;
    } finally {
      clearTimeout(timer);
    }
  } catch (error) {
    const hit = await cache.match(request);
    if (hit) return hit;
    throw error;
  }
}

sw.addEventListener("fetch", ((event: FetchEventLike) => {
  const request = event.request;
  const strategy = strategyFor(
    { method: request.method, url: request.url, mode: request.mode, hasRange: request.headers.has("range") },
    origin,
  );
  if (strategy === "page") event.respondWith(networkFirstPage(request));
  else if (strategy === "static") event.respondWith(cacheFirst(request, STATIC, false));
  else if (strategy === "media") event.respondWith(cacheFirst(request, MEDIA_CACHE, true));
}) as (event: never) => void);

// The page loaded before this worker controlled it: it reports what it is made of, so the very
// first visit is already available offline.
sw.addEventListener("message", ((event: MessageEventLike) => {
  const data = event.data as { type?: string; urls?: unknown; page?: unknown } | null;
  if (!data || data.type !== "cache-resources" || !Array.isArray(data.urls)) return;
  const page = typeof data.page === "string" ? data.page : null;
  const reported: unknown[] = data.urls;
  event.waitUntil(
    (async () => {
      const cache = await caches.open(STATIC);
      const urls = [...(page ? [page] : []), ...reported.filter((u): u is string => typeof u === "string")];
      for (const url of urls) {
        if (!strategyForResource(url, origin, url === page)) continue;
        if (await cache.match(url)) continue;
        try {
          const response = await fetch(url);
          if (storable(response)) await cache.put(url, response);
        } catch {
          /* offline or gone: it is cached when it is next requested */
        }
      }
    })(),
  );
}) as (event: never) => void);
