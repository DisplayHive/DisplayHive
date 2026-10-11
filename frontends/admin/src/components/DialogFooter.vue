<script setup lang="ts">
// The footer every form dialog uses: Cancel, an optional "Update" (save and keep the dialog
// open) and the primary action. Use it in a Dialog's `#footer` slot. It has several root
// nodes on purpose — PrimeVue's `.p-dialog-footer` flex layout applies to its direct children.
withDefaults(defineProps<{
  /** Label of the primary action. */
  confirmLabel?: string
  /** PrimeIcons class of the primary action, e.g. `pi pi-check`. */
  confirmIcon?: string
  confirmSeverity?: 'danger'
  /** Show the secondary "Update" button (save without closing). */
  showUpdate?: boolean
  /** Spinner on Update and the primary action; both are disabled while it is set. */
  loading?: boolean
  /** Disables Update and the primary action. */
  disabled?: boolean
  cancelDisabled?: boolean
  /** `data-tour` value for the Cancel button, if a tour points at it. */
  cancelTour?: string
}>(), {
  confirmLabel: 'Save',
})

defineEmits<{
  cancel: []
  update: []
  confirm: []
}>()
</script>

<template>
  <Button
    :data-tour="cancelTour"
    label="Cancel"
    text
    :disabled="cancelDisabled"
    @click="$emit('cancel')"
  />
  <Button
    v-if="showUpdate"
    label="Update"
    severity="secondary"
    outlined
    :loading="loading"
    :disabled="loading || disabled"
    @click="$emit('update')"
  />
  <Button
    :label="confirmLabel"
    :icon="confirmIcon"
    :severity="confirmSeverity"
    :loading="loading"
    :disabled="loading || disabled"
    @click="$emit('confirm')"
  />
</template>
