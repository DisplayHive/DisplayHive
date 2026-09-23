import './assets/main.css'
import './assets/views.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

// PrimeVue 4
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
// PrimeVue components (registered globally)
import Select from 'primevue/select'
import Menubar from 'primevue/menubar'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import Ripple from 'primevue/ripple'
import Tooltip from 'primevue/tooltip'

// PrimeIcons
import 'primeicons/primeicons.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

async function bootstrap() {
  // Theme is fixed to 'aura' (no user-facing switcher wired into the app).
  const mod = await import('@primeuix/themes/aura')
  const preset = mod.default || mod

  // If Quill is available as a module or on window, ensure it has a
  // `getSemanticHTML` method. PrimeVue Editor expects `quill.getSemanticHTML()`
  // but some Quill builds may not provide it; add a safe fallback to avoid
  // runtime errors during Editor initialization.
  //
  // `quill` (v1.x here) ships no types and no @types/quill is installed, so
  // its shape is genuinely unknown to TS — this minimal interface covers
  // only what's actually touched below.
  interface QuillCtorType {
    prototype: { getSemanticHTML?: (this: { root?: { innerHTML?: string } }) => string }
  }

  try {
    // Try to import the module (will be cached for later dynamic imports).
    const quillModule: unknown = await (async () => {
      try {
        return await import('quill')
      } catch {
        return null
      }
    })()

    const windowWithQuill = window as typeof window & { Quill?: QuillCtorType }
    const QuillCtor: QuillCtorType | null = quillModule
      ? ((quillModule as { default?: QuillCtorType }).default ?? (quillModule as QuillCtorType))
      : typeof window !== 'undefined'
        ? (windowWithQuill.Quill ?? null)
        : null

    if (QuillCtor && QuillCtor.prototype && !QuillCtor.prototype.getSemanticHTML) {
      QuillCtor.prototype.getSemanticHTML = function () {
        // fall back to the editor root HTML when semantic API is missing
        return (this.root && this.root.innerHTML) || ''
      }
      // ensure window.Quill is set so PrimeVue path that reads window.Quill sees it
      if (typeof window !== 'undefined' && !windowWithQuill.Quill) {
        windowWithQuill.Quill = QuillCtor
      }
    }
  } catch (e) {
    console.warn('[main] could not preload/patch quill (ok if not installed)', e)
  }

  app.use(PrimeVue, {
    theme: {
      preset,
      options: {
        darkModeSelector: '.dark-mode',
      },
    },
  })

  app.use(ToastService)
  app.use(ConfirmationService)

  // register commonly used components globally so single-file components
  // can use them without local registration
  // eslint-disable-next-line vue/multi-word-component-names, vue/no-reserved-component-names -- PrimeVue's own component names, used as such in every template that references them
  app.component('Select', Select)
  // eslint-disable-next-line vue/multi-word-component-names
  app.component('Menubar', Menubar)
  // eslint-disable-next-line vue/multi-word-component-names
  app.component('Toast', Toast)
  app.component('ConfirmDialog', ConfirmDialog)
  app.directive('ripple', Ripple)
  app.directive('tooltip', Tooltip)

  app.mount('#app')
}

bootstrap()
