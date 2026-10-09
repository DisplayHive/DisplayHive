<script setup lang="ts">
import { useFieldContext } from '../../composables/fields/useFieldContext'
import FieldSlot from './FieldSlot.vue'
import Checkbox from 'primevue/checkbox'

const f = useFieldContext()
f.reportVisibleWhen(() => !f.isHidden(f.name))
</script>

<template>
  <FieldSlot :field-key="f.name">
    <Checkbox
      :inputId="`field-${f.name}`"
      :binary="true"
      :modelValue="!!f.get(f.name)"
      @update:modelValue="(v: boolean) => f.set(f.name, v)"
      :disabled="f.isLocked(f.name)"
    />
  </FieldSlot>
</template>
