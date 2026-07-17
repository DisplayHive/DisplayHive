<script setup lang="ts">
import { onMounted, computed, ref, watch } from 'vue'

const gitCommit = ref(__GIT_COMMIT__)
import { RouterView, useRouter, useRoute } from 'vue-router'
import { useSocket } from './composables/useSocket'
import { useAuthStore } from './stores/auth'
import { useSettingsStore } from './stores/settings'
import { useRightsStore } from './stores/rights'
import LoginView from './views/LoginView.vue'

// PrimeVue components
import Menubar from 'primevue/menubar'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import Button from 'primevue/button'
// use static public logo (frontends/admin/public/logo_wh.png)
const Logo = '/admin/logo_wh.png'

const router = useRouter()
const route = useRoute()
const { connect, isConnected, reconnectFailed, on } = useSocket()
const authStore = useAuthStore()
const settingsStore = useSettingsStore()
const rightsStore = useRightsStore()

on('connect_error', (err: unknown) => {
  const message = (err as { message?: string } | null)?.message
  if (message === 'invalid_token') {
    authStore.logout()
  }
})

// Socket.IO gives up retrying after its configured reconnection attempts are
// exhausted and never tries again on its own. Without this, a prolonged
// outage (or being logged out server-side while offline) would leave the
// user stuck on the greyed-out "Disconnected" overlay indefinitely. Drop
// back to the login screen instead so they have a way forward.
watch(reconnectFailed, (failed) => {
  if (failed) {
    authStore.logout()
  }
})

type SecurityStatus = {
  secret_key_is_default?: boolean
  cors_wildcard?: boolean
  sqlite_in_use?: boolean
  debug_enabled?: boolean
}

const securityStatus = ref<SecurityStatus>({})

on('displayhive:system:stc:security_status', (data: SecurityStatus) => {
  securityStatus.value = data || {}
})

// Insecure defaults (SECRET_KEY, CORS, SQLite, debugger) are the norm in
// local dev and would otherwise show on every load — only surface these
// banners in a built/production bundle (import.meta.env.DEV is false there).
const securityWarnings = computed(() => {
  const warnings: string[] = []
  if (import.meta.env.DEV) return warnings
  if (securityStatus.value.secret_key_is_default) {
    warnings.push(
      'SECRET_KEY is using the insecure default value. Set the SECRET_KEY environment variable before deploying to production.',
    )
  }
  if (securityStatus.value.cors_wildcard) {
    warnings.push(
      'CORS_ALLOWED_ORIGINS is unset and defaulting to "*" (any origin allowed). Set it to your allowed origins before deploying to production.',
    )
  }
  if (securityStatus.value.sqlite_in_use) {
    warnings.push(
      'DATABASE_URL is unset — the server is running on a local SQLite file. Set DATABASE_URL to a PostgreSQL connection string before deploying to production.',
    )
  }
  if (securityStatus.value.debug_enabled) {
    warnings.push(
      'The Werkzeug debugger is enabled (FLASK_DEBUG). This allows arbitrary code execution if exposed to the network — disable it (FLASK_DEBUG=0) before deploying to production.',
    )
  }
  return warnings
})

const hasEverConnected = ref(false)
let disconnectTimer: ReturnType<typeof setTimeout> | null = null
let shouldReloadOnReconnect = false

watch(isConnected, (connected) => {
  if (connected) {
    if (disconnectTimer !== null) {
      clearTimeout(disconnectTimer)
      disconnectTimer = null
    }
    if (shouldReloadOnReconnect) {
      shouldReloadOnReconnect = false
      window.location.reload()
    }
    hasEverConnected.value = true
    settingsStore.fetchSettings()
    rightsStore.fetchMyRights()
  } else if (hasEverConnected.value) {
    // Only reload on reconnect if the disconnect lasts longer than the grace
    // period — brief polling hiccups (~1 s) must not trigger a page reload.
    disconnectTimer = setTimeout(() => {
      disconnectTimer = null
      shouldReloadOnReconnect = true
    }, 3_000)
  }
})

