/**
 * Registry of icon libraries used to resolve the 'icon' field handler's
 * placeholder elements into real SVG markup — see icon-resolver.ts.
 *
 * Uses Vite's `import.meta.glob` to build a static map of file path ->
 * lazy import() function per library at build time. Enumerating names is
 * free; an icon's raw SVG text is only fetched (its own on-demand chunk)
 * when actually resolved on screen. Mirrors
 * frontends/admin/src/utils/iconLibraries.ts, kept as a separate copy since
 * the two frontends share no code today — this copy omits license text,
 * which only the admin picker needs to display.
 */

type GlobRecord = Record<string, () => Promise<string>>

interface IconLibrary {
  id: string
  names: string[]
  load: (name: string) => Promise<string>
}

const basename = (path: string): string => path.split('/').pop() || path
const stripExt = (s: string): string => s.replace(/\.svg$/i, '')

function buildLibrary(
  id: string,
  files: GlobRecord,
  extractName: (path: string) => string | null,
): IconLibrary {
  const byName = new Map<string, () => Promise<string>>()
  for (const [path, loader] of Object.entries(files)) {
    const name = extractName(path)
    if (name && !byName.has(name)) byName.set(name, loader)
  }
  return {
    id,
    names: Array.from(byName.keys()).sort(),
    load: async (name: string) => {
      const loader = byName.get(name)
      if (!loader) throw new Error(`Unknown icon: ${id}/${name}`)
      return loader()
    },
  }
}

// These glob a project-owned folder (ts/generated-icons/), NOT node_modules
// directly — Vite's glob scanner hard-excludes node_modules from every
// import.meta.glob call regardless of the pattern given. scripts/copy-
// icons.mjs (run via the "postinstall" script) populates this folder from
// each library's npm package, already normalized to lowercase-kebab-case
// filenames, so no further name extraction is needed here. Keep in sync
// with the admin frontend's copy of this file if a library's path pattern
// ever changes.
const lucideFiles = import.meta.glob('/ts/generated-icons/lucide/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const heroiconsFiles = import.meta.glob('/ts/generated-icons/heroicons/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const phosphorFiles = import.meta.glob('/ts/generated-icons/phosphor/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const tablerFiles = import.meta.glob('/ts/generated-icons/tabler/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const featherFiles = import.meta.glob('/ts/generated-icons/feather/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const materialSymbolsFiles = import.meta.glob('/ts/generated-icons/material-symbols/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const bootstrapFiles = import.meta.glob('/ts/generated-icons/bootstrap-icons/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const iconoirFiles = import.meta.glob('/ts/generated-icons/iconoir/*.svg', { query: '?raw', import: 'default' }) as GlobRecord
const remixFiles = import.meta.glob('/ts/generated-icons/remixicon/*.svg', { query: '?raw', import: 'default' }) as GlobRecord

const byBasename = (p: string) => stripExt(basename(p))

const ICON_LIBRARIES: IconLibrary[] = [
  buildLibrary('lucide', lucideFiles, byBasename),
  buildLibrary('heroicons', heroiconsFiles, byBasename),
  buildLibrary('phosphor', phosphorFiles, byBasename),
  buildLibrary('tabler', tablerFiles, byBasename),
  buildLibrary('feather', featherFiles, byBasename),
  buildLibrary('material-symbols', materialSymbolsFiles, byBasename),
  buildLibrary('bootstrap-icons', bootstrapFiles, byBasename),
  buildLibrary('iconoir', iconoirFiles, byBasename),
  buildLibrary('remixicon', remixFiles, byBasename),
]

export async function loadIcon(libraryId: string, name: string): Promise<string | null> {
  const lib = ICON_LIBRARIES.find((l) => l.id === libraryId)
  if (!lib) return null
  try {
    return await lib.load(name)
  } catch {
    return null
  }
}
