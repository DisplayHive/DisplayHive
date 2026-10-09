import { describe, expect, it } from 'vitest'
import { clamp, closestWithinThreshold, edgeTargets, resizeFromCorner, round1, sameShape, snapAxis, snapMove } from '../layoutGeometry'

const noTargets = { hTargets: [], vTargets: [] }

describe('layout geometry', () => {
  it('clamps and rounds', () => {
    expect(clamp(150, 0, 100)).toBe(100)
    expect(clamp(-5, 0, 100)).toBe(0)
    expect(round1(12.3456)).toBe(12.3)
  })

  it('compares aspect ratios by shape', () => {
    expect(sameShape('4:3', '8:6')).toBe(true)
    expect(sameShape('16:9', '4:3')).toBe(false)
  })

  it('snaps only within the threshold, to the closest target', () => {
    expect(closestWithinThreshold(50.9, [0, 50, 100])).toBe(50)
    expect(closestWithinThreshold(53, [0, 50, 100])).toBeNull()
    expect(closestWithinThreshold(49.2, [48.5, 50])).toBe(48.5)
  })

  it('collects canvas, container and snapline targets', () => {
    const { hTargets, vTargets } = edgeTargets(
      [{ left: 10, top: 20, width: 30, height: 40 }],
      [{ axis: 'v', position: 75 }, { axis: 'h', position: 33 }],
    )
    expect(hTargets).toEqual(expect.arrayContaining([0, 50, 100, 10, 40, 25, 75]))
    expect(vTargets).toEqual(expect.arrayContaining([0, 50, 100, 20, 60, 40, 33]))
    expect(hTargets).not.toContain(33)
  })

  it('snaps a box by its left edge, right edge or centre', () => {
    expect(snapAxis(0.8, 20, [0, 50, 100])).toBe(0)
    expect(snapAxis(79.4, 20, [0, 50, 100])).toBe(80) // right edge to 100
    expect(snapAxis(39.5, 20, [0, 50, 100])).toBe(40) // centre to 50
    expect(snapAxis(30, 20, [0, 50, 100])).toBe(30)
  })

  it('moves snap both axes', () => {
    const t = { hTargets: [0, 50, 100], vTargets: [0, 50, 100] }
    expect(snapMove(0.5, 99.5 - 10, 10, 10, t)).toEqual({ left: 0, top: 90 })
  })

  it('resizes from a corner keeping the opposite corner fixed', () => {
    const start = { left: 20, top: 20, width: 30, height: 30 }
    expect(resizeFromCorner('br', start, 10, 10, noTargets)).toEqual({ left: 20, top: 20, width: 40, height: 40 })
    expect(resizeFromCorner('tl', start, -10, -5, noTargets)).toEqual({ left: 10, top: 15, width: 40, height: 35 })
  })

  it('never resizes below the minimum size or past the canvas', () => {
    const start = { left: 20, top: 20, width: 30, height: 30 }
    const small = resizeFromCorner('br', start, -100, -100, noTargets)
    expect(small.width).toBe(4)
    expect(small.height).toBe(4)
    const big = resizeFromCorner('br', start, 500, 500, noTargets)
    expect(big.left + big.width).toBe(100)
  })

  it('snaps the dragged edge to a target', () => {
    const start = { left: 20, top: 20, width: 30, height: 30 }
    const r = resizeFromCorner('br', start, 49, 0, { hTargets: [100], vTargets: [] })
    expect(r.left + r.width).toBe(100)
  })
})
