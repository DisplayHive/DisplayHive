import { beforeEach, describe, expect, it } from 'vitest'
import { markRaw } from 'vue'
import { addFieldHandler, addPage, fieldHandlerDef, fieldHandlerOptions, pluginRegistry, removePlugin } from '../registry'
import { registerBundledPlugins } from '../testing'
import { fieldEditorFor } from '../../components/fields/registry'
import TextField from '../../components/fields/TextField.vue'

const editor = markRaw({ template: '<i />' })

describe('the plugin registry', () => {
  beforeEach(() => {
    for (const id of ['acme.demo', 'acme.other']) removePlugin(id)
  })

  it('offers None first and the active handlers A to Z', () => {
    addFieldHandler('acme.demo', { id: 'zeta', label: 'Zeta', editor })
    addFieldHandler('acme.demo', { id: 'alpha', label: 'Alpha', editor })
    const labels = fieldHandlerOptions.value.map((o) => o.label)
    expect(labels[0]).toBe('None')
    expect(labels.indexOf('Alpha')).toBeLessThan(labels.indexOf('Zeta'))
  })

  it('takes back everything a plugin added, and only that', () => {
    addFieldHandler('acme.demo', { id: 'mine', label: 'Mine', editor })
    addFieldHandler('acme.other', { id: 'theirs', label: 'Theirs', editor })
    addPage('acme.demo', { path: '/demo', name: 'demo', component: async () => ({ default: editor }), title: 'Demo', icon: '', right: 'acme.demo.use' })
    removePlugin('acme.demo')
    expect(fieldHandlerDef('mine')).toBeUndefined()
    expect(pluginRegistry.pages.has('demo')).toBe(false)
    expect(fieldHandlerDef('theirs')).toBeDefined()
  })

  it('does not offer a handler that is marked as not selectable, but still has an editor for it', () => {
    addFieldHandler('acme.demo', { id: 'hidden', label: 'Hidden', editor, selectable: false })
    expect(fieldHandlerOptions.value.map((o) => o.value)).not.toContain('hidden')
    expect(fieldEditorFor('hidden').component).toBe(editor)
  })

  it('falls back to the text editor for a handler nobody provides', () => {
    expect(fieldEditorFor('nobody').component).toBe(TextField)
  })
})

describe('the bundled plugins', () => {
  it('register the handlers the backend provides, each with an editor', () => {
    registerBundledPlugins()
    const ids = ['textklein', 'textbig', 'link', 'wysiwyg', 'numbers', 'checkbox', 'table', 'image', 'icon', 'arrows',
      'datetime_format', 'countdown', 'marquee', 'rawhtml', 'iframe', 'pretalx_table']
    for (const id of ids) expect(fieldHandlerDef(id)?.editor, id).toBeDefined()
  })

  it('translate a container default in both directions', () => {
    registerBundledPlugins()
    const countdown = fieldHandlerDef('countdown')!.container!
    const packed = JSON.stringify({ target: '2030-01-01T00:00', format: 'HH:mm', finished_text: 'Done' })
    const bag = countdown.unpack(packed)
    expect(bag).toEqual({ default: '2030-01-01T00:00', default__format: 'HH:mm', default__finished_text: 'Done' })
    expect(JSON.parse(countdown.pack(bag))).toEqual(JSON.parse(packed))

    const image = fieldHandlerDef('image')!.container!
    expect(image.unpack('/static/media/a.png')).toEqual({ default: '/static/media/a.png' })      // the old plain URL
    const random = image.unpack(JSON.stringify({ url: '', mode: 'random_tags', tags: ['a'] }))
    expect(random.default__image_tags).toEqual(['a'])
    expect(JSON.parse(image.pack(random)).mode).toBe('random_tags')

    const pretalx = fieldHandlerDef('pretalx_table')!.container!
    const table = pretalx.unpack(JSON.stringify({ url: 'https://x', linecount: 3 }))
    expect(table.default).toBe('https://x')
    expect(table.default__linecount).toBe(3)
    expect(table.default__type).toBe('list')
    expect(JSON.parse(pretalx.pack(table)).url).toBe('https://x')
  })
})
