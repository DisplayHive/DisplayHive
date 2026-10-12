<script setup lang="ts">
// Thin wrapper around PrimeVue's ColorPicker: an empty value shows a
// checkerboard swatch ("no color set", like image editors' transparency)
// instead of PrimeVue's default red, which reads as a real, chosen color.
// Everything else (props, events, classes) passes straight through.
import ColorPicker from 'primevue/colorpicker'

defineProps<{ modelValue?: string | null }>()
defineEmits<{ 'update:modelValue': [value: string | undefined] }>()
</script>

<template>
  <ColorPicker
    :model-value="modelValue ?? undefined"
    :class="{ 'color-unset': !modelValue }"
    @update:model-value="(v: unknown) => $emit('update:modelValue', v as string | undefined)"
  />
</template>

<style scoped>
.color-unset :deep(.p-colorpicker-preview) {
  /* !important: PrimeVue paints the preview via an inline background-color. */
  background-color: var(--p-content-background, #fff) !important;
  background-image:
    linear-gradient(45deg, var(--p-surface-300, #ccc) 25%, transparent 25%, transparent 75%, var(--p-surface-300, #ccc) 75%),
    linear-gradient(45deg, var(--p-surface-300, #ccc) 25%, transparent 25%, transparent 75%, var(--p-surface-300, #ccc) 75%) !important;
  background-size: 10px 10px !important;
  background-position: 0 0, 5px 5px !important;
}
</style>
