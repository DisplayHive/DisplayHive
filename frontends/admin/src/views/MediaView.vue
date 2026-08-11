<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useMediaStore } from '../stores/media'
import { useRightsStore } from '../stores/rights'
import type { MediaItem } from '../types/models'

// PrimeVue components
import Card from 'primevue/card'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'
import ProgressBar from 'primevue/progressbar'

const toast = useToast()
const confirm = useConfirm()
const { emitWithAck } = useSocket()
const mediaStore = useMediaStore()
const rightsStore = useRightsStore()

const canUpload = computed(() => rightsStore.can('media.upload'))
const canDelete = computed(() => rightsStore.can('media.delete'))
const canRename = computed(() => rightsStore.can('media.rename'))
const canTag = computed(() => rightsStore.can('media.tag'))
const canEdit = computed(() => canRename.value || canTag.value)

const selectedFolder = ref<string>('')
const filterText = ref('')
const selectedTags = ref<string[]>([])

// Edit dialog
const isSavingMedia = ref(false)
const showEditDialog = ref(false)
const editForm = ref({
  id: null as number | null,
  title: '',
  preview_url: '',
  url: '',
  mimetype: '',
})
const editTags = ref<string[]>([])
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

// Upload dialog
const showUploadDialog = ref(false)
const uploadFiles = ref<File[]>([])
const uploadProgress = ref<{ name: string; status: 'pending' | 'uploading' | 'done' | 'error'; error?: string }[]>([])
const isUploading = ref(false)
const uploadDropActive = ref(false)

const ACCEPTED_TYPES = ['image/jpeg', 'image/png']

const onUploadDrop = (event: DragEvent) => {
  uploadDropActive.value = false
  const dropped = Array.from(event.dataTransfer?.files || []).filter(f => ACCEPTED_TYPES.includes(f.type))
  uploadFiles.value = [...uploadFiles.value, ...dropped]
}

const onUploadFileInput = (event: Event) => {
  const input = event.target as HTMLInputElement
  const selected = Array.from(input.files || [])
  uploadFiles.value = [...uploadFiles.value, ...selected]
  input.value = ''
}

const removeUploadFile = (index: number) => {
  uploadFiles.value = uploadFiles.value.filter((_, i) => i !== index)
  uploadProgress.value = uploadProgress.value.filter((_, i) => i !== index)
}

const closeUploadDialog = () => {
  if (isUploading.value) return
  showUploadDialog.value = false
  uploadFiles.value = []
  uploadProgress.value = []
}

const startUpload = async () => {
  if (!uploadFiles.value.length || isUploading.value) return
  isUploading.value = true
  uploadProgress.value = uploadFiles.value.map((f) => ({ name: f.name, status: 'pending' }))

  for (let i = 0; i < uploadFiles.value.length; i++) {
    const file = uploadFiles.value[i] as File
    const progress = uploadProgress.value[i]!
    progress.status = 'uploading'
    try {
      const base64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = (e) => resolve(e.target?.result as string)
        reader.onerror = reject
        reader.readAsDataURL(file)
      })
      const result = await emitWithAck<{ success: boolean; error?: string }>('displayhive:media:cts:upload', {
        file_data: base64,
        filename: file.name,
        mime_type: file.type,
        folder: selectedFolder.value || '',
        title: file.name,
        tags: '',
      })
      if (!result?.success) throw new Error(result?.error || 'Upload failed')
      progress.status = 'done'
    } catch (e: any) {
      progress.status = 'error'
      progress.error = e?.message || 'Upload failed'
    }
  }

  isUploading.value = false
  const failed = uploadProgress.value.filter((p) => p.status === 'error')
  if (failed.length === 0) {
    toast.add({ severity: 'success', summary: 'Upload complete', detail: `${uploadFiles.value.length} file(s) uploaded`, life: 3000 })
    closeUploadDialog()
    mediaStore.fetch()
  } else {
    toast.add({ severity: 'warn', summary: 'Upload finished with errors', detail: `${failed.length} file(s) failed`, life: 5000 })
    mediaStore.fetch()
  }
}

