<script setup lang="ts">
/**
 * Config editor for the `icon` field handler — shared by ContentEditor.vue
 * (a Contenttype field's live value) and LayoutCanvasEditor.vue (a
 * container's default_content), following the same modelValue pattern as
 * PretalxTableFieldEditor.vue so this multi-part picker UI (library
 * toggles, search, results grid, license dialog, height input) isn't
 * duplicated across both editors.
 *
 * Which libraries are active and the current search text are pure
 * in-component UI state — nothing here is persisted beyond the final
 * selected "<library>/<name>" value and its height.
 */
import { ref, computed, onMounted, watch } from 'vue'
import { ICON_LIBRARIES, loadIcon, type IconLibrary, type IconPickerValue } from '../utils/iconLibraries'

import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Checkbox from 'primevue/checkbox'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Tag from 'primevue/tag'

const props = defineProps<{
  modelValue: IconPickerValue
}>()

const emit = defineEmits<{
  'update:modelValue': [value: IconPickerValue]
}>()

const patch = (partial: Partial<IconPickerValue>) => emit('update:modelValue', { ...props.modelValue, ...partial })

const activeLibraries = ref<Set<string>>(new Set(ICON_LIBRARIES.map((l) => l.id)))
const allActive = computed(() => activeLibraries.value.size === ICON_LIBRARIES.length)
const toggleLibrary = (id: string, checked: boolean) => {
  const next = new Set(activeLibraries.value)
  if (checked) next.add(id)
  else next.delete(id)
  activeLibraries.value = next
}
const toggleAll = () => {
  activeLibraries.value = allActive.value ? new Set() : new Set(ICON_LIBRARIES.map((l) => l.id))
}

const searchText = ref('')

interface IconMatch {
  library: IconLibrary
  name: string
}

const filteredIcons = computed<IconMatch[]>(() => {
  const query = searchText.value.trim().toLowerCase()
  const results: IconMatch[] = []
  for (const library of ICON_LIBRARIES) {
    if (!activeLibraries.value.has(library.id)) continue
    for (const name of library.names) {
      if (query && !name.includes(query)) continue
      results.push({ library, name })
      if (results.length >= 50) return results
    }
  }
  return results
})

// Lazily-loaded raw SVG text per "<library>/<name>" key, for the result
// grid's previews and the currently-selected icon's own preview.
const previewCache = ref<Record<string, string>>({})
const previewKey = (libraryId: string, name: string) => `${libraryId}/${name}`

async function ensurePreview(libraryId: string, name: string): Promise<void> {
  const key = previewKey(libraryId, name)
  if (key in previewCache.value) return
  const svg = await loadIcon(libraryId, name)
  if (svg) previewCache.value = { ...previewCache.value, [key]: svg }
}

// Eagerly load previews for every icon currently shown in the results grid
// (rather than only on hover) so the grid renders with real icons visible
// immediately instead of empty slots until the user mouses over each one.
watch(
  filteredIcons,
  (matches) => {
    for (const match of matches) void ensurePreview(match.library.id, match.name)
  },
  { immediate: true },
)

const selectedLibraryId = computed(() => props.modelValue.icon.split('/', 1)[0] || '')
const selectedName = computed(() => props.modelValue.icon.slice(selectedLibraryId.value.length + 1))
const selectedLibrary = computed(() => ICON_LIBRARIES.find((l) => l.id === selectedLibraryId.value))

onMounted(() => {
  if (props.modelValue.icon) void ensurePreview(selectedLibraryId.value, selectedName.value)
})

const selectIcon = (match: IconMatch) => {
  patch({ icon: `${match.library.id}/${match.name}` })
  void ensurePreview(match.library.id, match.name)
}
const clearIcon = () => patch({ icon: '' })

const showLicenseDialog = ref(false)
</script>

