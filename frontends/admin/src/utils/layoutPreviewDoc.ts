import type { DefaultColor } from '../types/models'
import { getEffectDefinition } from './backgroundEffects'
// `?raw` inlines the pre-built bundle's source as a string at build time.
// It has to run *inside* the preview iframe's own document (own
// customElements registry), so it can't just be imported/evaluated in this
// page's JS realm — but it also can't be loaded via `<script src="...">`:
// module scripts always fetch with CORS semantics, and the iframe is
// `sandbox="allow-scripts"` *without* `allow-same-origin` (intentionally,
// so a Design's own arbitrary HTML/CSS can't reach this page's cookies/
// storage), which gives it an opaque `Origin: null` — the static asset
// server has no matching CORS header for that, so the browser silently
// blocks the fetch. Inlining the source as literal script *content*
// sidesteps the network fetch (and CORS) entirely.
import bbScriptSource from 'beautiful-backgrounds?raw'

// A `</script` appearing verbatim inside that source (e.g. in a minified
// string literal) would prematurely close our injected <script> tag when
// the HTML parser scans for it — inserting a backslash breaks that literal
// match for the parser while remaining valid (harmless) JS if it happens to
// land inside a string/regex in the source itself.
const bbScriptSourceSafe = bbScriptSource.replace(/<\/script/gi, '<\\/script')

const SCRIPT_OPEN_TAG = '<' + 'script type="module">'
const SCRIPT_CLOSE_TAG = '<' + '/script>'

/**
 * The active Design as the Layout editor previews it — the same {name, html, css,
 * background_effect} shape/CSS-layering as what upd_content pushes to real screens (see
 * application/admin/designs/helper.py's build_design_payload).
 */
export interface DesignPreview {
  name: string
  html: string
  css: string
  background_effect: { name: string; settings: Record<string, unknown> } | null
  /** Active Design's color palette — offered as quick-pick swatches by the
   * container-default icon handler's color picker. */
  default_colors?: DefaultColor[]
}

// Attribute-value escaping for the effect's custom-element tag below — the
// settings values come from the backend (design's stored JSON), not from
// this page's own trusted template literals, so they need escaping same as
// any other data interpolated into an HTML string.
const escapeAttr = (v: string): string =>
  v.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')

// The effect canvas sits between the Backdrop (body's own background-color/
// image/gradients) and the Design's own HTML — same stacking as the real
// screen's #design-effect-background / #design-background (see
// frontends/screen/templates/index.html) — which is only achievable by
// rendering it inside the *same* document as the backdrop CSS, hence
// building it into the srcdoc rather than as a separate layer in the
// parent page (an iframe's own background-color would otherwise fully
// hide anything layered behind it from outside).
export const effectFragment = (preview: DesignPreview | null, disabled: boolean): string => {
  if (disabled) return ''
  const effect = preview?.background_effect
  if (!effect) return ''
  const def = getEffectDefinition(effect.name)
  if (!def) return ''
  const attrs = def.params
    .map((p) => {
      const value = effect.settings[p.key] ?? p.default
      const attrValue = Array.isArray(value) ? value.join(',') : String(value)
      return `${p.key}="${escapeAttr(attrValue)}"`
    })
    .join(' ')
  return (
    `<div id="design-effect-background" style="position:absolute;inset:0;overflow:hidden;">` +
    `<${def.tag} style="display:block;width:100%;height:100%;" ${attrs}></${def.tag}></div>` +
    SCRIPT_OPEN_TAG + bbScriptSourceSafe + SCRIPT_CLOSE_TAG
  )
}

/** A positioned box in the preview: the container's own fallback content at its live position. */
export const previewContainerHtml = (id: number, pos: { top: number; left: number; width: number; height: number }, html: string): string =>
  `<div class="dh-container dh-container-${id}" style="position:absolute;top:${pos.top}vh;left:${pos.left}vw;width:${pos.width}vw;height:${pos.height}vh;">${html}</div>`

/** The complete preview document. `backdropOverride` and `stagedCss` are appended after the Design's CSS. */
export const buildPreviewSrcdoc = (parts: {
  preview: DesignPreview
  effectHtml: string
  stagedCss: string
  backdropOverride: string
  containersHtml: string
}): string =>
  `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;position:relative;}${parts.preview.css}${parts.stagedCss}${parts.backdropOverride}</style></head><body>${parts.effectHtml}<div style="position:relative;">${parts.preview.html}</div>${parts.containersHtml}</body></html>`

/** Overrides the Backdrop back out of the preview (an approximation: see the editor's toggle). */
export const BACKDROP_OVERRIDE_CSS = 'body{background-color:transparent!important;background-image:none!important;}'
