<script setup lang="ts">
import { useLayoutEditor } from '../../composables/layoutEditor/useLayoutEditor'
import CollapsibleCard from './CollapsibleCard.vue'
import Button from 'primevue/button'
import InputNumber from 'primevue/inputnumber'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import ToggleSwitch from 'primevue/toggleswitch'

// Local preview toggles and the snaplines.
const ed = useLayoutEditor()

</script>

<template>
  <CollapsibleCard card-key="options" icon="pi-eye" title="Preview &amp; Guides" class="editor-options-card">
    <div class="preview-toggles">
      <div class="filter-toggle">
        <label for="disable-animations-preview">Disable animations in Preview</label>
        <ToggleSwitch id="disable-animations-preview" v-model="ed.preview.disableAnimationsInPreview" />
      </div>
      <div class="filter-toggle">
        <label for="disable-backdrop-preview">Disable Backdrop in Preview</label>
        <ToggleSwitch id="disable-backdrop-preview" v-model="ed.preview.disableBackdropInPreview" />
      </div>
      <div class="filter-toggle">
        <label for="disable-default-content-preview">Disable default content in Preview</label>
        <ToggleSwitch id="disable-default-content-preview" v-model="ed.preview.disableDefaultContentInPreview" />
      </div>
      <div class="filter-toggle">
        <label for="hide-handler-elements">Disable Handlerelements</label>
        <ToggleSwitch id="hide-handler-elements" v-model="ed.preview.hideHandlerElements" />
      </div>
    </div>

    <div class="snapline-bar">
      <Select v-model="ed.newSnaplineAxis" :options="[{ label: 'Horizontal', value: 'h' }, { label: 'Vertical', value: 'v' }]" optionLabel="label" optionValue="value" class="snapline-axis-select" />
      <InputNumber v-model="ed.newSnaplinePosition" :min="0" :max="100" suffix="%" class="snapline-position-input" />
      <Button label="Add Snapline" icon="pi pi-plus" size="small" outlined @click="ed.addSnapline" />
      <div class="snapline-chip-list">
        <Tag v-for="(line, i) in ed.snaplines" :key="i" class="snapline-chip">
          {{ line.axis === 'h' ? 'H' : 'V' }} @ {{ line.position }}%
          <i class="pi pi-times snapline-chip-remove" @click="ed.removeSnapline(i)"></i>
        </Tag>
      </div>
    </div>
  </CollapsibleCard>
</template>

<style scoped>
.editor-options-card {
  width: 100%;
}

.preview-toggles {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1rem;
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

.snapline-bar {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.5rem;
}

.snapline-axis-select {
  width: 100%;
}

.snapline-position-input {
  width: 100%;
}

.snapline-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.snapline-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.snapline-chip-remove {
  cursor: pointer;
  font-size: 0.7rem;
}
</style>
