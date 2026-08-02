/**
 * Registry of the icon libraries selectable by the 'icon' field handler.
 *
 * Each library's icon set is loaded via Vite's `import.meta.glob`, which
 * resolves to a static map of file path -> lazy import() function at build
 * time. Enumerating names (the map's keys) is free; fetching an icon's raw
 * SVG text only happens when its loader is actually invoked (`load()`),
 * so browsing/searching never pulls in more than the handful of SVGs
 * actually shown or selected. This mirrors the same pattern used in
 * frontends/screen/ts/screen/icon-libraries.ts for the final screen render
 * — kept as two separate copies since the two frontends share no code today.
 */

export interface IconPickerValue {
  /** "<library-id>/<icon-name>", or '' when nothing is selected. */
  icon: string
  /** Rendered height, in vh. */
  size: number
}

type GlobRecord = Record<string, () => Promise<string>>

export interface IconLibrary {
  id: string
  label: string
  license: string
  homepage: string
  licenseText: string
  names: string[]
  load: (name: string) => Promise<string>
}

const basename = (path: string) => path.split('/').pop() || path
const stripExt = (s: string) => s.replace(/\.svg$/i, '')

function buildLibrary(
  id: string,
  label: string,
  license: string,
  homepage: string,
  licenseText: string,
  files: GlobRecord,
  extractName: (path: string) => string | null,
): IconLibrary {
  const byName = new Map<string, () => Promise<string>>()
  for (const [path, loader] of Object.entries(files)) {
    const name = extractName(path)
    if (name && !byName.has(name)) byName.set(name, loader)
  }
  const names = Array.from(byName.keys()).sort()
  return {
    id,
    label,
    license,
    homepage,
    licenseText,
    names,
    load: async (name: string) => {
      const loader = byName.get(name)
      if (!loader) throw new Error(`Unknown icon: ${id}/${name}`)
      return loader()
    },
  }
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

// --- Per-library glob calls. Vite requires the glob pattern to be a static
// string literal at each call site, so these cannot be built in a loop. ---

// These glob a project-owned folder (src/assets/icons/), NOT node_modules
// directly — Vite's glob scanner hard-excludes node_modules from every
// import.meta.glob call regardless of the pattern given. scripts/copy-
// icons.mjs (run via the "postinstall" script) populates this folder from
// each library's npm package, already normalized to lowercase-kebab-case
// filenames, so no further name extraction is needed here.
const lucideFiles = import.meta.glob('/src/assets/icons/lucide/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const heroiconsFiles = import.meta.glob('/src/assets/icons/heroicons/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const phosphorFiles = import.meta.glob('/src/assets/icons/phosphor/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const tablerFiles = import.meta.glob('/src/assets/icons/tabler/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const featherFiles = import.meta.glob('/src/assets/icons/feather/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const materialSymbolsFiles = import.meta.glob('/src/assets/icons/material-symbols/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const bootstrapFiles = import.meta.glob('/src/assets/icons/bootstrap-icons/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const iconoirFiles = import.meta.glob('/src/assets/icons/iconoir/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const remixFiles = import.meta.glob('/src/assets/icons/remixicon/*.svg', { query: '?raw', import: 'default' }) as GlobRecord

const byBasename = (p: string) => stripExt(basename(p))

export const ICON_LIBRARIES: IconLibrary[] = [
  buildLibrary('lucide', 'Lucide', 'ISC', 'https://lucide.dev', ISC_TEMPLATE('Copyright (c) Lucide Contributors 2022'), lucideFiles, byBasename),
  buildLibrary('heroicons', 'Heroicons', 'MIT', 'https://heroicons.com', MIT_TEMPLATE('Copyright (c) Tailwind Labs, Inc.'), heroiconsFiles, byBasename),
  buildLibrary('phosphor', 'Phosphor Icons', 'MIT', 'https://phosphoricons.com', MIT_TEMPLATE('Copyright (c) 2023 Phosphor Icons'), phosphorFiles, byBasename),
  buildLibrary('tabler', 'Tabler Icons', 'MIT', 'https://tabler.io/icons', MIT_TEMPLATE('Copyright (c) 2020-2024 Paweł Kuna'), tablerFiles, byBasename),
  buildLibrary('feather', 'Feather', 'MIT', 'https://feathericons.com', MIT_TEMPLATE('Copyright (c) 2013-2023 Cole Bemis'), featherFiles, byBasename),
  buildLibrary('material-symbols', 'Material Symbols', 'Apache-2.0', 'https://fonts.google.com/icons', APACHE_2_TEMPLATE('Copyright (c) Google Inc.'), materialSymbolsFiles, byBasename),
  buildLibrary('bootstrap-icons', 'Bootstrap Icons', 'MIT', 'https://icons.getbootstrap.com', MIT_TEMPLATE('Copyright (c) 2019-2024 The Bootstrap Authors'), bootstrapFiles, byBasename),
  buildLibrary('iconoir', 'Iconoir', 'MIT', 'https://iconoir.com', MIT_TEMPLATE('Copyright (c) 2021 Luca Burgio'), iconoirFiles, byBasename),
  buildLibrary('remixicon', 'Remix Icon', 'Apache-2.0', 'https://remixicon.com', APACHE_2_TEMPLATE('Copyright (c) 2024 Remix Design'), remixFiles, byBasename),
]

export function getIconLibrary(id: string): IconLibrary | undefined {
  return ICON_LIBRARIES.find((l) => l.id === id)
}

export async function loadIcon(libraryId: string, name: string): Promise<string | null> {
  const lib = getIconLibrary(libraryId)
  if (!lib) return null
  try {
    return await lib.load(name)
  } catch {
    return null
  }
}
