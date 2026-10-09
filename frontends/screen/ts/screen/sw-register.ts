/**
 * Registers the screen's service worker (ts/sw/screen-sw.ts, served as /screen-sw.js) so a screen
 * can start and keep playing while the server is unreachable.
 *
 * The release's ASSET_VERSION (a <meta> of index.html) goes on the script URL: a new release is
 * a new worker URL, which installs, takes over and drops the old release's cache.
 *
 * Needs a secure context (https or localhost); on plain http from another host the browser offers
 * no service workers, and the screen simply runs as before.
 */

import { log } from "./logger.js";

/** The URLs this page was made of — what the worker should already have in its cache. */
function loadedResources(): string[] {
  return performance
    .getEntriesByType("resource")
    .map((entry) => entry.name)
    .filter((name) => name.startsWith(window.location.origin));
}

export function registerServiceWorker(): void {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
  const version = document.querySelector('meta[name="asset-version"]')?.getAttribute("content") || "dev";
  navigator.serviceWorker
    .register(`/screen-sw.js?v=${encodeURIComponent(version)}`, { scope: "/" })
    .then(() => navigator.serviceWorker.ready)
    .then((registration) => {
      // The page loaded before the worker controlled it: tell it what the page consists of.
      registration.active?.postMessage({ type: "cache-resources", page: window.location.href, urls: loadedResources() });
      log("info", "sw-register", `Service worker ready (release ${version})`);
    })
    .catch((error) => log("warn", "sw-register", "Service worker not available", String(error)));
}
