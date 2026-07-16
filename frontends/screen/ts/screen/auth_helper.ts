// Authentication helper for screen clients.
// Orchestrates the auth-vs-adoption branch on page load:
// if a deviceKey exists in localStorage (or URL params), connect the socket;
// otherwise start the adoption workflow.

import { getDeviceKey } from "./storage";
import { getSessionDdk } from "./ddk";

type InitOptions = {
  getAdoptionToken?: () => string | null;
  generateQRCode?: (token: string) => void;
  showAdoptionOverlay?: () => void;
  startAdoptionFlow?: () => void;
};

export function initializeAuthentication(adopt?: InitOptions) {
  console.log("[Authentication] Starting authentication flow");
  // First check for a dynamic device key (ddk) delivered via the URL
  // fragment. If present we use it for this session only - it is never
  // persisted to localStorage, and the fragment has already been stripped
  // from the URL/history by consumeDdkFromFragment().
  let deviceKey: string | null = null;
  try {
    const ddk = getSessionDdk();
    if (ddk) {
      console.log(
        "[Authentication] Dynamic device key (ddk) found in URL fragment - using it for this session only",
      );
      deviceKey = ddk;
      if (typeof window !== "undefined") (window as any).deviceKey = deviceKey;
    }
  } catch (e) {
    console.warn("[Authentication] Error reading dynamic device key", e);
  }

  // Next check for impersonation via URL parameters. If present we will
  // honor the URL-provided devicekey for this session but NOT persist it
  // to localStorage (so this is a transient impersonation).
  try {
    if (!deviceKey && typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const impersonate = params.get("impersonate");
      const urlKey = params.get("devicekey");
      if (impersonate && urlKey) {
        console.log(
          "[Authentication] Impersonation parameters found in URL - using URL devicekey for this session",
        );
        deviceKey = String(urlKey);
        (window as any).deviceKey = deviceKey;
        (window as any).__impersonate = true;
      }
    }
  } catch (e) {
    console.warn(
      "[Authentication] Error parsing URL params for impersonation",
      e,
    );
  }

  // If no URL-provided deviceKey, fall back to localStorage-stored deviceKey
  if (!deviceKey) {
    deviceKey = getDeviceKey();
    if (typeof window !== "undefined") (window as any).deviceKey = deviceKey;
  }

  if (deviceKey) {
    // Device has a key - proceed to socket connection workflow (login workflow)
    console.log(
      "[Authentication] deviceKey found in localStorage, proceeding to socket connection",
    );
    if (
      typeof window !== "undefined" &&
      typeof (window as any).initializeSocketConnection === "function"
    ) {
      (window as any).initializeSocketConnection();
    } else {
      console.warn(
        "[Authentication] initializeSocketConnection() is not available.",
      );
    }
  } else {
    // No devicekey - go to adoption workflow
    console.log(
      "[Authentication] No deviceKey found, starting adoption workflow",
    );

    // Check if there's a persisted adoption token to resume
    const persisted = adopt?.getAdoptionToken ? adopt.getAdoptionToken() : null;

    if (persisted && adopt?.showAdoptionOverlay) {
      // Resume existing adoption flow (regenerate QR, show overlay, socket will reconnect with adoptionkey)
      console.log(
        "[Authentication] Resuming existing adoption with token:",
        persisted.substring(0, 8) + "...",
      );
      // Regenerate QR code with existing token
      if (adopt?.generateQRCode) {
        adopt.generateQRCode(persisted);
      }
      adopt.showAdoptionOverlay();
      // Trigger socket connection with adoptionkey
      if (
        typeof window !== "undefined" &&
        typeof (window as any).initializeSocketConnection === "function"
      ) {
        (window as any).initializeSocketConnection();
      }
    } else if (adopt?.startAdoptionFlow) {
      // Start new adoption flow (clears localStorage, generates token, shows QR, connects socket)
      console.log("[Authentication] Starting new adoption flow");
      adopt.startAdoptionFlow();
    } else if (adopt?.showAdoptionOverlay) {
      // Fallback: just show overlay (shouldn't reach here if startAdoptionFlow is provided)
      console.warn(
        "[Authentication] startAdoptionFlow not provided, falling back to showAdoptionOverlay",
      );
      adopt.showAdoptionOverlay();
    } else {
      console.error(
        "[Authentication] Adoption callbacks not provided - cannot show adoption overlay",
      );
    }
  }
}
