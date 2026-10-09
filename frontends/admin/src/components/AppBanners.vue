<script setup lang="ts">
import { useAuthStore } from '../stores/auth'
import type { SecurityIssue, SecurityStatus } from '../composables/useSecurityStatus'
import LegacyDataBanner from './LegacyDataBanner.vue'
import Button from 'primevue/button'

// The strips above the header: impersonation notice, data in old locations, and the
// server-configuration warnings. Styles: assets/shell/banners.css.
defineProps<{
  status: SecurityStatus
  criticalIssues: SecurityIssue[]
  warnings: string[]
}>()

const authStore = useAuthStore()
</script>

<template>
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

  <!-- Not suppressed in dev builds like the security warnings: the old
       locations need moving in a dev checkout too. -->
  <LegacyDataBanner
    v-if="status.legacy_data_paths?.length"
    :legacy-paths="status.legacy_data_paths"
    :deployment="status.deployment"
    :data-dir="status.data_dir"
  />

  <div v-if="criticalIssues.length || warnings.length" class="security-warnings">
    <div
      v-if="criticalIssues.length"
      class="security-critical"
      role="alert"
      data-testid="security-critical"
    >
      <div class="security-critical-title">
        <i class="pi pi-shield"></i>
        Insecure server configuration — fix this before going live
      </div>
      <ul class="security-critical-list">
        <li v-for="issue in criticalIssues" :key="issue.title" data-testid="security-warning">
          <strong>{{ issue.title }}</strong> {{ issue.detail }}
        </li>
      </ul>
    </div>
    <div
      v-for="(warning, i) in warnings"
      :key="i"
      class="security-warning"
      data-testid="security-warning"
    >
      <i class="pi pi-exclamation-triangle"></i>
      {{ warning }}
    </div>
  </div>
</template>
