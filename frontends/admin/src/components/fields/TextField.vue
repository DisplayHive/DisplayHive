<script setup lang="ts">
import { useFieldContext } from '../../composables/fields/useFieldContext'
import FieldSlot from './FieldSlot.vue'
import InputText from 'primevue/inputtext'

// One line of text: short text (the default handler), link and iframe URL.
const props = withDefaults(defineProps<{ type?: 'text' | 'url' }>(), { type: 'text' })
const f = useFieldContext()
f.reportVisibleWhen(() => !f.isHidden(f.name))
</script>

<template>
  <FieldSlot :field-key="f.name">
    <InputText
      :id="`field-${f.name}`"
      :modelValue="String(f.get(f.name))"
      @update:modelValue="(v: string | undefined) => f.set(f.name, v ?? '')"
      v-bind="props.type === 'url' ? { type: 'url', placeholder: 'https://example.com' } : {}"
      :maxlength="f.tag.max_length"
      :disabled="f.isLocked(f.name)"
      class="w-full"
    />
  </FieldSlot>
</template>
