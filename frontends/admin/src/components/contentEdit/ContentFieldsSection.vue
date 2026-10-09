<script setup lang="ts">
import { ref } from 'vue'
import { useContentEditor } from '../../composables/contentEdit/useContentEditor'
import FieldValueEditor from '../FieldValueEditor.vue'
import InputText from 'primevue/inputtext'
import Popover from 'primevue/popover'

// The "Content" section: the title and one editor per field of the content type.
const ed = useContentEditor()

const titleHelpPopover = ref<InstanceType<typeof Popover> | null>(null)
const toggleTitleHelp = (e: Event) => titleHelpPopover.value?.toggle(e)
</script>

<template>
  <section class="form-section">
    <h3 class="form-section-title">Content</h3>

    <div class="field" data-tour="content-title-field">
      <label for="create-title">
        Title *
        <i
          class="pi pi-question-circle field-help-icon"
          role="button"
          tabindex="0"
          aria-label="Help: Title"
          @click="toggleTitleHelp"
          @keydown.enter="toggleTitleHelp"
        ></i>
      </label>
      <Popover ref="titleHelpPopover">
        <p class="field-help-text">
          The title is only shown in the admin backend and in on-screen debug overlays —
          it's never rendered to viewers. It exists purely to help you keep an overview of
          your content list.
        </p>
      </Popover>
      <InputText id="create-title" v-model="ed.createForm.title" class="w-full" />
    </div>

    <div v-if="ed.tagConfigs.length > 0" class="tag-fields-section">
      <div
        v-for="tag in ed.tagConfigs"
        v-show="tag.fieldHandler !== '' && ed.tagHasVisibleControl[tag.name] !== false"
        :key="tag.name"
        class="field"
      >
        <label :for="`field-${tag.name}`">{{ tag.title || tag.name }}</label>
        <small v-if="tag.description" class="field-description">{{ tag.description }}</small>
        <FieldValueEditor
          :tag="tag"
          :fields="ed.createForm.fields"
          mode="edit"
          :palette="ed.designPalette"
          :option-flags="tag.optionFlags"
          @update:has-visible-control="(v) => (ed.tagHasVisibleControl[tag.name] = v)"
        />
      </div>
    </div>
  </section>
</template>

<style scoped>
.form-section {
  margin-bottom: 1.5rem;
}

.form-section-title {
  margin: 0 0 0.75rem 0;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--p-content-border-color, #e5e7eb);
  font-size: 0.95rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--p-text-muted-color, #6b7280);
}

.field-help-icon {
  font-size: 0.85rem;
  margin-left: 0.35rem;
  color: var(--p-text-muted-color, #9ca3af);
  cursor: pointer;
}

.field-help-text {
  max-width: 300px;
  margin: 0;
  font-size: 0.85rem;
  line-height: 1.5;
}

.tag-fields-section {
  display: flex;
  flex-direction: column;
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--p-content-border-color, #ddd);
}

.tag-fields-section h4 {
  margin: 0 0 1rem 0;
  font-size: 1rem;
}

.tag-fields-section .field {
  padding: 1.5rem 0;
  border-bottom: 1px solid var(--p-content-border-color, #e5e7eb);
}

.tag-fields-section .field:last-child {
  padding-bottom: 0;
  border-bottom: none;
}

.tag-fields-section .field:first-child {
  padding-top: 0;
}

.field-description {
  color: #666;
  font-size: 0.75rem;
  margin-top: -0.25rem;
}
</style>
