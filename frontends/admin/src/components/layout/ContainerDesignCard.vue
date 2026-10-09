<script setup lang="ts">
import { useLayoutEditor } from '../../composables/layoutEditor/useLayoutEditor'
import CollapsibleCard from './CollapsibleCard.vue'
import ContainerDesignFields from '../ContainerDesignFields.vue'

// Font & alignment of the selected container in the active Design (staged, saved with the Layout).
const ed = useLayoutEditor()

</script>

<template>
  <CollapsibleCard card-key="design" icon="pi-palette" title="Container Design" v-if="ed.preview.canEditContainerDesign" class="editor-design-card">
    <div v-if="!ed.selectedContainer" class="empty-state empty-state--compact">
      <i class="pi pi-palette"></i>
      <p>Select a container to edit its design.</p>
    </div>
    <template v-else>
      <p class="hint">Font &amp; alignment for #{{ ed.selectedContainer.id }} in the active Design. Previewed live; saved with the layout.</p>
      <ContainerDesignFields
        :styles="ed.preview.selectedContainerDesignStyles"
        :palette="ed.preview.designPreview?.default_colors ?? []"
        @change="ed.preview.setContainerDesignStyle"
      />
    </template>
  </CollapsibleCard>
</template>

<style scoped>
.editor-design-card {
  width: 100%;
}

.hint {
  color: var(--p-text-muted-color, #888);
  font-size: 0.75rem;
  margin: 0;
}
</style>
