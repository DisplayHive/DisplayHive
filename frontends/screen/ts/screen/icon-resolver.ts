/**
 * Resolves the 'icon' field handler's server-rendered placeholder elements
 * ([data-dh-icon-library]) into real inline SVG markup, using the icon
 * library registry in icon-libraries.ts. Mirrors clock.ts's role for
 * [data-dh-clock] elements — called from container-manager.ts right after
 * HTML is injected into a container.
 */

import { loadIcon } from './icon-libraries.js';

/**
 * Strip any hardcoded width/height off the SVG root so it scales to its
 * wrapper, and — when a color was configured (data-dh-icon-color, already
 * resolved to a literal CSS color server-side) — force that color onto the
 * icon. Most icon sets draw with `currentColor`, so setting `color` on the
 * root covers them; libraries that hardcode `fill`/`stroke` on the root are
 * overridden too (a `none` value is kept, so outline icons stay outlines).
 */
function styleSvg(svg: string, color: string | null): string {
  return svg.replace(/<svg\b([^>]*)>/i, (_match, rawAttrs: string) => {
    let attrs = rawAttrs.replace(/\s+(width|height)="[^"]*"/gi, '');
    let style = 'height:100%;width:auto;display:block;';
    if (color) {
      style += `color:${color};`;
      attrs = attrs.replace(
        /\s+(fill|stroke)="([^"]*)"/gi,
        (m: string, prop: string, val: string) =>
          val.trim().toLowerCase() === 'none' ? m : ` ${prop}="${color}"`,
      );
    }
    return `<svg${attrs} style="${style}">`;
  });
}

export async function resolveIcons(root: ParentNode = document): Promise<void> {
  const els = root.querySelectorAll<HTMLElement>('[data-dh-icon-library]');
  await Promise.all(
    Array.from(els).map(async (el) => {
      const library = el.getAttribute('data-dh-icon-library');
      const name = el.getAttribute('data-dh-icon-name');
      if (!library || !name) return;
      const svg = await loadIcon(library, name);
      if (svg) el.innerHTML = styleSvg(svg, el.getAttribute('data-dh-icon-color'));
    }),
  );
}
