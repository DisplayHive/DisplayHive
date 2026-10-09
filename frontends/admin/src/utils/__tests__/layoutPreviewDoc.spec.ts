import { describe, expect, it, vi } from 'vitest'

vi.mock('beautiful-backgrounds?raw', () => ({ default: 'console.log("</script>")' }))

import { BACKDROP_OVERRIDE_CSS, buildPreviewSrcdoc, effectFragment, previewContainerHtml } from '../layoutPreviewDoc'

const preview = { name: 'D', html: '<p>hi</p>', css: 'p{color:red}', background_effect: null }

describe('layout preview document', () => {
  it('layers the Design CSS, the staged CSS and the overrides in that order', () => {
    const doc = buildPreviewSrcdoc({ preview, effectHtml: '', stagedCss: '.a{x:y}', backdropOverride: BACKDROP_OVERRIDE_CSS, containersHtml: '<i></i>' })
    expect(doc.indexOf('p{color:red}')).toBeLessThan(doc.indexOf('.a{x:y}'))
    expect(doc.indexOf('.a{x:y}')).toBeLessThan(doc.indexOf('background-color:transparent'))
    expect(doc).toContain('<div style="position:relative;"><p>hi</p></div><i></i>')
  })

  it('positions a container preview in viewport units', () => {
    expect(previewContainerHtml(3, { top: 1, left: 2, width: 3, height: 4 }, 'X'))
      .toBe('<div class="dh-container dh-container-3" style="position:absolute;top:1vh;left:2vw;width:3vw;height:4vh;">X</div>')
  })

  it('renders no effect when there is none or it is switched off', () => {
    expect(effectFragment(preview, false)).toBe('')
    expect(effectFragment({ ...preview, background_effect: { name: 'nope', settings: {} } }, false)).toBe('')
    expect(effectFragment({ ...preview, background_effect: { name: 'nope', settings: {} } }, true)).toBe('')
  })
})
