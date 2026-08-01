// Registry of the "beautiful-backgrounds" animated canvas background effects
// (https://github.com/niekes/beautiful-backgrounds), mirrored from
// frontends/screen/ts/screen/background-effects.ts — the screen client is
// the one that actually renders these; this copy drives the admin edit
// form + live preview. Kept in sync manually since frontends/admin and
// frontends/screen are separate npm projects with no shared package.

export type EffectParamType = 'number' | 'string' | 'color' | 'colorArray'

export interface EffectParam {
  key: string // HTML attribute name, e.g. "particle-force"
  label: string
  type: EffectParamType
  default: number | string | string[]
  min?: number
  max?: number
  step?: number
}

export interface EffectDefinition {
  key: string // stored in Design.background_effect
  tag: string // custom element tag name
  label: string
  params: EffectParam[]
}

// Shared attributes every effect's base class (BeautifulBackground) accepts.
const BASE_PARAMS: EffectParam[] = [
  { key: 'bg-colors', label: 'Backdrop gradient colors', type: 'colorArray', default: ['#000000', '#000000'] },
  { key: 'bg-angle', label: 'Backdrop gradient angle', type: 'number', default: 0, min: 0, max: 360, step: 1 },
  { key: 'background-color', label: 'Canvas clear color (r, g, b)', type: 'string', default: '0, 0, 0' },
  { key: 'trail-opacity', label: 'Trail fade opacity', type: 'number', default: 0.1, min: 0, max: 1, step: 0.01 },
]