// Connect (or reset reload tracking) whenever auth state flips. Driven off
// the store directly rather than a `login-success` event from LoginView:
// setSession() flips `isAuthenticated` synchronously, which Vue's reactivity
// flush picks up and unmounts LoginView *before* the awaited login() call in
// LoginView resumes and emits — so a child-emitted event fires after LoginView
// is already gone and is silently dropped. Watching the store here has no
// such race.
watch(
  () => authStore.isAuthenticated,
  (authenticated) => {
    if (authenticated) {
      connect()
    } else {
      // Reset the "reload on reconnect" tracking on logout — an intentional
      // disconnect from logging out is not the kind of unexpected drop this
      // mechanism exists to recover from, so it must not trigger a reload the
      // next time the user connects (e.g. right after logging back in).
      hasEverConnected.value = false
      shouldReloadOnReconnect = false
      rightsStore.reset()
      if (disconnectTimer !== null) {
        clearTimeout(disconnectTimer)
        disconnectTimer = null
      }
    }
  },
)

watch(
  () => [settingsStore.hideDemoMode, route.name] as const,
  ([hidden, name]) => {
    if (hidden && name === 'demo') {
      router.replace('/')
    }
  },
)

onMounted(async () => {
  await authStore.restore()
  if (authStore.isAuthenticated) {
    connect()
  }
})

const contentMenuItems = computed(() => [
  ...(rightsStore.can('content.page')
    ? [
        {
          label: 'Content',
          icon: 'pi pi-box',
          command: () => router.push('/content'),
        },
      ]
    : []),
  ...(rightsStore.can('screens.page')
    ? [
        {
          label: 'Screens',
          icon: 'pi pi-window-maximize',
          command: () => router.push('/screens'),
        },
      ]
    : []),
  ...(rightsStore.can('screengroups.page')
    ? [
        {
          label: 'Screen Groups',
          icon: 'pi pi-clone',
          command: () => router.push('/screengroups'),
        },
      ]
    : []),
  ...(rightsStore.can('media.page')
    ? [
        {
          label: 'Media',
          icon: 'pi pi-images',
          command: () => router.push('/media'),
        },
      ]
    : []),
])

const adminMenuItems = computed(() => [
  ...(rightsStore.can('device.page')
    ? [
        {
          label: 'Devices',
          icon: 'pi pi-desktop',
          command: () => router.push('/devices'),
        },
      ]
    : []),
  ...(rightsStore.can('screens.page') && rightsStore.can('screengroups.page')
    ? [
        {
          label: 'Matrix',
          icon: 'pi pi-th-large',
          command: () => router.push('/matrix'),
        },
      ]
    : []),
  ...(rightsStore.can('contenttypes.page')
    ? [
        {
          label: 'Content Types',
          icon: 'pi pi-file',
          command: () => router.push('/contenttypes'),
        },
      ]
    : []),
  ...(rightsStore.can('templates.page')
    ? [
        {
          label: 'Templates',
          icon: 'pi pi-palette',
          command: () => router.push('/templates'),
        },
      ]
    : []),
  ...(rightsStore.can('magictags.page') || rightsStore.can('magictagvaluelists.page')
    ? [
        {
          label: 'Magic Tags',
          icon: 'pi pi-tags',
          command: () => router.push('/magictags'),
        },
      ]
    : []),
  ...(rightsStore.can('settings.page')
    ? [
        {
          label: 'Settings',
          icon: 'pi pi-cog',
          command: () => router.push('/settings'),
        },
      ]
    : []),
  ...(rightsStore.can('alerting.page')
    ? [
        {
          label: 'Alerting',
          icon: 'pi pi-bell',
          command: () => router.push('/alerting'),
        },
      ]
    : []),
  ...(rightsStore.can('logger.page')
    ? [
        {
          label: 'Logger',
          icon: 'pi pi-list',
          command: () => router.push('/logger'),
        },
      ]
    : []),
  ...(rightsStore.can('importexport.page')
    ? [
        {
          label: 'Im-/Export',
          icon: 'pi pi-database',
          command: () => router.push('/importexport'),
        },
      ]
    : []),
  ...(rightsStore.can('pretalx.page')
    ? [
        {
          label: 'Pretalx',
          icon: 'pi pi-calendar',
          command: () => router.push('/pretalx'),
        },
      ]
    : []),
  ...(rightsStore.can('users.page') || rightsStore.can('rights.page')
    ? [
        {
          label: 'Users & Rights',
          icon: 'pi pi-users',
          command: () => router.push('/users'),
        },
      ]
    : []),
])

