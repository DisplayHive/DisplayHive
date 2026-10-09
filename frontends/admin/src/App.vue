<script setup lang="ts">
import { RouterView } from 'vue-router'
import { useSocket } from './composables/useSocket'
import { useAuthStore } from './stores/auth'
import { useSessionLifecycle } from './composables/useSessionLifecycle'
import { useSecurityStatus } from './composables/useSecurityStatus'
import LoginView from './views/LoginView.vue'
import ChangePasswordView from './views/ChangePasswordView.vue'
import AppBanners from './components/AppBanners.vue'
import AppHeader from './components/AppHeader.vue'
import PageHeader from './components/PageHeader.vue'
import CommandPalette from './components/CommandPalette.vue'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'

// The page frame. What it is made of: the session and connection handling
// (composables/useSessionLifecycle.ts), the banners, header and page header
// (components/App*.vue, PageHeader.vue), and the shell's CSS (assets/shell/).
const { isConnected } = useSocket()
const authStore = useAuthStore()
useSessionLifecycle()
const security = useSecurityStatus()
</script>

<template>
  <div class="app-container">
    <Toast position="bottom-right" />
    <ConfirmDialog />

    <!-- Brief validation of a stored token on boot; avoids flashing the login form. -->
    <template v-if="authStore.restoring"></template>

    <LoginView v-else-if="!authStore.isAuthenticated" />

    <ChangePasswordView v-else-if="authStore.mustChangePassword" />

    <template v-else>
      <AppBanners :status="security.status.value" :critical-issues="security.criticalIssues.value" :warnings="security.warnings.value" />

      <AppHeader />
      <CommandPalette />

      <main class="app-main p-fluid">
        <div v-if="!isConnected" class="disconnect-overlay" data-testid="disconnect-overlay">
          <div class="disconnect-message">
            <i class="pi pi-exclamation-circle disconnect-icon"></i>
            <span>No connection to Server</span>
          </div>
        </div>
        <PageHeader />
        <RouterView />
      </main>

      <div class="git-commit-badge">
        <a href="https://docs.displayhive.org/" target="_blank" rel="noopener" class="docs-link">DisplayHive Documentation</a>
        · Version {{ security.version.value }} · Commit: {{ security.revision.value }}
      </div>
    </template>
  </div>
</template>

<style src="./assets/shell/index.css"></style>
