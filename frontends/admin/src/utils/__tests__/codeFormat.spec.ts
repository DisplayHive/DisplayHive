import { describe, expect, it } from 'vitest'
import { formatCss, formatHtml } from '../codeFormat'

describe('formatCss', () => {
  it('formats messy CSS', async () => {
    const r = await formatCss('.a{color:red;margin:0 auto}\n\n\n.b>.c{padding:1vh}')
    expect(r).toEqual({
      ok: true,
      code: '.a {\n  color: red;\n  margin: 0 auto;\n}\n\n.b > .c {\n  padding: 1vh;\n}\n',
    })
  })

  it('reports invalid CSS instead of returning half-formatted code', async () => {
    const r = await formatCss('.a{color:red')
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toMatch(/unclosed|brace|block/i)
  })

  it('leaves empty input alone', async () => {
    expect(await formatCss('  \n')).toEqual({ ok: true, code: '  \n' })
  })
})

describe('formatHtml', () => {
  it('indents nested markup and formats embedded <style>', async () => {
    const r = await formatHtml('<div><p>Hi</p><style>.a{color:red}</style></div>')
    expect(r.ok).toBe(true)
    if (r.ok) {
      expect(r.code).toContain('<div>\n  <p>Hi</p>')
      expect(r.code).toContain('.a {\n      color: red;\n    }')
    }
  })

  it('formats embedded <script>', async () => {
    const r = await formatHtml('<script>const a=1;function f(){return a}</script>')
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.code).toContain('const a = 1;')
  })

  it('does not change the text content or add whitespace inside inline elements', async () => {
    const r = await formatHtml('<p>Hello <b>big</b>, <i>wide</i> world</p>')
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.code.replace(/\s+/g, ' ').trim()).toBe('<p>Hello <b>big</b>, <i>wide</i> world</p>')
  })
})
