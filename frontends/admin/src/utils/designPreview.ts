/**
 * Shared "render this as it would actually look on screen" iframe-srcdoc
 * builder — used by both the Content edit page's live preview
 * (ContentEditView.vue) and the Content list's row-expansion preview
 * (ContentTable.vue, fed by the backend's build_scene_containers). Each
 * container is absolutely positioned per its real Layout geometry (vh/vw)
 * and tagged with the same .dh-container/.dh-container-<id> classes the
 * real screen client adds in container-manager.ts — a Design's global/
 * per-container style CSS layers target exactly those selectors, so without
 * them here that CSS silently matches nothing.
 */
import { getEffectDefinition } from './backgroundEffects'
// `?raw` inlines the pre-built bundle's source as a string at build time —
// see LayoutCanvasEditor.vue for why this has to be literal <script> content
// rather than a normal import/evaluation inside a sandboxed srcdoc iframe.
import bbScriptSource from 'beautiful-backgrounds?raw'

const bbScriptSourceSafe = bbScriptSource.replace(/<\/script/gi, '<\\/script')

export interface DesignPreviewPayload {
  html: string
  css: string
  background_effect: { name: string; settings: Record<string, unknown> } | null
}

export interface PreviewContainer {
  top: number
  left: number
  width: number
  height: number
  html: string
}

// Attribute-value escaping for the effect's custom-element tag — the
// settings values come from the backend (a Design's stored JSON), not from
// this file's own trusted template literals, so they need escaping same as
// any other data interpolated into an HTML string.
const escapeAttr = (v: string): string =>
  v.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;')

function buildEffectFragment(effect: DesignPreviewPayload['background_effect'] | null | undefined): string {
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
    `<script type="module">${bbScriptSourceSafe}<\/script>`
  )
}

export function buildDesignPreviewSrcdoc(
  design: DesignPreviewPayload | null | undefined,
  containers: Record<string, PreviewContainer> | null | undefined,
): string {
  if (!design) return ''
  const containersHtml = Object.entries(containers || {})
    .map(
      ([id, c]) =>
        `<div class="dh-container dh-container-${id}" style="position:absolute;top:${c.top}vh;left:${c.left}vw;width:${c.width}vw;height:${c.height}vh;">${c.html}</div>`,
    )
    .join('')
  return (
    `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;position:relative;}${design.css}</style></head>` +
    `<body>${buildEffectFragment(design.background_effect)}<div style="position:relative;">${design.html}</div>${containersHtml}</body></html>`
  )
}
