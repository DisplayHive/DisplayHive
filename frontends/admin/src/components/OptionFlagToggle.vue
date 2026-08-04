<script setup lang="ts">
/**
 * Small inline pair of icon toggles placed next to an individual field
 * sub-control in the Contenttype editor's preset-authoring mode — "Prohibit
 * overwrite" (locked) and "Hide from user" (hidden). Purely presentational;
 * the owning component (FieldValueEditor.vue, IconPickerField.vue,
 * PretalxTableFieldEditor.vue) tracks the actual flags and reacts to these
 * emits.
 */
defineProps<{
  locked: boolean
  hidden: boolean
}>()

const emit = defineEmits<{
  'toggle-locked': []
  'toggle-hidden': []
}>()
</script>

<template>
  <span class="option-flag-toggle">
    <button
      type="button"
      :class="['option-flag-btn', locked && 'option-flag-btn--active']"
      title="Prohibit overwrite — shown, pre-filled, but disabled in the Content Editor"
      @click="emit('toggle-locked')"
    >
      <i :class="locked ? 'pi pi-lock' : 'pi pi-lock-open'"></i>
    </button>
    <button
      type="button"
      :class="['option-flag-btn', hidden && 'option-flag-btn--active']"
      title="Hide from user — doesn't show in the Content Editor at all"
      @click="emit('toggle-hidden')"
    >
      <i :class="hidden ? 'pi pi-eye-slash' : 'pi pi-eye'"></i>
    </button>
  </span>
</template>

<style scoped>
.option-flag-toggle {
  display: inline-flex;
  gap: 0.2rem;
  margin-left: 0.4rem;
  vertical-align: middle;
}

.option-flag-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4rem;
  height: 1.4rem;
  border: 1px solid var(--p-surface-300, #cbd5e1);
  border-radius: 4px;
  background: white;
  color: #94a3b8;
  cursor: pointer;
  font-size: 0.7rem;
  padding: 0;
  line-height: 1;
}

.option-flag-btn:hover {
  border-color: var(--p-primary-color, #3b82f6);
  color: var(--p-primary-color, #3b82f6);
}

.option-flag-btn--active {
  background: var(--p-primary-color, #3b82f6);
  border-color: var(--p-primary-color, #3b82f6);
  color: white;
}
</style>
