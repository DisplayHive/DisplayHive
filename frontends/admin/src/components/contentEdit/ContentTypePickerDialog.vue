<script setup lang="ts">
import { useContentEditor } from '../../composables/contentEdit/useContentEditor'
import DialogTitle from '../DialogTitle.vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Dialog from 'primevue/dialog'

// Step 1 of a new content element: choose its content type.
const ed = useContentEditor()
</script>

<template>
<Dialog
  v-model:visible="ed.showSelectContentTypeDialog"
  modal
  :style="{ width: '600px' }"
>
  <template #header>
      <DialogTitle icon="pi-list" title="Select Content Type" />
    </template>
  <div class="contenttype-list">
    <Card
      v-for="ct in ed.contentTypes"
      :key="ct.id"
      :data-tour="`contenttype-card-${ct.id}`"
      class="contenttype-card"
      @click="ed.selectContentType(ct)"
    >
      <template #title>{{ ct.name }}</template>
      <template #content>
        <p v-if="ct.description" class="text-muted">{{ ct.description }}</p>
      </template>
    </Card>
    <div v-if="ed.contentTypes.length === 0" class="empty-state">
      <i class="pi pi-inbox"></i>
      <p>No content types available</p>
    </div>
  </div>
  <template #footer>
    <Button label="Cancel" @click="ed.goBack" text />
  </template>
</Dialog>
</template>

<style scoped>
.contenttype-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
  max-height: 400px;
  overflow-y: auto;
}

.contenttype-card {
  cursor: pointer;
  transition: all 0.2s;
}

.contenttype-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}
</style>
