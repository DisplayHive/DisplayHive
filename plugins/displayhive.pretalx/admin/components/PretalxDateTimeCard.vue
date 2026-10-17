<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import DatePicker from 'primevue/datepicker'
import InputText from 'primevue/inputtext'
import { usePluginSocket } from '@/composables/usePluginSocket'
import { PLUGIN_ID } from '../pluginId'
import FormatPreview from '@/components/fields/FormatPreview.vue'
import { FORMAT_TOKENS, formatDateString as formatDateStr } from '@/utils/content/fieldPreviews'
import type { PretalxSettings } from './types'

// "Date / Time Settings" card of the Pretalx page: display format (with a live
// preview in the instance's timezone), end of day and the simulation datetime.
const props = defineProps<{ settings: PretalxSettings; canManage: boolean; timezone: string; now: number }>()

const { call } = usePluginSocket(PLUGIN_ID)
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
    await call('save_settings', {
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
            <FormatPreview :value="formatDatePreview(pretalxTimeFormat)" :note="timezone" :tokens="FORMAT_TOKENS" />
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
</style>
