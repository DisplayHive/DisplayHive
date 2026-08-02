/**
 * Resolves the 'icon' field handler's server-rendered placeholder elements
 * ([data-dh-icon-library]) into real inline SVG markup, using the icon
 * library registry in icon-libraries.ts. Mirrors clock.ts's role for
 * [data-dh-clock] elements — called from container-manager.ts right after
 * HTML is injected into a container.
 */

import { loadIcon } from './icon-libraries.js';

/** Strip any hardcoded width/height off the SVG root so it scales to its wrapper. */
function sizeToFit(svg: string): string {
  return svg.replace(
    /<svg\b([^>]*)>/i,
    (_match, attrs: string) =>
      `<svg${attrs.replace(/\s+(width|height)="[^"]*"/gi, '')} style="height:100%;width:auto;display:block;">`,
  );
}

export async function resolveIcons(root: ParentNode = document): Promise<void> {
  const els = root.querySelectorAll<HTMLElement>('[data-dh-icon-library]');
  await Promise.all(
    Array.from(els).map(async (el) => {
      const library = el.getAttribute('data-dh-icon-library');
      const name = el.getAttribute('data-dh-icon-name');
      if (!library || !name) return;
      const svg = await loadIcon(library, name);
      if (svg) el.innerHTML = sizeToFit(svg);
    }),
  );
}
