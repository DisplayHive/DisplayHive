import './assets/main.css'
import './assets/views.css'
import './assets/field-editors.css'

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
