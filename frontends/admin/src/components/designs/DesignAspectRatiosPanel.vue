<script setup lang="ts">
import { ref } from 'vue'
import type { DesignForm } from '../../types/designForm'
import DesignPanel from './DesignPanel.vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import Tag from 'primevue/tag'

// Extra "W:H" shapes this Design supports, on top of the always-available 16:9 base. Screens
// pick one, and Layouts get one variation (own container membership + positions) per ratio.
// Duplicates are by shape (4:3 == 8:6) and 16:9 itself is never listed.
const form = defineModel<DesignForm>('form', { required: true })

const RATIO_PRESETS = ['4:3', '16:10', '21:9', '1:1', '3:4', '10:16', '9:16']
const newRatioW = ref<number | null>(null)
const newRatioH = ref<number | null>(null)

const ratioValue = (r: string) => {
  const [w = 1, h = 1] = r.split(':').map(Number)
  return w / h
}
const hasRatio = (r: string) =>
  Math.abs(ratioValue(r) - 16 / 9) < 1e-9 || form.value.aspect_ratios.some((x) => Math.abs(ratioValue(x) - ratioValue(r)) < 1e-9)
const addRatio = (r: string) => {
  if (!/^\d{1,4}:\d{1,4}$/.test(r) || r.startsWith('0:') || r.endsWith(':0') || hasRatio(r)) return
  form.value.aspect_ratios = [...form.value.aspect_ratios, r]
}
const addCustomRatio = () => {
  if (!newRatioW.value || !newRatioH.value) return
  addRatio(`${newRatioW.value}:${newRatioH.value}`)
  newRatioW.value = null
  newRatioH.value = null
}
const removeRatio = (r: string) => {
  form.value.aspect_ratios = form.value.aspect_ratios.filter((x) => x !== r)
}
</script>

<template>
  <DesignPanel
    title="Aspect Ratios"
    description="16:9 is always available. Add more here, then give Screens a ratio and Layouts a variation per ratio."
    section-tour="designs-aspect-ratios"
  >
    <div class="aspect-ratio-list">
      <Tag value="16:9 (base)" severity="secondary" />
      <Tag v-for="r in form.aspect_ratios" :key="r" severity="info" class="aspect-ratio-chip">
        {{ r }}
        <i class="pi pi-times aspect-ratio-remove" title="Remove" @click="removeRatio(r)"></i>
      </Tag>
    </div>
    <div class="aspect-ratio-presets">
      <Button
        v-for="r in RATIO_PRESETS.filter((x) => !hasRatio(x))" :key="r"
        :label="r" icon="pi pi-plus" text size="small" @click="addRatio(r)"
      />
    </div>
    <div class="aspect-ratio-custom">
      <InputNumber v-model="newRatioW" :min="1" :max="9999" placeholder="W" size="small" style="width: 5rem" />
      <span>:</span>
      <InputNumber v-model="newRatioH" :min="1" :max="9999" placeholder="H" size="small" style="width: 5rem" />
      <Button label="Add ratio" icon="pi pi-plus" size="small" outlined :disabled="!newRatioW || !newRatioH" @click="addCustomRatio" />
    </div>
  </DesignPanel>
</template>

<style scoped>
.aspect-ratio-list,
.aspect-ratio-presets,
.aspect-ratio-custom {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}

.aspect-ratio-remove {
  margin-left: 0.4rem;
  cursor: pointer;
  font-size: 0.75rem;
}
</style>
