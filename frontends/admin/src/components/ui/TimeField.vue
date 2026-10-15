<script setup lang="ts">
import { computed } from 'vue'
import DatePicker from 'primevue/datepicker'

// A time of day, always on a 24-hour clock ("HH:MM", no AM/PM — the browser's own <input type="time">
// follows the browser language and shows AM/PM in some of them). The value is the "HH:MM" text the
// server stores; the empty string means no time.
const props = defineProps<{ disabled?: boolean; inputId?: string; ariaLabel?: string; placeholder?: string }>()
const model = defineModel<string>({ default: '' })

const pad = (n: number) => String(n).padStart(2, '0')

const asDate = computed<Date | null>({
  get: () => {
    const m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(model.value || '')
    if (!m) return null
    const d = new Date()
    d.setHours(Number(m[1]), Number(m[2]), 0, 0)
    return d
  },
  set: (d) => {
    model.value = d ? `${pad(d.getHours())}:${pad(d.getMinutes())}` : ''
  },
})
</script>

<template>
  <DatePicker
    v-model="asDate"
    :input-id="props.inputId"
    :aria-label="props.ariaLabel"
    :disabled="props.disabled"
    :placeholder="props.placeholder ?? 'HH:MM'"
    time-only
    hour-format="24"
    class="time-field"
  />
</template>

<style scoped>
.time-field {
  width: 7rem;
}
</style>
