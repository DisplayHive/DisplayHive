#!/usr/bin/env node
/**
 * Copies each icon library's raw SVGs from node_modules into
 * ts/generated-icons/, a project-owned folder ts/screen/icon-libraries.ts
 * can glob with Vite's import.meta.glob.
 *
 * This has to be a copy step, not a direct glob into node_modules: Vite's
 * glob scanner hard-excludes node_modules from every import.meta.glob call
 * regardless of the pattern given, so an earlier version that globbed
 * node_modules paths directly silently resolved to zero icons for every
 * library. Runs automatically via the "postinstall" script in package.json.
 *
 * Keep the library list here in sync with the glob patterns in
 * ts/screen/icon-libraries.ts, and with frontends/admin's copy of this
 * script (the two frontends share no code today, so this is duplicated).
 */
import { existsSync, mkdirSync, readdirSync, rmSync, copyFileSync } from 'node:fs'
import { join, extname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = fileURLToPath(new URL('.', import.meta.url))
const packageRoot = join(scriptDir, '..')
const nodeModules = join(packageRoot, 'node_modules')
const destRoot = join(packageRoot, 'ts', 'generated-icons')

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
    return
  }
  const destDir = join(destRoot, id)
  mkdirSync(destDir, { recursive: true })
  const seen = new Set()
  let count = 0
  for (const file of walkSvgFiles(srcDir)) {
    const name = extractName(basename(file, '.svg'))
    if (!name || seen.has(name)) continue
    seen.add(name)
    copyFileSync(file, join(destDir, `${name}.svg`))
    count++
  }
  console.log(`[copy-icons] ${id}: copied ${count} icon(s) from ${srcDir}`)
}

rmSync(destRoot, { recursive: true, force: true })
mkdirSync(destRoot, { recursive: true })

copyLibrary('lucide', ['lucide-static/icons'], toKebab)
copyLibrary('heroicons', ['heroicons/24/outline'], toKebab)
copyLibrary('phosphor', ['@phosphor-icons/core/assets/regular', '@phosphor-icons/core/assets'], toKebab)
copyLibrary('tabler', ['@tabler/icons/icons/outline', '@tabler/icons/icons'], toKebab)
copyLibrary('feather', ['feather-icons/dist/icons'], toKebab)
copyLibrary('material-symbols', ['@material-symbols/svg-400/outlined', '@material-symbols/svg-400/outline'], toKebab)
copyLibrary('bootstrap-icons', ['bootstrap-icons/icons'], toKebab)
copyLibrary('iconoir', ['iconoir/icons/regular', 'iconoir/icons'], toKebab)
copyLibrary('remixicon', ['remixicon/icons'], (base) => {
  if (!base.endsWith('-line')) return null
  return toKebab(base.slice(0, -'-line'.length))
})
