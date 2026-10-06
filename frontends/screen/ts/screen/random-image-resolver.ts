/**
 * Resolves the 'image' field handler's `random_tags`-mode server-rendered
 * placeholder elements ([data-dh-random-pool]) into a real `<img src>`,
 * picking a fresh cached candidate on every call. Mirrors icon-resolver.ts's
 * role for [data-dh-icon-library] elements, with one deliberate difference:
 * icons are deterministic and only need re-resolving when their config
 * changes, but a random-image pool must resolve to a *new* pick every time
 * — see container-manager.ts's renderScene, which calls this unconditionally
 * for every active container rather than only ones whose HTML changed.
 */

import { pickCached, getObjectUrl, topUp } from "./random-image-cache.js";
import { preferredUrl } from "./media-renditions.js";

// Tracks the object URL currently assigned to each element so it can be
// revoked when replaced — object URLs are otherwise never released and
// would leak memory over a long-running kiosk session.
const activeObjectUrls = new WeakMap<HTMLImageElement, string>();

function parseCandidates(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((u) => typeof u === "string") : [];
  } catch {
    return [];
  }
}

export async function resolveRandomImages(root: ParentNode = document): Promise<void> {
  const els = root.querySelectorAll<HTMLImageElement>("[data-dh-random-pool]");
  await Promise.all(
    Array.from(els).map(async (el) => {
      // Each candidate is loaded at the size that fits this screen (its FHD/4K/8K
      // rendition, or the original where that doesn't exist).
      const candidates = parseCandidates(el.getAttribute("data-dh-random-pool")).map(preferredUrl);
      if (!candidates.length) return;

      const chosen = pickCached(candidates);
      if (!chosen) {
        // Nothing cached yet for this pool (freshly adopted device, or a
        // brand-new tag) — leave whatever's currently showing (if anything)
        // alone rather than blanking the element, and try to get something
        // cached for next time.
        void topUp(candidates);
        return;
      }

      const objectUrl = await getObjectUrl(chosen);
      if (!objectUrl) {
        // Manifest said it was cached but the Cache Storage entry is gone
        // (cleared out from under us) — same graceful fallback as above.
        void topUp(candidates);
        return;
      }

      const previous = activeObjectUrls.get(el);
      el.src = objectUrl;
      activeObjectUrls.set(el, objectUrl);
      if (previous) URL.revokeObjectURL(previous);

      void topUp(candidates, {}, { currentlyDisplayed: chosen });
    }),
  );
}
