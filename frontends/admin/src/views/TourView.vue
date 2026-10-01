<script setup lang="ts">
import { computed } from 'vue'
import { useRightsStore } from '../stores/rights'
import { useSettingsStore } from '../stores/settings'
import { useTourRunner } from '../tour/runner'
import { toursByCategory } from '../tour/tours'
import type { TourDefinition } from '../tour/types'

import Card from 'primevue/card'
import Button from 'primevue/button'

const rightsStore = useRightsStore()
const settingsStore = useSettingsStore()
const { start } = useTourRunner()

const userTours = computed(() => (settingsStore.hideUserTours ? [] : toursByCategory('user')))
const adminTours = computed(() => (settingsStore.hideAdminTours ? [] : toursByCategory('admin')))

const runTour = (tour: TourDefinition) => start(tour)
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('tour.page')" class="tour-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Guided Tour page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="tour-view">
    <section v-if="userTours.length" class="tour-section">
      <h2 class="tour-section-title"><i class="pi pi-user"></i> User</h2>
      <div class="tour-list">
        <Card v-for="tour in userTours" :key="tour.id" class="tour-card">
          <template #content>
            <div class="tour-card-body">
              <div class="tour-icon"><i :class="tour.icon"></i></div>
              <div class="tour-card-main">
                <h3 class="tour-name">{{ tour.title }}</h3>
                <p class="description">{{ tour.description }}</p>
                <Button label="Start Tour" icon="pi pi-play" @click="runTour(tour)" />
              </div>
            </div>
          </template>
        </Card>
      </div>
    </section>

    <section v-if="adminTours.length" class="tour-section">
      <h2 class="tour-section-title"><i class="pi pi-cog"></i> Admin Path</h2>
      <div class="tour-list">
        <Card v-for="tour in adminTours" :key="tour.id" class="tour-card">
          <template #content>
            <div class="tour-card-body">
              <div class="tour-icon"><i :class="tour.icon"></i></div>
              <div class="tour-card-main">
                <h3 class="tour-name">{{ tour.title }}</h3>
                <p class="description">{{ tour.description }}</p>
                <Button label="Start Tour" icon="pi pi-play" @click="runTour(tour)" />
              </div>
            </div>
          </template>
        </Card>
      </div>
    </section>
  </div>
</template>

<style scoped>
.tour-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  width: 100%;
}

.tour-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.tour-section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.15rem;
  font-weight: 600;
  margin: 0;
}

.tour-list {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.tour-card {
  width: 100%;
}

.tour-card-body {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.tour-icon {
  flex-shrink: 0;
  width: 96px;
  height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: var(--p-surface-100, #f3f4f6);
}

.tour-icon i {
  font-size: 2.5rem;
  color: var(--p-primary-color, #667eea);
}

.tour-card-main {
  flex: 1;
  min-width: 0;
}

.tour-name {
  margin: 0 0 0.4rem;
  font-size: 1.1rem;
  font-weight: 600;
}

.description {
  margin-bottom: 1rem;
  color: var(--p-text-muted-color, #6b7280);
}

/* Dark mode: --p-surface-100 is a fixed ramp point, kept as the light-mode
   shade above — see docs/developer/styleguide.md. */
.dark-mode .tour-icon {
  background: var(--p-surface-700, #334155);
}
</style>
