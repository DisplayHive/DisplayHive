<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useRightsStore } from '../stores/rights'

import Card from 'primevue/card'
import SettingsDashboardCard from '../components/settings/SettingsDashboardCard.vue'
import SettingsContentEditorCard from '../components/settings/SettingsContentEditorCard.vue'
import SettingsTimeCard from '../components/settings/SettingsTimeCard.vue'
import SettingsScreensCard from '../components/settings/SettingsScreensCard.vue'
import LoginProvidersCard from '../components/settings/LoginProvidersCard.vue'
import IconLibrariesCard from '../components/settings/IconLibrariesCard.vue'
import OutboundPolicyCard from '../components/settings/OutboundPolicyCard.vue'
import type { SystemSettings } from '../components/settings/types'

const { on, off, emit } = useSocket()
const rightsStore = useRightsStore()

const canEdit = computed(() => rightsStore.can('settings.edit'))

const loading = ref(true)
const settings = ref<SystemSettings>({})
const serverTime = ref<string | null>(null)
const serverTimeReceivedAt = ref(0)
// The timezone being edited in the Time card (the Screens card shows it too).
const selectedTimezone = ref('UTC')

const handleSettings = (data: { system_settings?: SystemSettings; server_time?: string }) => {
  loading.value = false
  settings.value = data?.system_settings || {}
  if (data?.server_time) {
    serverTime.value = data.server_time
    serverTimeReceivedAt.value = Date.now()
  }
  selectedTimezone.value = settings.value.timezone ?? 'UTC'
}

onMounted(() => {
  on('displayhive:admin:stc:admin_settings', handleSettings)
  emit('displayhive:admin:cts:get_admin_settings')
})

onUnmounted(() => {
  off('displayhive:admin:stc:admin_settings', handleSettings)
})
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('settings.page')" class="settings-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Settings page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="settings-page" class="settings-view">

    <div v-if="loading" class="loading-state">
      <i class="pi pi-spin pi-spinner"></i>
      <p>Loading settings…</p>
    </div>

    <template v-else>
      <SettingsDashboardCard :settings="settings" :can-edit="canEdit" />

      <SettingsContentEditorCard :settings="settings" :can-edit="canEdit" />

      <SettingsTimeCard
        v-model:timezone="selectedTimezone"
        :can-edit="canEdit"
        :server-time="serverTime"
        :server-time-received-at="serverTimeReceivedAt"
      />

      <SettingsScreensCard :settings="settings" :can-edit="canEdit" :timezone="selectedTimezone" />

      <IconLibrariesCard v-if="rightsStore.can('icons.manage') || rightsStore.can('settings.page')" />

      <LoginProvidersCard v-if="rightsStore.can('authproviders.manage')" />

      <OutboundPolicyCard />

    </template>

  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  max-width: 640px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 3rem;
  color: var(--p-text-muted-color, #9ca3af);
}
</style>
