/**
 * Bounded, explicitly-managed offline cache for `random_tags` image field
 * candidates.
 *
 * Deliberately NOT the browser's ambient HTTP cache: that's an opaque cache
 * subject to eviction under storage pressure with no size/count control of
 * our own — so this module fetches candidates explicitly, stores them in
 * a named Cache Storage bucket, and hands back object URLs read straight
 * from the cached bytes, guaranteeing a picked image can always be shown
 * offline as long as it's in the manifest below. (The service worker,
 * ts/sw, also keeps recently used media, bounded by count; this cache is
 * the one with a byte budget and a say in *which* candidate is shown.)
 *
 * The manifest (url/size/lastUsed per entry) is the only thing persisted to
 * localStorage (see storage.ts) — tiny bookkeeping, not image bytes.
 */

import { getRandomImageManifest, setRandomImageManifest } from "./storage.js";
import { log } from "./logger.js";
import { markRenditionMissing } from "./media-renditions.js";

const CACHE_NAME = "dh-random-images";
const DEFAULT_MAX_ENTRIES = 40;
const DEFAULT_MAX_BYTES = 60 * 1024 * 1024; // 60 MB

interface ManifestEntry {
  url: string;
  size: number;
  lastUsed: number;
}

export interface Budget {
  maxEntries?: number;
  maxBytes?: number;
}

function readManifest(): ManifestEntry[] {
  try {
    const raw = getRandomImageManifest();
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeManifest(entries: ManifestEntry[]): void {
  try {
    setRandomImageManifest(JSON.stringify(entries));
  } catch {
    /* intentional: storage may be unavailable */
  }
}

function cacheStorageAvailable(): boolean {
  return typeof caches !== "undefined";
}

/** Random choice among `candidates` restricted to what's actually cached — never picks blind. */
export function pickCached(candidates: string[]): string | null {
  if (!candidates.length) return null;
  const cachedUrls = new Set(readManifest().map((e) => e.url));
  const available = candidates.filter((u) => cachedUrls.has(u));
  if (!available.length) return null;
  return available[Math.floor(Math.random() * available.length)];
}

/** Read a cached image's bytes back out as an object URL for `<img src>`. Caller must revoke it when done with it. */
export async function getObjectUrl(url: string): Promise<string | null> {
  if (!cacheStorageAvailable()) return null;
  try {
    const cache = await caches.open(CACHE_NAME);
    const response = await cache.match(url);
    if (!response) return null;
    const blob = await response.blob();
    return URL.createObjectURL(blob);
  } catch (e) {
    log("debug", "getObjectUrl", "Failed to read cached image", url, e);
    return null;
  }
}

// Guards against firing a second fetch for a URL that's already mid-flight
// (e.g. the same pool resolved in two containers at once).
const inFlight = new Set<string>();

/**
 * Fire-and-forget background top-up: fetch at most ONE not-yet-cached
 * candidate (never a batch of the whole pool — this is meant to be cheap
 * and called on every resolve, piggybacking on the normal rotation
 * cadence). Only once that fetch succeeds and is stored does it check the
 * budget and evict oldest-by-`lastUsed` entries — excluding
 * `opts.currentlyDisplayed` and the just-fetched entry — until back under
 * budget. Eviction never happens before a replacement is confirmed stored,
 * and the currently-displayed image is never evicted out from under itself.
 */
export async function topUp(
  candidates: string[],
  budget: Budget = {},
  opts: { currentlyDisplayed?: string } = {},
): Promise<void> {
  if (!cacheStorageAvailable()) return;
  if (typeof navigator !== "undefined" && navigator.onLine === false) return;

  const maxEntries = budget.maxEntries ?? DEFAULT_MAX_ENTRIES;
  const maxBytes = budget.maxBytes ?? DEFAULT_MAX_BYTES;

  const manifest = readManifest();
  if (opts.currentlyDisplayed) {
    const entry = manifest.find((e) => e.url === opts.currentlyDisplayed);
    if (entry) entry.lastUsed = Date.now();
  }

  const cachedUrls = new Set(manifest.map((e) => e.url));
  const missing = candidates.filter((u) => !cachedUrls.has(u) && !inFlight.has(u));
  if (!missing.length) {
    writeManifest(manifest); // persist the lastUsed touch above even if nothing to fetch
    return;
  }

  const next = missing[Math.floor(Math.random() * missing.length)];
  inFlight.add(next);
  try {
    const response = await fetch(next);
    if (!response.ok) {
      // A 404 for a rendition means the source was smaller than that tier —
      // remember it so the next pass asks for the original instead.
      markRenditionMissing(next);
      return;
    }
    const size = Number(response.headers.get("content-length")) || 0;
    const cache = await caches.open(CACHE_NAME);
    await cache.put(next, response.clone());
    manifest.push({ url: next, size, lastUsed: Date.now() });

    const protectedUrls = new Set([opts.currentlyDisplayed, next].filter(Boolean) as string[]);
    manifest.sort((a, b) => a.lastUsed - b.lastUsed);
    let totalBytes = manifest.reduce((sum, e) => sum + e.size, 0);
    while (manifest.length > maxEntries || totalBytes > maxBytes) {
      const idx = manifest.findIndex((e) => !protectedUrls.has(e.url));
      if (idx === -1) break; // everything left is protected — stop rather than evict those
      const [evicted] = manifest.splice(idx, 1);
      totalBytes -= evicted.size;
      try {
        await cache.delete(evicted.url);
      } catch {
        /* intentional: best-effort cleanup */
      }
    }

    writeManifest(manifest);
    log(
      "debug", "topUp",
      `Cached ${next} (${manifest.length} entries, ${(totalBytes / 1024 / 1024).toFixed(1)}MB)`,
    );
  } catch (e) {
    log("debug", "topUp", "Failed to fetch/cache candidate", next, e);
  } finally {
    inFlight.delete(next);
  }
}
