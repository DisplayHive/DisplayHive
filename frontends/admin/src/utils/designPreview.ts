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
import { loadIcon } from './iconLibraries'
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

/** Strip any hardcoded width/height off the SVG root so it scales to its wrapper — mirrors icon-resolver.ts's sizeToFit. */
function sizeIconSvgToFit(svg: string): string {
  return svg.replace(
    /<svg\b([^>]*)>/i,
    (_match, attrs: string) =>
      `<svg${attrs.replace(/\s+(width|height)="[^"]*"/gi, '')} style="height:100%;width:auto;display:block;">`,
  )
}

// 'icon' fields render as a <div data-dh-icon-library data-dh-icon-name>
// placeholder (the backend can't read the icon SVGs — they ship as npm
// packages bundled into the frontends, not backend-readable files — see
// render_content_fields in application/admin/content/helper.py) that's
// normally resolved to real inline SVG client-side after DOM insertion
// (icon-resolver.ts, screen client only, via container-manager.ts). This
// preview is a srcdoc string for a sandboxed iframe with no
// allow-same-origin, so it gets an opaque origin — a <script> running inside
// it can't fetch same-server static files (no CORS headers on them, and the
// opaque origin makes the fetch cross-origin) the way the real screen client
// can. So placeholders are resolved here instead, in the real (non-sandboxed)
// admin page, before the srcdoc string is ever assembled.
export async function resolveIconPlaceholders(html: string): Promise<string> {
  if (!html.includes('data-dh-icon-library')) return html
  const doc = new DOMParser().parseFromString(`<div>${html}</div>`, 'text/html')
  const els = Array.from(doc.querySelectorAll<HTMLElement>('[data-dh-icon-library]'))
  await Promise.all(
    els.map(async (el) => {
      const library = el.getAttribute('data-dh-icon-library')
      const name = el.getAttribute('data-dh-icon-name')
      if (!library || !name) return
      const svg = await loadIcon(library, name)
      if (svg) el.innerHTML = sizeIconSvgToFit(svg)
    }),
  )
  return doc.body.firstElementChild?.innerHTML ?? html
}

// [data-dh-clock] and [data-dh-countdown] placeholders are normally ticked
// by the real screen client (clock.ts/countdown.ts) after DOM insertion —
// this sandboxed srcdoc has no access to that bundle, so it gets its own
// minimal, self-contained tick script (no fetch/DOM-outside-iframe access
// needed, so `sandbox="allow-scripts"` alone is enough to run it). Mirrors
// the token formats of both modules; kept in sync by hand since it can't
// import them into a plain string template.
const TICK_SCRIPT = `<script>
(function () {
  function fmtClock(d, fmt, tz) {
    try {
      var p = new Intl.DateTimeFormat('en-US', { timeZone: tz || 'UTC', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, weekday: 'long' }).formatToParts(d);
      var p12 = new Intl.DateTimeFormat('en-US', { timeZone: tz || 'UTC', hour: 'numeric', hour12: true }).formatToParts(d);
      var wdShort = new Intl.DateTimeFormat('en-US', { timeZone: tz || 'UTC', weekday: 'short' }).format(d);
      var get = function (t) { var m = p.find(function (x) { return x.type === t; }); return m ? m.value : ''; };
      var get12 = function (t) { var m = p12.find(function (x) { return x.type === t; }); return m ? m.value : ''; };
      var year = get('year'), month = get('month'), day = get('day');
      var h24 = parseInt(get('hour'), 10) % 24, minute = get('minute'), second = get('second');
      var wdFull = get('weekday'), h12raw = parseInt(get12('hour'), 10), h12 = h12raw === 0 ? 12 : h12raw;
      var period = (get12('dayPeriod') || (h24 < 12 ? 'AM' : 'PM')).toUpperCase();
      return fmt.replace(/YYYY|YY|dddd|ddd|MM|M|DD|D|HH|H|hh|h|mm|m|ss|s|A|a/g, function (t) {
        switch (t) {
          case 'YYYY': return year; case 'YY': return year.slice(-2);
          case 'dddd': return wdFull; case 'ddd': return wdShort;
          case 'MM': return month; case 'M': return String(parseInt(month, 10));
          case 'DD': return day; case 'D': return String(parseInt(day, 10));
          case 'HH': return String(h24).padStart(2, '0'); case 'H': return String(h24);
          case 'hh': return String(h12).padStart(2, '0'); case 'h': return String(h12);
          case 'mm': return minute; case 'm': return String(parseInt(minute, 10));
          case 'ss': return second; case 's': return String(parseInt(second, 10));
          case 'A': return period; case 'a': return period.toLowerCase();
          default: return t;
        }
      });
    } catch (e) { return fmt; }
  }
  function fmtCountdown(remainingMs, fmt) {
    var totalSeconds = Math.max(0, Math.floor(remainingMs / 1000));
    var days = Math.floor(totalSeconds / 86400);
    var hours = Math.floor((totalSeconds % 86400) / 3600);
    var minutes = Math.floor((totalSeconds % 3600) / 60);
    var seconds = totalSeconds % 60;
    return fmt.replace(/DD|D|HH|H|mm|m|ss|s/g, function (t) {
      switch (t) {
        case 'DD': return String(days).padStart(2, '0'); case 'D': return String(days);
        case 'HH': return String(hours).padStart(2, '0'); case 'H': return String(hours);
        case 'mm': return String(minutes).padStart(2, '0'); case 'm': return String(minutes);
        case 'ss': return String(seconds).padStart(2, '0'); case 's': return String(seconds);
        default: return t;
      }
    });
  }
  function tick() {
    var now = new Date();
    document.querySelectorAll('[data-dh-clock]').forEach(function (el) {
      el.textContent = fmtClock(now, el.getAttribute('data-dh-clock') || 'HH:mm:ss', el.getAttribute('data-dh-timezone') || 'UTC');
    });
    document.querySelectorAll('[data-dh-countdown]').forEach(function (el) {
      var target = new Date(el.getAttribute('data-dh-countdown-target') || '').getTime();
      if (isNaN(target)) { el.textContent = ''; return; }
      var finishedText = el.getAttribute('data-dh-countdown-finished') || '';
      var remainingMs = target - now.getTime();
      el.textContent = (remainingMs <= 0 && finishedText) ? finishedText : fmtCountdown(remainingMs, el.getAttribute('data-dh-countdown-format') || 'DD:HH:mm:ss');
    });
  }
  tick();
  setInterval(tick, 1000);
})();
<\/script>`

export async function buildDesignPreviewSrcdoc(
  design: DesignPreviewPayload | null | undefined,
  containers: Record<string, PreviewContainer> | null | undefined,
): Promise<string> {
  if (!design) return ''
  const containersHtml = (
    await Promise.all(
      Object.entries(containers || {}).map(async ([id, c]) => {
        const html = await resolveIconPlaceholders(c.html)
        return `<div class="dh-container dh-container-${id}" style="position:absolute;top:${c.top}vh;left:${c.left}vw;width:${c.width}vw;height:${c.height}vh;">${html}</div>`
      }),
    )
  ).join('')
  return (
    `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;width:100%;height:100%;overflow:hidden;position:relative;}${design.css}</style></head>` +
    `<body>${buildEffectFragment(design.background_effect)}<div style="position:relative;">${design.html}</div>${containersHtml}${TICK_SCRIPT}</body></html>`
  )
}
