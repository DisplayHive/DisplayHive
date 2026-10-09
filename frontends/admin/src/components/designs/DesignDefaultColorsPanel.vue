<script setup lang="ts">
import type { DesignForm } from '../../types/designForm'
import { newColorId } from '../../composables/designs/useDefaultColors'
import DesignPanel from './DesignPanel.vue'
import ColorPicker from '../ColorPicker.vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'

// The Design's named palette; every other color field offers these as quick picks.
const form = defineModel<DesignForm>('form', { required: true })

const addColor = () => {
  form.value.default_colors = [...form.value.default_colors, { id: newColorId(), name: '', hex: '#ffffff' }]
}
const removeColor = (idx: number) => {
  form.value.default_colors = form.value.default_colors.filter((_, i) => i !== idx)
}
const hexOf = (idx: number): string => (form.value.default_colors[idx]?.hex || '').replace(/^#/, '')
const setHex = (idx: number, hex: string | undefined) => {
  const entry = form.value.default_colors[idx]
  if (entry) entry.hex = hex ? `#${hex}` : ''
}
</script>

<template>
  <DesignPanel
    title="Default Colors"
    description="A named palette for this Design — pick the palette icon next to any color field below to reuse one of these."
    header-tour="designs-default-colors-header"
  >
    <div v-for="(c, idx) in form.default_colors" :key="c.id" class="default-color-row">
      <ColorPicker :model-value="hexOf(idx)" @update:model-value="(v) => setHex(idx, v)" />
      <InputText v-model="c.name" placeholder="Name" size="small" class="w-full" />
      <span class="color-field-value">{{ c.hex || '(not set)' }}</span>
      <Button icon="pi pi-trash" text size="small" severity="danger" title="Remove" @click="removeColor(idx)" />
    </div>
    <Button label="Add Color" icon="pi pi-plus" text size="small" @click="addColor" />
  </DesignPanel>
</template>

<style scoped>
.default-color-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.4rem;
}

.color-field-value {
  font-family: monospace;
  font-size: 0.8rem;
  color: #666;
}
</style>
