/**
 * Hides the mouse pointer on the screen: after a few seconds without movement it disappears
 * (class `cursor-hidden` on <html>, see screen.css) and comes back as soon as the mouse moves, so
 * an unattended screen shows no pointer, while someone setting it up (adoption link, debug panel)
 * still finds it.
 */

export const CURSOR_HIDE_AFTER_MS = 3_000;

let installed = false;

export function initCursorHider(): void {
  if (installed) return;
  installed = true;
  const root = document.documentElement;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const hideSoon = () => {
    clearTimeout(timer);
    timer = setTimeout(() => root.classList.add("cursor-hidden"), CURSOR_HIDE_AFTER_MS);
  };
  const show = () => {
    root.classList.remove("cursor-hidden");
    hideSoon();
  };

  window.addEventListener("mousemove", show, { passive: true });
  window.addEventListener("mousedown", show, { passive: true });
  hideSoon();
}
