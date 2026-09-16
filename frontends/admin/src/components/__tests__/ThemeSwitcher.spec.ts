import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ThemeSwitcher from '../ThemeSwitcher.vue'

describe('ThemeSwitcher', () => {
  it('applies selected theme and calls reload', async () => {
    // stub Select so we can emit events
    const SelectStub = {
      name: 'Select',
      props: ['options', 'modelValue'],
      template: '<div data-test="select"></div>',
    }

    // mock location.reload
    const reload = vi.fn()
    // @ts-ignore
    global.window.location = { ...global.window.location, reload }

    const wrapper = mount(ThemeSwitcher, {
      global: {
        stubs: { Select: SelectStub },
      },
    })

    const select = wrapper.findComponent(SelectStub as any)
    // simulate selecting a new theme and triggering change
    await select.vm.$emit('update:modelValue', 'lara')
    await select.vm.$emit('change')

    expect(localStorage.getItem('primevue-theme')).toBe('lara')
    expect(reload).toHaveBeenCalled()
  })
})
