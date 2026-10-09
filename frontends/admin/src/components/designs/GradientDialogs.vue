<script setup lang="ts">
import { computed } from 'vue'
import { useRightsStore } from '../../stores/rights'
import { useGradients, GRADIENT_SHAPE_OPTIONS, GRADIENT_SIZE_OPTIONS } from '../../composables/designs/useGradients'
import DialogTitle from '../DialogTitle.vue'
import ColorPicker from '../ColorPicker.vue'
import ColorPalettePicker from '../ColorPalettePicker.vue'
import Dialog from 'primevue/dialog'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Dropdown from 'primevue/dropdown'
import Checkbox from 'primevue/checkbox'

// The three Gradient dialogs of the Designs page: the library (manage), create/edit, and copy.
// The state and actions live in composables/designs/useGradients.ts.
const grad = useGradients()
const rightsStore = useRightsStore()
const canCreate = computed(() => rightsStore.can('designs.create'))
const canEdit = computed(() => rightsStore.can('designs.edit'))
const canDelete = computed(() => rightsStore.can('designs.delete'))
</script>

<template>
<!-- Manage Gradients Dialog -->
<Dialog v-model:visible="grad.showManageDialog" modal :style="{ width: '600px' }">
  <template #header>
    <DialogTitle icon="pi-sliders-h" title="Manage Gradients" />
  </template>
  <div class="gradient-manage-header">
    <Button v-if="canCreate" label="New Gradient" icon="pi pi-plus" size="small" @click="grad.openNew" />
  </div>
  <div v-if="!grad.gradients.length" class="hint">No gradients yet.</div>
  <div v-else class="gradient-list">
    <div v-for="g in grad.gradients" :key="g.id" class="gradient-list-item">
      <div class="gradient-list-swatch" :style="{ backgroundImage: grad.cssFor(g) }"></div>
      <div class="gradient-list-label">{{ g.name }} <small class="hint">({{ g.type }})</small></div>
      <div class="action-buttons">
        <Button v-if="canEdit" icon="pi pi-pencil" size="small" outlined title="Edit" @click="grad.openEdit(g)" />
        <Button v-if="canCreate" icon="pi pi-copy" size="small" outlined title="Copy" @click="grad.openCopy(g)" />
        <Button v-if="canDelete" icon="pi pi-trash" size="small" severity="danger" outlined title="Delete" @click="grad.remove(g)" />
      </div>
    </div>
  </div>
  <template #footer>
    <Button label="Close" @click="grad.showManageDialog = false" />
  </template>
</Dialog>

<!-- Copy Gradient Dialog -->
<Dialog v-model:visible="grad.showCopyDialog" modal :style="{ width: '400px' }">
  <template #header>
    <DialogTitle icon="pi-copy" title="Copy Gradient" />
  </template>
  <div class="field">
    <label for="copy-gradient-name">New Name</label>
    <InputText
      id="copy-gradient-name"
      v-model="grad.copyName"
      class="w-full"
      autofocus
      @keyup.enter="grad.executeCopy"
    />
  </div>
  <template #footer>
    <Button label="Cancel" @click="grad.showCopyDialog = false" text />
    <Button label="Copy" icon="pi pi-copy" @click="grad.executeCopy" :disabled="!grad.copyName.trim()" />
  </template>
</Dialog>

<!-- Edit Gradient Dialog -->
<Dialog
  v-model:visible="grad.showEditDialog"
  modal
  :style="{ width: '500px' }"
