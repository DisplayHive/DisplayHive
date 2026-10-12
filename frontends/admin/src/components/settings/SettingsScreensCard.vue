<script setup lang="ts">
import { ref, watch } from 'vue'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import ToggleSwitch from 'primevue/toggleswitch'
import Button from 'primevue/button'
import Card from 'primevue/card'

import { useAck } from '../../composables/useAck'
import type { SystemSettings } from './types'

// "Screens" card of the Settings page: status dot, daily reload and screen-log retention.
const props = defineProps<{ settings: SystemSettings; canEdit: boolean; timezone: string }>()

const { request } = useAck()

const logSaving = ref(false)
const screenLogMaxAgeHours = ref(72)
const screenLogMaxRows = ref(250000)
const statusIndicator = ref(true)
const reloadEnabled = ref(false)
const reloadAt = ref('04:00')

watch(() => props.settings, (sys) => {
  statusIndicator.value = !(sys.screen_status_indicator === false || sys.screen_status_indicator === 'false')
  reloadEnabled.value = !!sys.screen_reload_at
  if (sys.screen_reload_at) reloadAt.value = sys.screen_reload_at
  const logHours = Number(sys.screen_log_max_age_hours)
  screenLogMaxAgeHours.value = Number.isFinite(logHours) && logHours > 0 ? logHours : 72
  const logRows = Number(sys.screen_log_max_rows)
  screenLogMaxRows.value = Number.isFinite(logRows) && logRows > 0 ? logRows : 250000
}, { immediate: true })

const saveLogSettings = async () => {
  if (!props.canEdit) return
  logSaving.value = true
  try {
    await request(
      'displayhive:admin:cts:set_system_settings',
      {
        settings: {
          screen_log_max_age_hours: String(screenLogMaxAgeHours.value),
          screen_log_max_rows: String(screenLogMaxRows.value),
          screen_status_indicator: statusIndicator.value ? 'true' : 'false',
          screen_reload_at: reloadEnabled.value ? reloadAt.value : '',
        },
      },
      { success: 'Screen settings updated', error: 'Save failed' },
    )
  } finally {
    logSaving.value = false
  }
}
</script>

<template>
  <Card>
    <template #title>
      <div class="card-header-title">
        <i class="pi pi-list card-header-icon" />
        <span>Screens</span>
      </div>
    </template>
    <template #content>
      <div class="settings-form">
        <div class="toggle-group" data-tour="settings-status-indicator">
          <div class="field toggle-field">
            <label for="status-indicator-switch">Show a status dot on screens when something is wrong</label>
            <ToggleSwitch id="status-indicator-switch" v-model="statusIndicator" :disabled="!canEdit" />
          </div>
        </div>
        <div class="toggle-group" data-tour="settings-screen-reload">
          <div class="field toggle-field">
            <label for="screen-reload-switch">Reload screens once a day</label>
            <ToggleSwitch id="screen-reload-switch" v-model="reloadEnabled" :disabled="!canEdit" />
          </div>
          <div v-if="reloadEnabled" class="field">
            <label for="screen-reload-at">at (time zone: {{ timezone }})</label>
            <InputText id="screen-reload-at" v-model="reloadAt" type="time" :disabled="!canEdit" data-testid="screen-reload-at" />
          </div>
        </div>
        <p class="hint">
          A daily reload picks up a new release of the screen page. A screen without a connection tries again until it is back.
        </p>
        <p class="hint">
          The dot is hidden while all is well. Red <code>con</code>: no connection to the server.
          Yellow <code>mim</code>: content is missing or a picture/video did not load; yellow <code>js</code>: a script error.
          The codes are also written to the screen log.
        </p>
        <p class="hint">
          Screens report warnings and errors to the server, and everything while the Logger page is open.
          Lines are deleted when they are older than the first limit or when the table grows past the second.
        </p>
        <div class="field-group" data-tour="settings-screenlog-fields">
          <div class="field">
            <label for="screen-log-max-age">Keep lines for</label>
            <InputNumber id="screen-log-max-age" v-model="screenLogMaxAgeHours" :min="1" :max="8760" suffix=" hours" :disabled="!canEdit" />
          </div>
          <div class="field">
            <label for="screen-log-max-rows">Keep at most</label>
            <InputNumber id="screen-log-max-rows" v-model="screenLogMaxRows" :min="1000" :max="5000000" suffix=" lines" :disabled="!canEdit" />
          </div>
        </div>
        <div class="field-actions" data-tour="settings-screenlog-save">
          <Button v-if="canEdit" label="Save" icon="pi pi-check" :loading="logSaving" @click="saveLogSettings" />
        </div>
      </div>
    </template>
  </Card>
</template>

<style scoped src="./settingsForm.css"></style>
