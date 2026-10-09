import { describe, expect, it } from 'vitest'
import { searchEntries, type PaletteEntry } from '../commandSearch'

const e = (id: string, group: string, label: string, extra: Partial<PaletteEntry> = {}): PaletteEntry =>
  ({ id, group, label, icon: 'pi pi-x', run: () => {}, ...extra })

const entries = [
  e('p-screens', 'Pages', 'Screens'),
  e('c-welcome', 'Content', 'Welcome screen text', { hint: 'Text' }),
  e('s-lobby', 'Screens', 'Lobby', { hint: '1920x1080' }),
  e('a-new', 'Actions', 'New content', { keywords: 'create add' }),
  e('m-logo', 'Media', 'Company logo'),
]
const ids = (list: PaletteEntry[]) => list.map((x) => x.id)

describe('searchEntries', () => {
  it('matches every word, in any order, case-insensitively', () => {
    expect(ids(searchEntries(entries, 'TEXT welcome'))).toEqual(['c-welcome'])
    expect(ids(searchEntries(entries, 'nothing like it'))).toEqual([])
  })

  it('finds by hint and keywords', () => {
    expect(ids(searchEntries(entries, '1920'))).toEqual(['s-lobby'])
    expect(ids(searchEntries(entries, 'create'))).toEqual(['a-new'])
  })

  it('ranks a label that starts with the word above one that merely contains it', () => {
    expect(ids(searchEntries(entries, 'screen'))).toEqual(['p-screens', 'c-welcome'])
  })

  it('an empty query lists a few entries per group in group order', () => {
    expect(ids(searchEntries(entries, ''))).toEqual(['a-new', 'p-screens', 'c-welcome', 's-lobby', 'm-logo'])
  })

  it('caps the number of results', () => {
    expect(searchEntries(entries, '', 2)).toHaveLength(2)
  })
})
