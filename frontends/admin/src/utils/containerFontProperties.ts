// Per-container "Font" style properties — shared by the Designs page's
// Global Styles panel and the Layout editor's "Container Design" card, so
// both edit exactly the same set (DesignContainerStyle rows on the backend).
// Blank/"(not set)" means the property is omitted from the generated CSS.

export interface FontOption { label: string; value: string }
export interface FontProperty {
  key: string
  label: string
  /** 'dropdown' (editable Dropdown, default) | 'vh-number' (numeric vh input) | 'color' (ColorPicker) */
  type?: 'dropdown' | 'vh-number' | 'color' | 'number'
  options?: FontOption[]
  /** 'number' only: unit appended to the stored value ('' for unitless) and input bounds. */
  unit?: string
  min?: number
  max?: number
  step?: number
  /** The browser's own default, as the stored string. Selecting it is the same as "(not set)" and is never saved (see ContainerDesignFields). */
  systemDefault?: string
}

export const NOT_SET: FontOption = { label: '(not set)', value: '' }

export const WEB_SAFE_FONTS: FontOption[] = [
  { label: 'Arial', value: 'Arial, sans-serif' },
  { label: 'Arial Black', value: '"Arial Black", sans-serif' },
  { label: 'Verdana', value: 'Verdana, sans-serif' },
  { label: 'Tahoma', value: 'Tahoma, sans-serif' },
  { label: 'Trebuchet MS', value: '"Trebuchet MS", sans-serif' },
  { label: 'Impact', value: 'Impact, sans-serif' },
  { label: 'Segoe UI', value: '"Segoe UI", sans-serif' },
  { label: 'Times New Roman', value: '"Times New Roman", serif' },
  { label: 'Georgia', value: 'Georgia, serif' },
  { label: 'Garamond', value: 'Garamond, serif' },
  { label: 'Courier New', value: '"Courier New", monospace' },
  { label: 'Lucida Console', value: '"Lucida Console", monospace' },
  { label: 'Monaco', value: 'Monaco, monospace' },
  { label: 'Brush Script MT', value: '"Brush Script MT", cursive' },
  { label: 'Comic Sans MS', value: '"Comic Sans MS", cursive' },
  { label: 'Sans-serif (generic)', value: 'sans-serif' },
  { label: 'Serif (generic)', value: 'serif' },
  { label: 'Monospace (generic)', value: 'monospace' },
  { label: 'Cursive (generic)', value: 'cursive' },
  { label: 'Fantasy (generic)', value: 'fantasy' },
  { label: 'System UI (generic)', value: 'system-ui' },
]

export const keywordOptions = (...values: string[]): FontOption[] => values.map((v) => ({ label: v, value: v }))

export const FONT_PROPERTIES: FontProperty[] = [
  { key: 'font-family', label: 'Font Family', options: [NOT_SET, ...WEB_SAFE_FONTS] },
  { key: 'font-variant', label: 'Font Variant', options: [NOT_SET, ...keywordOptions(
    'normal', 'small-caps', 'all-small-caps', 'petite-caps', 'all-petite-caps', 'unicase', 'titling-caps',
  )] },
  { key: 'font-weight', label: 'Font Weight', options: [NOT_SET, ...keywordOptions(
    'normal', 'bold', 'bolder', 'lighter', '100', '200', '300', '400', '500', '600', '700', '800', '900',
  )] },
  { key: 'font-stretch', label: 'Font Stretch', options: [NOT_SET, ...keywordOptions(
    'normal', 'ultra-condensed', 'extra-condensed', 'condensed', 'semi-condensed',
    'semi-expanded', 'expanded', 'extra-expanded', 'ultra-expanded',
  )] },
  { key: 'font-size', label: 'Font Size', type: 'vh-number' },
  { key: 'line-height', label: 'Line Height', options: [NOT_SET, ...keywordOptions('normal')] },
  { key: 'font-style', label: 'Font Style', options: [NOT_SET, ...keywordOptions('normal', 'italic', 'oblique')] },
  { key: 'color', label: 'Color', type: 'color' },
  { key: 'letter-spacing', label: 'Letter Spacing', options: [NOT_SET, ...keywordOptions('normal', '0.05em', '0.1em', '0.2em', '-0.02em')] },
  { key: 'text-transform', label: 'Text Transform', options: [NOT_SET, ...keywordOptions('none', 'uppercase', 'lowercase', 'capitalize')] },
  { key: 'text-decoration', label: 'Text Decoration', options: [NOT_SET, ...keywordOptions('none', 'underline', 'overline', 'line-through')] },
  { key: 'text-shadow', label: 'Text Shadow', options: [NOT_SET, ...keywordOptions('none', '0 0.2vh 0.4vh rgba(0,0,0,0.5)', '0 0 1vh rgba(0,0,0,0.8)', '0 0 1vh rgba(255,255,255,0.8)')] },
  // Alignment: text-align always applies (block or flex); the other three
  // only take effect once `display` is switched to flex/grid — harmless
  // no-ops otherwise, so they're safe to leave "(not set)" by default.
  { key: 'text-align', label: 'Text Align', options: [NOT_SET, ...keywordOptions('left', 'center', 'right', 'justify')] },
  { key: 'display', label: 'Display (for content alignment)', options: [NOT_SET, ...keywordOptions('flex', 'grid', 'block')] },
  { key: 'justify-content', label: 'Justify Content (horizontal)', options: [NOT_SET, ...keywordOptions(
    'flex-start', 'center', 'flex-end', 'space-between', 'space-around', 'space-evenly',
  )] },
  { key: 'align-items', label: 'Align Items (vertical)', options: [NOT_SET, ...keywordOptions(
    'flex-start', 'center', 'flex-end', 'stretch', 'baseline',
  )] },
]