>
  <template #header>
    <DialogTitle icon="pi-sliders-h" :title="grad.isNew ? 'New Gradient' : 'Edit Gradient'" />
  </template>
  <div class="dialog-content">
    <div class="field">
      <label>Name</label>
      <InputText v-model="grad.editForm.name" size="small" class="w-full" />
    </div>
    <div class="position-grid">
      <div class="field">
        <label>Type</label>
        <Dropdown
          v-model="grad.editForm.type"
          :options="[{ label: 'Linear', value: 'linear' }, { label: 'Radial', value: 'radial' }, { label: 'Conic', value: 'conic' }]"
          optionLabel="label"
          optionValue="value"
          size="small"
          class="w-full"
        />
      </div>
      <div class="field repeating-field">
        <label>&nbsp;</label>
        <div class="repeating-checkbox-row">
          <Checkbox v-model="grad.editForm.repeating" binary inputId="gradient-repeating" />
          <label for="gradient-repeating">Repeating</label>
        </div>
      </div>
    </div>

    <div v-if="grad.editForm.type !== 'radial'" class="field">
      <label>{{ grad.editForm.type === 'conic' ? 'Start Angle (deg)' : 'Angle (deg)' }}</label>
      <InputNumber v-model="grad.editForm.angle" :min="0" :max="360" size="small" class="w-full" />
    </div>

    <div v-if="grad.editForm.type === 'radial'" class="position-grid">
      <div class="field">
        <label>Shape</label>
        <Dropdown v-model="grad.editForm.shape" :options="GRADIENT_SHAPE_OPTIONS" optionLabel="label" optionValue="value" size="small" class="w-full" />
      </div>
      <div class="field">
        <label>Size</label>
        <Dropdown v-model="grad.editForm.size" :options="GRADIENT_SIZE_OPTIONS" optionLabel="label" optionValue="value" size="small" class="w-full" />
      </div>
    </div>

    <div v-if="grad.editForm.type !== 'linear'" class="position-grid">
      <div class="field">
        <label>Position X (%)</label>
        <InputNumber v-model="grad.editForm.position_x" :min="0" :max="100" size="small" class="w-full" />
      </div>
      <div class="field">
        <label>Position Y (%)</label>
        <InputNumber v-model="grad.editForm.position_y" :min="0" :max="100" size="small" class="w-full" />
      </div>
    </div>

    <div class="field">
      <label>Color Stops</label>
      <div v-for="(stop, idx) in grad.editForm.stops" :key="idx" class="gradient-stop-row">
        <ColorPicker
          :model-value="grad.resolveStopColorHex(stop)"
          @update:model-value="(v) => { stop.color = v || ''; stop.ref = undefined }"
        />
        <ColorPalettePicker :palette="grad.palette" @select="(c) => grad.setStopColorRef(stop, c)" />
        <InputNumber v-model="stop.position" :min="0" :max="100" suffix=" %" size="small" style="width: 110px" title="Position" />
        <InputNumber v-model="stop.opacity" :min="0" :max="100" suffix=" %" size="small" style="width: 110px" title="Opacity" />
        <Button
          icon="pi pi-trash" text size="small" severity="danger" title="Remove stop"
          :disabled="grad.editForm.stops.length <= 2"
          @click="grad.removeStop(idx)"
        />
      </div>
      <Button label="Add Stop" icon="pi pi-plus" text size="small" @click="grad.addStop" />
    </div>

    <div class="field">
      <label>Preview</label>
      <div class="gradient-preview-box" :style="{ backgroundImage: grad.editPreview }"></div>
    </div>
  </div>
  <template #footer>
    <Button label="Cancel" @click="grad.showEditDialog = false" text />
    <Button label="Save" @click="grad.saveEdit" />
  </template>
</Dialog>
</template>

<style scoped>
.hint {
  color: #888;
  font-size: 0.75rem;
}

.position-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem 1rem;
}

.gradient-preview-box {
  margin-top: 0.6rem;
  height: 60px;
  border-radius: 6px;
  border: 1px solid var(--p-content-border-color, #ddd);
  background-size: cover;
}

.gradient-manage-header {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 0.75rem;
}

.gradient-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.gradient-list-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.4rem 0.5rem;
  border: 1px solid var(--p-content-border-color, #ddd);
  border-radius: 6px;
}

.gradient-list-swatch {
  width: 48px;
  height: 32px;
  border-radius: 4px;
  border: 1px solid var(--p-content-border-color, #ddd);
  flex-shrink: 0;
  background-size: cover;
}

.gradient-list-label {
  flex: 1;
  min-width: 0;
}

.gradient-stop-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.4rem;
}

.repeating-field {
  justify-content: flex-end;
}

.repeating-checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  height: 2.25rem;
}
</style>
