import { computed, ref, watchEffect } from 'vue'
import { useAuthStore } from '../stores/auth'

const DARK_MODE_CLASS = 'dark-mode'

const media = window.matchMedia('(prefers-color-scheme: dark)')
// A plain ref, not a computed reading media.matches directly: matchMedia
// gives no reactive hook of its own, so this ref plus the 'change' listener
// below is what makes systemPrefersDark actually update over time.
const systemPrefersDark = ref(media.matches)
media.addEventListener('change', (e) => {
  systemPrefersDark.value = e.matches
})

/**
 * Resolves the effective light/dark theme from the user's stored preference
 * (defaulting to 'system') plus the OS-level media query, applies it as
 * `.dark-mode` on <html> — the selector PrimeVue's aura preset is configured
 * with (see main.ts) — and exposes a setter that persists the explicit
 * choice via the auth store.
 *
 * The `media` listener is module-level (registered once) so this composable
 * can be called from multiple components without stacking duplicate
 * listeners; per-call reactivity comes from the computed/watchEffect below.
 */
export function useTheme() {
  const authStore = useAuthStore()

  const preference = computed(() => authStore.preferences.theme ?? 'system')
  const isDark = computed(() =>
    preference.value === 'system' ? systemPrefersDark.value : preference.value === 'dark'
  )

  watchEffect(() => {
    document.documentElement.classList.toggle(DARK_MODE_CLASS, isDark.value)
  })

  const setTheme = (theme: 'light' | 'dark' | 'system') => authStore.setPreferences({ theme })

  return { preference, isDark, setTheme }
}
