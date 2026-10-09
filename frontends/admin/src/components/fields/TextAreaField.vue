<script setup lang="ts">
import { useFieldContext } from '../../composables/fields/useFieldContext'
import FieldSlot from './FieldSlot.vue'
import Textarea from 'primevue/textarea'

// Several lines of text: long text, and raw HTML (which has no length limit).
const props = defineProps<{ rows: number; html?: boolean }>()
const f = useFieldContext()
f.reportVisibleWhen(() => !f.isHidden(f.name))
</script>

<template>
  <FieldSlot :field-key="f.name">
    <Textarea
      :id="`field-${f.name}`"
      :modelValue="String(f.get(f.name))"
      @update:modelValue="(v: string | undefined) => f.set(f.name, v ?? '')"
      :rows="props.rows"
      v-bind="props.html ? { placeholder: '<div>…</div>' } : { maxlength: f.tag.max_length }"
      :disabled="f.isLocked(f.name)"
      class="w-full"
    />
  </FieldSlot>
</template>
