<script setup lang="ts">
import { useLayoutEditor } from '../../composables/layoutEditor/useLayoutEditor'
import CollapsibleCard from './CollapsibleCard.vue'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Tag from 'primevue/tag'

// The Layout's aspect-ratio variations: switch between them, add and remove.
const ed = useLayoutEditor()

</script>

<template>
  <CollapsibleCard card-key="ratios" icon="pi-arrows-h" title="Aspect Ratio Variations" class="editor-ratio-card" data-tour="layout-aspect-ratios">
    <div class="ratio-list">
      <div
        v-for="r in ed.layoutRatioList"
        :key="r"
        class="ratio-row"
        :class="{ active: r === ed.activeRatio }"
        role="button"
        tabindex="0"
        @click="ed.selectRatio(r)"
        @keydown.enter.prevent="ed.selectRatio(r)"
      >
        <span class="ratio-name">{{ r }}<span v-if="r === ed.BASE_ASPECT_RATIO" class="hint"> (base)</span></span>
        <Tag :value="`${ed.idsOfLayoutAt(ed.layout, r).length} containers`" severity="secondary" />
        <Button
          v-if="r !== ed.BASE_ASPECT_RATIO"
          icon="pi pi-trash" text size="small" severity="danger" title="Remove this variation"
          @click.stop="ed.confirmDeleteVariation(r)"
        />
      </div>
    </div>
    <div class="ratio-add">
      <Select
        v-model="ed.newVariationRatio"
        :options="ed.addableRatios"
        placeholder="Add variation…"
        :disabled="!ed.addableRatios.length"
        class="ratio-add-select"
      />
      <Button icon="pi pi-plus" label="Add" size="small" outlined :disabled="!ed.newVariationRatio" @click="ed.addVariation" />
    </div>
    <p class="hint">
      A new variation starts as a copy of 16:9. Add or remove containers per variation; positions are per ratio,
      everything else about a container is shared.
      <template v-if="!ed.addableRatios.length">More ratios are added on the Designs page.</template>
    </p>
  </CollapsibleCard>
</template>

<style scoped>
.editor-ratio-card {
  width: 100%;
}

.ratio-list {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  margin-bottom: 0.75rem;
}

.ratio-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0.5rem;
  border: 1px solid var(--p-content-border-color, #ddd);
  border-radius: 6px;
  cursor: pointer;
}

.ratio-row:hover {
  background: var(--p-content-hover-background, rgba(128, 128, 128, 0.1));
}

.ratio-row.active {
  border-color: var(--p-primary-color, #6366f1);
  background: var(--p-highlight-background, rgba(99, 102, 241, 0.12));
}

.ratio-name {
  flex: 1;
  font-weight: 600;
}

.ratio-add {
  display: flex;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}

.ratio-add-select {
  flex: 1;
  min-width: 0;
}

.hint {
  color: var(--p-text-muted-color, #888);
  font-size: 0.75rem;
  margin: 0;
}
</style>
