// Adoption flow: generate adoption key, display QR, connect socket with adoption key.
// When the server validates and returns a device key, store it and reconnect.

import {
  getAdoptionToken as storageGetAdoptionToken,
  setAdoptionToken,
  clearAdoptionToken,
  setDeviceKey,
} from "./storage";

// Generate UUID (used for adoption token)
function generateUUID(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof (crypto as any).randomUUID === "function"
  ) {
    return (crypto as any).randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

// Placeholder shown in place of the token until the eye icon reveals it.
const TOKEN_MASK = "•".repeat(36); // matches a UUID's character length

/** Reset the token display to masked and point it at the given token. */
function renderTokenDisplay(token: string): void {
  const valueEl = document.getElementById("token-value");
  const toggleBtn = document.getElementById("token-toggle") as HTMLButtonElement | null;
  if (!valueEl) return;

  valueEl.dataset.token = token;
  valueEl.textContent = TOKEN_MASK;
  valueEl.classList.remove("revealed");

  if (toggleBtn) {
    toggleBtn.disabled = false;
    toggleBtn.title = "Show token";
    toggleBtn.setAttribute("aria-label", "Show token");
  }

  const manualAdoptLink = document.getElementById("manual-adopt-link") as HTMLAnchorElement | null;
  if (manualAdoptLink) {
    manualAdoptLink.href = `/admin/manualadopt?token=${encodeURIComponent(token)}`;
  }
}

/** Wire up the reveal (eye) and copy icon buttons. Idempotent. */
function wireTokenControls(): void {
  const valueEl = document.getElementById("token-value");
  const toggleBtn = document.getElementById("token-toggle") as HTMLButtonElement | null;
  const copyBtn = document.getElementById("token-copy") as HTMLButtonElement | null;
  if (!valueEl) return;

  // The eye icon only reveals the token - it does not re-mask it afterwards.
  if (toggleBtn && !toggleBtn.dataset.wired) {
    toggleBtn.dataset.wired = "true";
    toggleBtn.addEventListener("click", () => {
      const token = valueEl.dataset.token;
      if (!token) return;
      valueEl.textContent = token;
      valueEl.classList.add("revealed");
      toggleBtn.disabled = true;
      toggleBtn.title = "Token shown";
      toggleBtn.setAttribute("aria-label", "Token shown");
    });
  }

  if (copyBtn && !copyBtn.dataset.wired) {
    copyBtn.dataset.wired = "true";
    copyBtn.addEventListener("click", async () => {
      const token = valueEl.dataset.token;
      if (!token) return;
      try {
        await navigator.clipboard.writeText(token);
        copyBtn.classList.add("copied");
        setTimeout(() => copyBtn.classList.remove("copied"), 1500);
      } catch (e) {
        console.error("[Adoption] Failed to copy token", e);
      }
    });
  }
}

/**
 * Generate and render a QR code into the `#qr-code` element.
 * Polls at 100 ms intervals until the QRCode.js CDN library is available.
 */
export function generateQRCode(text: string): void {
  const qrContainer = document.getElementById("qr-code");
  if (!qrContainer) {
    console.error("[Adoption] QR code container not found");
    return;
  }

  renderTokenDisplay(text);
  wireTokenControls();

  qrContainer.innerHTML = "";

  const tryGenerate = () => {
    try {
      if (typeof (window as any).QRCode === "undefined") {
        setTimeout(tryGenerate, 100); // wait for CDN script to load
        return;
      }

      // @ts-ignore - QRCode is a global from QRCode.js
      new QRCode(qrContainer, {
        text,
        width: 300,
        height: 300,
        colorDark: "#000000",
        colorLight: "#ffffff",
        correctLevel: (QRCode as any).CorrectLevel.H,
      });
    } catch (e) {
      console.error("[Adoption] generateQRCode error", e);
    }
  };

  tryGenerate();
}

/** Show the adoption QR-code overlay. Call when no device key is present. */
export function showAdoptionOverlay(): void {
  const overlay = document.getElementById("registration-overlay");
  if (overlay) {
    overlay.classList.add("show");
  } else {
    console.error("[Adoption] registration-overlay element not found in DOM");
  }
}

/** Hide the adoption overlay after a device key has been assigned. */
export function hideAdoptionOverlay(): void {
  const overlay = document.getElementById("registration-overlay");
  if (overlay) overlay.classList.remove("show");
}

/**
 * Start the adoption workflow:
 * 1. Wipe localStorage so no stale keys interfere
 * 2. Generate a fresh adoption token and persist it
 * 3. Render a QR code and show the overlay
 * 4. Trigger `initializeSocketConnection` so the socket reconnects with the adoption key
 */
export function startAdoptionFlow(): void {
  // Clear only app-owned keys so no external storage data is affected.
  setDeviceKey(null);
  clearAdoptionToken();

  const token = generateUUID();
  setAdoptionToken(token);
  (window as any).adoptionToken = token;
  generateQRCode(token);
  showAdoptionOverlay();

  // initializeSocketConnection reads the adoption token from storage and
  // passes it in the Socket.IO handshake query.
  if (typeof (window as any).initializeSocketConnection === "function") {
    (window as any).initializeSocketConnection();
  } else {
    console.warn("[Adoption] initializeSocketConnection() is not available.");
  }
}

