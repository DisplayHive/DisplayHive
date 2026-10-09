<script setup lang="ts">
import { useFieldContext } from '../../composables/fields/useFieldContext'
import { usePreviewClock } from '../../composables/fields/usePreviewClock'
import {
  COUNTDOWN_TOKENS, formatCountdownPreview, formatCountdownTarget, parseCountdownTarget,
} from '../../utils/fieldPreviews'
import FieldSlot from './FieldSlot.vue'
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
    <div class="datetime-preview">
      <span class="datetime-preview-label">Preview</span>
      <span class="datetime-preview-value">{{ formatCountdownPreview(String(f.get(f.name) || ''), String(f.get(`${f.name}__format`) || 'DD:HH:mm:ss'), String(f.get(`${f.name}__finished_text`) || ''), now) }}</span>
    </div>
    <div class="datetime-tokens">
      <p class="datetime-tokens-title">Format tokens</p>
      <table class="token-table">
        <thead>
          <tr><th>Token</th><th>Description</th><th>Example</th></tr>
        </thead>
        <tbody>
          <tr v-for="t in COUNTDOWN_TOKENS" :key="t.token">
            <td><code>{{ t.token }}</code></td>
            <td>{{ t.desc }}</td>
            <td>{{ t.example }}</td>
          </tr>
        </tbody>
      </table>
    </div>
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

.datetime-tokens {
  margin-top: 0.1rem;
}

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

/* Dark mode: --p-surface-100..300 are fixed ramp points (always pale, in
   both themes), not semantic tokens — see docs/developer/styleguide.md.
   These shade a header/stripe distinguishable from its surrounding panel,
   so (unlike the content-background swaps above) they need an explicit
   dark surface rather than matching the panel exactly. */
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