<template>
  <div class="icon-picker">
    <div class="icon-picker-selected">
      <div v-if="modelValue.icon && selectedLibrary" class="icon-picker-preview">
        <span
          class="icon-picker-preview-svg"
          :style="{ height: `${modelValue.size}vh` }"
          v-html="previewCache[previewKey(selectedLibraryId, selectedName)] || ''"
        ></span>
        <span class="icon-picker-preview-label">
          {{ selectedName }}
          <Tag :value="selectedLibrary.label" severity="secondary" />
        </span>
        <Button icon="pi pi-times" text size="small" @click="clearIcon" aria-label="Clear selected icon" />
      </div>
      <span v-else class="icon-picker-none">No icon selected</span>
    </div>

    <div class="icon-picker-libraries">
      <label class="icon-picker-label">Libraries</label>
      <div class="icon-picker-library-list">
        <Button
          :label="allActive ? 'Deactivate all' : 'Activate all'"
          size="small"
          text
          @click="toggleAll"
        />
        <div v-for="library in ICON_LIBRARIES" :key="library.id" class="icon-picker-library-item">
          <Checkbox
            :inputId="'icon-lib-' + library.id"
            :binary="true"
            :modelValue="activeLibraries.has(library.id)"
            @update:modelValue="(v: boolean) => toggleLibrary(library.id, v)"
          />
          <label :for="'icon-lib-' + library.id">{{ library.label }}</label>
        </div>
      </div>
    </div>

    <div class="icon-picker-search">
      <InputText v-model="searchText" placeholder="Search icons…" class="w-full" />
    </div>

    <div class="icon-picker-results">
      <button
        v-for="match in filteredIcons"
        :key="match.library.id + '/' + match.name"
        type="button"
        class="icon-picker-result"
        :class="{ 'icon-picker-result--selected': modelValue.icon === `${match.library.id}/${match.name}` }"
        @click="selectIcon(match)"
        @mouseenter="ensurePreview(match.library.id, match.name)"
      >
        <span class="icon-picker-result-svg" v-html="previewCache[previewKey(match.library.id, match.name)] || ''"></span>
        <span class="icon-picker-result-name">{{ match.name }}</span>
        <Tag :value="match.library.label" severity="secondary" class="icon-picker-result-badge" />
      </button>
      <span v-if="filteredIcons.length === 0" class="icon-picker-empty">No matching icons</span>
    </div>

    <div class="icon-picker-size field">
      <label>Height (vh)</label>
      <InputNumber
        :modelValue="modelValue.size"
        @update:modelValue="(v: number | null) => patch({ size: v ?? 5 })"
        :min="1"
        :max="100"
        class="w-full"
      />
    </div>

    <Button label="Icon Libraries Licenses" icon="pi pi-info-circle" size="small" text @click="showLicenseDialog = true" />

    <Dialog v-model:visible="showLicenseDialog" header="Icon Libraries Licenses" modal :style="{ width: '40rem', maxWidth: '90vw' }">
      <div v-for="library in ICON_LIBRARIES" :key="library.id" class="icon-picker-license-entry">
        <h4>
          {{ library.label }}
          <Tag :value="library.license" severity="info" />
        </h4>
        <p><a :href="library.homepage" target="_blank" rel="noopener">{{ library.homepage }}</a></p>
        <pre class="icon-picker-license-text">{{ library.licenseText }}</pre>
      </div>
    </Dialog>
  </div>
</template>

<style scoped>
.icon-picker {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.icon-picker-selected {
  min-height: 2.5rem;
  display: flex;
  align-items: center;
}

.icon-picker-preview {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.icon-picker-preview-svg {
  display: inline-block;
  max-height: 8rem;
}

.icon-picker-preview-svg :deep(svg) {
  height: 100%;
  width: auto;
  display: block;
}

.icon-picker-result-svg :deep(svg) {
  width: 1.5rem;
  height: 1.5rem;
  display: block;
}

.icon-picker-preview-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.icon-picker-none {
  color: var(--p-text-muted-color, #6b7280);
  font-size: 0.9rem;
}

.icon-picker-label {
  font-weight: 600;
  font-size: 0.9rem;
  display: block;
  margin-bottom: 0.25rem;
}

.icon-picker-library-list {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.75rem;
}

.icon-picker-library-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}

.icon-picker-results {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(6.5rem, 1fr));
  gap: 0.5rem;
  max-height: 16rem;
  overflow-y: auto;
  padding: 0.5rem;
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  border-radius: 6px;
}

.icon-picker-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  padding: 0.5rem;
  border: 1px solid transparent;
  border-radius: 6px;
  background: none;
  cursor: pointer;
  text-align: center;
}

.icon-picker-result:hover {
  background: var(--p-content-hover-background, #f3f4f6);
}

.icon-picker-result--selected {
  border-color: var(--p-primary-color, #3b82f6);
}

.icon-picker-result-name {
  font-size: 0.7rem;
  word-break: break-word;
}

.icon-picker-result-badge {
  font-size: 0.6rem;
}

.icon-picker-empty {
  grid-column: 1 / -1;
  color: var(--p-text-muted-color, #6b7280);
  font-size: 0.9rem;
  padding: 0.5rem;
}

.icon-picker-license-entry {
  margin-bottom: 1.5rem;
}

.icon-picker-license-entry h4 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.25rem;
}

.icon-picker-license-text {
  white-space: pre-wrap;
  font-size: 0.75rem;
  background: var(--p-content-background, #f9fafb);
  padding: 0.75rem;
  border-radius: 6px;
  max-height: 12rem;
  overflow-y: auto;
}
</style>
