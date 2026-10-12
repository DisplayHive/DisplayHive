import { describe, expect, it } from 'vitest'
import { allCheckedKeys, buildTree, selectionFromKeys } from '../importExportTree'

const manifest = {
  media: [{ uuid: 'm1', id: 1, label: 'Logo' }],
  screens: [
    { uuid: 's1', id: 1, label: 'Lobby', conflict: true },
    { uuid: 's2', id: 2, label: 'Hall' },
  ],
  designs: [],
}

describe('buildTree', () => {
  it('orders the types like the server and skips empty ones', () => {
    const tree = buildTree(manifest)
    expect(tree.map((n) => n.key)).toEqual(['type:screens', 'type:media'])
    expect(tree[0]!.label).toBe('Screens (2)')
    expect(tree[0]!.children![0]!.data).toEqual({ typeKey: 'screens', uuid: 's1', conflict: true })
  })

  it('prefixes the keys', () => {
    expect(buildTree(manifest, 'import-')[0]!.key).toBe('import-type:screens')
  })
})

describe('selectionFromKeys', () => {
  it('returns the checked leaves per type', () => {
    const tree = buildTree(manifest)
    const keys = allCheckedKeys(tree)
    keys['item:screens:s2'] = { checked: false, partialChecked: false }
    expect(selectionFromKeys(tree, keys)).toEqual({ screens: ['s1'], media: ['m1'] })
  })
})
