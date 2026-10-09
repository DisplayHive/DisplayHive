<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import type { DesignForm } from '../../types/designForm'
import { useDefaultColors, colorRefFor } from '../../composables/designs/useDefaultColors'
import { useSocket } from '../../composables/useSocket'
import { useAck } from '../../composables/useAck'
import { FONT_PROPERTIES, type FontProperty } from '../../utils/containerFontProperties'
import DesignPanel from './DesignPanel.vue'
import ColorPicker from '../ColorPicker.vue'
import ColorPalettePicker from '../ColorPalettePicker.vue'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'

// Font styles applied to every container via `.dh-container`. A (property, value) pair per
// Design, not keyed by container. Precedence: these global ones < per-container overrides
// (Layout editor) < the Design's own hand-written CSS (see upd_content.py).
// Loads its own values when it appears, and saves each change (debounced).
const form = defineModel<DesignForm>('form', { required: true })
const { resolveColorRef, colorDisplayLabel } = useDefaultColors(form)
const { on, off, emit } = useSocket()
const { request } = useAck()

const globalStyles = ref<Record<string, string>>({})

// A stored value that no longer matches its property's current input type
// (e.g. "xx-small" for font-size after it changed from a keyword dropdown to
// a vh number) can't be shown OR cleared by that control. Discarding it on
// load turns "invisible stale value" into a visible "not set".
const isValidForType = (type: FontProperty['type'], value: string): boolean => {
  if (!value) return true
  if (type === 'vh-number') return /^-?\d+(\.\d+)?vh$/.test(value)
  if (type === 'color') return /^#[0-9a-fA-F]{6}$/.test(value)
  return true
}

const handleGlobalStyles = (data: { design_id?: number; data?: Record<string, string> }) => {
  if (!data || data.design_id !== form.value.id) return
  const styles: Record<string, string> = { ...data.data }
  for (const p of FONT_PROPERTIES) {
    const v = styles[p.key]
    if (v && !isValidForType(p.type, v)) delete styles[p.key]
  }
  globalStyles.value = styles
}

onMounted(() => {
  on('displayhive:admin:stc:design_global_styles', handleGlobalStyles)
  if (form.value.id) emit('displayhive:admin:cts:get_design_global_styles', { design_id: form.value.id })
})
onUnmounted(() => {
  off('displayhive:admin:stc:design_global_styles', handleGlobalStyles)
  if (saveDebounce) clearTimeout(saveDebounce)
})

const getValue = (prop: string): string => globalStyles.value[prop] ?? ''

let saveDebounce: ReturnType<typeof setTimeout> | null = null

const setValue = (prop: string, value: string | undefined) => {
  globalStyles.value = { ...globalStyles.value, [prop]: value || '' }

  if (!form.value.id) return
  if (saveDebounce) clearTimeout(saveDebounce)
  const designId = form.value.id
  saveDebounce = setTimeout(() => {
    const styles: Record<string, string> = {}
    for (const p of FONT_PROPERTIES) styles[p.key] = globalStyles.value[p.key] || ''
    void request('displayhive:admin:cts:save_design_global_styles', { design_id: designId, styles }, { error: 'Could not save the global styles' })
  }, 400)
}

const getVhNumber = (prop: string): number | null => {
  const raw = getValue(prop)
  if (!raw) return null
  const n = parseFloat(raw)
  return isNaN(n) ? null : n
}
const setVhValue = (prop: string, n: number | null | undefined) => {
  setValue(prop, n == null ? '' : `${n}vh`)
}
const getColorHex = (prop: string): string => {
  const raw = getValue(prop)
  return raw ? resolveColorRef(raw).replace(/^#/, '') : ''
}
const setColorHex = (prop: string, hex: string | undefined) => {
  setValue(prop, hex ? `#${hex}` : '')
}
</script>

<template>
  <DesignPanel
    title="Global Styles"
    description="Applies to every container via the shared .dh-container class. Loses to anything in the CSS editor below. Per-container styling is edited in the Layout editor's Container Design card."
    header-tour="designs-global-styles-header"
  >
    <div class="font-properties-grid">
      <div v-for="p in FONT_PROPERTIES" :key="p.key" class="field">
        <label>{{ p.label }}</label>
        <InputNumber
          v-if="p.type === 'vh-number'"
          :model-value="getVhNumber(p.key)"
          :min="0" :max="50" :step="0.1" :max-fraction-digits="2"
          suffix=" vh"
          size="small"
          class="w-full"
          @update:model-value="(v) => setVhValue(p.key, v)"
        />
        <div v-else-if="p.type === 'color'" class="color-field-row">
          <ColorPicker
            :model-value="getColorHex(p.key)"
            @update:model-value="(v) => setColorHex(p.key, v)"
          />
          <ColorPalettePicker :palette="form.default_colors" @select="(c) => setValue(p.key, colorRefFor(c.id))" />
          <span class="color-field-value">{{ colorDisplayLabel(getValue(p.key)) }}</span>
          <Button
            v-if="getColorHex(p.key)"
            icon="pi pi-times" text size="small" title="Clear"
            @click="setColorHex(p.key, '')"
          />
        </div>
        <Dropdown
          v-else
          :model-value="getValue(p.key)"
          :options="p.options"
          optionLabel="label"
          optionValue="value"
          editable
          size="small"
          class="w-full"
          @update:model-value="(v: string | undefined) => setValue(p.key, v)"
        />
      </div>
    </div>
  </DesignPanel>
</template>

<style scoped>
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
