<script setup lang="ts">
import { useLayoutEditor } from '../../composables/layoutEditor/useLayoutEditor'
import CollapsibleCard from './CollapsibleCard.vue'
import ContainerDefaultContentEditor from './ContainerDefaultContentEditor.vue'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import ToggleSwitch from 'primevue/toggleswitch'

// The selected container's settings (name, position, default content) and its actions. Every edit
// is staged live; nothing is sent until the Layout is saved.
const ed = useLayoutEditor()
</script>

<template>
  <CollapsibleCard card-key="settings" icon="pi-sliders-h" title="Container Settings" class="editor-settings-card">
      <div v-if="!ed.selectedContainer" class="empty-state empty-state--compact">
        <i class="pi pi-th-large"></i>
        <p>Select a container to edit its settings.</p>
      </div>
      <div v-else class="dialog-content">
    <div class="field">
      <label>Name</label>
      <InputText v-model="ed.containerEditForm.name" size="small" class="w-full" />
    </div>
    <div class="position-grid">
      <div class="field">
        <label>Top (vh)</label>
        <InputNumber v-model="ed.containerEditForm.top" size="small" class="w-full" :min="0" :max="100" />
      </div>
      <div class="field">
        <label>Left (vw)</label>
        <InputNumber v-model="ed.containerEditForm.left" size="small" class="w-full" :min="0" :max="100" />
      </div>
      <div class="field">
        <label>Width (vw)</label>
        <InputNumber v-model="ed.containerEditForm.width" size="small" class="w-full" :min="1" :max="100" />
      </div>
      <div class="field">
        <label>Height (vh)</label>
        <InputNumber v-model="ed.containerEditForm.height" size="small" class="w-full" :min="1" :max="100" />
      </div>
    </div>
    <p class="hint">Changes here are shown live, but only saved to the server when you save this Layout.</p>

    <div class="filter-toggle">
      <label for="container-show-when-empty">Show when empty</label>
      <ToggleSwitch id="container-show-when-empty" v-model="ed.containerEditForm.show_when_empty" />
    </div>
    <p class="hint">Off: a container with no content is not shown on screens at all. On: it is, so its Container Design background and border still appear.</p>

    <div class="field">
      <label>Default Field Handler</label>
      <Dropdown
        :model-value="ed.containerEditForm.default_field_handler"
        :options="ed.DEFAULT_FIELD_HANDLER_OPTIONS"
        optionLabel="label"
        optionValue="value"
        size="small"
        class="w-full"
        @update:model-value="ed.changeDefaultHandler"
      />
      <small class="hint">Shown when no active scene currently targets this container.</small>
    </div>

    <ContainerDefaultContentEditor
      :handler="ed.containerEditForm.default_field_handler"
      v-model:content="ed.containerEditForm.default_content"
      :palette="ed.preview.designPreview?.default_colors ?? []"
    />

    <div class="selected-actions">
      <Button
        v-if="ed.hasPendingChange(ed.selectedContainer)"
        label="Reset to Default Position" icon="pi pi-refresh" outlined size="small"
        @click="ed.resetContainerPosition(ed.selectedContainer)"
      />
      <Button
        :label="ed.selectedContainer.locked ? 'Unlock Position' : 'Lock Position'"
        :icon="ed.selectedContainer.locked ? 'pi pi-lock' : 'pi pi-lock-open'"
        outlined size="small"
        @click="ed.toggleContainerLock(ed.selectedContainer)"
      />
      <Button
        :label="ed.isSelectedPlaced ? 'Remove from Layout' : 'Add to Layout'"
        :icon="ed.isSelectedPlaced ? 'pi pi-eject' : 'pi pi-plus'"
        outlined size="small"
        @click="ed.toggleSelectedLayoutMembership"
      />
      <Button
        label="Delete Container" icon="pi pi-trash" severity="danger" outlined size="small"
        :disabled="!ed.canDeleteContainer(ed.selectedContainer)"
        :title="ed.canDeleteContainer(ed.selectedContainer) ? '' : 'In use — cannot delete'"
        @click="ed.confirmDeleteContainer(ed.selectedId)"
      />
      <Button
        v-if="ed.hasAnyPendingChange(ed.selectedContainer)"
        label="Revert" icon="pi pi-undo" outlined size="small"
        @click="ed.revertContainerEdit"
      />
    </div>
      </div>
  </CollapsibleCard>
</template>

<style scoped>
.editor-settings-card {
  width: 100%;
}

.filter-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.filter-toggle label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.hint {
  color: var(--p-text-muted-color, #888);
  font-size: 0.75rem;
  margin: 0;
}

.dialog-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 0;
  overflow-x: hidden;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.field label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #666);
}

/* Two columns (Top/Left, Width/Height): four did not fit the 340px right column
   and pushed Width/Height out of view. minmax(0, 1fr) + min-width: 0 let the
   number inputs shrink instead of forcing the grid wider than the card. */
.position-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem 0.5rem;
}

.position-grid .field,
.position-grid :deep(.p-inputnumber),
.position-grid :deep(.p-inputnumber-input) {
  min-width: 0;
  width: 100%;
}

.selected-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.25rem;
}
</style>
