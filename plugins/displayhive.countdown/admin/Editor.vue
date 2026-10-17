<script setup lang="ts">
import { useFieldContext } from '@/composables/fields/useFieldContext'
import { usePreviewClock } from '@/composables/fields/usePreviewClock'
import {
  COUNTDOWN_TOKENS, formatCountdownPreview, formatCountdownTarget, parseCountdownTarget,
} from '@/utils/content/fieldPreviews'
import FieldSlot from '@/components/fields/FieldSlot.vue'
import FormatPreview from '@/components/fields/FormatPreview.vue'
import DatePicker from 'primevue/datepicker'
import InputText from 'primevue/inputtext'

// A target date and time, the format of the remaining time and a text for when it is over, with a
// live preview and the token reference.
const f = useFieldContext()
const now = usePreviewClock()
</script>

<template>
  <div class="countdown-field-wrapper">
    <FieldSlot :field-key="f.name">
      <DatePicker
        :id="`field-${f.name}`"
        :modelValue="parseCountdownTarget(String(f.get(f.name) || ''))"
        @update:modelValue="(v: Date | Date[] | (Date | null)[] | null | undefined) => f.set(f.name, formatCountdownTarget(Array.isArray(v) ? (v[0] ?? null) : (v ?? null)))"
        showTime hourFormat="24" showClear dateFormat="dd.mm.yy"
        placeholder="Target date &amp; time"
        :disabled="f.isLocked(f.name)"
        class="w-full"
      />
    </FieldSlot>
    <FieldSlot :field-key="`${f.name}__format`">
      <div class="countdown-subfield">
        <label :for="`field-${f.name}-format`">Format</label>
        <InputText
          :id="`field-${f.name}-format`"
          :modelValue="String(f.get(`${f.name}__format`) || 'DD:HH:mm:ss')"
          @update:modelValue="(v: string | undefined) => f.set(`${f.name}__format`, v ?? '')"
          placeholder="DD:HH:mm:ss"
          :disabled="f.isLocked(`${f.name}__format`)"
          style="width: 160px"
        />
      </div>
    </FieldSlot>
    <FieldSlot :field-key="`${f.name}__finished_text`">
      <div class="countdown-subfield">
        <label :for="`field-${f.name}-finished`">Finished Text</label>
        <InputText
          :id="`field-${f.name}-finished`"
          :modelValue="String(f.get(`${f.name}__finished_text`) || '')"
          @update:modelValue="(v: string | undefined) => f.set(`${f.name}__finished_text`, v ?? '')"
          placeholder="Optional text shown once the countdown ends"
          :disabled="f.isLocked(`${f.name}__finished_text`)"
          class="w-full"
        />
      </div>
    </FieldSlot>
    <FormatPreview :value="formatCountdownPreview(String(f.get(f.name) || ''), String(f.get(`${f.name}__format`) || 'DD:HH:mm:ss'), String(f.get(`${f.name}__finished_text`) || ''), now)" :tokens="COUNTDOWN_TOKENS" />
  </div>
</template>

<style scoped>
.countdown-field-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.countdown-subfield {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.countdown-subfield label {
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
}
</style>
