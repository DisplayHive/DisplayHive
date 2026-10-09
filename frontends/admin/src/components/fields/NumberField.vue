<script setup lang="ts">
import { useFieldContext } from '../../composables/fields/useFieldContext'
import FieldSlot from './FieldSlot.vue'
import InputNumber from 'primevue/inputnumber'

const f = useFieldContext()
f.reportVisibleWhen(() => !f.isHidden(f.name))
</script>

<template>
  <FieldSlot :field-key="f.name">
    <InputNumber
      :id="`field-${f.name}`"
      :modelValue="Number(f.get(f.name))"
      @update:modelValue="(v: number | null) => f.set(f.name, v ?? 0)"
      :disabled="f.isLocked(f.name)"
      class="w-full"
    />
  </FieldSlot>
</template>
