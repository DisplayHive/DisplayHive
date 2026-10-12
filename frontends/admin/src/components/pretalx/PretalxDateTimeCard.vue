<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import DatePicker from 'primevue/datepicker'
import InputText from 'primevue/inputtext'
import { useAck } from '../../composables/useAck'
import { FORMAT_TOKENS, formatDateStr } from '../../utils/pretalxDateFormat'
import type { PretalxSettings } from './types'

// "Date / Time Settings" card of the Pretalx page: display format (with a live
// preview in the instance's timezone), end of day and the simulation datetime.
const props = defineProps<{ settings: PretalxSettings; canManage: boolean; timezone: string; now: number }>()

const { request } = useAck()
const pretalxTimeFormat = ref('HH:mm')
const pretalxEndOfDay = ref('23:59')
const pretalxSimDatetime = ref<Date | null>(null)
const settingsSaving = ref(false)

watch(() => props.settings, (s) => {
  pretalxTimeFormat.value  = s.time_format ?? 'HH:mm'
  pretalxEndOfDay.value    = s.end_of_day  ?? '23:59'
  pretalxSimDatetime.value = s.sim_datetime ? new Date(s.sim_datetime) : null
}, { immediate: true })

const formatDatePreview = (format: string): string =>
  formatDateStr(new Date(props.now), format || 'HH:mm', props.timezone)

const savePretalxSettings = async () => {
  settingsSaving.value = true
  try {
    const _d = pretalxSimDatetime.value
    const pad = (n: number) => String(n).padStart(2, '0')
    const simIso = _d
      ? `${_d.getFullYear()}-${pad(_d.getMonth() + 1)}-${pad(_d.getDate())}T${pad(_d.getHours())}:${pad(_d.getMinutes())}`
      : ''
    await request('displayhive:admin:pretalx:cts:save_settings', {
      time_format:   pretalxTimeFormat.value,
      end_of_day:    pretalxEndOfDay.value,
      sim_datetime:  simIso,
    }, { success: 'Date/Time settings updated', error: 'Save failed' })
  } finally {
    settingsSaving.value = false
  }
}
</script>

<template>
  <Card>
    <template #title>
      <div class="card-header">
        <i class="pi pi-clock card-header-icon" />
        <span>Date / Time Settings</span>
      </div>
    </template>
    <template #content>
      <p class="settings-hint">All settings are only default values. They may be overwritten in the content.</p>
      <div class="settings-form" data-tour="pretalx-datetime-fields">
        <div class="field">
          <label for="pretalx-time-format">Display Time Format</label>
          <div class="datetime-format-wrapper">
            <InputText id="pretalx-time-format" v-model="pretalxTimeFormat" placeholder="HH:mm" class="w-full" :disabled="!canManage" />
            <div class="datetime-preview">
              <span class="datetime-preview-label">Preview</span>
              <span class="datetime-preview-value">{{ formatDatePreview(pretalxTimeFormat) }}</span>
              <span class="datetime-preview-tz">({{ timezone }})</span>
            </div>
            <div class="datetime-tokens">
              <p class="datetime-tokens-title">Format tokens</p>
              <table class="token-table">
                <thead>
                  <tr><th>Token</th><th>Description</th><th>Example</th></tr>
                </thead>
                <tbody>
                  <tr v-for="t in FORMAT_TOKENS" :key="t.token">
                    <td><code>{{ t.token }}</code></td>
                    <td>{{ t.desc }}</td>
                    <td>{{ t.example }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
        <div class="field">
          <label for="pretalx-end-of-day">End of Day</label>
          <InputText id="pretalx-end-of-day" v-model="pretalxEndOfDay" placeholder="23:59" class="w-full" :disabled="!canManage" />
        </div>
        <div class="field">
          <label for="pretalx-sim-datetime">Simulation Datetime</label>
          <small class="field-description">If set, rendering uses this time instead of the current time. Leave empty to use live time.</small>
          <DatePicker
            id="pretalx-sim-datetime"
            v-model="pretalxSimDatetime"
            showTime
            hourFormat="24"
            showClear
            dateFormat="dd.mm.yy"
            placeholder="Use current time"
            class="w-full"
            :disabled="!canManage"
          />
        </div>
        <div class="field-actions">
          <Button v-if="canManage" label="Save" icon="pi pi-check" :loading="settingsSaving" @click="savePretalxSettings" />
        </div>
      </div>
    </template>
  </Card>
</template>

<style scoped src="./shared.css"></style>
<style scoped>
.datetime-format-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.datetime-preview {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.45rem 0.75rem;
  background: var(--p-surface-100, #f3f4f6);
  border-radius: 6px;
  font-family: monospace;
}

.datetime-preview-label {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--p-text-muted-color, #6b7280);
}

.datetime-preview-value {
  font-size: 1rem;
  font-weight: 600;
}

.datetime-preview-tz {
  margin-left: auto;
  font-size: 0.7rem;
  color: var(--p-text-muted-color, #9ca3af);
}

.datetime-tokens { margin-top: 0.1rem; }

.datetime-tokens-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
  margin: 0 0 0.35rem;
}

.token-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
}

.token-table th {
  text-align: left;
  padding: 0.2rem 0.5rem;
  border-bottom: 1px solid var(--p-surface-300, #d1d5db);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.token-table td {
  padding: 0.18rem 0.5rem;
  border-bottom: 1px solid var(--p-surface-200, #e5e7eb);
}

.token-table td code {
  background: var(--p-surface-200, #e5e7eb);
  padding: 0 0.3rem;
  border-radius: 3px;
  font-size: 0.74rem;
}

/* Dark mode: --p-surface-100..300 are fixed ramp points, kept as the
   light-mode shades above — see docs/developer/styleguide.md. */
.dark-mode .datetime-preview {
  background: var(--p-surface-800, #1e293b);
}

.dark-mode .token-table th {
  border-bottom-color: var(--p-surface-600, #475569);
}

.dark-mode .token-table td {
  border-bottom-color: var(--p-surface-700, #334155);
}

.dark-mode .token-table td code {
  background: var(--p-surface-700, #334155);
}
</style>
