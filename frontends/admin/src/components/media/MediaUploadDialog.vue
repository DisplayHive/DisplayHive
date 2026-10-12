<script setup lang="ts">
import { ref, computed } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import ProgressBar from 'primevue/progressbar'
import DialogTitle from '../ui/DialogTitle.vue'
import DialogFooter from '../ui/DialogFooter.vue'
import { useMediaStore } from '../../stores/media'
import { useAuthStore } from '../../stores/auth'
import { uploadMedia, MAX_MEDIA_UPLOAD_BYTES } from '../../utils/media/uploadMedia'

// The "Upload Media" dialog of the Media page: drop zone, file list and a
// sequential per-file upload with progress.
const props = withDefaults(defineProps<{ folder?: string }>(), { folder: '' })
const visible = defineModel<boolean>('visible', { default: false })

const toast = useToast()
const mediaStore = useMediaStore()
const authStore = useAuthStore()

const uploadFiles = ref<File[]>([])
const uploadProgress = ref<
  { name: string; status: 'pending' | 'uploading' | 'done' | 'error'; error?: string; loaded: number }[]
>([])
const maxUploadMb = MAX_MEDIA_UPLOAD_BYTES / 1024 / 1024

// Overall progress across the batch, by bytes sent (finished/failed files count as fully sent).
const uploadPercent = computed(() => {
  const total = uploadFiles.value.reduce((sum, f) => sum + f.size, 0)
  if (!total) return 0
  const sent = uploadProgress.value.reduce(
    (sum, p, i) => sum + (p.status === 'done' || p.status === 'error' ? (uploadFiles.value[i]?.size ?? 0) : p.loaded),
    0,
  )
  return Math.min(100, Math.round((sent / total) * 100))
})
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
  visible.value = false
  uploadFiles.value = []
  uploadProgress.value = []
}

const startUpload = async () => {
  if (!uploadFiles.value.length || isUploading.value) return
  isUploading.value = true
  uploadProgress.value = uploadFiles.value.map((f) => ({ name: f.name, status: 'pending', loaded: 0 }))

  // One request per file, one after another: per-file progress and errors,
  // and never more than one large body in flight.
  for (let i = 0; i < uploadFiles.value.length; i++) {
    const file = uploadFiles.value[i] as File
    const progress = uploadProgress.value[i]!
    progress.status = 'uploading'
    const result = await uploadMedia(
      file,
      { folder: props.folder, title: file.name, tags: '' },
      authStore.authHeader(),
      (loaded) => (progress.loaded = loaded),
    )
    if (result.success) {
      progress.status = 'done'
    } else {
      progress.status = 'error'
      progress.error = result.error
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
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="{ width: '620px' }"
    :closable="!isUploading"
    @hide="closeUploadDialog"
  >
    <template #header>
      <DialogTitle icon="pi-upload" title="Upload Media" />
    </template>
    <!-- Drop zone -->
    <div
      class="upload-drop-zone"
      data-tour="media-upload-dropzone"
      :class="{ 'drop-active': uploadDropActive }"
      @dragover.prevent="uploadDropActive = true"
      @dragleave.prevent="uploadDropActive = false"
      @drop.prevent="onUploadDrop"
      @click="($refs.uploadInput as HTMLInputElement).click()"
    >
      <i class="pi pi-cloud-upload" />
      <p class="upload-drop-zone-text">Drag &amp; drop files here, or <strong>click to browse</strong></p>
      <p class="upload-drop-zone-hint">JPEG &amp; PNG only (max {{ maxUploadMb }} MB each)</p>
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
          <template v-if="uploadProgress[idx].status === 'uploading'">
            <span class="upload-file-percent">{{ file.size ? Math.round((uploadProgress[idx].loaded / file.size) * 100) : 0 }}%</span>
            <i class="pi pi-spin pi-spinner" />
          </template>
          <i v-else-if="uploadProgress[idx].status === 'done'" class="pi pi-check" />
          <i v-else-if="uploadProgress[idx].status === 'error'" class="pi pi-times" :title="uploadProgress[idx].error" />
        </span>
        <Button
          v-if="!isUploading"
          icon="pi pi-times"
          text
          rounded
          size="small"
          @click.stop="removeUploadFile(idx)"
        />
        <small v-if="uploadProgress[idx]?.status === 'error'" class="upload-file-error">{{ uploadProgress[idx].error }}</small>
      </div>
    </div>

    <ProgressBar v-if="isUploading" :value="uploadPercent" :show-value="false" class="mt-4 thin-progress" />

    <template #footer>
      <DialogFooter
        cancel-tour="media-upload-cancel"
        confirm-label="Upload"
        confirm-icon="pi pi-upload"
        :disabled="!uploadFiles.length"
        :loading="isUploading"
        :cancel-disabled="isUploading"
        @cancel="closeUploadDialog"
        @confirm="startUpload"
      />
    </template>
  </Dialog>
</template>

<style scoped>
/* Upload dialog styles */
.upload-drop-zone {
  border: 2px dashed var(--p-content-border-color, #ccc);
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
.upload-drop-zone i {
  font-size: 2rem;
  color: var(--p-text-muted-color, #aaa);
}
.upload-drop-zone-text {
  margin: 0.5rem 0 0;
}
.upload-drop-zone-hint {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #aaa);
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
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.3rem 0.5rem;
  border-radius: 4px;
  background: var(--p-content-background, #f5f5f5);
  font-size: 0.85rem;
}
.upload-file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.upload-file-size {
  color: var(--p-text-muted-color, #888);
  font-size: 0.8rem;
  white-space: nowrap;
}
.upload-status-done {
  color: var(--p-green-500, #22c55e);
}
.upload-status-error {
  color: var(--p-red-500, #ef4444);
}
.upload-file-percent {
  color: var(--p-text-muted-color, #888);
  font-size: 0.8rem;
  margin-right: 0.35rem;
}
/* Full-width line under the row; same fixed status red as the icon above. */
.upload-file-error {
  flex-basis: 100%;
  color: var(--p-red-500, #ef4444);
}
</style>
