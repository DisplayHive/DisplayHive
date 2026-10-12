<script setup lang="ts">
import { provideLayoutEditor } from '../composables/layoutEditor/useLayoutEditor'
import type { Layout, ContentContainer } from '../types/models'
import LayoutContainerSidebar from './layout/LayoutContainerSidebar.vue'
import LayoutCanvas from './layout/LayoutCanvas.vue'
import ContainerDesignCard from './layout/ContainerDesignCard.vue'
import LayoutRatioCard from './layout/LayoutRatioCard.vue'
import LayoutOptionsCard from './layout/LayoutOptionsCard.vue'
import ContainerSettingsCard from './layout/ContainerSettingsCard.vue'

// The Layout canvas editor: containers as rectangles on a canvas (move, resize, draw), the lists
// of containers, the aspect-ratio variations, preview options and the selected container's
// settings. Moves, resizes and settings edits are only STAGED here (and previewed live);
// the Layout page sends them with flushPendingPositions() when the Layout is saved.
//
// The state and behaviour live in composables/layoutEditor/ (see useLayoutEditor.ts); the
// parts of the screen are the components in ./layout/, which get the editor by injection.
const props = defineProps<{
  layout: Layout
  containers: ContentContainer[]
  layouts: Layout[]
}>()

const editor = provideLayoutEditor(props)

defineExpose({
  flushPendingPositions: editor.flushPendingPositions,
  discardPendingPositions: editor.discardPendingPositions,
})
</script>

<template>
  <div class="layout-editor">
    <LayoutContainerSidebar />

    <div class="editor-main">
      <LayoutCanvas />
      <ContainerDesignCard />
    </div>

    <div class="editor-right-column">
      <LayoutRatioCard />
      <LayoutOptionsCard />
      <ContainerSettingsCard />
    </div>
  </div>
</template>

<style scoped>
.layout-editor {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
}

.editor-right-column {
  flex: 0 0 340px;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  position: sticky;
  top: 1rem;
  max-height: calc(100vh - 2rem);
  overflow-y: auto;
  overflow-x: hidden;
}

.editor-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
</style>
