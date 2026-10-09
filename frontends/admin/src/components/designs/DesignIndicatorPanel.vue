<script setup lang="ts">
import type { DesignForm } from '../../types/designForm'
import { useDefaultColors, colorRefFor } from '../../composables/designs/useDefaultColors'
import DesignPanel from './DesignPanel.vue'
import ColorPicker from '../ColorPicker.vue'
import ColorPalettePicker from '../ColorPalettePicker.vue'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'

// The thin progress bar along the bottom of the screen. Its colour uses the same
// literal-or-"@default:<id>" convention as the Backdrop colour.
const form = defineModel<DesignForm>('form', { required: true })
const { resolveColorRef, colorDisplayLabel } = useDefaultColors(form)

const INDICATOR_DIRECTIONS = [
  { label: 'Left to right', value: 'ltr' },
  { label: 'Right to left', value: 'rtl' },
]
const colorHex = (): string => resolveColorRef(form.value.indicator_color).replace(/^#/, '')
const setColorHex = (hex: string | undefined) => {
  form.value.indicator_color = hex ? `#${hex}` : ''
}
</script>

<template>
  <DesignPanel
    title="Indicator"
    description="A thin bar along the bottom of the screen that fills over the time the current content is shown."
    section-tour="designs-indicator"
  >
    <div class="field indicator-enable-row">
      <Checkbox v-model="form.indicator_enabled" inputId="indicator-enabled" binary />
      <label for="indicator-enabled">Show the indicator</label>
    </div>
    <div class="font-properties-grid" :class="{ 'indicator-fields-off': !form.indicator_enabled }">
      <div class="field">
        <label>Color</label>
        <div class="color-field-row">
          <ColorPicker :model-value="colorHex()" @update:model-value="(v) => setColorHex(v)" />
          <ColorPalettePicker :palette="form.default_colors" @select="(c) => (form.indicator_color = colorRefFor(c.id))" />
          <span class="color-field-value">{{ colorDisplayLabel(form.indicator_color) }}</span>
          <Button
            v-if="form.indicator_color"
            icon="pi pi-times" text size="small" title="Clear (white)"
            @click="form.indicator_color = ''"
          />
        </div>
      </div>
      <div class="field">
        <label for="indicator-height">Height</label>
        <InputNumber
          v-model="form.indicator_height" inputId="indicator-height"
          :min="0.1" :max="10" :step="0.1" :max-fraction-digits="2" suffix=" vh" size="small" class="w-full"
        />
      </div>
      <div class="field">
        <label for="indicator-direction">Direction</label>
        <Dropdown
          v-model="form.indicator_direction" inputId="indicator-direction"
          :options="INDICATOR_DIRECTIONS" optionLabel="label" optionValue="value" size="small" class="w-full"
        />
      </div>
    </div>
  </DesignPanel>
</template>

<style scoped>
.indicator-enable-row {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}

.indicator-fields-off {
  opacity: 0.55;
}

.font-properties-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem 1rem;
  margin-top: 0.6rem;
}

.font-properties-grid .field label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #666;
}

.color-field-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.color-field-value {
  font-family: monospace;
  font-size: 0.8rem;
  color: #666;
}
</style>