export const BACKGROUND_EFFECTS: EffectDefinition[] = [
  {
    key: 'star-trail',
    tag: 'bb-star-trail',
    label: 'Star Trail',
    params: [
      ...BASE_PARAMS,
      { key: 'particle-force', label: 'Particle force', type: 'number', default: 0 },
      { key: 'particle-size-min', label: 'Particle size min', type: 'number', default: 0.5, min: 0, step: 0.1 },
      { key: 'particle-size-max', label: 'Particle size max', type: 'number', default: 1.5, min: 0, step: 0.1 },
      { key: 'particle-speed-min', label: 'Particle speed min', type: 'number', default: 0.025, step: 0.001 },
      { key: 'particle-speed-max', label: 'Particle speed max', type: 'number', default: 0.05, step: 0.001 },
      { key: 'particle-color-hue-start', label: 'Color hue start', type: 'number', default: 30, min: 0, max: 360 },
      { key: 'particle-color-hue-end', label: 'Color hue end', type: 'number', default: 75, min: 0, max: 360 },
      { key: 'particle-color-saturation-start', label: 'Saturation start', type: 'number', default: 100, min: 0, max: 100 },
      { key: 'particle-color-saturation-end', label: 'Saturation end', type: 'number', default: 100, min: 0, max: 100 },
      { key: 'particle-color-lightness-start', label: 'Lightness start', type: 'number', default: 50, min: 0, max: 100 },
      { key: 'particle-color-lightness-end', label: 'Lightness end', type: 'number', default: 50, min: 0, max: 100 },
      { key: 'particle-radius-min', label: 'Orbit radius min', type: 'number', default: 1, min: 0 },
      { key: 'particle-radius-max', label: 'Orbit radius max', type: 'number', default: 100, min: 0 },
      { key: 'particle-lifespan-min', label: 'Lifespan min (ms)', type: 'number', default: 1000, min: 0 },
      { key: 'particle-lifespan-max', label: 'Lifespan max (ms)', type: 'number', default: 10000, min: 0 },
      { key: 'particle-amount', label: 'Particle amount', type: 'number', default: 1000, min: 0, max: 5000 },
      { key: 'grid-sides', label: 'Grid sides', type: 'number', default: 6, min: 3 },
      { key: 'grid-size', label: 'Grid size', type: 'number', default: 40, min: 1 },
      { key: 'grid-angle', label: 'Grid angle', type: 'number', default: 0 },
      { key: 'particle-colors', label: 'Explicit particle colors (overrides hue range)', type: 'colorArray', default: [] },
    ],
  },
  {
    key: 'digital-rain',
    tag: 'bb-digital-rain',
    label: 'Digital Rain',
    params: [
      ...BASE_PARAMS,
      { key: 'speed', label: 'Fall speed', type: 'number', default: 10, min: 0 },
      { key: 'characters', label: 'Character set', type: 'string', default: 'ｦｱｳｴｵｶｷｹｺｻｼｽｾｿﾀﾂﾃﾅﾆﾇﾈﾊﾋﾎﾏﾐﾑﾒﾓﾔﾕﾗﾘﾜ' },
      { key: 'randomness', label: 'Randomness', type: 'number', default: 0.975, min: 0, max: 1, step: 0.001 },
      { key: 'font-size', label: 'Font size', type: 'number', default: 24, min: 1 },
      { key: 'font-color-hue-start', label: 'Color hue start', type: 'number', default: 60, min: 0, max: 360 },
      { key: 'font-color-hue-end', label: 'Color hue end', type: 'number', default: 150, min: 0, max: 360 },
      { key: 'font-color-saturation-start', label: 'Saturation start', type: 'number', default: 90, min: 0, max: 100 },
      { key: 'font-color-saturation-end', label: 'Saturation end', type: 'number', default: 100, min: 0, max: 100 },
      { key: 'font-color-lightness-start', label: 'Lightness start', type: 'number', default: 50, min: 0, max: 100 },
      { key: 'font-color-lightness-end', label: 'Lightness end', type: 'number', default: 50, min: 0, max: 100 },
      { key: 'font-colors', label: 'Explicit font colors (overrides hue range)', type: 'colorArray', default: [] },
    ],
  },
  {
    key: 'hexagon-wave',
    tag: 'bb-hexagon-wave',
    label: 'Hexagon Wave',
    params: [
      ...BASE_PARAMS,
      { key: 'hex-size', label: 'Hex size', type: 'number', default: 50, min: 1 },
      { key: 'wave-amplitude', label: 'Wave amplitude', type: 'number', default: 5.5 },
      { key: 'wave-speed', label: 'Wave speed', type: 'number', default: 1.0, step: 0.1 },
      { key: 'wave-x-factor', label: 'Wave X factor', type: 'number', default: -0.005, step: 0.001 },
      { key: 'wave-y-factor', label: 'Wave Y factor', type: 'number', default: -0.005, step: 0.001 },
      { key: 'shade-amplitude', label: 'Shade amplitude', type: 'number', default: 0.5, step: 0.1 },
      { key: 'shade-lightness-boost', label: 'Shade lightness boost', type: 'number', default: 15 },
      { key: 'base-lightness', label: 'Base lightness', type: 'number', default: 10, min: 0, max: 100 },
      { key: 'lightness-range', label: 'Lightness range', type: 'number', default: 25, min: 0, max: 100 },
      { key: 'hex-hue-start', label: 'Hue start', type: 'number', default: 310, min: 0, max: 360 },
      { key: 'hex-hue-end', label: 'Hue end', type: 'number', default: 200, min: 0, max: 360 },
      { key: 'hex-saturation', label: 'Saturation', type: 'number', default: 100, min: 0, max: 100 },
      { key: 'hex-scale', label: 'Hex scale', type: 'number', default: 1.0, step: 0.1 },
      { key: 'hex-colors', label: 'Explicit hex colors (overrides hue range)', type: 'colorArray', default: [] },
    ],
  },
  {
    key: 'liquid-lines',
    tag: 'bb-liquid-lines',
    label: 'Liquid Lines',
    params: [
      ...BASE_PARAMS,
      { key: 'line-count', label: 'Line count', type: 'number', default: 20, min: 1 },
      { key: 'line-amplitude', label: 'Line amplitude', type: 'number', default: 30 },
      { key: 'line-frequency', label: 'Line frequency', type: 'number', default: 0.005, step: 0.001 },
      { key: 'speed', label: 'Speed', type: 'number', default: 0.5, step: 0.1 },
      { key: 'line-spacing', label: 'Line spacing', type: 'number', default: 40, min: 0 },
      { key: 'line-width', label: 'Line width', type: 'number', default: 2, min: 0 },
      { key: 'line-hue-start', label: 'Hue start', type: 'number', default: 200, min: 0, max: 360 },
      { key: 'line-hue-end', label: 'Hue end', type: 'number', default: 280, min: 0, max: 360 },
      { key: 'line-saturation', label: 'Saturation', type: 'number', default: 80, min: 0, max: 100 },
      { key: 'line-offset-step', label: 'Line offset step', type: 'number', default: 0.2, step: 0.01 },
      { key: 'wiggle-amplitude', label: 'Wiggle amplitude', type: 'number', default: 20 },
      { key: 'wiggle-speed', label: 'Wiggle speed', type: 'number', default: 0.3, step: 0.1 },
      { key: 'line-colors', label: 'Explicit line colors (overrides hue range)', type: 'colorArray', default: [] },
    ],
  },
  {
    key: 'neon-rails',
    tag: 'bb-neon-rails',
    label: 'Neon Rails',
    params: [
      ...BASE_PARAMS.filter((p) => p.key !== 'trail-opacity'), // neon-rails has its own trail-opacity default below
      { key: 'particle-size-min', label: 'Particle size min', type: 'number', default: 1, min: 0 },
      { key: 'particle-size-max', label: 'Particle size max', type: 'number', default: 1, min: 0 },
      { key: 'particle-speed-min', label: 'Particle speed min', type: 'number', default: -30 },
      { key: 'particle-speed-max', label: 'Particle speed max', type: 'number', default: 30 },
      { key: 'particle-color-hue-start', label: 'Color hue start', type: 'number', default: 130, min: 0, max: 360 },
      { key: 'particle-color-hue-end', label: 'Color hue end', type: 'number', default: 300, min: 0, max: 360 },
      { key: 'particle-color-saturation-start', label: 'Saturation start', type: 'number', default: 100, min: 0, max: 100 },
      { key: 'particle-color-saturation-end', label: 'Saturation end', type: 'number', default: 100, min: 0, max: 100 },
      { key: 'particle-color-lightness-start', label: 'Lightness start', type: 'number', default: 50, min: 0, max: 100 },
      { key: 'particle-color-lightness-end', label: 'Lightness end', type: 'number', default: 0, min: 0, max: 100 },
      { key: 'particle-lifespan-min', label: 'Lifespan min (ms)', type: 'number', default: 100, min: 0 },
      { key: 'particle-lifespan-max', label: 'Lifespan max (ms)', type: 'number', default: 50000, min: 0 },
      { key: 'particle-amount', label: 'Particle amount', type: 'number', default: 2000, min: 0, max: 5000 },
      { key: 'grid-sides', label: 'Grid sides', type: 'number', default: 3, min: 3 },
      { key: 'grid-size', label: 'Grid size', type: 'number', default: 60, min: 1 },
      { key: 'grid-angle', label: 'Grid angle', type: 'number', default: Math.PI / 2, step: 0.01 },
      { key: 'particle-colors', label: 'Explicit particle colors (overrides hue range)', type: 'colorArray', default: [] },
      { key: 'trail-opacity', label: 'Trail fade opacity', type: 'number', default: 0.0125, min: 0, max: 1, step: 0.001 },
    ],
  },
  {
    key: 'ambient-ribbon',
    tag: 'bb-ambient-ribbon',
    label: 'Ambient Ribbon',
    params: [
      ...BASE_PARAMS,
      { key: 'ribbon-count', label: 'Ribbon count', type: 'number', default: 5, min: 1 },
      { key: 'ribbon-width', label: 'Ribbon width', type: 'number', default: 100, min: 1 },
      { key: 'ribbon-rotation', label: 'Ribbon rotation', type: 'number', default: 45, min: 0, max: 360 },
      { key: 'ribbon-hue-start', label: 'Hue start', type: 'number', default: 11, min: 0, max: 360 },
      { key: 'ribbon-hue-end', label: 'Hue end', type: 'number', default: 14, min: 0, max: 360 },
      { key: 'ribbon-saturation-start', label: 'Saturation start', type: 'number', default: 100, min: 0, max: 100 },
      { key: 'ribbon-saturation-end', label: 'Saturation end', type: 'number', default: 100, min: 0, max: 100 },
      { key: 'ribbon-lightness-start', label: 'Lightness start', type: 'number', default: 50, min: 0, max: 100 },
      { key: 'ribbon-lightness-end', label: 'Lightness end', type: 'number', default: 50, min: 0, max: 100 },
      { key: 'ribbon-amplitude', label: 'Amplitude', type: 'number', default: 0.5, step: 0.1 },
      { key: 'ribbon-speed-min', label: 'Speed min', type: 'number', default: 0.004, step: 0.001 },
      { key: 'ribbon-speed-max', label: 'Speed max', type: 'number', default: 0.008, step: 0.001 },
      { key: 'ribbon-line-width', label: 'Line width', type: 'number', default: 2, min: 0 },
      { key: 'ribbon-line-opacity', label: 'Line opacity', type: 'number', default: 0.2, min: 0, max: 1, step: 0.01 },
    ],
  },
]

export function getEffectDefinition(key: string): EffectDefinition | undefined {
  return BACKGROUND_EFFECTS.find((e) => e.key === key)
}

/** Build a settings object with every param defaulted, for a freshly-picked effect. */
export function defaultSettingsFor(def: EffectDefinition): Record<string, number | string | string[]> {
  const out: Record<string, number | string | string[]> = {}
  for (const p of def.params) out[p.key] = p.default
  return out
}

/**
 * Set attribute values on *el* from a settings object, falling back to each
 * param's own default when missing. Array-valued params (colorArray) are
 * comma-separated — the library's array converter does
 * `value.split(",").map(trim)`, not JSON.
 */
export function applyEffectAttributes(
  el: HTMLElement,
  def: EffectDefinition,
  settings: Record<string, unknown>,
): void {
  for (const param of def.params) {
    const value = settings[param.key] ?? param.default
    const attrValue = Array.isArray(value) ? value.join(',') : String(value)
    el.setAttribute(param.key, attrValue)
  }
}
