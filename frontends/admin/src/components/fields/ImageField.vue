<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useFieldContext } from '../../composables/fields/useFieldContext'
import { useSocket } from '../../composables/useSocket'
import DialogTitle from '../DialogTitle.vue'
import FieldSlot from './FieldSlot.vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Tag from 'primevue/tag'

// An image: one picked from the media library, or a random one by tag, plus how it fits its
// container (fixed height, full width/height, stretch).
interface MediaItem {
  id: number
  title: string
  filename: string
  mimetype: string
  url: string
  preview_url: string
  tags: string[]
}

const f = useFieldContext()
const { on, off, emit: socketEmit } = useSocket()

const imageModeOptions = [
  { label: 'Single Image', value: 'single' },
  { label: 'Random Image from Tags', value: 'random_tags' },
]

// How the image fills its container, as an alternative to a fixed Size (vh): '' keeps today's
// behavior (Size field, or natural scaling if unset); the other three ignore Size entirely and are
// computed server-side the same way — see _image_style() in application/admin/content/helper.py.
const imageFitOptions = [
  { label: 'Fixed height (vh)', value: '' },
  { label: 'Full height of container (keep ratio)', value: 'height' },
  { label: 'Full width of container (keep ratio)', value: 'width' },
  { label: 'Full width & height (stretch)', value: 'stretch' },
]

const availableImageTags = ref<string[]>([])

const imageMode = computed(() => String(f.fields[`${f.name}__image_mode`] || 'single'))

const setImageMode = (mode: string) => {
  f.set(`${f.name}__image_mode`, mode)
  if (mode === 'random_tags' && availableImageTags.value.length === 0) {
    socketEmit('displayhive:admin:cts:get_image_tags')
  }
}

const imageTags = computed((): string[] => {
  const v = f.fields[`${f.name}__image_tags`]
  if (Array.isArray(v)) return v as unknown as string[]
  if (typeof v === 'string' && v) {
    try { return JSON.parse(v) } catch { return [] }
  }
  return []
})

const toggleImageTag = (tag: string) => {
  const current = imageTags.value
  const idx = current.indexOf(tag)
  f.set(`${f.name}__image_tags`, idx === -1 ? [...current, tag] : current.filter((t) => t !== tag))
}

// Fixes the rendered <img>'s height (vh) regardless of its container's own height — blank/0
// leaves it scaling to fit the container, as before.
const imageSize = computed((): number | null => {
  const v = f.fields[`${f.name}__size`]
  const n = Number(v)
  return v !== '' && v != null && !isNaN(n) && n > 0 ? n : null
})

const imageFit = computed(() => String(f.fields[`${f.name}__fit`] || ''))

// --- the picker dialog ---
const showPicker = ref(false)
const pickerMediaItems = ref<MediaItem[]>([])
const pickerSearchText = ref('')
const pickerLoading = ref(false)

const pickerFiltered = computed(() => {
  const q = pickerSearchText.value.toLowerCase()
  const images = pickerMediaItems.value.filter((m) => m.mimetype.startsWith('image/'))
  if (!q) return images
  return images.filter(
    (m) =>
      m.title?.toLowerCase().includes(q) ||
      m.filename?.toLowerCase().includes(q) ||
      (m.tags || []).some((t) => t.toLowerCase().includes(q)),
  )
})

const openPicker = () => {
  pickerSearchText.value = ''
  pickerLoading.value = true
  showPicker.value = true
  socketEmit('displayhive:admin:cts:get_media_for_picker')
}

const selectPickerImage = (item: MediaItem) => {
  f.set(f.name, item.url)
  showPicker.value = false
}

const handleMediaForPicker = (data: { media: MediaItem[] }) => {
  pickerMediaItems.value = data.media || []
  pickerLoading.value = false
}
const handleImageTags = (data: { tags: string[] }) => {
  availableImageTags.value = data.tags || []
}

