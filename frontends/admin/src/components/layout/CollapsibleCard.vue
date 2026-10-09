<script setup lang="ts">
import { useLayoutEditor } from '../../composables/layoutEditor/useLayoutEditor'
import Card from 'primevue/card'

// A card of the editor's side columns whose header collapses its content (local UI state,
// never persisted; all start expanded).
defineProps<{ cardKey: string; icon: string; title: string }>()
const ed = useLayoutEditor()
</script>

<template>
  <Card>
    <template #title>
      <div
        class="card-header-title card-header-collapsible" role="button" tabindex="0"
        :aria-expanded="!ed.collapsedCards[cardKey]"
        @click="ed.toggleCard(cardKey)" @keydown.enter.prevent="ed.toggleCard(cardKey)" @keydown.space.prevent="ed.toggleCard(cardKey)"
      >
        <i :class="['pi', icon, 'card-header-icon']" />
        <span v-html="title" />
        <i class="pi card-header-chevron" :class="ed.collapsedCards[cardKey] ? 'pi-chevron-down' : 'pi-chevron-up'" />
      </div>
    </template>
    <template #content>
      <div v-show="!ed.collapsedCards[cardKey]">
        <slot />
      </div>
    </template>
  </Card>
</template>

<style scoped>
.card-header-collapsible {
  cursor: pointer;
  user-select: none;
}

.card-header-chevron {
  margin-left: auto;
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #6b7280);
}
</style>
