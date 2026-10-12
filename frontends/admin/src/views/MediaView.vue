<script setup lang="ts">
import { useConfirmAction } from '../composables/useConfirmAction'
import PageActions from '../components/PageActions.vue'
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAck, type Ack } from '../composables/useAck'
import { useToast } from 'primevue/usetoast'
import { useMediaStore } from '../stores/media'
import { useRightsStore } from '../stores/rights'
import { deleteWarning, isUnused } from '../utils/mediaUsage'
import MediaEditDialog from '../components/media/MediaEditDialog.vue'
import MediaUploadDialog from '../components/media/MediaUploadDialog.vue'
import SelectButton from 'primevue/selectbutton'
import type { MediaItem } from '../types/models'

// PrimeVue components
import Card from 'primevue/card'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'

const toast = useToast()
const { confirmDanger } = useConfirmAction()
const { request } = useAck()
const mediaStore = useMediaStore()
const rightsStore = useRightsStore()

const canUpload = computed(() => rightsStore.can('media.upload'))
const canDelete = computed(() => rightsStore.can('media.delete'))
const canEdit = computed(() => rightsStore.can('media.rename') || rightsStore.can('media.tag'))

const selectedFolder = ref<string>('')
// `/media?search=<file>` (from the command palette) arrives with the search already typed.
const route = useRoute()
const filterText = ref(typeof route.query.search === 'string' ? route.query.search : '')
const selectedTags = ref<string[]>([])
const usageFilter = ref<'all' | 'unused' | 'used'>('all')
const usageOptions = [
  { label: 'All', value: 'all' },
  { label: 'Unused', value: 'unused' },
  { label: 'In use', value: 'used' },
]
const unusedCount = computed(() => mediaStore.mediaItems.filter(isUnused).length)

const filteredMedia = computed(() => {
  let items = mediaStore.mediaItems
  if (selectedFolder.value) items = items.filter((m) => m.folder === selectedFolder.value)
  if (selectedTags.value.length > 0) {
    const sel = selectedTags.value.map((s) => s.toLowerCase())
    items = items.filter((m) => (m.tags || []).some((t) => sel.includes(t.toLowerCase())))
  }
  if (usageFilter.value !== 'all') items = items.filter((m) => isUnused(m) === (usageFilter.value === 'unused'))
  if (filterText.value) {
    const search = filterText.value.toLowerCase()
    items = items.filter(
      (m) =>
        m.title?.toLowerCase().includes(search) ||
        m.filename?.toLowerCase().includes(search) ||
        m.tags?.some((t) => t.toLowerCase().includes(search))
    )
  }
  return items
})

const toggleTag = (tag: string) => {
  const idx = selectedTags.value.indexOf(tag)
  if (idx === -1) selectedTags.value.push(tag)
  else selectedTags.value.splice(idx, 1)
}

const clearTagFilters = () => { selectedTags.value = [] }

const showUploadDialog = ref(false)
const showEditDialog = ref(false)
const editingItem = ref<MediaItem | null>(null)

const openEditDialog = (item: MediaItem) => {
  editingItem.value = item
  showEditDialog.value = true
}

onMounted(() => {
  mediaStore.fetch()
})

const deleteMedia = (item: MediaItem) => {
  confirmDanger({
    message: `Are you sure you want to delete "${item.title || item.filename}"?${deleteWarning(item)}`,
    // The server pushes the new list itself (no fetch() behind the delete).
    accept: async () => {
      await request('displayhive:media:cts:delete_media', { id: item.id }, { success: 'Media deleted', error: 'Could not delete the media' })
    },
  })
}