onMounted(() => {
  on('displayhive:admin:stc:media_for_picker', handleMediaForPicker)
  on('displayhive:admin:stc:image_tags', handleImageTags)
  if (imageMode.value === 'random_tags') socketEmit('displayhive:admin:cts:get_image_tags')
})
onUnmounted(() => {
  off('displayhive:admin:stc:media_for_picker', handleMediaForPicker)
  off('displayhive:admin:stc:image_tags', handleImageTags)
})

f.reportVisibleWhen(
  () =>
    !f.isHidden(`${f.name}__image_mode`) ||
    !f.isHidden(`${f.name}__size`) ||
    (imageMode.value === 'single' && !f.isHidden(f.name)) ||
    (imageMode.value === 'random_tags' && !f.isHidden(`${f.name}__image_tags`)),
)
</script>

<template>
  <div class="image-field-wrapper">
    <FieldSlot :field-key="`${f.name}__image_mode`" class="image-mode-select">
      <Select
        :modelValue="imageMode"
        @update:modelValue="(v: string) => setImageMode(v)"
        :options="imageModeOptions"
        optionLabel="label"
        optionValue="value"
        :disabled="f.isLocked(`${f.name}__image_mode`)"
        class="w-full"
      />
    </FieldSlot>

    <FieldSlot v-if="imageMode === 'single'" :field-key="f.name">
      <div :class="['fve-slot-control', { 'fve-disabled': f.isLocked(f.name) }]">
        <div v-if="f.get(f.name)" class="image-field-preview">
          <img :src="String(f.get(f.name))" class="image-field-thumb" alt="selected" />
          <div class="image-field-actions">
            <Button icon="pi pi-pencil" size="small" label="Change" outlined @click="openPicker" />
            <Button icon="pi pi-times" size="small" severity="danger" outlined @click="f.set(f.name, '')" />
          </div>
        </div>
        <div v-else class="image-field-empty" @click="openPicker">
          <i class="pi pi-image" />
          <span>Click to select an image</span>
        </div>
      </div>
    </FieldSlot>

    <FieldSlot v-else-if="imageMode === 'random_tags'" :field-key="`${f.name}__image_tags`">
      <div :class="['image-tags-cloud', 'fve-slot-control', { 'fve-disabled': f.isLocked(`${f.name}__image_tags`) }]">
        <p class="image-tags-hint">Select one or more tags — a random matching image will be shown on each display refresh.</p>
        <div v-if="availableImageTags.length === 0" class="image-tags-empty">
          <i class="pi pi-spin pi-spinner" /> Loading tags…
        </div>
        <div v-else class="image-tags-list">
          <button
            v-for="tag2 in availableImageTags"
            :key="tag2"
            type="button"
            :class="['image-tag-chip', imageTags.includes(tag2) ? 'image-tag-chip--selected' : '']"
            @click="toggleImageTag(tag2)"
          >{{ tag2 }}</button>
        </div>
        <small v-if="imageTags.length > 0" class="image-tags-selected-summary">
          Selected: {{ imageTags.join(', ') }}
        </small>
      </div>
    </FieldSlot>

    <FieldSlot :field-key="`${f.name}__fit`" class="image-size-row">
      <label :for="`field-${f.name}-fit`" class="image-size-label">Fit</label>
      <Select
        :id="`field-${f.name}-fit`"
        :modelValue="imageFit"
        @update:modelValue="(v: string) => f.set(`${f.name}__fit`, v)"
        :options="imageFitOptions"
        optionLabel="label"
        optionValue="value"
        :disabled="f.isLocked(`${f.name}__fit`)"
        style="width: 260px"
      />
    </FieldSlot>

    <FieldSlot v-if="!imageFit" :field-key="`${f.name}__size`" class="image-size-row">
      <label :for="`field-${f.name}-size`" class="image-size-label">Size (vh)</label>
      <InputNumber
        :id="`field-${f.name}-size`"
        :modelValue="imageSize"
        @update:modelValue="(v: number | null) => f.set(`${f.name}__size`, v ?? '')"
        :min="0" :max="100" :step="0.5" :max-fraction-digits="2"
        suffix=" vh"
        placeholder="auto"
        :disabled="f.isLocked(`${f.name}__size`)"
        style="width: 140px"
      />
    </FieldSlot>

    <Dialog
      v-model:visible="showPicker"
      modal
      :style="{ width: '860px', maxWidth: '95vw' }"
    >
      <template #header>
        <DialogTitle icon="pi-image" title="Select Image" />
      </template>
      <div class="picker-toolbar">
        <InputText v-model="pickerSearchText" placeholder="Search images…" class="picker-search" />
        <Tag :value="`${pickerFiltered.length} images`" />
      </div>
      <div v-if="pickerLoading" class="loading-state">
        <i class="pi pi-spin pi-spinner" />
        <p>Loading media…</p>
      </div>
      <div v-else-if="pickerFiltered.length === 0" class="empty-state">
        <i class="pi pi-images" />
        <p>No images found</p>
      </div>
      <div v-else class="picker-grid">
        <div
          v-for="item in pickerFiltered"
          :key="item.id"
          class="picker-item"
          :class="{ 'picker-item--selected': String(f.get(f.name)) === item.url }"
          @click="selectPickerImage(item)"
        >
          <div class="picker-thumb">
            <img :src="item.preview_url || item.url" :alt="item.title" />
          </div>
          <div class="picker-label">{{ item.title || item.filename }}</div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" text @click="showPicker = false" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.image-field-wrapper {
  width: 100%;
}

