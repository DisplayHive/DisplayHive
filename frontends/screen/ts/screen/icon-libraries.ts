/**
 * Resolves the 'icon' field handler's placeholder elements to real SVG
 * markup — see icon-resolver.ts.
 *
 * Icon SVGs are served as plain static files under /icons/ (populated by
 * scripts/copy-icons.mjs into public/icons/, which Vite copies byte-for-
 * byte with no per-file processing) and resolved at runtime via fetch() —
 * NOT via `import.meta.glob`. An earlier version globbed all ~18,000 SVGs
 * across the 9 libraries directly, which made Rollup statically analyze
 * every single one at build time and reliably OOM-crashed the Vite build in
 * memory-constrained deploy environments. This module never needs to
 * enumerate icon names (only ever resolves one already-known library+name
 * at a time), so — unlike the admin frontend's copy of this concept in
 * src/utils/iconLibraries.ts — no manifest fetch is needed here either.
 */

// Vite's `base` config (this bundle is served at /dist/screen/, not site
// root — see vite.config.ts's `base: "/dist/screen/"`) is exposed as
// import.meta.env.BASE_URL (always trailing-slash-terminated) — icon files
// land under it too, since they're copied into the same build output root
// as everything else in public/, so a hardcoded leading "/icons/..." would
// 404 in production.
const iconsBaseUrl = `${import.meta.env.BASE_URL}icons/`;

export async function loadIcon(libraryId: string, name: string): Promise<string | null> {
  try {
    const res = await fetch(`${iconsBaseUrl}${libraryId}/${name}.svg`);
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}
