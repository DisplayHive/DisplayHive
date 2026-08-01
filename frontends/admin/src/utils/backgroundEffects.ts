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

export interface EffectPreset {
  label: string
  values: Partial<Record<string, number | string | string[]>>
}

export interface EffectDefinition {
  key: string // stored in Design.background_effect
  tag: string // custom element tag name
  label: string
  params: EffectParam[]
  // Named variants curated from the beautiful-backgrounds Storybook
  // (https://niekes.github.io/beautiful-backgrounds). Each preset's values
  // are applied on top of defaultSettingsFor(def).
  presets?: EffectPreset[]
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
    presets: [
      {
        label: 'Galactic Vortex',
        values: { 'bg-colors': ['#000', '#030'], 'bg-angle': 275, 'particle-amount': 1000, 'particle-color-hue-start': 30, 'particle-color-hue-end': 75, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 50, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 1000, 'particle-lifespan-max': 10000, 'particle-size-min': 0.5, 'particle-size-max': 1.5, 'particle-speed-min': 0.1, 'particle-speed-max': 0.2, 'trail-opacity': 0.328, 'particle-colors': [] },
      },
      {
        label: 'Whirlpool Galaxy',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'particle-amount': 5000, 'particle-color-hue-start': 30, 'particle-color-hue-end': 75, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 50, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 5000, 'particle-lifespan-max': 20000, 'particle-size-min': 1.1, 'particle-size-max': 2.5, 'particle-speed-min': 0.1, 'particle-speed-max': 0.2, 'trail-opacity': 0.071, 'particle-colors': ['#0b2c55', '#1c5d92', '#6faee8', '#f7da85', '#d56297'], 'particle-force': 23 },
      },
      {
        label: 'Party Lights',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'particle-amount': 1000, 'particle-color-hue-start': 0, 'particle-color-hue-end': 360, 'particle-color-lightness-start': 70, 'particle-color-lightness-end': 90, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 3100, 'particle-lifespan-max': 13900, 'particle-size-min': 3.6, 'particle-size-max': 6.2, 'particle-speed-min': -0.01, 'particle-speed-max': 0.01, 'trail-opacity': 0.1, 'particle-colors': [] },
      },
      {
        label: 'Blue Fire Flies',
        values: { 'bg-colors': ['#050035', '#050035'], 'bg-angle': 0, 'particle-amount': 2000, 'particle-color-hue-start': 169, 'particle-color-hue-end': 275, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 50, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 100, 'particle-lifespan-max': 1000, 'particle-size-min': 0.2, 'particle-size-max': 0.8, 'particle-speed-min': -0.01, 'particle-speed-max': 0.01, 'trail-opacity': 0.1, 'particle-colors': [] },
      },
      {
        label: 'Cyan Ring',
        values: { 'bg-colors': ['#000000', '#000000'], 'bg-angle': 0, 'particle-amount': 2000, 'particle-color-hue-start': 174, 'particle-color-hue-end': 200, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 50, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 10000, 'particle-lifespan-max': 20000, 'particle-size-min': 0.2, 'particle-size-max': 0.8, 'particle-speed-min': -0.1, 'particle-speed-max': 0.1, 'trail-opacity': 0.1, 'particle-colors': [], 'particle-radius-max': 225, 'particle-radius-min': 153 },
      },
      {
        label: 'Gravitational Collapse',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'particle-amount': 2326, 'particle-color-hue-start': 0, 'particle-color-hue-end': 360, 'particle-color-lightness-start': 56, 'particle-color-lightness-end': 100, 'particle-color-saturation-start': 49, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 1000, 'particle-lifespan-max': 2600, 'particle-size-min': 0.5, 'particle-size-max': 2.5, 'particle-speed-min': -0.21, 'particle-speed-max': -0.14, 'trail-opacity': 0.275, 'particle-force': -31.8 },
      },
      {
        label: 'RGB Stars',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'particle-amount': 500, 'particle-color-hue-start': 30, 'particle-color-hue-end': 75, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 50, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 1000, 'particle-lifespan-max': 10000, 'particle-size-min': 2, 'particle-size-max': 4, 'particle-speed-min': 0.1, 'particle-speed-max': 0.2, 'trail-opacity': 0.1, 'particle-colors': ['#ff0000', '#00ff00', '#0000ff'] },
      },
      {
        label: 'Golden Nebula',
        values: { 'bg-colors': ['#1a0f00', '#1a0f00'], 'bg-angle': 0, 'particle-amount': 3000, 'particle-color-hue-start': 35, 'particle-color-hue-end': 55, 'particle-color-lightness-start': 60, 'particle-color-lightness-end': 85, 'particle-color-saturation-start': 80, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 8000, 'particle-lifespan-max': 15000, 'particle-size-min': 0.3, 'particle-size-max': 2, 'particle-speed-min': -0.1, 'particle-speed-max': 0.1, 'trail-opacity': 0.31, 'particle-colors': [], 'particle-force': 15 },
      },
      {
        label: 'Aurora Borealis',
        values: { 'bg-colors': ['#000a1a', '#000a1a'], 'bg-angle': 0, 'particle-amount': 4000, 'particle-color-hue-start': 30, 'particle-color-hue-end': 75, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 50, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 10000, 'particle-lifespan-max': 18000, 'particle-size-min': 0.5, 'particle-size-max': 1.5, 'particle-speed-min': -0.3, 'particle-speed-max': 0.3, 'trail-opacity': 0.08, 'particle-colors': ['#00ff88', '#00ffcc', '#88ff00', '#ccff00', '#00ccff'], 'particle-force': 8, 'particle-radius-min': 50, 'particle-radius-max': 300 },
      },
      {
        label: 'Cosmic Dust',
        values: { 'bg-colors': ['#0a0a14', '#0a0a14'], 'bg-angle': 0, 'particle-amount': 6000, 'particle-color-hue-start': 200, 'particle-color-hue-end': 280, 'particle-color-lightness-start': 40, 'particle-color-lightness-end': 70, 'particle-color-saturation-start': 60, 'particle-color-saturation-end': 90, 'particle-lifespan-min': 3000, 'particle-lifespan-max': 12000, 'particle-size-min': 0.1, 'particle-size-max': 0.8, 'particle-speed-min': 0.04, 'particle-speed-max': 0.03, 'trail-opacity': 0.126, 'particle-colors': [], 'particle-force': -5 },
      },
      {
        label: 'Firefly Forest',
        values: { 'bg-colors': ['#0f1a0a', '#0f1a0a'], 'bg-angle': 0, 'particle-amount': 800, 'particle-color-hue-start': 30, 'particle-color-hue-end': 75, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 50, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 500, 'particle-lifespan-max': 2000, 'particle-size-min': 1.5, 'particle-size-max': 3.5, 'particle-speed-min': -0.2, 'particle-speed-max': 0.2, 'trail-opacity': 0.217, 'particle-colors': ['#ffff00', '#ffee00', '#ffdd00'], 'particle-force': 0, 'particle-radius-min': 20, 'particle-radius-max': 400 },
      },
      {
        label: 'Neon Vortex',
        values: { 'bg-colors': ['#000000', '#000000'], 'bg-angle': 0, 'particle-amount': 3500, 'particle-color-hue-start': 30, 'particle-color-hue-end': 75, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 50, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 2000, 'particle-lifespan-max': 8000, 'particle-size-min': 0.8, 'particle-size-max': 2.5, 'particle-speed-min': 0.1, 'particle-speed-max': 0.2, 'trail-opacity': 0.075, 'particle-colors': ['#ff00ff', '#00ffff', '#ff0080', '#0080ff'], 'particle-force': 40, 'particle-radius-min': 100, 'particle-radius-max': 350 },
      },
      {
        label: 'Starfield Warp',
        values: { 'bg-colors': ['#000000', '#000000'], 'bg-angle': 0, 'particle-amount': 2000, 'particle-color-hue-start': 180, 'particle-color-hue-end': 240, 'particle-color-lightness-start': 80, 'particle-color-lightness-end': 100, 'particle-color-saturation-start': 50, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 500, 'particle-lifespan-max': 2000, 'particle-size-min': 0.5, 'particle-size-max': 3, 'particle-speed-min': -0.5, 'particle-speed-max': -0.25, 'trail-opacity': 0.2, 'particle-colors': [], 'particle-force': -50 },
      },
      {
        label: 'Twilight Sparkle',
        values: { 'bg-colors': ['#1a0f2e', '#1a0f2e'], 'bg-angle': 0, 'particle-amount': 1500, 'particle-color-hue-start': 30, 'particle-color-hue-end': 75, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 50, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 4000, 'particle-lifespan-max': 12000, 'particle-size-min': 1, 'particle-size-max': 3, 'particle-speed-min': -0.01, 'particle-speed-max': 0.01, 'trail-opacity': 0.189, 'particle-colors': ['#ff69b4', '#ba55d3', '#9370db', '#dda0dd'], 'particle-force': 12, 'particle-radius-min': 80, 'particle-radius-max': 280 },
      },
      {
        label: 'Rainbow Burst',
        values: { 'bg-colors': ['#000000', '#000000'], 'bg-angle': 0, 'particle-amount': 4500, 'particle-color-hue-start': 0, 'particle-color-hue-end': 360, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 70, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-lifespan-min': 500, 'particle-lifespan-max': 900, 'particle-size-min': 0.5, 'particle-size-max': 2, 'particle-speed-min': -0.03, 'particle-speed-max': -0.02, 'trail-opacity': 0.1, 'particle-colors': [], 'particle-force': -25, 'particle-radius-min': 1, 'particle-radius-max': 150 },
      },
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
    presets: [
      {
        label: 'Classic Matrix Rain',
        values: { 'bg-colors': ['#000', '#005c00'], 'bg-angle': 90, 'characters': 'ｱｲｳｴｵｶｷｸｹｺ', 'randomness': 0.95, 'font-size': 20, 'font-color-hue-start': 120, 'font-color-hue-end': 140, 'font-color-saturation-start': 80, 'font-color-saturation-end': 100, 'font-color-lightness-start': 40, 'font-color-lightness-end': 60, 'speed': 8, 'trail-opacity': 0.08, 'font-colors': [] },
      },
      {
        label: 'Cyberpunk Pink',
        values: { 'bg-colors': ['#570044', '#570099'], 'bg-angle': 0, 'characters': 'ΨΦΧΩΣΠΛΔΓΒΑ01100110ЯΞ', 'randomness': 0.975, 'font-size': 24, 'font-color-hue-start': 300, 'font-color-hue-end': 340, 'font-color-saturation-start': 90, 'font-color-saturation-end': 100, 'font-color-lightness-start': 50, 'font-color-lightness-end': 50, 'speed': 10, 'trail-opacity': 0.1, 'font-colors': [] },
      },
      {
        label: 'Purple Rain',
        values: { 'bg-colors': ['#000000', '#000000'], 'bg-angle': 0, 'characters': '|', 'randomness': 0.98, 'font-size': 12, 'font-color-hue-start': 261, 'font-color-hue-end': 289, 'font-color-saturation-start': 87, 'font-color-saturation-end': 100, 'font-color-lightness-start': 43, 'font-color-lightness-end': 55, 'speed': 5.4, 'trail-opacity': 0.1, 'font-colors': [] },
      },
      {
        label: 'Neon Blue',
        values: { 'bg-colors': ['#001122', '#001122'], 'bg-angle': 0, 'characters': 'ABCDEF0123456789', 'randomness': 0.9, 'font-size': 18, 'font-color-hue-start': 180, 'font-color-hue-end': 210, 'font-color-saturation-start': 90, 'font-color-saturation-end': 100, 'font-color-lightness-start': 60, 'font-color-lightness-end': 70, 'speed': 6, 'trail-opacity': 0.12, 'font-colors': [] },
      },
      {
        label: 'Orange Fire',
        values: { 'bg-colors': ['#220000', '#220000'], 'bg-angle': 0, 'characters': '▲◆●★', 'randomness': 0.92, 'font-size': 22, 'font-color-hue-start': 30, 'font-color-hue-end': 45, 'font-color-saturation-start': 80, 'font-color-saturation-end': 100, 'font-color-lightness-start': 50, 'font-color-lightness-end': 60, 'speed': 7, 'trail-opacity': 0.15, 'font-colors': [] },
      },
      {
        label: 'Ghost White',
        values: { 'bg-colors': ['#111111', '#111111'], 'bg-angle': 0, 'characters': '░▒▓■□▲▼', 'randomness': 0.98, 'font-size': 16, 'font-color-hue-start': 0, 'font-color-hue-end': 0, 'font-color-saturation-start': 0, 'font-color-saturation-end': 0, 'font-color-lightness-start': 80, 'font-color-lightness-end': 100, 'speed': 4, 'trail-opacity': 0.05, 'font-colors': [] },
      },
      {
        label: 'Rainbow Chaos',
        values: { 'bg-colors': ['#000000', '#000000'], 'bg-angle': 0, 'characters': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', 'randomness': 0.99, 'font-size': 14, 'font-color-hue-start': 0, 'font-color-hue-end': 360, 'font-color-saturation-start': 70, 'font-color-saturation-end': 100, 'font-color-lightness-start': 50, 'font-color-lightness-end': 50, 'speed': 9, 'trail-opacity': 0.09, 'font-colors': [] },
      },
      {
        label: 'Matrix Red',
        values: { 'bg-colors': ['#110000', '#110000'], 'bg-angle': 0, 'characters': 'ｦｱｳｴｵｶｷｹｺｻｼｽｾｿﾀﾂﾃﾅﾆﾇﾈﾊﾋﾎﾏﾐﾑﾒﾓﾔﾕﾗﾘﾜ13579ｦｲｸｺｿﾁﾄﾉﾌﾔﾖﾙﾚﾛﾝZ:."¦=*+-<>|ﾘçδ╘', 'randomness': 0.975, 'font-size': 18, 'font-color-hue-start': 100, 'font-color-hue-end': 140, 'font-color-saturation-start': 90, 'font-color-saturation-end': 100, 'font-color-lightness-start': 50, 'font-color-lightness-end': 50, 'speed': 12, 'trail-opacity': 0.1, 'font-colors': ['#ff0000', '#aa0000', '#550000'] },
      },
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
    presets: [
      {
        label: 'Honeycomb Pulsar',
        values: { 'bg-colors': ['#0071bc', '#0071bc'], 'bg-angle': 0, 'hex-size': 50, 'wave-amplitude': 5.5, 'wave-speed': 1.3, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 30, 'lightness-range': 32, 'hex-hue-start': 207, 'hex-hue-end': 318, 'hex-saturation': 75, 'hex-scale': 1, 'trail-opacity': 0.1, 'hex-colors': [] },
      },
      {
        label: 'Sunset Gradient',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'hex-size': 50, 'wave-amplitude': 5.5, 'wave-speed': 1.1, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 50, 'lightness-range': 30, 'hex-hue-start': 10, 'hex-hue-end': 60, 'hex-saturation': 60, 'hex-scale': 1, 'trail-opacity': 0.1, 'hex-colors': [] },
      },
      {
        label: 'Neon Vibe',
        values: { 'bg-colors': ['#050510', '#050510'], 'bg-angle': 0, 'hex-size': 50, 'wave-amplitude': 5.5, 'wave-speed': 1.1, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 50, 'lightness-range': 40, 'hex-hue-start': 280, 'hex-hue-end': 320, 'hex-saturation': 60, 'hex-scale': 0.8, 'trail-opacity': 0.1, 'hex-colors': [] },
      },
      {
        label: 'Honey Combs',
        values: { 'bg-colors': ['#eeff00', '#eeff00'], 'bg-angle': 0, 'hex-size': 50, 'wave-amplitude': 5.5, 'wave-speed': 1.1, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 50, 'lightness-range': 25, 'hex-hue-start': 40, 'hex-hue-end': 80, 'hex-saturation': 60, 'hex-scale': 0.9, 'trail-opacity': 0.1, 'hex-colors': [] },
      },
      {
        label: 'Tiny Cells',
        values: { 'bg-colors': ['#321145', '#213f52'], 'bg-angle': 0, 'hex-size': 16, 'wave-amplitude': 4, 'wave-speed': 1.1, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 50, 'lightness-range': 25, 'hex-hue-start': 200, 'hex-hue-end': 260, 'hex-saturation': 60, 'hex-scale': 0.6, 'trail-opacity': 0.1, 'hex-colors': [] },
      },
      {
        label: 'Ocean Depths',
        values: { 'bg-colors': ['#001a33', '#001a33'], 'bg-angle': 0, 'hex-size': 60, 'wave-amplitude': 9.9, 'wave-speed': 0.5, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 45, 'lightness-range': 23, 'hex-hue-start': 180, 'hex-hue-end': 220, 'hex-saturation': 60, 'hex-scale': 1.1, 'trail-opacity': 0.1, 'hex-colors': [] },
      },
      {
        label: 'Lava Flow',
        values: { 'bg-colors': ['#ff8e00', '#ff8e00'], 'bg-angle': 0, 'hex-size': 45, 'wave-amplitude': 5.5, 'wave-speed': 0.8, 'wave-x-factor': 0.005, 'wave-y-factor': 0.005, 'base-lightness': 50, 'lightness-range': 15, 'hex-hue-start': 0, 'hex-hue-end': 38, 'hex-saturation': 60, 'hex-scale': 1, 'trail-opacity': 0.1, 'hex-colors': [] },
      },
      {
        label: 'Arctic Ice',
        values: { 'bg-colors': ['#e6f7ff', '#e6f7ff'], 'bg-angle': 0, 'hex-size': 70, 'wave-amplitude': 5.5, 'wave-speed': 1.1, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 60, 'lightness-range': 20, 'hex-hue-start': 180, 'hex-hue-end': 200, 'hex-saturation': 60, 'hex-scale': 0.95, 'trail-opacity': 0.15, 'hex-colors': [] },
      },
      {
        label: 'Cyberpunk Grid',
        values: { 'bg-colors': ['#0a0014', '#0a0014'], 'bg-angle': 0, 'hex-size': 35, 'wave-amplitude': 5.5, 'wave-speed': 2, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 50, 'lightness-range': 30, 'hex-hue-start': 310, 'hex-hue-end': 200, 'hex-saturation': 60, 'hex-scale': 1, 'trail-opacity': 0.1, 'hex-colors': ['#ff00ff', '#00ffff', '#ff0080'] },
      },
      {
        label: 'Forest Canopy',
        values: { 'bg-colors': ['#0d1f0d', '#0d1f0d'], 'bg-angle': 0, 'hex-size': 55, 'wave-amplitude': 5.5, 'wave-speed': 0.6, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 15, 'lightness-range': 25, 'hex-hue-start': 90, 'hex-hue-end': 150, 'hex-saturation': 60, 'hex-scale': 1, 'trail-opacity': 0.1, 'hex-colors': [] },
      },
      {
        label: 'Desert Mirage',
        values: { 'bg-colors': ['#2b1f0f', '#2b1f0f'], 'bg-angle': 0, 'hex-size': 40, 'wave-amplitude': 0.8, 'wave-speed': 1.2, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 35, 'lightness-range': 30, 'hex-hue-start': 30, 'hex-hue-end': 50, 'hex-saturation': 60, 'hex-scale': 1, 'trail-opacity': 0.1, 'hex-colors': [] },
      },
      {
        label: 'Electric Storm',
        values: { 'bg-colors': ['#0f0f1a', '#0f0f1a'], 'bg-angle': 0, 'hex-size': 30, 'wave-amplitude': 21.4, 'wave-speed': 3, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 46, 'lightness-range': 43, 'hex-hue-start': 240, 'hex-hue-end': 280, 'hex-saturation': 60, 'hex-scale': 1.15, 'trail-opacity': 0.1, 'hex-colors': [] },
      },
      {
        label: 'Pastel Dream',
        values: { 'bg-colors': ['#fff5f8', '#fff5f8'], 'bg-angle': 0, 'hex-size': 50, 'wave-amplitude': 0.3, 'wave-speed': 2.4, 'wave-x-factor': -0.005, 'wave-y-factor': -0.005, 'base-lightness': 63, 'lightness-range': 15, 'hex-hue-start': 310, 'hex-hue-end': 200, 'hex-saturation': 60, 'hex-scale': 0.9, 'trail-opacity': 0.2, 'hex-colors': ['#ffb3d9', '#b3d9ff', '#d9b3ff', '#ffffb3'] },
      },
      {
        label: 'Surfers Paradise',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'hex-size': 7, 'wave-amplitude': 5.5, 'wave-speed': -1, 'wave-x-factor': -0.007, 'wave-y-factor': 0.03, 'base-lightness': 37, 'lightness-range': 25, 'hex-hue-start': 182, 'hex-hue-end': 233, 'hex-saturation': 100, 'hex-scale': 1.2, 'trail-opacity': 0.1, 'hex-colors': [] },
      },
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
    presets: [
      {
        label: 'Serpentine Flow',
        values: { 'bg-colors': ['#000000', '#000000'], 'bg-angle': 0, 'line-count': 16, 'line-amplitude': 48, 'line-frequency': 0.005, 'speed': 2.05, 'line-spacing': 40, 'line-width': 2, 'line-hue-start': 200, 'line-hue-end': 280, 'line-saturation': 80, 'line-offset-step': 0.2, 'line-colors': [], 'wiggle-amplitude': 20, 'wiggle-speed': 0.3, 'trail-opacity': 0.1 },
      },
      {
        label: 'Deep Sea',
        values: { 'bg-colors': ['#000814', '#000814'], 'bg-angle': 0, 'line-count': 40, 'line-amplitude': 60, 'line-frequency': 0.003, 'speed': 0.2, 'line-spacing': 25, 'line-width': 2, 'line-hue-start': 180, 'line-hue-end': 220, 'line-saturation': 80, 'line-offset-step': 0.2, 'line-colors': [], 'wiggle-amplitude': 1, 'wiggle-speed': 5, 'trail-opacity': 0.1 },
      },
      {
        label: 'Sunset Glow',
        values: { 'bg-colors': ['#1a0f00', '#1a0f00'], 'bg-angle': 0, 'line-count': 15, 'line-amplitude': 40, 'line-frequency': 0.008, 'speed': 0.8, 'line-spacing': 50, 'line-width': 2, 'line-hue-start': 10, 'line-hue-end': 50, 'line-saturation': 80, 'line-offset-step': 0.2, 'line-colors': [], 'wiggle-amplitude': 20, 'wiggle-speed': 0.7, 'trail-opacity': 0.1 },
      },
      {
        label: 'Neon Pulse',
        values: { 'bg-colors': ['#050010', '#050010'], 'bg-angle': 0, 'line-count': 30, 'line-amplitude': 100, 'line-frequency': 0.012, 'speed': 1.2, 'line-spacing': 30, 'line-width': 1, 'line-hue-start': 280, 'line-hue-end': 320, 'line-saturation': 80, 'line-offset-step': 0.2, 'line-colors': [], 'wiggle-amplitude': 2, 'wiggle-speed': 3, 'trail-opacity': 0.05 },
      },
      {
        label: 'Minimalist',
        values: { 'bg-colors': ['#ffffff', '#ffffff'], 'bg-angle': 0, 'line-count': 8, 'line-amplitude': 20, 'line-frequency': 0.002, 'speed': 0.1, 'line-spacing': 100, 'line-width': 0.5, 'line-hue-start': 0, 'line-hue-end': 0, 'line-saturation': 0, 'line-offset-step': 0.2, 'line-colors': [], 'wiggle-amplitude': 20, 'wiggle-speed': 0.3, 'trail-opacity': 0.1 },
      },
      {
        label: 'Aurora Borealis',
        values: { 'bg-colors': ['#000510', '#000510'], 'bg-angle': 0, 'line-count': 25, 'line-amplitude': 120, 'line-frequency': 0.004, 'speed': 0.3, 'line-spacing': 35, 'line-width': 3, 'line-hue-start': 120, 'line-hue-end': 180, 'line-saturation': 90, 'line-offset-step': 0.2, 'line-colors': [], 'wiggle-amplitude': 40, 'wiggle-speed': 3.1, 'trail-opacity': 0.08 },
      },
      {
        label: 'Molten Magma',
        values: { 'bg-colors': ['#100000', '#100000'], 'bg-angle': 0, 'line-count': 12, 'line-amplitude': 50, 'line-frequency': 0.006, 'speed': 0.15, 'line-spacing': 60, 'line-width': 12, 'line-hue-start': 0, 'line-hue-end': 30, 'line-saturation': 100, 'line-offset-step': 0.2, 'line-colors': [], 'wiggle-amplitude': 10, 'wiggle-speed': 0.1, 'trail-opacity': 0.1 },
      },
      {
        label: 'Digital Mist',
        values: { 'bg-colors': ['#0a0a0a', '#0a0a0a'], 'bg-angle': 0, 'line-count': 60, 'line-amplitude': 15, 'line-frequency': 0.02, 'speed': 0.8, 'line-spacing': 15, 'line-width': 0.5, 'line-hue-start': 200, 'line-hue-end': 240, 'line-saturation': 80, 'line-offset-step': 0.2, 'line-colors': [], 'wiggle-amplitude': 20, 'wiggle-speed': 0.3, 'trail-opacity': 0.2 },
      },
      {
        label: 'Bioluminescence',
        values: { 'bg-colors': ['#000a0a', '#000a0a'], 'bg-angle': 0, 'line-count': 54, 'line-amplitude': 80, 'line-frequency': 0.004, 'speed': 0.88, 'line-spacing': 16, 'line-width': 3.2, 'line-hue-start': 164, 'line-hue-end': 245, 'line-saturation': 80, 'line-offset-step': 0.04, 'line-colors': [], 'wiggle-amplitude': 3, 'wiggle-speed': 1.6, 'trail-opacity': 0.03 },
      },
      {
        label: 'Golden Hour',
        values: { 'bg-colors': ['#1a1500', '#1a1500'], 'bg-angle': 0, 'line-count': 10, 'line-amplitude': 30, 'line-frequency': 0.003, 'speed': 0.2, 'line-spacing': 80, 'line-width': 5, 'line-hue-start': 40, 'line-hue-end': 60, 'line-saturation': 70, 'line-offset-step': 0.2, 'line-colors': [], 'wiggle-amplitude': 20, 'wiggle-speed': 0.3, 'trail-opacity': 0.1 },
      },
      {
        label: 'Rainbow',
        values: { 'bg-colors': ['#000000', '#000000'], 'bg-angle': 0, 'line-count': 30, 'line-amplitude': 40, 'line-frequency': 0.005, 'speed': 0.5, 'line-spacing': 30, 'line-width': 2, 'line-hue-start': 200, 'line-hue-end': 280, 'line-saturation': 80, 'line-offset-step': 0.2, 'line-colors': ['#ff0000', '#ffa500', '#ffff00', '#008000', '#0000ff', '#4b0082', '#ee82ee'], 'wiggle-amplitude': 10, 'wiggle-speed': 0.5, 'trail-opacity': 0.1 },
      },
      {
        label: 'Pink Shutters',
        values: { 'bg-colors': ['#ffffff', '#ffffff'], 'bg-angle': 0, 'line-count': 61, 'line-amplitude': 48, 'line-frequency': 0.0007, 'speed': -1, 'line-spacing': 23, 'line-width': 0.9, 'line-hue-start': 276, 'line-hue-end': 360, 'line-saturation': 80, 'line-offset-step': 0.2, 'line-colors': [], 'wiggle-amplitude': 5, 'wiggle-speed': 0.7, 'trail-opacity': 0.15 },
      },
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
    presets: [
      {
        label: 'Cyber Grid Network',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'particle-size-min': 1, 'particle-size-max': 1, 'particle-speed-min': -1, 'particle-speed-max': 1, 'particle-color-hue-start': 130, 'particle-color-hue-end': 300, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 0, 'particle-lifespan-min': 100, 'particle-lifespan-max': 50000, 'particle-amount': 2000, 'grid-sides': 6, 'grid-size': 60, 'grid-angle': 3.141593, 'trail-opacity': 0.0125, 'particle-colors': [] },
      },
      {
        label: 'Laser Security Grid',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'particle-size-min': 0.1, 'particle-size-max': 0.1, 'particle-speed-min': 1.7, 'particle-speed-max': 3.2, 'particle-color-hue-start': 350, 'particle-color-hue-end': 353, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 0, 'particle-color-lightness-end': 50, 'particle-lifespan-min': 3600, 'particle-lifespan-max': 7900, 'particle-amount': 2000, 'grid-sides': 6, 'grid-size': 60, 'grid-angle': 1.570796, 'trail-opacity': 0.0125, 'particle-colors': [] },
      },
      {
        label: 'Golden Mesh',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'particle-size-min': 0.1, 'particle-size-max': 1.3, 'particle-speed-min': -0.8, 'particle-speed-max': 0.9, 'particle-color-hue-start': 21, 'particle-color-hue-end': 33, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 62, 'particle-color-lightness-end': 98, 'particle-lifespan-min': 100, 'particle-lifespan-max': 3200, 'particle-amount': 5000, 'grid-sides': 3, 'grid-size': 31, 'grid-angle': 1.570796, 'trail-opacity': 0.0125, 'particle-colors': [] },
      },
      {
        label: 'Star Role',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'particle-size-min': 1, 'particle-size-max': 1.7, 'particle-speed-min': 0.1, 'particle-speed-max': 2.7, 'particle-color-hue-start': 194, 'particle-color-hue-end': 360, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 0, 'particle-lifespan-min': 100, 'particle-lifespan-max': 6000, 'particle-amount': 997, 'grid-sides': 2, 'grid-size': 60, 'grid-angle': 1.570796, 'trail-opacity': 0.078, 'particle-colors': [] },
      },
      {
        label: 'Maze',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'particle-size-min': 2, 'particle-size-max': 2, 'particle-speed-min': 2.5, 'particle-speed-max': 4, 'particle-color-hue-start': 130, 'particle-color-hue-end': 300, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 0, 'particle-lifespan-min': 100, 'particle-lifespan-max': 50000, 'particle-amount': 506, 'grid-sides': 4, 'grid-size': 29, 'grid-angle': 3.141593, 'trail-opacity': 0.05, 'particle-colors': ['#ffffff', '#008BFF', '#E4FF30'] },
      },
      {
        label: 'Triangle Chain',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'particle-size-min': 0.1, 'particle-size-max': 0.2, 'particle-speed-min': 0.1, 'particle-speed-max': 10, 'particle-color-hue-start': 63, 'particle-color-hue-end': 81, 'particle-color-saturation-start': 60, 'particle-color-saturation-end': 70, 'particle-color-lightness-start': 0, 'particle-color-lightness-end': 100, 'particle-lifespan-min': 100, 'particle-lifespan-max': 6000, 'particle-amount': 200, 'grid-sides': 3, 'grid-size': 29, 'grid-angle': 6.283185, 'trail-opacity': 0.001, 'particle-colors': [] },
      },
      {
        label: 'Pink Veins',
        values: { 'bg-colors': ['#000', '#000'], 'bg-angle': 0, 'particle-size-min': 0.1, 'particle-size-max': 1, 'particle-speed-min': -4.6, 'particle-speed-max': 2.8, 'particle-color-hue-start': 278, 'particle-color-hue-end': 307, 'particle-color-saturation-start': 19, 'particle-color-saturation-end': 82, 'particle-color-lightness-start': 0, 'particle-color-lightness-end': 100, 'particle-lifespan-min': 100, 'particle-lifespan-max': 31800, 'particle-amount': 166, 'grid-sides': 6, 'grid-size': 10, 'grid-angle': 2.932153, 'trail-opacity': 0.001, 'particle-colors': [] },
      },
      {
        label: 'Electric Highway',
        values: { 'bg-colors': ['#000a1a', '#000a1a'], 'bg-angle': 0, 'particle-size-min': 1.5, 'particle-size-max': 3, 'particle-speed-min': 15, 'particle-speed-max': 25, 'particle-color-hue-start': 130, 'particle-color-hue-end': 300, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 0, 'particle-lifespan-min': 2000, 'particle-lifespan-max': 8000, 'particle-amount': 800, 'grid-sides': 4, 'grid-size': 80, 'grid-angle': 0, 'trail-opacity': 0.08, 'particle-colors': ['#00ffff', '#0080ff'] },
      },
      {
        label: 'Violet Lattice',
        values: { 'bg-colors': ['#0f0014', '#0f0014'], 'bg-angle': 0, 'particle-size-min': 0.5, 'particle-size-max': 2, 'particle-speed-min': -3, 'particle-speed-max': 3, 'particle-color-hue-start': 130, 'particle-color-hue-end': 300, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 0, 'particle-lifespan-min': 5000, 'particle-lifespan-max': 15000, 'particle-amount': 1500, 'grid-sides': 6, 'grid-size': 45, 'grid-angle': 0.523599, 'trail-opacity': 0.02, 'particle-colors': ['#ff00ff', '#ff0080', '#8000ff'] },
      },
      {
        label: 'Tron Legacy',
        values: { 'bg-colors': ['#000000', '#000000'], 'bg-angle': 0, 'particle-size-min': 0.8, 'particle-size-max': 1.7, 'particle-speed-min': 8, 'particle-speed-max': 20, 'particle-color-hue-start': 180, 'particle-color-hue-end': 200, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 80, 'particle-lifespan-min': 3000, 'particle-lifespan-max': 10000, 'particle-amount': 2500, 'grid-sides': 4, 'grid-size': 50, 'grid-angle': 2.007129, 'trail-opacity': 0.05, 'particle-colors': [] },
      },
      {
        label: 'Neural Network',
        values: { 'bg-colors': ['#0a0a0f', '#0a0a0f'], 'bg-angle': 0, 'particle-size-min': 0.3, 'particle-size-max': 1.2, 'particle-speed-min': -2, 'particle-speed-max': 2, 'particle-color-hue-start': 130, 'particle-color-hue-end': 300, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 0, 'particle-lifespan-min': 8000, 'particle-lifespan-max': 25000, 'particle-amount': 3000, 'grid-sides': 5, 'grid-size': 35, 'grid-angle': 0, 'trail-opacity': 0.044, 'particle-colors': ['#00ff88', '#00ffcc', '#00ffff'] },
      },
      {
        label: 'Rainbow Circuit',
        values: { 'bg-colors': ['#000000', '#000000'], 'bg-angle': 0, 'particle-size-min': 1, 'particle-size-max': 2.5, 'particle-speed-min': 2.6, 'particle-speed-max': 3.3, 'particle-color-hue-start': 0, 'particle-color-hue-end': 360, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 70, 'particle-lifespan-min': 4000, 'particle-lifespan-max': 12000, 'particle-amount': 1800, 'grid-sides': 8, 'grid-size': 60, 'grid-angle': 0.392699, 'trail-opacity': 0.03, 'particle-colors': [] },
      },
      {
        label: 'Quantum Tunnels',
        values: { 'bg-colors': ['#000000', '#000000'], 'bg-angle': 0, 'particle-size-min': 0.2, 'particle-size-max': 1.8, 'particle-speed-min': -12, 'particle-speed-max': 12, 'particle-color-hue-start': 260, 'particle-color-hue-end': 280, 'particle-color-saturation-start': 80, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 40, 'particle-color-lightness-end': 90, 'particle-lifespan-min': 1500, 'particle-lifespan-max': 8000, 'particle-amount': 4000, 'grid-sides': 3, 'grid-size': 40, 'grid-angle': 1.047198, 'trail-opacity': 0.01, 'particle-colors': [] },
      },
      {
        label: 'Emerald Matrix',
        values: { 'bg-colors': ['#001a00', '#001a00'], 'bg-angle': 0, 'particle-size-min': 0.5, 'particle-size-max': 1.5, 'particle-speed-min': 3, 'particle-speed-max': 10, 'particle-color-hue-start': 120, 'particle-color-hue-end': 150, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 30, 'particle-color-lightness-end': 70, 'particle-lifespan-min': 5000, 'particle-lifespan-max': 18000, 'particle-amount': 2200, 'grid-sides': 4, 'grid-size': 25, 'grid-angle': 0, 'trail-opacity': 0.025, 'particle-colors': [] },
      },
      {
        label: 'Sunset Grid',
        values: { 'bg-colors': ['#1a0a00', '#1a0a00'], 'bg-angle': 0, 'particle-size-min': 0.8, 'particle-size-max': 2.5, 'particle-speed-min': -5, 'particle-speed-max': 5, 'particle-color-hue-start': 130, 'particle-color-hue-end': 300, 'particle-color-saturation-start': 100, 'particle-color-saturation-end': 100, 'particle-color-lightness-start': 50, 'particle-color-lightness-end': 0, 'particle-lifespan-min': 6000, 'particle-lifespan-max': 20000, 'particle-amount': 1200, 'grid-sides': 6, 'grid-size': 55, 'grid-angle': 1.570796, 'trail-opacity': 0.04, 'particle-colors': ['#ff6600', '#ff9900', '#ffcc00', '#ff3300'] },
      },
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
    presets: [
      {
        label: 'Signature Flow',
        values: { 'ribbon-count': 20, 'ribbon-width': 100, 'ribbon-rotation': 159, 'ribbon-hue-start': 330, 'ribbon-hue-end': 360, 'ribbon-saturation-start': 100, 'ribbon-saturation-end': 100, 'ribbon-lightness-start': 50, 'ribbon-lightness-end': 50, 'ribbon-amplitude': 0.5, 'ribbon-speed-min': 0.004, 'ribbon-speed-max': 0.008, 'ribbon-line-width': 0.3, 'ribbon-line-opacity': 0.26, 'bg-colors': ['#000', '#5d0e21'], 'bg-angle': 90, 'trail-opacity': 0.1 },
      },
      {
        label: 'Colorful',
        values: { 'ribbon-count': 10, 'ribbon-width': 100, 'ribbon-rotation': 45, 'ribbon-hue-start': 0, 'ribbon-hue-end': 360, 'ribbon-saturation-start': 100, 'ribbon-saturation-end': 100, 'ribbon-lightness-start': 50, 'ribbon-lightness-end': 50, 'ribbon-amplitude': 0.5, 'ribbon-speed-min': 0.004, 'ribbon-speed-max': 0.008, 'ribbon-line-width': 2, 'ribbon-line-opacity': 0.2, 'bg-colors': ['#000', '#681666'], 'bg-angle': 90, 'trail-opacity': 0.1 },
      },
      {
        label: 'Monochrome',
        values: { 'ribbon-count': 6, 'ribbon-width': 100, 'ribbon-rotation': 45, 'ribbon-hue-start': 0, 'ribbon-hue-end': 0, 'ribbon-saturation-start': 0, 'ribbon-saturation-end': 0, 'ribbon-lightness-start': 70, 'ribbon-lightness-end': 40, 'ribbon-amplitude': 0.5, 'ribbon-speed-min': 0.004, 'ribbon-speed-max': 0.008, 'ribbon-line-width': 2, 'ribbon-line-opacity': 0.2, 'bg-colors': ['#0a0a0a', '#1a1a1a'], 'bg-angle': 90, 'trail-opacity': 0.1 },
      },
      {
        label: 'Emerald Forest',
        values: { 'ribbon-count': 15, 'ribbon-width': 100, 'ribbon-rotation': 45, 'ribbon-hue-start': 120, 'ribbon-hue-end': 160, 'ribbon-saturation-start': 60, 'ribbon-saturation-end': 80, 'ribbon-lightness-start': 40, 'ribbon-lightness-end': 60, 'ribbon-amplitude': 0.5, 'ribbon-speed-min': 0.004, 'ribbon-speed-max': 0.008, 'ribbon-line-width': 2, 'ribbon-line-opacity': 0.2, 'bg-colors': ['#062006', '#000'], 'bg-angle': 90, 'trail-opacity': 0.1 },
      },
      {
        label: 'Golden Hour',
        values: { 'ribbon-count': 12, 'ribbon-width': 100, 'ribbon-rotation': 0, 'ribbon-hue-start': 40, 'ribbon-hue-end': 55, 'ribbon-saturation-start': 80, 'ribbon-saturation-end': 100, 'ribbon-lightness-start': 50, 'ribbon-lightness-end': 70, 'ribbon-amplitude': 0.5, 'ribbon-speed-min': 0.004, 'ribbon-speed-max': 0.008, 'ribbon-line-width': 2, 'ribbon-line-opacity': 0.2, 'bg-colors': ['#2d1b00', '#4d3300'], 'bg-angle': 180, 'trail-opacity': 0.1 },
      },
      {
        label: 'Midnight Aura',
        values: { 'ribbon-count': 40, 'ribbon-width': 100, 'ribbon-rotation': 45, 'ribbon-hue-start': 240, 'ribbon-hue-end': 320, 'ribbon-saturation-start': 50, 'ribbon-saturation-end': 70, 'ribbon-lightness-start': 40, 'ribbon-lightness-end': 50, 'ribbon-amplitude': 0.5, 'ribbon-speed-min': 0.004, 'ribbon-speed-max': 0.008, 'ribbon-line-width': 0.1, 'ribbon-line-opacity': 0.1, 'bg-colors': ['#000', '#0a001a'], 'bg-angle': 90, 'trail-opacity': 0.1 },
      },
      {
        label: 'Soft Pastel',
        values: { 'ribbon-count': 5, 'ribbon-width': 100, 'ribbon-rotation': 45, 'ribbon-hue-start': 180, 'ribbon-hue-end': 260, 'ribbon-saturation-start': 40, 'ribbon-saturation-end': 60, 'ribbon-lightness-start': 70, 'ribbon-lightness-end': 85, 'ribbon-amplitude': 0.5, 'ribbon-speed-min': 0.002, 'ribbon-speed-max': 0.004, 'ribbon-line-width': 2, 'ribbon-line-opacity': 0.2, 'bg-colors': ['#f5f7fa', '#e4ecf5'], 'bg-angle': 90, 'trail-opacity': 0.1 },
      },
      {
        label: 'Neon Glow',
        values: { 'ribbon-count': 7, 'ribbon-width': 100, 'ribbon-rotation': 45, 'ribbon-hue-start': 280, 'ribbon-hue-end': 320, 'ribbon-saturation-start': 100, 'ribbon-saturation-end': 100, 'ribbon-lightness-start': 60, 'ribbon-lightness-end': 70, 'ribbon-amplitude': 0.5, 'ribbon-speed-min': 0.004, 'ribbon-speed-max': 0.008, 'ribbon-line-width': 3, 'ribbon-line-opacity': 0.6, 'bg-colors': ['#050008', '#12001f'], 'bg-angle': 90, 'trail-opacity': 0.1 },
      },
      {
        label: 'Minimal Lines',
        values: { 'ribbon-count': 2, 'ribbon-width': 100, 'ribbon-rotation': 45, 'ribbon-hue-start': 11, 'ribbon-hue-end': 14, 'ribbon-saturation-start': 100, 'ribbon-saturation-end': 100, 'ribbon-lightness-start': 50, 'ribbon-lightness-end': 50, 'ribbon-amplitude': 0.2, 'ribbon-speed-min': 0.004, 'ribbon-speed-max': 0.008, 'ribbon-line-width': 0.2, 'ribbon-line-opacity': 0.15, 'bg-colors': ['#000', '#000'], 'bg-angle': 90, 'trail-opacity': 0.1 },
      },
      {
        label: 'Sunset Flow',
        values: { 'ribbon-count': 5, 'ribbon-width': 100, 'ribbon-rotation': 45, 'ribbon-hue-start': 15, 'ribbon-hue-end': 45, 'ribbon-saturation-start': 90, 'ribbon-saturation-end': 100, 'ribbon-lightness-start': 55, 'ribbon-lightness-end': 45, 'ribbon-amplitude': 0.5, 'ribbon-speed-min': 0.004, 'ribbon-speed-max': 0.007, 'ribbon-line-width': 2, 'ribbon-line-opacity': 0.2, 'bg-colors': ['#2b0a1f', '#ff6a00'], 'bg-angle': 120, 'trail-opacity': 0.1 },
      },
      {
        label: 'Cold Wave',
        values: { 'ribbon-count': 2, 'ribbon-width': 100, 'ribbon-rotation': 45, 'ribbon-hue-start': 190, 'ribbon-hue-end': 220, 'ribbon-saturation-start': 70, 'ribbon-saturation-end': 80, 'ribbon-lightness-start': 60, 'ribbon-lightness-end': 50, 'ribbon-amplitude': 0.5, 'ribbon-speed-min': 0.003, 'ribbon-speed-max': 0.006, 'ribbon-line-width': 2, 'ribbon-line-opacity': 0.2, 'bg-colors': ['#020617', '#0f172a'], 'bg-angle': 90, 'trail-opacity': 0.1 },
      },
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
