<script setup lang="ts">
import { useFieldContext } from '../../composables/fields/useFieldContext'
import OptionFlagToggle from '../OptionFlagToggle.vue'

// One row per individual option/sub-control of a field: the control itself (grows to fill the
// width) plus, in preset-authoring mode, its lock/hide toggle pair anchored to the right. In a
// Content Editor a hidden option renders nothing at all. `fieldKey` is the key of the option in
// the field's value bag (e.g. `name`, `name__size`).
defineProps<{ fieldKey: string }>()
const f = useFieldContext()
</script>

<template>
  <div v-if="f.mode !== 'edit' || !f.isHidden(fieldKey)" class="fve-slot">
    <slot />
    <OptionFlagToggle
      v-if="f.mode === 'preset'"
      v-bind="f.flagsFor(fieldKey)"
      @toggle-locked="f.toggleFlag(fieldKey, 'locked')"
      @toggle-hidden="f.toggleFlag(fieldKey, 'hidden')"
    />
  </div>
</template>
