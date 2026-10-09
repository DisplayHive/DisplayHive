<script setup lang="ts">
import { useLayoutEditor } from '../../composables/layoutEditor/useLayoutEditor'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'

// The left column: a search box and the two lists of containers (used in this Layout / available).
const ed = useLayoutEditor()
</script>

<template>
<div class="editor-left-column">
  <div class="container-filter">
    <i class="pi pi-search container-filter-icon"></i>
    <InputText v-model="ed.containerFilterText" size="small" class="w-full" placeholder="Search containers…" />
    <button v-if="ed.containerFilterText" type="button" class="container-filter-clear" title="Clear" @click="ed.containerFilterText = ''">
      <i class="pi pi-times"></i>
    </button>
  </div>

  <Card class="editor-used-card">
    <template #title>
      <div class="card-header-title">
        <i class="pi pi-check-square card-header-icon" />
        <span>Used in this Layout</span>
      </div>
    </template>
    <template #content>
      <div class="sidebar-list">
        <div
          v-for="c in ed.filteredPlacedContainers"
          :key="c.id"
          class="sidebar-item"
          :class="{ selected: ed.selectedId === c.id }"
          @click="ed.selectedId = c.id"
        >
          <i class="pi pi-th-large"></i>
          <span class="sidebar-item-label">{{ ed.contentFor(c).name }} <span class="hint">#{{ c.id }}</span></span>
          <button type="button" class="sidebar-icon-btn" title="Remove from Layout" @click.stop.prevent="ed.removeFromLayout(c.id)">
            <i class="pi pi-minus"></i>
          </button>
        </div>
        <p v-if="!ed.placedContainers.length" class="hint">No containers placed in this layout yet.</p>
        <p v-else-if="!ed.filteredPlacedContainers.length" class="hint">No containers match "{{ ed.containerFilterText }}".</p>
      </div>
    </template>
  </Card>

  <Card class="editor-containers-card">
    <template #title>
      <div class="card-header-title">
        <i class="pi pi-th-large card-header-icon" />
        <span>Containers</span>
      </div>
    </template>
    <template #content>
      <Button label="New Container" icon="pi pi-plus" size="small" class="w-full" @click="ed.addNewContainerViaButton" />
      <h4>Available Containers</h4>
      <p class="hint">Drag one onto the canvas to add it to this Layout.</p>
      <div class="sidebar-list">
        <div
          v-for="c in ed.filteredAvailableContainers"
          :key="c.id"
          class="sidebar-item"
          :class="{ selected: ed.selectedId === c.id }"
          draggable="true"
          @click="ed.selectedId = c.id"
          @dragstart="ed.onSidebarDragStart($event, c)"
        >
          <i class="pi pi-th-large"></i>
          <span class="sidebar-item-label">{{ ed.contentFor(c).name }} <span class="hint">#{{ c.id }}</span></span>
          <button
            type="button"
            class="sidebar-icon-btn"
            :class="{ disabled: !ed.canDeleteContainer(c) }"
            :title="ed.canDeleteContainer(c) ? 'Delete container entirely' : 'In use — cannot delete'"
            @click.stop.prevent="ed.confirmDeleteContainer(c.id)"
          >
            <i class="pi pi-times"></i>
          </button>
        </div>
        <p v-if="!ed.availableContainers.length" class="hint">All containers are already in this layout.</p>
        <p v-else-if="!ed.filteredAvailableContainers.length" class="hint">No containers match "{{ ed.containerFilterText }}".</p>
      </div>
    </template>
  </Card>
</div>
</template>

<style scoped>
.editor-left-column {
  flex: 0 0 260px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: sticky;
  top: 1rem;
}

.editor-used-card,
.editor-containers-card {
  width: 100%;
}

.container-filter {
  position: relative;
  display: flex;
  align-items: center;
}

.container-filter-icon {
  position: absolute;
  left: 0.6rem;
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #888);
  pointer-events: none;
}

.container-filter :deep(input) {
  padding-left: 1.8rem;
  padding-right: 1.8rem;
}

.container-filter-clear {
  position: absolute;
  right: 0.4rem;
  width: 18px;
  height: 18px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--p-text-muted-color, #888);
  cursor: pointer;
  font-size: 0.65rem;
  border-radius: 3px;
}

.container-filter-clear:hover {
  background: rgba(0, 0, 0, 0.08);
  color: var(--p-text-color, #333);
}

.hint {
  color: var(--p-text-muted-color, #888);
  font-size: 0.75rem;
  margin: 0;
}

.editor-left-column h4 {
  margin: 0;
  font-size: 0.9rem;
}

.sidebar-list {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.sidebar-item {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--p-content-border-color, #ddd);
  border-radius: 4px;
  cursor: grab;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  background: var(--p-content-background, #fff);
}

.sidebar-item.selected {
  border-color: #2563ab;
  background: rgba(37, 99, 171, 0.08);
}

.sidebar-item:active {
  cursor: grabbing;
}

.sidebar-item-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-icon-btn {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: var(--p-text-muted-color, #666);
  cursor: pointer;
  border-radius: 3px;
  font-size: 0.7rem;
}

.sidebar-icon-btn:hover {
  background: rgba(37, 99, 171, 0.15);
  color: #2563ab;
}

.sidebar-icon-btn.disabled {
  color: var(--p-text-muted-color, #ccc);
  cursor: not-allowed;
}

.sidebar-icon-btn.disabled:hover {
  background: transparent;
  color: var(--p-text-muted-color, #ccc);
}
</style>
