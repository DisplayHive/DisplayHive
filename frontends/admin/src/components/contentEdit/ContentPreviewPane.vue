<script setup lang="ts">
import { useContentEditor } from '../../composables/contentEdit/useContentEditor'
import { useSettingsStore } from '../../stores/settings'
import { cssAspectRatio } from '../../composables/useAspectRatios'
import { computed, ref } from 'vue'
import type { ContainerTextStyle } from '../../utils/design/designPreview'
import { useRightsStore } from '../../stores/rights'
import PreviewFrame from '../ui/PreviewFrame.vue'
import PreviewEditLayer from './PreviewEditLayer.vue'
import Select from 'primevue/select'

// The live preview next to the form (its width is a Settings option).
const ed = useContentEditor()
const settingsStore = useSettingsStore()

// Editing in the preview: see PreviewEditLayer.vue. Changing needs the right to save: content.create
// for new content (and copies), content.edit for existing content.
const textStyles = ref<Record<string, ContainerTextStyle>>({})
const rights = useRightsStore()
const canChange = computed(() => rights.can(ed.editMode ? 'content.edit' : 'content.create'))
</script>

<template>
<div class="content-edit-preview" :style="{ flex: `0 0 ${settingsStore.contentEditPreviewSize}%` }">
  <div v-if="ed.previewRatios.length > 1" class="content-edit-preview-ratio">
    <label for="preview-ratio">Preview as</label>
    <Select id="preview-ratio" v-model="ed.previewRatio" :options="ed.previewRatios" size="small" />
  </div>
  <div v-if="!ed.previewSrcdoc" class="content-edit-preview-empty" :style="{ aspectRatio: cssAspectRatio(ed.previewRatio) }">
    <i class="pi pi-eye"></i>
    <p>Preview will appear here once a content type is selected.</p>
  </div>
  <div v-else class="content-edit-preview-stage" :style="{ aspectRatio: cssAspectRatio(ed.previewRatio) }">
    <PreviewFrame
      :html="ed.previewSrcdoc"
      class="content-edit-preview-iframe"
      title="Content preview"
      @container-styles="(s) => (textStyles = s)"
    />
    <PreviewEditLayer
      :containers="ed.previewContainers"
      :tags="ed.tagConfigs"
      :fields="ed.createForm.fields"
      :palette="ed.designPalette"
      :editable="canChange"
      :control-visible="ed.tagHasVisibleControl"
      :text-styles="textStyles"
    />
  </div>
</div>
</template>

<style scoped>
.content-edit-preview {
  flex: 1;
  min-width: 0;
  position: sticky;
  top: calc(1rem + 200px);
}

.content-edit-preview h4 {
  margin-top: 0;
}

.content-edit-preview-ratio {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.content-edit-preview-ratio label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.content-edit-preview-stage {
  position: relative;
  width: 100%;
}

.content-edit-preview-stage .content-edit-preview-iframe {
  position: absolute;
  inset: 0;
  height: 100%;
}

.content-edit-preview-iframe {
  width: 100%;
  aspect-ratio: 16 / 9;
  border: 1px solid var(--p-content-border-color, #ccc);
  border-radius: 6px;
}

.content-edit-preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  aspect-ratio: 16 / 9;
  border: 1px dashed var(--p-content-border-color, #ccc);
  border-radius: 6px;
  color: var(--p-text-muted-color, #6b7280);
}

.content-edit-preview-empty i {
  font-size: 2rem;
}
</style>
