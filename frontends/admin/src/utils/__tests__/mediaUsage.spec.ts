import { describe, expect, it } from 'vitest'
import { deleteWarning, isUnused, usageLabel, usageLink } from '../mediaUsage'
import type { MediaItem } from '../../types/models'

const item = (used_by: MediaItem['used_by']): MediaItem => ({ id: 1, title: 't', filename: 'f.png', mimetype: 'image/png', used_by })

describe('mediaUsage', () => {
  it('knows unused files', () => {
    expect(isUnused(item([]))).toBe(true)
    expect(isUnused(item(undefined))).toBe(true)
    expect(isUnused(item([{ kind: 'content', id: 2, name: 'Welcome' }]))).toBe(false)
  })

  it('labels and links a usage', () => {
    const u = { kind: 'content' as const, id: 2, name: 'Welcome' }
    expect(usageLabel(u)).toBe('Content: Welcome')
    expect(usageLink(u)).toEqual({ name: 'content-edit', params: { id: 2 } })
    expect(usageLink({ kind: 'container', id: 3, name: 'side' })).toBeNull()
  })

  it('warns only when something uses the file, and shortens long lists', () => {
    expect(deleteWarning(item([]))).toBe('')
    const many = Array.from({ length: 7 }, (_, i) => ({ kind: 'content' as const, id: i, name: `C${i}` }))
    const text = deleteWarning(item(many))
    expect(text).toContain('Content: C0')
    expect(text).not.toContain('C5')
    expect(text).toContain('and 2 more')
  })
})
