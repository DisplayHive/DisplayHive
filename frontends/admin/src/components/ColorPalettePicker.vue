<script setup lang="ts">
import { ref } from 'vue'
import Button from 'primevue/button'
import Popover from 'primevue/popover'
import type { DefaultColor } from '../types/models'

defineProps<{
  palette: DefaultColor[]
}>()

// Emits the picked entry itself (not just its hex) — callers store a live
// "@default:<id>" reference rather than copying the hex, so future edits to
// this palette entry are reflected everywhere it was picked.
const emit = defineEmits<{
  select: [color: DefaultColor]
}>()

const popover = ref<InstanceType<typeof Popover> | null>(null)
const toggle = (e: Event) => popover.value?.toggle(e)

const pick = (color: DefaultColor, e: Event) => {
  emit('select', color)
  popover.value?.toggle(e)
}
</script>

<template>
  <Button icon="pi pi-palette" text size="small" title="Pick from default colors" @click="toggle" />
  <Popover ref="popover">
    <div class="color-palette-picker">
      <p v-if="!palette.length" class="color-palette-empty">No default colors yet — add some in the "Default Colors" section.</p>
      <button
        v-for="c in palette"
        :key="c.id"
        type="button"
        class="color-palette-swatch"
        :style="{ backgroundColor: c.hex }"
        :title="`${c.name} (${c.hex})`"
        @click="(e) => pick(c, e)"
      />
    </div>
  </Popover>
</template>

<style scoped>
.color-palette-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  max-width: 220px;
}

.color-palette-empty {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #777);
  margin: 0;
  max-width: 200px;
}

.color-palette-swatch {
  width: 24px;
  height: 24px;
  border-radius: 5px;
  border: 1px solid var(--p-surface-border, #ddd);
  cursor: pointer;
  padding: 0;
}

.color-palette-swatch:hover {
  outline: 2px solid var(--p-primary-color, #6366f1);
  outline-offset: 1px;
}
</style>
