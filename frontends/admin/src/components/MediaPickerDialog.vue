<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useSocket } from '../composables/useSocket'

import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import Button from 'primevue/button'

interface MediaItem {
  id: number
  title: string
  filename: string
  mimetype: string
  url: string
  preview_url: string
  tags: string[]
}

const props = defineProps<{
  visible: boolean
  /** Currently selected image URL, if any — highlighted in the grid. */
  selectedUrl?: string | null
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  select: [item: MediaItem]
}>()

const { on, off, emit: socketEmit } = useSocket()

const mediaItems = ref<MediaItem[]>([])
const searchText = ref('')
const loading = ref(false)

const filtered = computed(() => {
  const q = searchText.value.toLowerCase()
  const images = mediaItems.value.filter((m) => m.mimetype.startsWith('image/'))
  if (!q) return images
  return images.filter(
    (m) => m.title?.toLowerCase().includes(q) || m.filename?.toLowerCase().includes(q),
  )
})

const handleMediaForPicker = (data: { media: MediaItem[] }) => {
  mediaItems.value = data.media || []
  loading.value = false
}

onMounted(() => {
  on('displayhive:admin:stc:media_for_picker', handleMediaForPicker)
})

onUnmounted(() => {
  off('displayhive:admin:stc:media_for_picker', handleMediaForPicker)
})

// Fetch fresh each time the dialog opens.
watch(() => props.visible, (v) => {
  if (!v) return
  searchText.value = ''
  loading.value = true
  socketEmit('displayhive:admin:cts:get_media_for_picker')
})

const selectItem = (item: MediaItem) => {
  emit('select', item)
  emit('update:visible', false)
}
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="(v) => emit('update:visible', v)"
    header="Select Image"
    modal
    :style="{ width: '860px', maxWidth: '95vw' }"
  >
    <div class="picker-toolbar">
      <InputText v-model="searchText" placeholder="Search images…" class="picker-search" />
      <Tag :value="`${filtered.length} images`" />
    </div>
    <div v-if="loading" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem" />
      <p>Loading media…</p>
    </div>
    <div v-else-if="filtered.length === 0" class="empty-state">
      <i class="pi pi-images" style="font-size: 3rem" />
      <p>No images found</p>
    </div>
    <div v-else class="picker-grid">
      <div
        v-for="item in filtered"
        :key="item.id"
        class="picker-item"
        :class="{ 'picker-item--selected': selectedUrl === item.url }"
        @click="selectItem(item)"
      >
        <div class="picker-thumb">
          <img :src="item.preview_url || item.url" :alt="item.title" />
        </div>
        <div class="picker-label">{{ item.title || item.filename }}</div>
      </div>
    </div>
    <template #footer>
      <Button label="Cancel" text @click="emit('update:visible', false)" />
    </template>
  </Dialog>
</template>

<style scoped>
.picker-toolbar {
  display: flex;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1rem;
}

.picker-search {
  flex: 1;
  max-width: 320px;
}

.picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 0.75rem;
  max-height: 460px;
  overflow-y: auto;
  padding: 0.25rem;
}

.picker-item {
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}

.picker-item:hover {
  border-color: var(--p-primary-color, #3b82f6);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.15);
}

.picker-item--selected {
  border-color: var(--p-primary-color, #3b82f6);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
}

.picker-thumb {
  width: 100%;
  height: 90px;
  background: #f1f5f9;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
}

.picker-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.picker-label {
  padding: 0.3rem 0.4rem;
  font-size: 0.75rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  background: white;
}
</style>