const syncingPreviews = ref(false)
const syncPreviews = async () => {
  syncingPreviews.value = true
  try {
    const ack = await request<Ack & {
      total?: number
      missing?: number
      regenerated?: number
      skipped_no_source?: number
    }>('displayhive:media:cts:sync_previews', undefined, { error: 'Failed to sync previews' })
    if (!ack) return
    if (!ack.missing) {
      toast.add({ severity: 'success', summary: 'Up to date', detail: `All ${ack.total} images have previews`, life: 3000 })
    } else {
      const parts = [`${ack.regenerated} of ${ack.missing} missing preview(s) regenerated`]
      if (ack.skipped_no_source) parts.push(`${ack.skipped_no_source} skipped (original file missing)`)
      // (The server pushes the refreshed list itself when it regenerated something.)
      toast.add({ severity: 'success', summary: 'Previews synced', detail: parts.join(' — '), life: 5000 })
    }
  } finally {
    syncingPreviews.value = false
  }
}

const isImage = (mimetype: string) => mimetype?.startsWith('image/')
const isVideo = (mimetype: string) => mimetype?.startsWith('video/')

const copyUrl = (url: string) => {
  navigator.clipboard.writeText(url).then(() => {
    toast.add({ severity: 'info', summary: 'Copied', detail: 'URL copied to clipboard', life: 2000 })
  })
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('media.page')" class="media-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Media page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="media-page" class="media-view">
    <PageActions
      :primary="canUpload ? { label: 'Upload', icon: 'pi pi-upload', tour: 'media-upload', onClick: () => (showUploadDialog = true) } : null"
      :secondary="[canUpload && { label: 'Sync Previews', icon: 'pi pi-sync', tour: 'media-sync-previews', title: 'Count images vs. previews and regenerate any missing ones', loading: syncingPreviews, onClick: syncPreviews }]"
    />
    <div class="media-content">
      <Card>
        <template #content>
          <div class="tag-cloud" data-tour="media-tag-cloud">
            <div class="tag-cloud-list">
              <span
                v-for="t in mediaStore.allTags"
                :key="t.tag"
                class="tag-pill"
                :class="{ selected: selectedTags.includes(t.tag) }"
                role="button"
                tabindex="0"
                @click="toggleTag(t.tag)"
              >
                {{ t.tag }}
                <small class="tag-count">{{ t.count }}</small>
              </span>
            </div>
            <div class="tag-cloud-actions">
              <Button label="Clear tag selection" text size="small" @click="clearTagFilters" />
            </div>
          </div>

          <div class="filter-bar">
            <InputText v-model="filterText" data-tour="media-search-field" placeholder="Search media..." class="filter-input" />
            <SelectButton
              v-model="usageFilter"
              data-tour="media-usage-filter"
              :options="usageOptions"
              option-label="label"
              option-value="value"
              :allow-empty="false"
              size="small"
              :title="`${unusedCount} file(s) are not used anywhere`"
            />
            <Tag :value="`${filteredMedia.length} items`" />
          </div>

          <div class="media-grid" data-tour="media-grid" v-if="!mediaStore.loading">
            <div
              v-for="item in filteredMedia"
              :key="item.id"
              class="media-item"
            >
              <div class="media-preview">
                <Tag
                  v-if="isUnused(item)"
                  class="media-unused-tag"
                  value="Unused"
                  severity="warn"
                  title="Not used by any content, preset, container default, design or setting"
                />
                <img v-if="isImage(item.mimetype)" :src="item.preview_url || item.url" :alt="item.title" />
                <video v-else-if="isVideo(item.mimetype)" :src="item.url" />
                <div v-else class="file-icon">
                  <i class="pi pi-file"></i>
                </div>
              </div>
              <div class="media-info">
                <span class="media-title">{{ item.title || item.filename }}</span>
                <span class="media-filename">{{ item.filename }}</span>
                <span v-if="item.url" class="media-url-row">
                  <a :href="item.url" class="media-url" target="_blank" :title="item.url">{{ item.url }}</a>
                  <i class="pi pi-copy media-url-copy" data-tour="media-item-url-copy" :title="'Copy URL'" @click.prevent="copyUrl(item.url)" />
                </span>
                <div class="media-tags" v-if="item.tags?.length">
                  <Tag v-for="(tag, ti) in item.tags" :key="tag + ti" :value="tag" severity="secondary" />
                  <!-- If there are many tags, keep layout tidy by limiting visual overflow -->
                  <!-- The CSS will wrap tags; consider adding a '+N' indicator in future if desired -->
                </div>
              </div>
              <div class="media-actions">
                <Button v-if="canEdit" data-tour="media-item-edit" icon="pi pi-pencil" @click="openEditDialog(item)" size="small" outlined title="Edit" />
                <Button v-if="canDelete" data-tour="media-item-delete" icon="pi pi-trash" @click="deleteMedia(item)" size="small" severity="danger" outlined title="Delete" />
              </div>
            </div>
          </div>

          <div class="loading-state" v-if="mediaStore.loading">
            <i class="pi pi-spin pi-spinner"></i>
            <p>Loading media...</p>
          </div>

          <div class="empty-state" v-if="!mediaStore.loading && filteredMedia.length === 0">
            <i class="pi pi-images"></i>
            <p>No media files found</p>
          </div>
        </template>
      </Card>
    </div>

    <MediaEditDialog v-model:visible="showEditDialog" :item="editingItem" />
    <MediaUploadDialog v-model:visible="showUploadDialog" :folder="selectedFolder" />
  </div>
</template>

<style scoped src="../components/media/tagPill.css"></style>
<style scoped>
.media-view {
  display: flex;
  gap: 1rem;
  height: calc(100vh - 150px);
}
/* No title text left in the card header — keep the action buttons
   right-aligned instead of collapsing to the start. */
.card-header {
  justify-content: flex-end;
}
.media-content {
  flex: 1;
  overflow: hidden;
}
.filter-bar {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  align-items: center;
}
.tag-cloud {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.tag-cloud-list {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}
.tag-pill.selected {
  background: var(--p-primary-color, #3b82f6);
  color: white;
  border-color: rgba(255,255,255,0.1);
}
.tag-cloud-actions {
  flex-shrink: 0;
}
.media-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
  max-height: calc(100vh - 350px);
  overflow-y: auto;
}
.media-item {
  background: var(--p-content-background, #f9f9f9);
  border: 1px solid var(--p-content-border-color, #e0e0e0);
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.2s;
}
.media-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}
.media-preview {
  position: relative;
  height: 150px;
  background: var(--p-surface-200, #ddd);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.media-preview img,
.media-preview video {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.file-icon {
  color: var(--p-text-muted-color, #888);
  font-size: 3rem;
}
.media-info {
  padding: 0.75rem;
}
.media-title {
  display: block;
  font-weight: 600;
  font-size: 0.9rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.media-filename {
  display: block;
  font-size: 0.75rem;
  color: var(--p-text-muted-color, #888);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
/* Dark mode: --p-surface-200 is a fixed ramp point, kept as the light-mode
   placeholder shade above — see docs/developer/styleguide.md. */
.dark-mode .media-preview {
  background: var(--p-surface-700, #334155);
}
.media-url-row {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  margin-top: 0.1rem;
  min-width: 0;
}
.media-url {
  font-size: 0.7rem;
  color: var(--p-primary-color, #6366f1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  text-decoration: none;
  flex: 1;
  min-width: 0;
}
.media-url:hover {
  text-decoration: underline;
}
.media-url-copy {
  font-size: 0.7rem;
  color: var(--p-text-muted-color, #9ca3af);
  flex-shrink: 0;
  cursor: pointer;
}
.media-url-copy:hover {
  color: var(--p-primary-color, #6366f1);
}
.media-tags {
  display: flex;
  gap: 0.25rem;
  margin-top: 0.5rem;
  flex-wrap: wrap;
}
.media-actions {
  padding: 0.5rem 0.75rem;
  border-top: 1px solid var(--p-content-border-color, #e0e0e0);
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}
/* Badge for a file nothing uses — a theme-aware PrimeVue Tag, so no dark-mode override needed. */
.media-unused-tag {
  position: absolute;
  top: 0.4rem;
  left: 0.4rem;
  z-index: 1;
}
</style>
