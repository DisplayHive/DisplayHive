<script setup lang="ts">
import { computed } from 'vue'
import { provideFieldContext, type FieldEditorProps } from '../composables/fields/useFieldContext'
import { fieldEditorFor } from './fields/registry'
import type { OptionFlags } from '../utils/optionFlags'

/**
 * The editor of one Contenttype field (TagConfig), chosen by its field handler — the editors are
 * the components in components/fields/ (registered in fields/registry.ts). Used by the content
 * edit page (mode 'edit') and by the Contenttype editor's field-preset panel (mode 'preset'), so
 * both show exactly the same widgets. The value bag, modes and per-option lock/hide flags are
 * documented on FieldEditorProps (composables/fields/useFieldContext.ts).
 */
const props = withDefaults(defineProps<FieldEditorProps>(), {
  disabled: false,
  mode: 'edit',
  optionFlags: undefined,
  palette: () => [],
})

const emit = defineEmits<{
  'update:optionFlags': [OptionFlags]
  'update:hasVisibleControl': [boolean]
}>()

provideFieldContext(props, emit)
// An editor that has options it can hide reports below; every other one always shows something.
emit('update:hasVisibleControl', true)

const editor = computed(() => fieldEditorFor(props.tag.fieldHandler))
</script>

<template>
  <div :class="['field-value-editor', { 'fve-disabled': disabled }]">
    <component :is="editor.component" v-bind="editor.props" />
  </div>
</template>
