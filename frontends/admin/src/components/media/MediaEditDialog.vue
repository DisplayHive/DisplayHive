<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import DialogTitle from '../ui/DialogTitle.vue'
import DialogFooter from '../ui/DialogFooter.vue'
import RouteLink from '../ui/RouteLink.vue'
import { useAck } from '../../composables/useAck'
import { useMediaStore } from '../../stores/media'
import { useRightsStore } from '../../stores/rights'
import { usageLabel, usageLink } from '../../utils/media/mediaUsage'
import type { MediaItem } from '../../types/models'

// The "Edit Media" dialog of the Media page: preview, where the file is used,
// title and the assigned/available tag clouds. Fills itself from `item` each
// time it opens and saves through the media socket action.
const props = defineProps<{ item: MediaItem | null }>()
const visible = defineModel<boolean>('visible', { default: false })

const { request } = useAck()
const mediaStore = useMediaStore()
const rightsStore = useRightsStore()
const canRename = computed(() => rightsStore.can('media.rename'))
const canTag = computed(() => rightsStore.can('media.tag'))

const isSavingMedia = ref(false)
const editForm = ref({
  id: null as number | null,
  title: '',
  preview_url: '',
  url: '',
  mimetype: '',
})
const editTags = ref<string[]>([])
const editUsedBy = ref<MediaItem['used_by']>([])
const newTagInput = ref('')

const editAssignedSet = computed(() => new Set(editTags.value.map((t) => t.toLowerCase())))

const editAvailableTags = computed(() => {
  const map = new Map<string, number>()
  mediaStore.mediaItems.forEach((m) => {
    ;(m.tags || []).forEach((t) => {
      const key = (t || '').trim()
      if (!key || editAssignedSet.value.has(key.toLowerCase())) return
      map.set(key, (map.get(key) || 0) + 1)
    })
  })
  return Array.from(map.entries())
    .map(([tag, count]) => ({ tag, count }))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag))
})

const editRemoveTag = (tag: string) => {
  if (!canTag.value) return
  editTags.value = editTags.value.filter((t) => t !== tag)
}

const editAddTag = (tag: string) => {
  if (!canTag.value) return
  const trimmed = tag.trim()
  if (!trimmed || editAssignedSet.value.has(trimmed.toLowerCase())) return
  editTags.value.push(trimmed)
}

const editNewTagKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Enter') {
    event.preventDefault()
    editAddTag(newTagInput.value)
    newTagInput.value = ''
  }
}

const load = (item: MediaItem) => {
  editForm.value = {
    id: item.id,
    title: item.title,
    preview_url: item.preview_url || item.url || '',
    url: item.url || '',
    mimetype: item.mimetype || '',
  }
  editTags.value = [...(item.tags || [])]
  editUsedBy.value = item.used_by ?? []
  newTagInput.value = ''
}

watch(visible, (open) => {
  if (open && props.item) load(props.item)
})

