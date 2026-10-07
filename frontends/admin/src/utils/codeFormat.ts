/**
 * Auto-format for the Design page's HTML and CSS editors (issue #2).
 *
 * Prettier (standalone build + the plugins for the languages involved) is
 * loaded on first use, so the editors cost nothing until someone actually
 * presses "Format". A source Prettier cannot parse (an unclosed `{`, a broken
 * tag) is reported and left untouched — never half-formatted.
 */

export type FormatResult = { ok: true; code: string } | { ok: false; error: string }

const OPTIONS = {
  tabWidth: 2,
  printWidth: 100,
  // Background HTML is rendered as-is on the screen, so keep Prettier's default
  // CSS-aware whitespace handling rather than "ignore": inline elements keep
  // the spacing the browser would render.
  htmlWhitespaceSensitivity: 'css' as const,
}

async function run(source: string, parser: 'html' | 'css'): Promise<FormatResult> {
  if (!source.trim()) return { ok: true, code: source }
  try {
    const [{ format }, html, postcss, babel, estree] = await Promise.all([
      import('prettier/standalone'),
      import('prettier/plugins/html'),
      import('prettier/plugins/postcss'),
      import('prettier/plugins/babel'),
      import('prettier/plugins/estree'),
    ])
    // The html plugin formats embedded <style>/<script> with postcss/babel(+estree).
    const code = await format(source, { ...OPTIONS, parser, plugins: [html, postcss, babel, estree] })
    return { ok: true, code }
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e)
    // Prettier errors carry a code frame after the first line — keep just the message.
    return { ok: false, error: message.split('\n')[0] || 'Could not format' }
  }
}

export const formatHtml = (source: string): Promise<FormatResult> => run(source, 'html')
export const formatCss = (source: string): Promise<FormatResult> => run(source, 'css')
