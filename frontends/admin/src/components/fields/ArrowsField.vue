<script setup lang="ts">
import { useFieldContext } from '../../composables/fields/useFieldContext'
import FieldSlot from './FieldSlot.vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'

// An arrow character picked from a grid, and its size.
const f = useFieldContext()

const ARROWS = [
  { char: '←', label: 'Left' },
  { char: '→', label: 'Right' },
  { char: '↑', label: 'Up' },
  { char: '↓', label: 'Down' },
  { char: '↖', label: 'Up-Left' },
  { char: '↗', label: 'Up-Right' },
  { char: '↙', label: 'Down-Left' },
  { char: '↘', label: 'Down-Right' },
  { char: '↔', label: 'Left-Right' },
  { char: '↕', label: 'Up-Down' },
  { char: '⇐', label: 'Double Left' },
  { char: '⇒', label: 'Double Right' },
  { char: '⇑', label: 'Double Up' },
  { char: '⇓', label: 'Double Down' },
  { char: '⇖', label: 'Double Up-Left' },
  { char: '⇗', label: 'Double Up-Right' },
  { char: '⇙', label: 'Double Down-Left' },
  { char: '⇘', label: 'Double Down-Right' },
  { char: '⇔', label: 'Double Left-Right' },
  { char: '⇕', label: 'Double Up-Down' },
]

f.reportVisibleWhen(() => !f.isHidden(f.name) || !f.isHidden(`${f.name}_size`))
</script>

<template>
  <div class="arrow-picker-wrapper">
    <FieldSlot :field-key="f.name">
      <div :class="['fve-slot-control', 'w-full', { 'fve-disabled': f.isLocked(f.name) }]">
        <div class="arrow-grid">
          <button
            v-for="arrow in ARROWS"
            :key="arrow.char"
            type="button"
            :class="['arrow-btn', f.get(f.name) === arrow.char ? 'arrow-btn--selected' : '']"
            :title="arrow.label"
            @click="f.set(f.name, arrow.char)"
          >{{ arrow.char }}</button>
        </div>
        <div class="arrow-selected-preview" v-if="f.get(f.name)">
          Selected: <span class="arrow-preview-char">{{ f.get(f.name) }}</span>
          <Button icon="pi pi-times" size="small" text @click="f.set(f.name, '')" title="Clear" />
        </div>
      </div>
    </FieldSlot>
    <FieldSlot :field-key="`${f.name}_size`" class="arrow-size-row">
      <label :for="`field-${f.name}-size`" class="arrow-size-label">Größe (vh)</label>
      <InputNumber
        :id="`field-${f.name}-size`"
        :modelValue="Number(f.get(`${f.name}_size`)) || 5"
        @update:modelValue="(v: number | null) => f.set(`${f.name}_size`, v ?? 5)"
        :min="0.1"
        :max="50"
        :step="0.1"
        suffix=" vh"
        :disabled="f.isLocked(`${f.name}_size`)"
        style="width: 120px"
      />
    </FieldSlot>
  </div>
</template>

<style scoped>
/* Arrow picker */
.arrow-picker-wrapper {
  width: 100%;
}

.arrow-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.5rem;
  background: var(--p-content-background, #f8fafc);
  border: 1px solid var(--p-content-border-color, #e2e8f0);
  border-radius: 8px;
}

.arrow-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.4rem;
  height: 2.4rem;
  font-size: 1.4rem;
  border: 1px solid var(--p-content-border-color, #cbd5e1);
  border-radius: 6px;
  background: var(--p-content-background, white);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
  line-height: 1;
}

.arrow-btn:hover {
  background: var(--p-primary-50, #eff6ff);
  border-color: var(--p-primary-color, #3b82f6);
}

.arrow-btn--selected {
  background: var(--p-primary-color, #3b82f6);
  border-color: var(--p-primary-color, #3b82f6);
  color: white;
}

.arrow-selected-preview {
  margin-top: 0.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
}

.arrow-preview-char {
  font-size: 2rem;
  line-height: 1;
}

.arrow-size-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.6rem;
}

.arrow-size-label {
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
  white-space: nowrap;
}

/* .fve-slot's ":first-child { flex: 1 }" rule (a class + pseudo-class
   selector, specificity 0-2-0) is meant for the control, not a leading
   label — a plain ".arrow-size-label { flex: 0 0 auto }" (specificity
   0-1-0) can never win against it regardless of source order, so the
   override has to match that same specificity. Without this, a label
   placed first (as here) grabs the row's flex-grow and shoves the actual
   control off to the right instead. Same fix repeated for
   .image-size-label / .marquee-speed-label below. */
.fve-slot > .arrow-size-label:first-child {
  flex: 0 0 auto;
}

/* Unlike the full-width dropdown/textarea controls elsewhere in this file,
   these rows' InputNumber has a fixed width and never grows to fill the
   row, so its OptionFlagToggle would otherwise sit right next to it instead
   of flush with the right edge like every other row's toggle. :deep()
   reaches into OptionFlagToggle's own root (a separate component, so scoped
   styles here don't reach it without it) to override its default
   margin-left. Repeated for .image-size-row / .marquee-speed-row below. */
.arrow-size-row :deep(.option-flag-toggle) {
  margin-left: auto;
}
</style>