const filteredMedia = computed(() => {
  let items = mediaStore.mediaItems
  if (selectedFolder.value) items = items.filter((m) => m.folder === selectedFolder.value)
  if (selectedTags.value.length > 0) {
    const sel = selectedTags.value.map((s) => s.toLowerCase())
    items = items.filter((m) => (m.tags || []).some((t) => sel.includes(t.toLowerCase())))
  }
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

onMounted(() => {
  mediaStore.fetch()
})

const openEditDialog = (item: MediaItem) => {
  editForm.value = {
    id: item.id,
    title: item.title,
    preview_url: item.preview_url || item.url || '',
    url: item.url || '',
    mimetype: item.mimetype || '',
  }
  editTags.value = [...(item.tags || [])]
  newTagInput.value = ''
  showEditDialog.value = true
}

const saveMedia = async (keepOpen = false) => {
  isSavingMedia.value = true
  try {
    const result = await mediaStore.updateMedia(editForm.value.id!, editForm.value.title, editTags.value)
    if (result?.success === false) {
      toast.add({ severity: 'error', summary: 'Error', detail: result.error || 'Save failed', life: 4000 })
      return
    }
    toast.add({ severity: 'success', summary: 'Saved', detail: 'Media updated', life: 3000 })
    if (!keepOpen) showEditDialog.value = false
    mediaStore.fetch()
  } catch (e: any) {
    toast.add({ severity: 'error', summary: 'Error', detail: e?.message || 'Save failed', life: 4000 })
  } finally {
    isSavingMedia.value = false
  }
}

const deleteMedia = (item: MediaItem) => {
  confirm.require({
    message: `Are you sure you want to delete "${item.title || item.filename}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      mediaStore.deleteMedia(item.id)
      toast.add({ severity: 'success', summary: 'Success', detail: 'Media deleted', life: 3000 })
      mediaStore.fetch()
    },
  })
}

const syncingPreviews = ref(false)
const syncPreviews = async () => {
  syncingPreviews.value = true
  try {
    const ack = await emitWithAck<{
      success: boolean
      total?: number
      missing?: number
      regenerated?: number
      skipped_no_source?: number
      error?: string
    }>('displayhive:media:cts:sync_previews')
    if (!ack?.success) {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Failed to sync previews', life: 4000 })
      return
    }
    if (!ack.missing) {
      toast.add({ severity: 'success', summary: 'Up to date', detail: `All ${ack.total} images have previews`, life: 3000 })
    } else {
      const parts = [`${ack.regenerated} of ${ack.missing} missing preview(s) regenerated`]
      if (ack.skipped_no_source) parts.push(`${ack.skipped_no_source} skipped (original file missing)`)
      toast.add({ severity: 'success', summary: 'Previews synced', detail: parts.join(' — '), life: 5000 })
      mediaStore.fetch()
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Could not reach the server', life: 4000 })
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
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Media page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="media-view">
    <div class="media-content">
      <Card>
        <template #title>
          <div class="card-header">
            <div class="header-actions">
              <Button v-if="canUpload" icon="pi pi-upload" label="Upload" @click="showUploadDialog = true" size="small" />
              <Button
                v-if="canUpload"
                icon="pi pi-sync"
                label="Sync Previews"
                @click="syncPreviews"
                :loading="syncingPreviews"
                size="small"
                outlined
                title="Count images vs. previews and regenerate any missing ones"
              />
              <Button icon="pi pi-refresh" @click="mediaStore.fetch()" size="small" outlined />
            </div>
          </div>
        </template>
        <template #content>
          <div class="tag-cloud">
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
            <InputText v-model="filterText" placeholder="Search media..." class="filter-input" />
            <Tag :value="`${filteredMedia.length} items`" />
          </div>

          <div class="media-grid" v-if="!mediaStore.loading">
            <div
              v-for="item in filteredMedia"
              :key="item.id"
              class="media-item"
            >
              <div class="media-preview">
                <img v-if="isImage(item.mimetype)" :src="item.preview_url || item.url" :alt="item.title" />
                <video v-else-if="isVideo(item.mimetype)" :src="item.url" />
                <div v-else class="file-icon">
                  <i class="pi pi-file" style="font-size: 3rem"></i>
                </div>
              </div>
              <div class="media-info">
                <span class="media-title">{{ item.title || item.filename }}</span>
                <span class="media-filename">{{ item.filename }}</span>
                <span v-if="item.url" class="media-url-row">
                  <a :href="item.url" class="media-url" target="_blank" :title="item.url">{{ item.url }}</a>
                  <i class="pi pi-copy media-url-copy" :title="'Copy URL'" @click.prevent="copyUrl(item.url)" />
                </span>
                <div class="media-tags" v-if="item.tags?.length">
                  <Tag v-for="(tag, ti) in item.tags" :key="tag + ti" :value="tag" severity="secondary" />
                  <!-- If there are many tags, keep layout tidy by limiting visual overflow -->
                  <!-- The CSS will wrap tags; consider adding a '+N' indicator in future if desired -->
                </div>
              </div>
              <div class="media-actions">
                <Button v-if="canEdit" icon="pi pi-pencil" @click="openEditDialog(item)" size="small" outlined title="Edit" />
                <Button v-if="canDelete" icon="pi pi-trash" @click="deleteMedia(item)" size="small" severity="danger" outlined title="Delete" />
              </div>
            </div>
          </div>

          <div class="loading-state" v-if="mediaStore.loading">
            <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
            <p>Loading media...</p>
          </div>

          <div class="empty-state" v-if="!mediaStore.loading && filteredMedia.length === 0">
            <i class="pi pi-images" style="font-size: 3rem"></i>
            <p>No media files found</p>
          </div>
        </template>
      </Card>
    </div>

    <!-- Edit Dialog -->
    <Dialog
      v-model:visible="showEditDialog"
      header="Edit Media"
      modal
      :style="{ width: '820px', maxWidth: '95vw' }"
    >
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
            <i class="pi pi-file" style="font-size: 3rem; color: #94a3b8" />
          </div>
        </div>

        <!-- Title field -->
        <div class="field">
          <label for="media-title">Title</label>
          <InputText id="media-title" v-model="editForm.title" class="w-full" :disabled="!canRename" />
        </div>

        <!-- Tag clouds -->
        <div class="edit-tag-area">
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
            <i class="pi pi-arrows-h" style="font-size: 1.2rem; color: #94a3b8" />
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
        <Button label="Cancel" @click="showEditDialog = false" text :disabled="isSavingMedia" />
        <Button label="Update" severity="secondary" outlined @click="saveMedia(true)" :loading="isSavingMedia" :disabled="isSavingMedia" />
        <Button label="Save" @click="saveMedia()" :loading="isSavingMedia" :disabled="isSavingMedia" />
      </template>
    </Dialog>

    <!-- Upload Dialog -->
    <Dialog
      v-model:visible="showUploadDialog"
      header="Upload Media"
      modal
      :style="{ width: '620px' }"
      :closable="!isUploading"
      @hide="closeUploadDialog"
    >
      <!-- Drop zone -->
      <div
        class="upload-drop-zone"
        :class="{ 'drop-active': uploadDropActive }"
        @dragover.prevent="uploadDropActive = true"
        @dragleave.prevent="uploadDropActive = false"
        @drop.prevent="onUploadDrop"
        @click="($refs.uploadInput as HTMLInputElement).click()"
      >
        <i class="pi pi-cloud-upload" style="font-size: 2rem; color: #aaa" />
        <p style="margin: 0.5rem 0 0">Drag &amp; drop files here, or <strong>click to browse</strong></p>
        <p style="font-size: 0.8rem; color: #aaa">JPEG &amp; PNG only (max 50 MB each)</p>
      </div>
      <input
        ref="uploadInput"
        type="file"
        multiple
        accept="image/jpeg,image/png"
        style="display: none"
        @change="onUploadFileInput"
      />

      <!-- File list -->
      <div v-if="uploadFiles.length" class="upload-file-list">
        <div
          v-for="(file, idx) in uploadFiles"
          :key="idx"
          class="upload-file-row"
        >
          <span class="upload-file-name">{{ file.name }}</span>
          <span class="upload-file-size">{{ (file.size / 1024 / 1024).toFixed(1) }} MB</span>
          <span v-if="uploadProgress[idx]" :class="'upload-status-' + uploadProgress[idx].status">
            <i v-if="uploadProgress[idx].status === 'uploading'" class="pi pi-spin pi-spinner" />
            <i v-else-if="uploadProgress[idx].status === 'done'" class="pi pi-check" style="color: green" />
            <i v-else-if="uploadProgress[idx].status === 'error'" class="pi pi-times" style="color: red" :title="uploadProgress[idx].error" />
          </span>
          <Button
            v-if="!isUploading"
            icon="pi pi-times"
            text
            rounded
            size="small"
            @click.stop="removeUploadFile(idx)"
          />
        </div>
      </div>

      <ProgressBar v-if="isUploading" mode="indeterminate" style="margin-top: 1rem; height: 6px" />

      <template #footer>
        <Button label="Cancel" text :disabled="isUploading" @click="closeUploadDialog" />
        <Button
          label="Upload"
          icon="pi pi-upload"
          :disabled="!uploadFiles.length || isUploading"
          :loading="isUploading"
          @click="startUpload"
        />
      </template>
    </Dialog>
  </div>
</template>

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
.tag-pill {
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  padding: 0.25rem 0.5rem;
  border-radius: 999px;
  font-size: 0.8rem;
  color: #334155;
  cursor: pointer;
  display: inline-flex;
  gap: 0.4rem;
  align-items: center;
}
.tag-pill.selected {
  background: var(--p-primary-color, #3b82f6);
  color: white;
  border-color: rgba(255,255,255,0.1);
}
.tag-pill:focus {
  outline: 2px solid rgba(59,130,246,0.25);
}
.tag-count {
  opacity: 0.7;
  font-size: 0.75rem;
  margin-left: 0.2rem;
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
  background: #f9f9f9;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.2s;
}

.media-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.media-preview {
  height: 150px;
  background: #ddd;
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
  color: #888;
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
  color: #888;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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
  border-top: 1px solid #e0e0e0;
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

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
  background: #e2e8f0;
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
  color: #334155;
}

.edit-tag-panel-count {
  font-size: 0.75rem;
  color: #94a3b8;
  background: #f1f5f9;
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
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fafafa;
}

.edit-tag-cloud.cloud-empty {
  align-items: center;
  justify-content: center;
}

.cloud-placeholder {
  font-size: 0.8rem;
  color: #94a3b8;
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
  background: #f1f5f9;
  color: #334155;
  border-color: #e2e8f0;
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

.new-tag-row {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}

.new-tag-input {
  flex: 1;
  font-size: 0.85rem;
}

/* Upload dialog styles */
.upload-drop-zone {
  border: 2px dashed #ccc;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
  user-select: none;
}
.upload-drop-zone:hover,
.upload-drop-zone.drop-active {
  border-color: var(--p-primary-color, #3b82f6);
  background: rgba(59, 130, 246, 0.04);
}
.upload-file-list {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-height: 200px;
  overflow-y: auto;
}
.upload-file-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  background: #f5f5f5;
  font-size: 0.85rem;
}
.upload-file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.upload-file-size {
  color: #888;
  font-size: 0.8rem;
  white-space: nowrap;
}
</style>
