import { afterEach, describe, expect, it, vi } from 'vitest'
import { getIconManifest, getInstalledLibraries, loadIcon } from '../iconLibraries'

const answer = (body: unknown, ok = true) => Promise.resolve({ ok, json: () => Promise.resolve(body), text: () => Promise.resolve(String(body)) } as Response)

afterEach(() => vi.unstubAllGlobals())

describe('icon libraries (installed at /static/icons)', () => {
  it('reads the manifest afresh and survives a missing one', async () => {
    const fetchMock = vi.fn(() => answer({ lucide: ['home'] }))
    vi.stubGlobal('fetch', fetchMock)
    expect(await getIconManifest()).toEqual({ lucide: ['home'] })
    expect(fetchMock).toHaveBeenCalledWith('/static/icons/manifest.json', { cache: 'no-cache' })
    vi.stubGlobal('fetch', vi.fn(() => answer({}, false)))
    expect(await getIconManifest()).toEqual({})
    vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('offline'))))
    expect(await getIconManifest()).toEqual({})
  })

  it('knows the listed libraries by their license text and the own ones by what was entered', async () => {
    vi.stubGlobal('fetch', vi.fn(() => answer({
      mine: { label: 'My icons', license: 'CC0' },
      lucide: { label: 'x' },
    })))
    const libs = await getInstalledLibraries()
    expect(libs.map((l) => l.id)).toEqual(['lucide', 'mine'])
    expect(libs[0]!.licenseText).toContain('ISC License')
    expect(libs[1]).toMatchObject({ id: 'mine', label: 'My icons', license: 'CC0', licenseText: '' })
  })

  it('loads one icon from its library folder and answers null when it is missing', async () => {
    const fetchMock = vi.fn(() => answer('<svg/>'))
    vi.stubGlobal('fetch', fetchMock)
    expect(await loadIcon('lucide', 'arrow-up')).toBe('<svg/>')
    expect(fetchMock).toHaveBeenCalledWith('/static/icons/lucide/arrow-up.svg')
    vi.stubGlobal('fetch', vi.fn(() => answer('', false)))
    expect(await loadIcon('lucide', 'nope')).toBeNull()
  })
})
