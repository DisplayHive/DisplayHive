import type { GradientStop } from '../types/models'

export type GradientLike = {
  type: string
  repeating: boolean
  angle: number
  shape: string
  size: string
  position_x: number
  position_y: number
  stops: GradientStop[]
}

/** The hex of a stop's colour (with or without a leading "#"), e.g. after resolving a palette reference. */
export type ResolveStopHex = (stop: GradientStop) => string

// Mirrors gradient_css_value()'s alpha handling server-side: a stop's
// opacity (0-100, default 100/opaque) becomes an 8-digit hex alpha channel
// so a fully opaque top layer doesn't always hide gradients listed after it.
export const stopColorWithAlpha = (s: GradientStop, resolveHex: ResolveStopHex): string => {
  // resolveHex's contract is "return stop.color as-is, resolving a same-Design ref first" —
  // it makes no promise about a leading '#', and callers disagree on it: the Color Stops
  // editor strips it (its stops are always hash-less), but a Gradient fetched straight from
  // the server keeps whatever's in the DB, which always has one. Blindly prepending '#'
  // doubled it for the second case ("##eeff00"), an invalid CSS color that silently dropped
  // the *entire* background-image. Strip first so this works for both, matching the
  // backend's gradient_css_value()/_stop_color().
  const hex = resolveHex(s).replace(/^#/, '')
  const color = `#${hex}`
  const opacity = s.opacity ?? 100
  if (opacity >= 100 || !color.startsWith('#') || color.length !== 7) return color
  const alpha = Math.round((Math.max(0, Math.min(100, opacity)) / 100) * 255)
  return `${color}${alpha.toString(16).padStart(2, '0')}`
}

export const gradientCssValue = (g: GradientLike, resolveHex: ResolveStopHex): string => {
  if (!g.stops || g.stops.length < 2) return ''
  const stopStr = g.stops.map((s) => `${stopColorWithAlpha(s, resolveHex)} ${s.position}%`).join(', ')
  const prefix = g.repeating ? 'repeating-' : ''
  const x = g.position_x ?? 50
  const y = g.position_y ?? 50

  if (g.type === 'radial') {
    const shapeSize = [g.shape, g.size].filter(Boolean).join(' ')
    const head = `${shapeSize} at ${x}% ${y}%`.trim()
    return `${prefix}radial-gradient(${head}, ${stopStr})`
  }
  if (g.type === 'conic') {
    return `${prefix}conic-gradient(from ${g.angle}deg at ${x}% ${y}%, ${stopStr})`
  }
  return `${prefix}linear-gradient(${g.angle}deg, ${stopStr})`
}

/** Stacks every gradient's CSS into one combined `background-image` value. */
export const combinedGradientCss = (list: GradientLike[], resolveHex: ResolveStopHex): string =>
  list.map((g) => gradientCssValue(g, resolveHex)).filter(Boolean).join(', ')
