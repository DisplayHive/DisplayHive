/**
 * Tracks the visible viewport dimensions (window.innerWidth / innerHeight),
 * updates the debug panel, and emits them to the backend via Socket.IO.
 */

type SafeEmit = (event: string, payload?: unknown) => void;

let _emit: SafeEmit | null = null;

function getViewport(): { width: number; height: number } {
  return { width: window.innerWidth, height: window.innerHeight };
}

function updateDebugPanel(width: number, height: number): void {
  try {
    window.debugPanel?.push?.("Screen Info", "Viewport", "Width", `${width}px`);
    window.debugPanel?.push?.("Screen Info", "Viewport", "Height", `${height}px`);
  } catch {
    /* intentional: debugPanel may not be ready */
  }
}

function report(): void {
  const { width, height } = getViewport();
  updateDebugPanel(width, height);
  _emit?.("displayhive:devices:cts:upd_viewport", { width, height });
}

/** Emit the current viewport to the backend. Call after socket authentication. */
export function emitCurrentViewport(): void {
  report();
}

/**
 * Start tracking the viewport. Sets the safeEmit function and wires up
 * the resize listener. Must only be called once.
 */
export function initViewportTracking(safeEmit: SafeEmit): void {
  _emit = safeEmit;
  report();

  let timer: ReturnType<typeof setTimeout> | null = null;
  window.addEventListener("resize", () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(report, 300);
  });
}
