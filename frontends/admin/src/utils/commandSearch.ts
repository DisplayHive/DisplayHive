/** One thing the command palette can jump to or do. */
export interface PaletteEntry {
  id: string
  /** Section heading in the results ("Pages", "Content" …). */
  group: string
  label: string
  /** Secondary text (content type, resolution …). */
  hint?: string
  icon: string
  /** Extra words that also match. */
  keywords?: string
  run: () => void
}

/** Section order in the results; unknown groups come last. */
export const GROUP_ORDER = ['Actions', 'Pages', 'Content', 'Screens', 'Screen groups', 'Media']

const score = (entry: PaletteEntry, words: string[]): number => {
  const label = entry.label.toLowerCase()
  const haystack = `${label} ${(entry.hint ?? '').toLowerCase()} ${(entry.keywords ?? '').toLowerCase()}`
  let total = 0
  for (const word of words) {
    if (!haystack.includes(word)) return -1
    // A match at the start of the label (or of one of its words) ranks above one buried in the text.
    if (label.startsWith(word)) total += 3
    else if (label.includes(` ${word}`)) total += 2
    else if (label.includes(word)) total += 1
  }
  return total
}

/**
 * The entries matching every word of *query* (case-insensitive, any order), best first and,
 * within equal rank, in group order. An empty query lists the first entries of each group.
 */
export function searchEntries(entries: PaletteEntry[], query: string, limit = 30): PaletteEntry[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  const rank = (e: PaletteEntry) => {
    const i = GROUP_ORDER.indexOf(e.group)
    return i === -1 ? GROUP_ORDER.length : i
  }
  if (!words.length) {
    const seen: Record<string, number> = {}
    return entries
      .filter((e) => (seen[e.group] = (seen[e.group] ?? 0) + 1) <= 5)
      .sort((a, b) => rank(a) - rank(b))
      .slice(0, limit)
  }
  return entries
    .map((entry) => ({ entry, s: score(entry, words) }))
    .filter((x) => x.s >= 0)
    .sort((a, b) => b.s - a.s || rank(a.entry) - rank(b.entry))
    .slice(0, limit)
    .map((x) => x.entry)
}
