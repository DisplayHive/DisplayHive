/**
 * Resolves the 'icon' field handler's placeholder elements to real SVG markup — see icon-resolver.ts.
 *
 * Icons are not part of the screen bundle: an administrator installs icon libraries in the admin
 * (Settings → Icon libraries), and they are served as plain SVG files at /static/icons/<library>/<name>.svg
 * (application/icon_libraries.py). This module only ever resolves one already-known library and name at a
 * time, so it needs no index. The files are sanitised when a library is installed, and the service worker
 * keeps the ones a screen has used, so they are there when the server is not.
 */

const iconsBaseUrl = "/static/icons/";

export async function loadIcon(libraryId: string, name: string): Promise<string | null> {
  try {
    const res = await fetch(`${iconsBaseUrl}${encodeURIComponent(libraryId)}/${encodeURIComponent(name)}.svg`);
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}
