<script setup lang="ts">
import { useFieldContext } from '../../composables/fields/useFieldContext'
import FieldSlot from './FieldSlot.vue'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'

// A scrolling text and its speed.
const f = useFieldContext()
</script>

<template>
  <div class="marquee-field-wrapper">
    <FieldSlot :field-key="f.name">
      <InputText
        :id="`field-${f.name}`"
        :modelValue="String(f.get(f.name))"
        @update:modelValue="(v: string | undefined) => f.set(f.name, v ?? '')"
        placeholder="Dein Lauftext…"
        :disabled="f.isLocked(f.name)"
        class="w-full"
      />
    </FieldSlot>
    <FieldSlot :field-key="`${f.name}__speed`" class="marquee-speed-row">
      <label :for="`field-${f.name}-speed`" class="marquee-speed-label">Geschwindigkeit (s)</label>
      <InputNumber
        :id="`field-${f.name}-speed`"
        :modelValue="Number(f.get(`${f.name}__speed`)) || 20"
        @update:modelValue="(v: number | null) => f.set(`${f.name}__speed`, v ?? 20)"
        :min="1" :max="300" :step="1"
        suffix=" s"
        :disabled="f.isLocked(`${f.name}__speed`)"
        style="width: 130px"
      />
    </FieldSlot>
    <small class="marquee-hint">Niedrigere Zahl = schnellere Laufgeschwindigkeit.</small>
  </div>
</template>

<style scoped>
.marquee-field-wrapper {
  width: 100%;
}

.marquee-speed-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.4rem;
}

.marquee-speed-label {
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
  white-space: nowrap;
}

/* .fve-slot's ":first-child { flex: 1 }" rule (specificity 0-2-0) is meant
   for the control, not a leading label — a plain single-class override
   (0-1-0, as this used to be) can never beat it regardless of source
   order, so the selector has to match that specificity. Without this, a
   label placed first (as here) grabs the row's flex-grow and shoves the
   actual control off to the right instead. Same fix as .arrow-size-label /
   .image-size-label above. */
.fve-slot > .marquee-speed-label:first-child {
  flex: 0 0 auto;
}

/* Same right-alignment fix as .arrow-size-row above. */
.marquee-speed-row :deep(.option-flag-toggle) {
  margin-left: auto;
}

.marquee-hint {
  font-size: 0.78rem;
  color: var(--p-text-muted-color, #64748b);
  display: block;
  margin-top: 0.2rem;
}
</style>
