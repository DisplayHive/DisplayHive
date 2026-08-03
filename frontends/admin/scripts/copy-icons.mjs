#!/usr/bin/env node
/**
 * Copies each icon library's raw SVGs from node_modules into public/icons/,
 * plus a manifest.json listing each library's icon names, so
 * src/utils/iconLibraries.ts can resolve icons via plain runtime fetch()
 * calls instead of bundling them.
 *
 * This has to write into public/ specifically (Vite copies that directory
 * byte-for-byte with zero per-file processing), not a src/ folder Vite
 * would import.meta.glob over: an earlier version globbed ~18,000 SVGs
 * across the 9 libraries directly, which made Rollup statically analyze
 * every one of them at build time and reliably OOM-crashed the Vite build
 * in memory-constrained deploy environments. Runs automatically via the
 * "postinstall" script in package.json.
 *
 * Keep the library list here in sync with src/utils/iconLibraries.ts and
 * this script's counterpart in frontends/screen/scripts/copy-icons.mjs.
 */
import { existsSync, mkdirSync, readdirSync, rmSync, copyFileSync, writeFileSync } from 'node:fs'
import { join, extname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = fileURLToPath(new URL('.', import.meta.url))
const packageRoot = join(scriptDir, '..')
const nodeModules = join(packageRoot, 'node_modules')
const destRoot = join(packageRoot, 'public', 'icons')

function walkSvgFiles(dir) {
  const out = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) out.push(...walkSvgFiles(full))
    else if (entry.isFile() && extname(entry.name).toLowerCase() === '.svg') out.push(full)
  }
  return out
}

const toKebab = (s) => s.replace(/_/g, '-').toLowerCase()

/** Returns the first candidate dir (relative to node_modules) that actually exists. */
function firstExistingDir(candidates) {
  for (const rel of candidates) {
    const dir = join(nodeModules, ...rel.split('/'))
    if (existsSync(dir)) return dir
  }
  return null
}

function copyLibrary(id, srcCandidates, extractName) {
  const srcDir = firstExistingDir(srcCandidates)
  if (!srcDir) {
    console.warn(`[copy-icons] ${id}: no candidate source dir found (tried: ${srcCandidates.join(', ')}) — skipping`)
    return []
  }
  const destDir = join(destRoot, id)
  mkdirSync(destDir, { recursive: true })
  const seen = new Set()
  for (const file of walkSvgFiles(srcDir)) {
    const name = extractName(basename(file, '.svg'))
    if (!name || seen.has(name)) continue
    seen.add(name)
    copyFileSync(file, join(destDir, `${name}.svg`))
  }
  console.log(`[copy-icons] ${id}: copied ${seen.size} icon(s) from ${srcDir}`)
  return Array.from(seen).sort()
}

rmSync(destRoot, { recursive: true, force: true })
mkdirSync(destRoot, { recursive: true })

const manifest = {
  lucide: copyLibrary('lucide', ['lucide-static/icons'], toKebab),
  heroicons: copyLibrary('heroicons', ['heroicons/24/outline'], toKebab),
  phosphor: copyLibrary('phosphor', ['@phosphor-icons/core/assets/regular', '@phosphor-icons/core/assets'], toKebab),
  tabler: copyLibrary('tabler', ['@tabler/icons/icons/outline', '@tabler/icons/icons'], toKebab),
  feather: copyLibrary('feather', ['feather-icons/dist/icons'], toKebab),
  'material-symbols': copyLibrary('material-symbols', ['@material-symbols/svg-400/outlined', '@material-symbols/svg-400/outline'], toKebab),
  'bootstrap-icons': copyLibrary('bootstrap-icons', ['bootstrap-icons/icons'], toKebab),
  iconoir: copyLibrary('iconoir', ['iconoir/icons/regular', 'iconoir/icons'], toKebab),
  remixicon: copyLibrary('remixicon', ['remixicon/icons'], (base) => {
    // Each icon ships as both a "-line" and "-fill" variant; keep only
    // "-line" so every icon name is unique.
    if (!base.endsWith('-line')) return null
    return toKebab(base.slice(0, -'-line'.length))
  }),
}

writeFileSync(join(destRoot, 'manifest.json'), JSON.stringify(manifest))
console.log(`[copy-icons] wrote manifest.json (${Object.values(manifest).reduce((n, a) => n + a.length, 0)} icons total)`)
