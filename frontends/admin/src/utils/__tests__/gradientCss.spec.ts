import { describe, expect, it } from 'vitest'
import { combinedGradientCss, gradientCssValue, stopColorWithAlpha } from '../gradientCss'

const plain = (s: { color: string }) => s.color
const base = { repeating: false, angle: 90, shape: '', size: '', position_x: 50, position_y: 50 }

describe('gradient CSS', () => {
  it('builds a linear gradient from two stops', () => {
    const css = gradientCssValue({ ...base, type: 'linear', stops: [{ color: '#ffffff', position: 0 }, { color: '#000000', position: 100 }] }, plain)
    expect(css).toBe('linear-gradient(90deg, #ffffff 0%, #000000 100%)')
  })

  it('needs at least two stops', () => {
    expect(gradientCssValue({ ...base, type: 'linear', stops: [{ color: '#fff', position: 0 }] }, plain)).toBe('')
  })

  it('builds radial and conic gradients with their position', () => {
    const stops = [{ color: '#111111', position: 0 }, { color: '#222222', position: 100 }]
    expect(gradientCssValue({ ...base, type: 'radial', shape: 'circle', size: 'closest-side', position_x: 20, position_y: 30, stops }, plain))
      .toBe('radial-gradient(circle closest-side at 20% 30%, #111111 0%, #222222 100%)')
    expect(gradientCssValue({ ...base, type: 'conic', repeating: true, angle: 45, stops }, plain))
      .toBe('repeating-conic-gradient(from 45deg at 50% 50%, #111111 0%, #222222 100%)')
  })

  it('does not double the hash, and turns opacity into an alpha channel', () => {
    expect(stopColorWithAlpha({ color: 'eeff00', position: 0 }, plain)).toBe('#eeff00')
    expect(stopColorWithAlpha({ color: '#eeff00', position: 0 }, plain)).toBe('#eeff00')
    expect(stopColorWithAlpha({ color: '#ff0000', position: 0, opacity: 50 }, plain)).toBe('#ff000080')
  })

  it('resolves palette references through the given resolver', () => {
    const resolve = () => '00ff00'
    expect(stopColorWithAlpha({ color: 'ffffff', position: 0 }, resolve)).toBe('#00ff00')
  })

  it('stacks layers and skips incomplete ones', () => {
    const two = { ...base, type: 'linear', stops: [{ color: '#111111', position: 0 }, { color: '#222222', position: 100 }] }
    const one = { ...base, type: 'linear', stops: [{ color: '#111111', position: 0 }] }
    expect(combinedGradientCss([two, one, two], plain).split('), ')).toHaveLength(2)
  })
})