// --- Layout editor "Container Design" tabs ----------------------------------
// Groups shown as tabs. Font is the shared FONT_PROPERTIES list (also used by
// the Designs page); the rest are Layout-editor-only for now. Every property
// is a plain (property, value) DesignContainerStyle row rendered into
// `.dh-container-<id> { ... }`, so no backend change is needed per property.

export interface ContainerStyleGroup {
  key: string
  label: string
  icon: string
  properties: FontProperty[]
}

const px = (key: string, label: string, max = 50, min = 0): FontProperty =>
  ({ key, label, type: 'number', unit: 'vh', min, max, step: 0.1 })

export const BACKGROUND_PROPERTIES: FontProperty[] = [
  { key: 'background-color', label: 'Background Color', type: 'color' },
  { key: 'opacity', label: 'Opacity', type: 'number', unit: '', min: 0, max: 1, step: 0.05 },
  { key: 'backdrop-filter', label: 'Backdrop Filter (blur behind)', options: [NOT_SET, ...keywordOptions(
    'none', 'blur(0.5vh)', 'blur(1vh)', 'blur(2vh)', 'blur(4vh)', 'brightness(0.7)', 'grayscale(1)',
  )] },
]

export const BORDER_PROPERTIES: FontProperty[] = [
  { key: 'border-style', label: 'Border Style', options: [NOT_SET, ...keywordOptions(
    'none', 'solid', 'dashed', 'dotted', 'double', 'groove', 'ridge',
  )] },
  px('border-width', 'Border Width', 20),
  { key: 'border-color', label: 'Border Color', type: 'color' },
  px('border-radius', 'Corner Radius', 50),
  { key: 'box-shadow', label: 'Box Shadow', options: [NOT_SET, ...keywordOptions(
    'none', '0 0.3vh 0.8vh rgba(0,0,0,0.35)', '0 1vh 2vh rgba(0,0,0,0.45)', '0 0 2vh rgba(0,0,0,0.6)', 'inset 0 0 1vh rgba(0,0,0,0.5)',
  )] },
]

export const OTHER_PROPERTIES: FontProperty[] = [
  px('padding', 'Padding', 50),
  { key: 'direction', label: 'Text Direction (RTL)', options: [NOT_SET, ...keywordOptions('ltr', 'rtl')] },
  { key: 'white-space', label: 'White Space', options: [NOT_SET, ...keywordOptions('normal', 'nowrap', 'pre', 'pre-wrap', 'pre-line')] },
  { key: 'word-break', label: 'Word Break', options: [NOT_SET, ...keywordOptions('normal', 'break-all', 'keep-all', 'break-word')] },
  { key: 'overflow', label: 'Overflow', options: [NOT_SET, ...keywordOptions('visible', 'hidden', 'auto', 'scroll')] },
  { key: 'text-overflow', label: 'Text Overflow', options: [NOT_SET, ...keywordOptions('clip', 'ellipsis')] },
  { key: 'mix-blend-mode', label: 'Blend Mode', options: [NOT_SET, ...keywordOptions(
    'normal', 'multiply', 'screen', 'overlay', 'darken', 'lighten', 'difference',
  )] },
  { key: 'rotate', label: 'Rotation', type: 'number', unit: 'deg', min: -360, max: 360, step: 1 },
  { key: 'z-index', label: 'Stacking Order (z-index)', type: 'number', unit: '', min: -10, max: 100, step: 1 },
]

export const CONTAINER_STYLE_GROUPS: ContainerStyleGroup[] = [
  { key: 'font', label: 'Font', icon: 'pi-pencil', properties: FONT_PROPERTIES },
  { key: 'background', label: 'Background', icon: 'pi-image', properties: BACKGROUND_PROPERTIES },
  { key: 'border', label: 'Border', icon: 'pi-stop', properties: BORDER_PROPERTIES },
  { key: 'other', label: 'Other', icon: 'pi-ellipsis-h', properties: OTHER_PROPERTIES },
]

export const ALL_CONTAINER_STYLE_PROPERTIES: FontProperty[] = CONTAINER_STYLE_GROUPS.flatMap((g) => g.properties)

// CSS initial values that are equivalent to leaving the property unset. Only
// listed where the preset really is what a plain <div> does by default.
const SYSTEM_DEFAULTS: Record<string, string> = {
  'font-variant': 'normal', 'font-weight': 'normal', 'font-stretch': 'normal',
  'line-height': 'normal', 'font-style': 'normal', 'letter-spacing': 'normal',
  'text-transform': 'none', 'text-decoration': 'none', 'text-shadow': 'none',
  display: 'block',
  'backdrop-filter': 'none', opacity: '1',
  'border-style': 'none', 'border-radius': '0vh', 'box-shadow': 'none',
  padding: '0vh', direction: 'ltr', 'white-space': 'normal', 'word-break': 'normal',
  overflow: 'visible', 'text-overflow': 'clip', 'mix-blend-mode': 'normal', rotate: '0deg',
}
for (const p of ALL_CONTAINER_STYLE_PROPERTIES) p.systemDefault = SYSTEM_DEFAULTS[p.key]
