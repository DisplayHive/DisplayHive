/**
 * Safe localStorage helpers.
 *
 * All direct localStorage access is centralised here so the ESLint rule that
 * disallows ad-hoc `localStorage` calls throughout the codebase has a single
 * approved exemption point.
 */

function safeGet(key: string): string | null {
  try {
    if (typeof localStorage === "undefined") return null;
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    if (typeof localStorage !== "undefined") localStorage.setItem(key, value);
  } catch {
    /* intentional: storage may be unavailable (private browsing, quota) */
  }
}

function safeRemove(key: string): void {
  try {
    if (typeof localStorage !== "undefined") localStorage.removeItem(key);
  } catch {
    /* intentional */
  }
}

// ── Device key ───────────────────────────────────────────────────────────────

export function getDeviceKey(): string | null {
  return safeGet("deviceKey");
}

export function setDeviceKey(key: string | null): void {
  if (key === null) {
    safeRemove("deviceKey");
  } else {
    safeSet("deviceKey", key);
  }
}

// ── Adoption token ───────────────────────────────────────────────────────────

export function getAdoptionToken(): string | null {
  return safeGet("adoptionToken");
}

export function setAdoptionToken(token: string): void {
  safeSet("adoptionToken", token);
}

export function clearAdoptionToken(): void {
  safeRemove("adoptionToken");
}

// ── Random-tag image cache manifest ──────────────────────────────────────────
// The image bytes themselves live in the Cache Storage API (see
// random-image-cache.ts); this is just the small bookkeeping list (url,
// size, lastUsed per entry) needed to enforce a size/count budget and pick
// only among what's actually cached — cheap enough for localStorage, and
// persists across reloads/restarts the same way the device key does.

export function getRandomImageManifest(): string | null {
  return safeGet("randomImageManifest");
}

export function setRandomImageManifest(json: string): void {
  safeSet("randomImageManifest", json);
}

// ── Screen rotation ──────────────────────────────────────────────────────────
// Last rotation (0/90/180/270) the server configured for this screen, kept so
// the stage can be turned on the very first paint after a reload instead of
// flashing unrotated until the device config arrives.

export function getStoredRotation(): number {
  const n = parseInt(safeGet("screenRotation") || "0", 10);
  return n === 90 || n === 180 || n === 270 ? n : 0;
}

export function setStoredRotation(deg: number): void {
  safeSet("screenRotation", String(deg));
}

// ── Last content snapshot ────────────────────────────────────────────────────
// The last `upd_content` the server sent (see content-snapshot.ts), so a screen that restarts
// while the server is unreachable still has something to show.

export function getContentSnapshot(): string | null {
  return safeGet("contentSnapshot");
}

export function setContentSnapshot(json: string): void {
  safeSet("contentSnapshot", json);
}