const saveMedia = async (keepOpen = false) => {
  isSavingMedia.value = true
  try {
    // The server pushes the refreshed media list itself.
    const ack = await request('displayhive:media:cts:update_media', {
      id: editForm.value.id, title: editForm.value.title, tags: editTags.value,
    }, { success: 'Media updated', error: 'Save failed' })
    if (ack && !keepOpen) visible.value = false
  } finally {
    isSavingMedia.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: '820px', maxWidth: '95vw' }"
  >
    <template #header>
      <DialogTitle icon="pi-pencil" title="Edit Media" />
    </template>
    <div class="edit-dialog-content">
      <!-- Media preview -->
      <div class="edit-preview" v-if="editForm.preview_url || editForm.url">
        <img
          v-if="editForm.mimetype.startsWith('image/')"
          :src="editForm.preview_url || editForm.url"
          class="edit-preview-img"
          alt="preview"
        />
        <video
          v-else-if="editForm.mimetype.startsWith('video/')"
          :src="editForm.url"
          class="edit-preview-img"
          controls
        />
        <div v-else class="edit-preview-file">
          <i class="pi pi-file" />
        </div>
      </div>

      <!-- Where the file is used -->
      <div class="field edit-usage" data-tour="media-edit-usage">
        <label>Used in</label>
        <ul v-if="editUsedBy?.length" class="edit-usage-list">
          <li v-for="u in editUsedBy" :key="u.kind + u.id">
            <RouteLink v-if="usageLink(u)" :to="usageLink(u)!">{{ usageLabel(u) }}</RouteLink>
            <span v-else>{{ usageLabel(u) }}</span>
          </li>
        </ul>
        <span v-else class="hint">Not used anywhere.</span>
      </div>

      <!-- Title field -->
      <div class="field" data-tour="media-edit-title-field">
        <label for="media-title">Title</label>
        <InputText id="media-title" v-model="editForm.title" class="w-full" :disabled="!canRename" />
      </div>

      <!-- Tag clouds -->
      <div class="edit-tag-area" data-tour="media-edit-tags">
        <!-- Assigned tags -->
        <div class="edit-tag-panel">
          <div class="edit-tag-panel-header">
            <span class="edit-tag-panel-label">Assigned tags</span>
            <span class="edit-tag-panel-count">{{ editTags.length }}</span>
          </div>
          <div class="edit-tag-cloud" :class="{ 'cloud-empty': editTags.length === 0 }">
            <span
              v-for="tag in editTags"
              :key="tag"
              class="tag-pill tag-pill--assigned"
              role="button"
              tabindex="0"
              title="Click to remove"
              @click="editRemoveTag(tag)"
              @keydown.enter="editRemoveTag(tag)"
            >
              {{ tag }}
              <i class="pi pi-times tag-pill-icon" />
            </span>
            <span v-if="editTags.length === 0" class="cloud-placeholder">No tags assigned</span>
          </div>
          <!-- New tag input -->
          <div class="new-tag-row">
            <InputText
              v-model="newTagInput"
              placeholder="New tag… press Enter"
              class="new-tag-input"
              :disabled="!canTag"
              @keydown="editNewTagKeydown"
            />
            <Button
              icon="pi pi-plus"
              size="small"
              :disabled="!canTag || !newTagInput.trim()"
              @click="() => { editAddTag(newTagInput); newTagInput = '' }"
            />
          </div>
        </div>

        <!-- Arrow divider -->
        <div class="edit-tag-divider">
          <i class="pi pi-arrows-h" />
        </div>

        <!-- Available tags (not yet assigned) -->
        <div class="edit-tag-panel">
          <div class="edit-tag-panel-header">
            <span class="edit-tag-panel-label">Available tags</span>
            <span class="edit-tag-panel-count">{{ editAvailableTags.length }}</span>
          </div>
          <div class="edit-tag-cloud" :class="{ 'cloud-empty': editAvailableTags.length === 0 }">
            <span
              v-for="t in editAvailableTags"
              :key="t.tag"
              class="tag-pill tag-pill--available"
              role="button"
              tabindex="0"
              title="Click to assign"
              @click="editAddTag(t.tag)"
              @keydown.enter="editAddTag(t.tag)"
            >
              <i class="pi pi-plus tag-pill-icon" />
              {{ t.tag }}
              <small class="tag-count">{{ t.count }}</small>
            </span>
            <span v-if="editAvailableTags.length === 0" class="cloud-placeholder">All tags assigned</span>
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <DialogFooter cancel-tour="media-edit-cancel" show-update :loading="isSavingMedia" :cancel-disabled="isSavingMedia" @cancel="visible = false" @update="saveMedia(true)" @confirm="saveMedia()" />
    </template>
  </Dialog>
</template>

<style scoped src="./tagPill.css"></style>
<style scoped>
.edit-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  padding: 0.5rem 0 0.25rem;
}
.edit-preview {
  width: 100%;
  max-height: 280px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--p-surface-200, #e2e8f0);
  display: flex;
  align-items: center;
  justify-content: center;
}
.edit-preview-img {
  width: 100%;
  max-height: 280px;
  object-fit: contain;
  display: block;
}
.edit-preview-file {
  padding: 2rem;
  font-size: 3rem;
  color: var(--p-text-muted-color, #94a3b8);
}
/* Tag-cloud area inside edit dialog */
.edit-tag-area {
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
}
.edit-tag-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.edit-tag-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.edit-tag-panel-label {
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--p-text-color, #334155);
}
.edit-tag-panel-count {
  font-size: 0.75rem;
  color: var(--p-text-muted-color, #94a3b8);
  background: var(--p-content-background, #f1f5f9);
  border-radius: 999px;
  padding: 0.1rem 0.45rem;
}
.edit-tag-cloud {
  min-height: 90px;
  max-height: 220px;
  overflow-y: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  align-content: flex-start;
  padding: 0.5rem;
  border: 1px solid var(--p-content-border-color, #e2e8f0);
  border-radius: 8px;
  background: var(--p-content-background, #fafafa);
}
.edit-tag-cloud.cloud-empty {
  align-items: center;
  justify-content: center;
}
.cloud-placeholder {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #94a3b8);
  font-style: italic;
}
.tag-pill--assigned {
  background: var(--p-primary-color, #3b82f6);
  color: white;
  border-color: transparent;
}
.tag-pill--assigned:hover {
  background: #2563eb;
}
.tag-pill--available {
  background: var(--p-content-background, #f1f5f9);
  color: var(--p-text-color, #334155);
  border-color: var(--p-content-border-color, #e2e8f0);
}
.tag-pill--available:hover {
  background: #e0f2fe;
  border-color: #7dd3fc;
  color: #0369a1;
}
.tag-pill-icon {
  font-size: 0.65rem;
  opacity: 0.8;
}
.edit-tag-divider {
  display: flex;
  align-items: center;
  padding-top: 2.2rem;
  flex-shrink: 0;
}
.edit-tag-divider i {
  font-size: 1.2rem;
  color: var(--p-text-muted-color, #94a3b8);
}
.new-tag-row {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}
.new-tag-input {
  flex: 1;
  font-size: 0.85rem;
}
/* Dark mode: --p-surface-200 is a fixed ramp point, kept as the light-mode
   placeholder shade for .edit-preview above — see docs/developer/styleguide.md. */
.dark-mode .edit-preview {
  background: var(--p-surface-700, #334155);
}
.edit-usage-list {
  margin: 0;
  padding-left: 1.2rem;
}
.edit-usage-list a {
  text-decoration: underline;
}
</style>
