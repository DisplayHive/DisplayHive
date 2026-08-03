/**
 * Registry of the icon libraries selectable by the 'icon' field handler.
 *
 * Icon SVGs are served as plain static files under /icons/ (populated by
 * scripts/copy-icons.mjs into public/icons/, which Vite copies byte-for-
 * byte with no per-file processing) and resolved at runtime via fetch() —
 * NOT via `import.meta.glob`. An earlier version globbed all ~18,000 SVGs
 * across these 9 libraries directly, which made Rollup statically analyze
 * every single one at build time and reliably OOM-crashed the Vite build in
 * memory-constrained deploy environments. Enumerating names for search
 * comes from public/icons/manifest.json (also written by copy-icons.mjs),
 * fetched once and cached. Mirrors frontends/screen/ts/screen/
 * icon-libraries.ts's resolution approach for the final screen render (that
 * copy doesn't need a manifest, since it only ever resolves one already-
 * known library+name, never enumerates) — kept as two separate copies since
 * the two frontends share no code today.
 */

export interface IconPickerValue {
  /** "<library-id>/<icon-name>", or '' when nothing is selected. */
  icon: string
  /** Rendered height, in vh. */
  size: number
}

export interface IconLibraryMeta {
  id: string
  label: string
  license: string
  homepage: string
  licenseText: string
}

// --- Standard license texts (boilerplate, filled in with each library's own copyright line) ---

const MIT_TEMPLATE = (copyright: string) => `MIT License

${copyright}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.`

const ISC_TEMPLATE = (copyright: string) => `ISC License

${copyright}

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY
AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM
LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR
OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR
PERFORMANCE OF THIS SOFTWARE.`

const APACHE_2_TEMPLATE = (copyright: string) => `Apache License
Version 2.0, January 2004
http://www.apache.org/licenses/

${copyright}

Licensed under the Apache License, Version 2.0 (the "License"); you may not
use this file except in compliance with the License. You may obtain a copy of
the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
License for the specific language governing permissions and limitations under
the License.

The full license text (including all terms, definitions, and the appendix for
applying the License to your own work) is available at:
http://www.apache.org/licenses/LICENSE-2.0`

export const ICON_LIBRARIES: IconLibraryMeta[] = [
  { id: 'lucide', label: 'Lucide', license: 'ISC', homepage: 'https://lucide.dev', licenseText: ISC_TEMPLATE('Copyright (c) Lucide Contributors 2022') },
  { id: 'heroicons', label: 'Heroicons', license: 'MIT', homepage: 'https://heroicons.com', licenseText: MIT_TEMPLATE('Copyright (c) Tailwind Labs, Inc.') },
  { id: 'phosphor', label: 'Phosphor Icons', license: 'MIT', homepage: 'https://phosphoricons.com', licenseText: MIT_TEMPLATE('Copyright (c) 2023 Phosphor Icons') },
  { id: 'tabler', label: 'Tabler Icons', license: 'MIT', homepage: 'https://tabler.io/icons', licenseText: MIT_TEMPLATE('Copyright (c) 2020-2024 Paweł Kuna') },
  { id: 'feather', label: 'Feather', license: 'MIT', homepage: 'https://feathericons.com', licenseText: MIT_TEMPLATE('Copyright (c) 2013-2023 Cole Bemis') },
  { id: 'material-symbols', label: 'Material Symbols', license: 'Apache-2.0', homepage: 'https://fonts.google.com/icons', licenseText: APACHE_2_TEMPLATE('Copyright (c) Google Inc.') },
  { id: 'bootstrap-icons', label: 'Bootstrap Icons', license: 'MIT', homepage: 'https://icons.getbootstrap.com', licenseText: MIT_TEMPLATE('Copyright (c) 2019-2024 The Bootstrap Authors') },
  { id: 'iconoir', label: 'Iconoir', license: 'MIT', homepage: 'https://iconoir.com', licenseText: MIT_TEMPLATE('Copyright (c) 2021 Luca Burgio') },
  { id: 'remixicon', label: 'Remix Icon', license: 'Apache-2.0', homepage: 'https://remixicon.com', licenseText: APACHE_2_TEMPLATE('Copyright (c) 2024 Remix Design') },
]

export function getIconLibraryMeta(id: string): IconLibraryMeta | undefined {
  return ICON_LIBRARIES.find((l) => l.id === id)
}

type Manifest = Record<string, string[]>

let manifestPromise: Promise<Manifest> | null = null

// Vite's `base` config (this app is served at /admin/, not site root — see
// vite.config.ts's `base: '/admin/'`) is exposed as import.meta.env.BASE_URL
// (always trailing-slash-terminated) — icon files land under it too, since
// they're copied into the same build output root as everything else in
// public/, so a hardcoded leading "/icons/..." would 404 in production.
const iconsBaseUrl = `${import.meta.env.BASE_URL}icons/`

/** Fetches (and caches) icons/manifest.json — {library id: sorted icon names[]}. */
function loadManifest(): Promise<Manifest> {
  if (!manifestPromise) {
    manifestPromise = fetch(`${iconsBaseUrl}manifest.json`)
      .then((res) => (res.ok ? res.json() : {}))
      .catch(() => ({}))
  }
  return manifestPromise
}

/** All libraries' icon names, keyed by library id. Fetched once, cached thereafter. */
export async function getIconManifest(): Promise<Manifest> {
  return loadManifest()
}

export async function loadIcon(libraryId: string, name: string): Promise<string | null> {
  try {
    const res = await fetch(`${iconsBaseUrl}${libraryId}/${name}.svg`)
    if (!res.ok) return null
    return await res.text()
  } catch {
    return null
  }
}