const menuItems = computed(() => [
  {
    label: 'Dashboard',
    icon: 'pi pi-home',
    command: () => router.push('/'),
  },
  ...(!settingsStore.hideDemoMode && rightsStore.can('importexport.page')
    ? [
        {
          label: 'Demo Mode',
          icon: 'pi pi-sparkles',
          command: () => router.push('/demo'),
        },
      ]
    : []),
  ...(contentMenuItems.value.length
    ? [
        {
          label: 'Content',
          icon: 'pi pi-folder',
          items: contentMenuItems.value,
        },
      ]
    : []),
  ...(adminMenuItems.value.length
    ? [
        {
          label: 'Admin',
          icon: 'pi pi-cog',
          items: adminMenuItems.value,
        },
      ]
    : []),
])

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    home: 'Dashboard',
    demo: 'Demo Mode',
    devices: 'Devices',
    screens: 'Screens',
    screengroups: 'Screen Groups',
    content: 'Content',
    contenttypes: 'Content Types',
    templates: 'Templates',
    magictags: 'Magic Tags',
    settings: 'Settings',
    logger: 'Logger',
    media: 'Media',
    matrix: 'Matrix',
    importexport: 'Im-/Export',
    alerting: 'Alerting',
    pretalx: 'Pretalx',
    users: 'Users & Rights',
  }
  return titles[route.name as string] || 'DisplayHive Admin'
})
</script>

<template>
  <div class="app-container">
    <Toast position="bottom-right" />
    <ConfirmDialog />

    <!-- Brief validation of a stored token on boot; avoids flashing the login form. -->
    <template v-if="authStore.restoring"></template>

    <LoginView v-else-if="!authStore.isAuthenticated" />

    <template v-else>
      <div v-if="authStore.isImpersonating" class="impersonation-banner" data-testid="impersonation-banner">
        <i class="pi pi-user-edit"></i>
        <span>
          You are impersonating <strong>{{ authStore.username }}</strong>
          (originally logged in as <strong>{{ authStore.originalUsername }}</strong>).
        </span>
        <Button
          label="Stop Impersonating"
          icon="pi pi-sign-out"
          size="small"
          severity="warn"
          data-testid="stop-impersonation-button"
          @click="authStore.stopImpersonation()"
        />
      </div>

      <div v-if="securityWarnings.length" class="security-warnings">
        <div
          v-for="(warning, i) in securityWarnings"
          :key="i"
          class="security-warning"
          data-testid="security-warning"
        >
          <i class="pi pi-exclamation-triangle"></i>
          {{ warning }}
        </div>
      </div>

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
        </div>
        <div class="header-controls">
          <Menubar :model="menuItems" class="app-menubar" breakpoint="600px" />
          <span class="current-user" data-testid="current-username">
            <i class="pi pi-user"></i>
            {{ authStore.username }}
          </span>
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

      <main class="app-main p-fluid">
        <div v-if="!isConnected" class="disconnect-overlay" data-testid="disconnect-overlay">
          <div class="disconnect-message">
            <i class="pi pi-exclamation-circle disconnect-icon"></i>
            <span>No connection to Server</span>
          </div>
        </div>
        <div v-if="pageTitle" class="page-header">
          <h1>{{ pageTitle }}</h1>
        </div>
        <RouterView />
      </main>

      <div class="git-commit-badge">Commit: {{ gitCommit }}</div>
    </template>
  </div>
</template>

<style>
:root {
  --header-height: 60px;
  --page-header-height: 50px;
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family:
    -apple-system,
    BlinkMacSystemFont,
    'Segoe UI',
    Roboto,
    'Helvetica Neue',
    Arial,
    sans-serif;
  background-color: #f8f9fa;
  overflow-x: hidden;
}

