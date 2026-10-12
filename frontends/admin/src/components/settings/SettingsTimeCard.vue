<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Button from 'primevue/button'
import Card from 'primevue/card'

import { useAck } from '../../composables/useAck'

// "Time" card of the Settings page: server time and the instance timezone. `timezone` is the
// edit in progress (v-model), so the Screens card can show it.
const props = defineProps<{ canEdit: boolean; serverTime: string | null; serverTimeReceivedAt: number }>()

const { request } = useAck()

const timezone = defineModel<string>('timezone', { default: 'UTC' })
const timeSaving = ref(false)
const displayedServerTime = ref('')
const correctedTime = ref('')
const serverTimeBase = computed(() => (props.serverTime ? new Date(props.serverTime) : null))

const timezoneOptions = Intl.supportedValuesOf('timeZone').map((tz: string) => ({
  label: tz,
  value: tz,
}))

let timeTicker: ReturnType<typeof setInterval> | null = null

const updateDisplayedTimes = () => {
  if (!serverTimeBase.value) return
  const elapsed = Date.now() - props.serverTimeReceivedAt
  const current = new Date(serverTimeBase.value.getTime() + elapsed)

  const fmtOpts: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }

  displayedServerTime.value =
    new Intl.DateTimeFormat('en-GB', { ...fmtOpts, timeZone: 'UTC' }).format(current) + ' UTC'

  try {
    correctedTime.value =
      new Intl.DateTimeFormat('en-GB', { ...fmtOpts, timeZone: timezone.value }).format(current) +
      ` (${timezone.value})`
  } catch {
    correctedTime.value = '—'
  }
}

watch([timezone, () => props.serverTime], updateDisplayedTimes, { immediate: true })

onMounted(() => {
  timeTicker = setInterval(updateDisplayedTimes, 1000)
})

onUnmounted(() => {
  if (timeTicker) clearInterval(timeTicker)
})

const saveTimeSettings = async () => {
  if (!props.canEdit) return
  timeSaving.value = true
  try {
    await request(
      'displayhive:admin:cts:set_system_settings',
      { settings: { timezone: timezone.value } },
      { success: 'Timezone updated', error: 'Save failed' },
    )
  } finally {
    timeSaving.value = false
  }
}
</script>

<template>
  <Card>
    <template #title>
      <div class="card-header-title">
        <i class="pi pi-clock card-header-icon" />
        <span>Time</span>
      </div>
    </template>
    <template #content>
      <div class="settings-form">
        <div class="field">
          <label>Server time</label>
          <InputText
            :value="displayedServerTime || '—'"
            class="w-full"
            readonly
            tabindex="-1"
          />
        </div>
        <div class="field" data-tour="settings-timezone-field">
          <label for="timezone">Timezone</label>
          <Select
            id="timezone"
            v-model="timezone"
            :options="timezoneOptions"
            optionLabel="label"
            optionValue="value"
            filter
            class="w-full"
            placeholder="Select timezone"
            :disabled="!canEdit"
          />
        </div>
        <div class="field">
          <label>Displayhive Time</label>
          <InputText
            :value="correctedTime || '—'"
            class="w-full"
            readonly
            tabindex="-1"
          />
        </div>
        <div class="field-actions" data-tour="settings-time-save">
          <Button
            v-if="canEdit"
            label="Save"
            icon="pi pi-check"
            :loading="timeSaving"
            @click="saveTimeSettings"
          />
        </div>
      </div>
    </template>
  </Card>
</template>

<style scoped src="./settingsForm.css"></style>
