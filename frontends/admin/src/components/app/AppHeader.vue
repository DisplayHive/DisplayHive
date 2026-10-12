<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useAuthStore } from '../stores/auth'
import { useSettingsStore } from '../stores/settings'
import { useRightsStore } from '../stores/rights'
import { useTheme } from '../composables/useTheme'
import { useAdminNavigation } from '../composables/useAdminNavigation'
import { useCommandPalette } from '../composables/useCommandPalette'
import Menubar from 'primevue/menubar'
import Button from 'primevue/button'
import Popover from 'primevue/popover'

// The top bar: logo, connection state, Demo Mode / Tour badges, the main menu, the signed-in
// person with theme switch and logout. Styles: assets/shell/header.css.
// Use static public logo (frontends/admin/public/logo_wh.png)
const Logo = '/admin/logo_wh.png'

const router = useRouter()
const route = useRoute()
const { isConnected } = useSocket()
const authStore = useAuthStore()
const settingsStore = useSettingsStore()
const rightsStore = useRightsStore()
const { preference: themePreference, isDark, setTheme } = useTheme()
const { menuItems } = useAdminNavigation()
const palette = useCommandPalette()
const shortcutLabel = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘K' : 'Ctrl K'

const themePopover = ref()
const toggleThemePopover = (event: Event) => themePopover.value?.toggle(event)
const THEME_OPTIONS = [
  { value: 'light' as const, label: 'Light', icon: 'pi pi-sun' },
  { value: 'dark' as const, label: 'Dark', icon: 'pi pi-moon' },
  { value: 'system' as const, label: 'System', icon: 'pi pi-desktop' },
]
const selectTheme = async (value: 'light' | 'dark' | 'system') => {
  themePopover.value?.hide()
  const error = await setTheme(value)
  if (error) console.error('Failed to save theme preference:', error)
}
</script>

<template>
  <header class="app-header">
    <div class="header-brand">
      <router-link to="/"><img :src="Logo" alt="DisplayHive" class="header-logo" /></router-link>
      <span
        class="connection-status"
        :class="{ connected: isConnected, disconnected: !isConnected }"
      >
        <i :class="isConnected ? 'pi pi-wifi' : 'pi pi-exclamation-triangle'"></i>
        {{ isConnected ? 'Connected' : 'Disconnected' }}
      </span>
      <span
        v-if="!settingsStore.hideDemoMode && rightsStore.can('importexport.page')"
        class="demo-mode-badge"
        :class="{ active: route.name === 'demo' }"
        data-testid="demo-mode-badge"
        @click="router.push('/demo')"
      >
        <i class="pi pi-sparkles"></i>
        Demo Mode
      </span>
      <span
        v-if="!(settingsStore.hideUserTours && settingsStore.hideAdminTours) && rightsStore.can('tour.page')"
        class="demo-mode-badge"
        :class="{ active: route.name === 'tour' }"
        data-testid="tour-badge"
        @click="router.push('/tour')"
      >
        <i class="pi pi-compass"></i>
        Tour
      </span>
    </div>
    <button
      type="button"
      class="palette-trigger"
      data-testid="palette-button"
      aria-label="Search (Ctrl+K)"
      v-tooltip.bottom="'Search (Ctrl+K)'"
      @click="palette.open()"
    >
      <i class="pi pi-search"></i>
      <span class="palette-trigger-label">Search …</span>
      <kbd class="palette-trigger-key">{{ shortcutLabel }}</kbd>
    </button>
    <div class="header-controls">
      <Menubar
        :model="menuItems"
        class="app-menubar"
        :class="{ 'app-menubar--disabled': !isConnected }"
        :aria-disabled="!isConnected"
        breakpoint="600px"
      />
      <span class="current-user" data-testid="current-username">
        <i class="pi pi-user"></i>
        {{ authStore.username }}
      </span>
      <Button
        :icon="isDark ? 'pi pi-moon' : 'pi pi-sun'"
        text
        size="small"
        class="theme-toggle-button"
        data-testid="theme-toggle-button"
        aria-label="Change theme"
        v-tooltip.bottom="'Change theme'"
        @click="toggleThemePopover"
      />
      <Popover ref="themePopover">
        <div class="theme-menu">
          <button
            v-for="option in THEME_OPTIONS"
            :key="option.value"
            type="button"
            class="theme-menu-item"
            :class="{ active: themePreference === option.value }"
            :data-testid="`theme-option-${option.value}`"
            @click="selectTheme(option.value)"
          >
            <i :class="option.icon"></i>
            {{ option.label }}
          </button>
        </div>
      </Popover>
      <Button
        icon="pi pi-sign-out"
        text
        size="small"
        class="logout-button"
        data-testid="logout-button"
        :aria-label="authStore.isImpersonating ? 'Stop impersonating' : 'Logout'"
        v-tooltip.bottom="authStore.isImpersonating ? 'Stop impersonating' : 'Logout'"
        @click="authStore.isImpersonating ? authStore.stopImpersonation() : authStore.logout()"
      />
    </div>
  </header>
</template>
