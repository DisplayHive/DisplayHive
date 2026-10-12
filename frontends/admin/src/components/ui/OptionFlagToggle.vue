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
  /* PrimeVue's input-like components (InputNumber, InputText, ...) set
     position: relative on their own root for their internal focus/decoration
     layer. A positioned sibling always paints above a plain position: static
     one — regardless of DOM order or whether their layout boxes actually
     overlap — so without this, that layer can silently paint over this
     toggle whenever it sits right next to one of those controls (seen with
     FieldValueEditor.vue's image-size-row: the toggle was in the DOM with
     correct non-overlapping coordinates, but invisible until given its own
     stacking context). Match it with position + z-index so this always wins. */
  position: relative;
  z-index: 1;
}

.option-flag-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4rem;
  height: 1.4rem;
  border: 1px solid var(--p-content-border-color, #cbd5e1);
  border-radius: 4px;
  /* Not --p-content-background: this button always sits inside a container
     using that same token for its own background (e.g. ContentTypesView's
     .tagconfig-preset-panel) — matching it exactly leaves nothing but a
     faint border to see, easy to miss entirely on a row with little else
     next to it (e.g. the image field's Size (vh) row). Use the token
     meant for this kind of subtle differentiation instead — same one
     IconPickerField/ContentTypesView already rely on for the same reason. */
  background: var(--p-content-hover-background, #f1f5f9);
  color: var(--p-text-muted-color, #94a3b8);
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
