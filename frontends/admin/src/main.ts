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
  // load selected theme from localStorage (fallback to 'aura')
  const selected =
    typeof window !== 'undefined' && localStorage.getItem('primevue-theme')
      ? (localStorage.getItem('primevue-theme') as string)
      : 'aura'

  let preset: any

  // Use a static map of imports so Vite/Rollup can analyze and include
  // the theme modules in the build. This avoids relying on fully dynamic
  // import specifiers which Vite warns about and may fail to bundle.
  const themeMap: Record<string, () => Promise<any>> = {
    aura: () => import('@primeuix/themes/aura'),
    lara: () => import('@primeuix/themes/lara'),
    material: () => import('@primeuix/themes/material'),
    nora: () => import('@primeuix/themes/nora'),
  }

  try {
    const loader = themeMap[selected] || themeMap['aura']!
    const mod = await loader()
    preset = mod.default || mod
  } catch (err) {
    console.warn('[main] failed to load theme', selected, err)
    const mod = await import('@primeuix/themes/aura')
    preset = mod.default || mod
  }

  // If Quill is available as a module or on window, ensure it has a
  // `getSemanticHTML` method. PrimeVue Editor expects `quill.getSemanticHTML()`
  // but some Quill builds may not provide it; add a safe fallback to avoid
  // runtime errors during Editor initialization.
  try {
    // Try to import the module (will be cached for later dynamic imports).
    const quillModule = await (async () => {
      try {
        return await import('quill')
      } catch (e) {
        return null
      }
    })()

    const QuillCtor = quillModule
      ? quillModule.default || quillModule
      : typeof window !== 'undefined'
        ? (window as any).Quill
        : null

    if (QuillCtor && QuillCtor.prototype && !QuillCtor.prototype.getSemanticHTML) {
      QuillCtor.prototype.getSemanticHTML = function () {
        // fall back to the editor root HTML when semantic API is missing
        return (this.root && this.root.innerHTML) || ''
      }
      // ensure window.Quill is set so PrimeVue path that reads window.Quill sees it
      if (typeof window !== 'undefined' && !(window as any).Quill) {
        ;(window as any).Quill = QuillCtor
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
  app.component('Select', Select)
  app.component('Menubar', Menubar)
  app.component('Toast', Toast)
  app.component('ConfirmDialog', ConfirmDialog)
  app.directive('ripple', Ripple)
  app.directive('tooltip', Tooltip)

  app.mount('#app')
}

bootstrap()