.image-mode-select {
  margin-bottom: 0.75rem;
}

.image-field-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  border: 2px dashed var(--p-content-border-color, #cbd5e1);
  border-radius: 8px;
  padding: 1.5rem;
  cursor: pointer;
  color: var(--p-text-muted-color, #94a3b8);
  font-size: 0.875rem;
  transition: border-color 0.2s, background 0.2s;
}

.image-field-empty i {
  font-size: 2rem;
}

.image-field-empty:hover {
  border-color: var(--p-primary-color, #3b82f6);
  background: rgba(59, 130, 246, 0.04);
}

.image-field-preview {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.image-field-thumb {
  width: 80px;
  height: 60px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid var(--p-content-border-color, #e2e8f0);
}

.image-field-actions {
  display: flex;
  gap: 0.4rem;
}

.image-tags-cloud {
  border: 1px solid var(--p-content-border-color, #e2e8f0);
  border-radius: 8px;
  padding: 0.75rem;
  background: var(--p-content-background, #f8fafc);
}

.image-tags-hint {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #64748b);
  margin: 0 0 0.6rem;
}

.image-tags-empty {
  color: var(--p-text-muted-color, #94a3b8);
  font-size: 0.85rem;
}

.image-tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}

.image-tag-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.7rem;
  border-radius: 999px;
  border: 1px solid var(--p-content-border-color, #cbd5e1);
  background: var(--p-content-background, white);
  font-size: 0.8rem;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}

.image-tag-chip:hover {
  border-color: var(--p-primary-color, #3b82f6);
  background: var(--p-primary-50, #eff6ff);
}

.image-tag-chip--selected {
  background: var(--p-primary-color, #3b82f6);
  border-color: var(--p-primary-color, #3b82f6);
  color: white;
}

.image-tag-chip--selected:hover {
  background: var(--p-primary-600, #2563eb);
}

.image-tags-selected-summary {
  font-size: 0.78rem;
  color: var(--p-text-muted-color, #475569);
  display: block;
  margin-top: 0.25rem;
}

.image-size-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.6rem;
}

.image-size-label {
  font-size: 0.875rem;
  color: var(--p-text-color, #334155);
  white-space: nowrap;
}

/* Same specificity fix as .arrow-size-label above. */
.fve-slot > .image-size-label:first-child {
  flex: 0 0 auto;
}

/* Same right-alignment fix as .arrow-size-row above. */
.image-size-row :deep(.option-flag-toggle) {
  margin-left: auto;
}

/* Image picker dialog */
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
  border: 2px solid var(--p-content-border-color, #e2e8f0);
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
  background: var(--p-content-background, #f1f5f9);
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
  background: var(--p-content-background, white);
}
</style>
