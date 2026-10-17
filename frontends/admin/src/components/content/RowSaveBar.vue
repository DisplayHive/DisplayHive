<script setup lang="ts">
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import { notifyRowSaved, useRowEditState } from '../../composables/contentEdit/useRowEditSession'

// The one Save / Discard of an expanded row: it covers what was changed in the preview (the fields)
// and in the delivery settings. Shown only while something is changed.
const props = defineProps<{ rowId: number }>()
const toast = useToast()
const state = useRowEditState(props.rowId)

const save = async () => {
  const saved = await state.save()
  if (saved) toast.add({ severity: 'success', summary: 'Success', detail: 'Content updated', life: 3000 })
  // What was saved partly is shown as it is now, too.
  notifyRowSaved()
}
</script>

<template>
  <div v-if="state.dirty()" class="row-save-bar" data-testid="row-save-bar">
    <span class="row-save-hint">Unsaved changes</span>
    <Button label="Save" icon="pi pi-check" size="small" :loading="state.saving()" data-testid="row-save" @click="save" />
    <Button label="Discard" icon="pi pi-times" size="small" severity="secondary" :disabled="state.saving()" data-testid="row-discard" @click="state.discard" />
  </div>
</template>

<style scoped>
.row-save-bar {
  flex: 1 0 100%;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.5rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--p-content-border-color, #ddd);
}

.row-save-hint {
  margin-right: auto;
  font-size: 0.85rem;
  color: var(--p-text-muted-color, #6b7280);
}
</style>
