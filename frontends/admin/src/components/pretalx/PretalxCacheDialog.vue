<script setup lang="ts">
import Dialog from 'primevue/dialog'
import DialogTitle from '../DialogTitle.vue'

// Read-only viewer for the cached response of a Pretalx API URL.
defineProps<{ cacheTitle: string; cacheFetchedAt: string; cacheContent: string }>()
const visible = defineModel<boolean>('visible', { default: false })
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: '900px', maxWidth: '95vw' }"
  >
    <template #header>
      <DialogTitle icon="pi-database" :title="`Cached Response — ${cacheTitle}`" />
    </template>
    <div class="cache-meta">Fetched at: {{ cacheFetchedAt }}</div>
    <pre class="cache-json">{{ cacheContent }}</pre>
  </Dialog>
</template>

<style scoped>
.cache-meta {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #6b7280);
  margin-bottom: 0.75rem;
}

.cache-json {
  background: #1a1a2e;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 6px;
  overflow: auto;
  max-height: 65vh;
  font-size: 0.78rem;
  font-family: 'Courier New', 'Consolas', monospace;
  white-space: pre;
  line-height: 1.5;
}
</style>
