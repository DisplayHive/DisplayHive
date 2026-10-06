/**
 * Picks the right size of an uploaded image for this screen.
 *
 * The server keeps FHD / 4K / 8K renditions of every uploaded image under
 * /static/media_renditions/<tier>/… (see application/media_renditions.py) —
 * measured on the long edge: 1920 / 3840 / 7680 px, and never larger than the
 * original (a tier the source can't fill simply doesn't exist). This module
 * chooses the smallest tier that is still at least as big as the screen's own
 * resolution ("the next larger image"), for the screen's biggest dimension:
 *
 *   1920x1080 -> FHD, 2560x1440 -> 4K, 3840x2160 -> 4K, 5120x2880 -> 8K …
 *
 * Because a tier can legitimately be missing (small source), every swap has a
 * fallback to the original URL; URLs that failed once are remembered so they
 * aren't retried on every scene.
 */

import { log } from "./logger.js";

const TIERS: ReadonlyArray<{ name: string; edge: number }> = [
  { name: "fhd", edge: 1920 },
  { name: "4k", edge: 3840 },
  { name: "8k", edge: 7680 },
];

// "/static/media/<rel>" optionally preceded by this server's origin.
const MEDIA_URL = /^(?:https?:\/\/[^/]+)?\/static\/media\/(.+)$/;
const MEDIA_URL_IN_CSS = /url\(\s*(['"]?)((?:https?:\/\/[^/'")]+)?\/static\/media\/[^'")]+)\1\s*\)/g;

/** Rendition URLs known not to exist (source smaller than that tier). */
const missing = new Set<string>();

/** The screen's resolution in physical pixels along its longer side. */
export function screenLongEdge(): number {
  if (typeof window === "undefined") return 0;
  const dpr = window.devicePixelRatio || 1;
  return Math.max(window.innerWidth, window.innerHeight) * dpr;
}

/** Smallest tier whose long edge covers *edge*; the largest tier if none does. */
export function pickTier(edge: number = screenLongEdge()): string {
  const tier = TIERS.find((t) => t.edge >= edge) ?? TIERS[TIERS.length - 1];
  return tier.name;
}

/** The rendition URL for a media URL, or null if it isn't an uploaded image. */
export function renditionUrl(url: string, tier: string = pickTier()): string | null {
  const m = MEDIA_URL.exec(url);
  return m ? `/static/media_renditions/${tier}/${m[1]}` : null;
}

/** Remember that *url* (a rendition) doesn't exist, so callers fall back to the original. */
export function markRenditionMissing(url: string): void {
  missing.add(url);
}

/** The best URL to load for a media URL: its rendition unless that is known to be missing. */
export function preferredUrl(url: string): string {
  const r = renditionUrl(url);
  return r && !missing.has(r) ? r : url;
}

/**
 * Point every uploaded-image `<img>` under *root* at its rendition, falling
 * back to the original if the rendition doesn't exist.
 */
export function adaptMediaImages(root: ParentNode): void {
  for (const img of Array.from(root.querySelectorAll<HTMLImageElement>("img[src]"))) {
    if (img.dataset.dhOriginal) continue; // already adapted
    const original = img.getAttribute("src") || "";
    const next = preferredUrl(original);
    if (next === original) continue;
    img.dataset.dhOriginal = original;
    img.addEventListener(
      "error",
      () => {
        markRenditionMissing(next);
        log("debug", "adaptMediaImages", `No rendition at ${next}, using the original`);
        img.src = original;
      },
      { once: true },
    );
    img.src = next;
  }
}

/**
 * Rewrites uploaded-image `url(...)`s in CSS (the Design's Backdrop image …)
 * to their renditions. A CSS background can't report a failed load, so each
 * candidate is probed with an Image first; only those that load are swapped.
 */
export async function adaptMediaCss(css: string): Promise<string> {
  const originals = Array.from(new Set(Array.from(css.matchAll(MEDIA_URL_IN_CSS), (m) => m[2])));
  if (!originals.length) return css;

  const swaps = new Map<string, string>();
  await Promise.all(
    originals.map(
      (original) =>
        new Promise<void>((resolve) => {
          const candidate = preferredUrl(original);
          if (candidate === original) return resolve();
          const probe = new Image();
          probe.onload = () => {
            swaps.set(original, candidate);
            resolve();
          };
          probe.onerror = () => {
            markRenditionMissing(candidate);
            resolve();
          };
          probe.src = candidate;
        }),
    ),
  );
  if (!swaps.size) return css;
  return css.replace(MEDIA_URL_IN_CSS, (whole, quote: string, url: string) => {
    const swapped = swaps.get(url);
    return swapped ? `url(${quote}${swapped}${quote})` : whole;
  });
}
