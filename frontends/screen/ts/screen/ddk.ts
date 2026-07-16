/**
 * Dynamic device key (ddk) handling.
 *
 * A ddk is a normal backend device key that is delivered to the client via
 * the URL fragment (e.g. `#devicekey=<uuid>`) instead of the query string,
 * so it is never sent to a web server in an access log or Referer header.
 * It is consumed once, kept in `sessionStorage` (so it survives a page
 * reload but is cleared as soon as the tab/browser closes - never written
 * to `localStorage`), and the fragment is stripped from the visible
 * URL/history immediately so it doesn't linger there either.
 */

const STORAGE_KEY = "ddk";

function safeGet(): string | null {
  try {
    if (typeof sessionStorage === "undefined") return null;
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function safeSet(value: string): void {
  try {
    if (typeof sessionStorage !== "undefined")
      sessionStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* intentional: storage may be unavailable (private browsing, quota) */
  }
}

/**
 * Read a ddk from `location.hash` (if present), stash it in
 * `sessionStorage`, and rewrite the URL to remove the fragment. Must be
 * called as early as possible on page load, before anything else inspects
 * the URL.
 */
export function consumeDdkFromFragment(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const hash = window.location.hash || "";
    if (hash.length < 2) return null;

    const params = new URLSearchParams(hash.slice(1));
    const key = params.get("devicekey");
    if (!key) return null;

    safeSet(key);

    try {
      const cleanUrl = window.location.pathname + window.location.search;
      window.history.replaceState(null, "", cleanUrl);
    } catch (e) {
      console.warn(
        "[ddk] Failed to rewrite URL after consuming fragment key",
        e,
      );
    }

    return key;
  } catch (e) {
    console.warn(
      "[ddk] Failed to parse URL fragment for dynamic device key",
      e,
    );
    return null;
  }
}

/**
 * Returns the ddk for this tab session, if any - either consumed from the
 * URL fragment earlier this page load, or persisted in `sessionStorage`
 * from a previous load of this tab (e.g. after a reload).
 */
export function getSessionDdk(): string | null {
  return safeGet();
}
