<script setup lang="ts">
import Panel from 'primevue/panel'

// One collapsible section of the Design dialog: a title with a short description, and the
// whole header row clickable (PrimeVue's Panel only toggles from its small chevron).
// `headerTour` / `sectionTour` set `data-tour` on the header row / the surrounding block.
withDefaults(
  defineProps<{
    title: string
    description: string
    /** Nested inside another panel: no surrounding block, a little space above. */
    nested?: boolean
    headerTour?: string
    sectionTour?: string
  }>(),
  { nested: false, headerTour: undefined, sectionTour: undefined },
)

const collapsed = defineModel<boolean>('collapsed', { default: true })
</script>

<template>
  <Panel
    v-if="nested"
    v-model:collapsed="collapsed"
    toggleable
    class="container-style-panel nested-panel"
  >
    <template #header>
      <div class="panel-header-clickable" :data-tour="headerTour" @click="collapsed = !collapsed">
        <span class="panel-header-title">{{ title }}</span>
        <small class="panel-header-desc">{{ description }}</small>
      </div>
    </template>
    <slot />
  </Panel>
  <div v-else class="container-styles-section" :data-tour="sectionTour">
    <Panel v-model:collapsed="collapsed" toggleable class="container-style-panel">
      <template #header>
        <div class="panel-header-clickable" :data-tour="headerTour" @click="collapsed = !collapsed">
          <span class="panel-header-title">{{ title }}</span>
          <small class="panel-header-desc">{{ description }}</small>
        </div>
      </template>
      <slot />
    </Panel>
  </div>
</template>

<style scoped>
.container-styles-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-top: 0.25rem;
}

.container-style-panel {
  font-size: 0.875rem;
}

.nested-panel {
  margin-top: 0.75rem;
}

.panel-header-clickable {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  flex: 1;
  cursor: pointer;
  padding: 0.25rem 0;
}

.panel-header-title {
  font-weight: 600;
  font-size: 0.95rem;
}

.panel-header-desc {
  font-weight: 400;
  font-size: 0.78rem;
  color: var(--p-text-muted-color, #777);
}
</style>