.app-container {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.security-warnings {
  position: sticky;
  top: 0;
  z-index: 1001;
  display: flex;
  flex-direction: column;
}

.security-warning {
  background: #b91c1c;
  color: #fff;
  padding: 0.5rem 1rem;
  text-align: center;
  font-size: 0.85rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.security-warning + .security-warning {
  border-top: 1px solid rgba(255, 255, 255, 0.25);
}

.impersonation-banner {
  position: sticky;
  top: 0;
  z-index: 1002;
  background: #facc15;
  color: #1f2937;
  padding: 0.5rem 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  font-size: 0.85rem;
  font-weight: 600;
  flex-wrap: wrap;
}

.app-header {
  background: #0b0b0b;
  color: #fff;
  padding: 0.75rem 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  position: sticky;
  top: 0;
  z-index: 1000;
}

.header-brand {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  /* allow the brand to shrink on small widths to avoid pushing controls */
  flex: 1 1 auto;
  min-width: 0;
}

.brand-text {
  font-size: 1.25rem;
  font-weight: 600;
}

.header-logo {
  height: 70px;
  width: auto;
  display: inline-block;
  object-fit: contain;
  margin-right: 0.75rem;
}

.connection-status {
  font-size: 0.75rem;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  margin-left: 1rem;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.connection-status.connected {
  background-color: rgba(76, 175, 80, 0.3);
  color: #a5d6a7;
}

.connection-status.disconnected {
  background-color: rgba(244, 67, 54, 0.3);
  color: #ef9a9a;
}

.app-menubar {
  background: transparent !important;
  border: none !important;
}

.header-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  /* allow controls to wrap on narrow screens to prevent overlap */
  flex-wrap: wrap;
}

.current-user {
  font-size: 1rem;
  color: white;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
}

.current-user i {
  /* Match the muted grey used by the menubar icons (see .p-menubar-item-icon). */
  color: #94a3b8;
}

.logout-button.p-button {
  color: white;
  padding: 0.5rem 0.75rem;
}

.logout-button.p-button:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}

.logout-button.p-button .p-button-icon {
  color: #94a3b8;
}

.app-menubar .p-menubar-root-list > .p-menubar-item > .p-menubar-item-content {
  background: transparent !important;
}

.app-menubar .p-menubar-root-list > .p-menubar-item > .p-menubar-item-content .p-menubar-item-link {
  color: white !important;
}

/* ensure submenu/menuitem links use readable default text color */
.app-menubar .p-submenu-list .p-menuitem-link,
.app-menubar .p-menubar .p-menuitem-link {
  color: inherit !important;
}

.app-menubar .p-menubar-item-link:hover {
  background: rgba(255, 255, 255, 0.1) !important;
}

.app-menubar .p-menubar-submenu {
  position: fixed !important;
  top: var(--header-height) !important;
}

.app-main {
  flex: 1;
  padding: 1.5rem;
  max-width: none;
  margin: 0;
  width: 100%;
  position: relative;
}

.disconnect-overlay {
  position: absolute;
  inset: 0;
  background: rgba(80, 80, 80, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 500;
  backdrop-filter: blur(2px);
}

.disconnect-message {
  background: #fff;
  border-radius: 8px;
  padding: 1.25rem 2rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.18);
  font-size: 1.05rem;
  color: #333;
  font-weight: 500;
}

.disconnect-icon {
  font-size: 1.5rem;
  color: #f59e0b;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h1 {
  font-size: 1.75rem;
  font-weight: 600;
  color: #333;
}

/* Mobile responsive styles */
@media (max-width: 768px) {
  .app-header {
    flex-direction: column;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
  }

  .header-brand {
    width: 100%;
    justify-content: space-between;
  }

  .header-logo {
    height: 50px;
    margin-right: 0.5rem;
  }

  .connection-status {
    margin-left: auto;
    font-size: 0.7rem;
  }

  .header-controls {
    width: 100%;
    justify-content: flex-start;
  }

  .app-menubar {
    width: 100%;
  }

  .app-main {
    padding: 1rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
  }

  .page-header {
    margin-bottom: 1rem;
  }

  /* Make PrimeVue DataTables scroll horizontally on mobile */
  .p-datatable-wrapper {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }

  /* Reduce button padding for better mobile touch targets */
  .p-button {
    padding: 0.5rem 0.75rem;
    font-size: 0.9rem;
  }

  /* Stack filter controls vertically on mobile */
  .filter-controls,
  .table-controls {
    flex-direction: column;
    gap: 0.5rem;
  }

  /* Reduce dialog padding on mobile */
  .p-dialog .p-dialog-content {
    padding: 1rem;
  }

  /* Make cards more compact on mobile */
  .p-card .p-card-body {
    padding: 1rem;
  }

  .p-card .p-card-content {
    padding: 0.5rem 0;
  }

  /* Better input field sizing on mobile */
  .p-inputtext {
    font-size: 16px; /* Prevents iOS zoom on focus */
  }

  /* Ensure modals don't exceed viewport */
  .p-dialog {
    max-width: 95vw !important;
    margin: 0.5rem;
  }
}

.git-commit-badge {
  position: fixed;
  bottom: 0.4rem;
  right: 0.6rem;
  font-size: 0.65rem;
  color: #6b7280;
  font-family: monospace;
  pointer-events: none;
  z-index: 9999;
}

/* Tablet styles */
@media (max-width: 1024px) {
  .app-main {
    padding: 1.25rem;
  }

  /* Allow DataTable columns to wrap more naturally */
  .p-datatable .p-datatable-tbody > tr > td {
    white-space: normal;
    word-wrap: break-word;
  }
}
</style>
