<script setup lang="ts">
import PageHeaderSlot from '../components/PageHeaderSlot.vue'
import RouteLink from '../components/RouteLink.vue'
import ContentTypePickerDialog from '../components/contentEdit/ContentTypePickerDialog.vue'
import ContentFieldsSection from '../components/contentEdit/ContentFieldsSection.vue'
import DeliverySettings from '../components/contentEdit/DeliverySettings.vue'
import ContentPreviewPane from '../components/contentEdit/ContentPreviewPane.vue'
import { provideContentEditor } from '../composables/contentEdit/useContentEditor'
import { links } from '../utils/links'
import { useRightsStore } from '../stores/rights'
import Button from 'primevue/button'
import Tag from 'primevue/tag'

// Create, edit or copy one content element. What is edited is decided by the URL; the form, saving,
// screen assignment and preview are composables/contentEdit/, the parts of the page are the
// components in components/contentEdit/ (they get the editor by injection).
const ed = provideContentEditor()
const rightsStore = useRightsStore()
</script>

<template>
  <ContentTypePickerDialog />

  <PageHeaderSlot>
    <Button label="Back to Content" icon="pi pi-arrow-left" text @click="ed.goBack" />
  </PageHeaderSlot>

  <div class="content-edit-page">
    <div v-if="ed.loadingContentTypeDetail" class="loading-state">
      <i class="pi pi-spin pi-spinner"></i>
      <p>Loading content type...</p>
    </div>
    <div v-else class="content-edit-columns">
      <div class="content-edit-form">
        <div class="dialog-content">
    <div v-if="ed.selectedContentType" class="content-type-banner">
      <i class="pi pi-file-edit"></i>
      <div>
        <strong>
          <RouteLink v-if="rightsStore.can('contenttypes.page')" :to="links.contentType(ed.selectedContentType.id)" title="Open this content type">{{ ed.selectedContentType.name }}</RouteLink>
          <template v-else>{{ ed.selectedContentType.name }}</template>
        </strong>
        <p v-if="ed.selectedContentType.description" class="text-muted">{{ ed.selectedContentType.description }}</p>
      </div>
    </div>

    <div v-if="ed.affectsMultipleScreens" class="multi-screen-warning">
      <i class="pi pi-exclamation-triangle"></i>
      <div>
        <p>
          This content element is shown on multiple screens via direct assignment or a group.
          If you edit it you will affect the following screens:
        </p>
        <div class="multi-screen-warning-list">
          <Tag v-for="name in ed.affectedScreenNames" :key="name" :value="name" severity="warn" />
        </div>
        <p class="multi-screen-warning-help">
          Changes here apply everywhere this content is used — there's no way to edit just one
          of these screens. If you only want to change it in one place, go back and use
          <strong>Copy</strong> to create an independent element first.
        </p>
      </div>
    </div>


          <ContentFieldsSection />
          <DeliverySettings />
        </div>

        <div class="content-edit-form-actions" data-tour="content-form-actions">
          <Button data-tour="content-cancel" label="Cancel" @click="ed.goBack" text />
          <Button v-if="ed.editMode && ed.createForm.id" label="Update" severity="secondary" outlined @click="ed.submitCreateContent(true)" :disabled="ed.loadingContentTypeDetail" />
          <Button data-tour="content-save" :label="ed.editMode && ed.createForm.id ? 'Save' : 'Create'" @click="ed.submitCreateContent()" :disabled="ed.loadingContentTypeDetail" />
        </div>
      </div>

      <ContentPreviewPane />
    </div>
  </div>
</template>

<style scoped>
.content-edit-page {
  padding: 1.5rem;
  max-width: 1600px;
  margin: 0 auto;
}

/* Two-column layout, mirroring LayoutCanvasEditor.vue's main+sidebar split
   (.layout-editor) — here both sides are flexible instead of one fixed. */
.content-edit-columns {
  display: flex;
  gap: 1.5rem;
  align-items: flex-start;
}

.content-edit-form {
  flex: 1;
  min-width: 0;
}

.content-edit-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.25rem;
}

.content-type-banner {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  background: var(--p-content-background, #f8f9fa);
  border: 1px solid var(--p-content-border-color, #e5e7eb);
  border-radius: 6px;
  padding: 0.75rem 1rem;
  margin-bottom: 1.25rem;
}

.content-type-banner > i {
  font-size: 1.1rem;
  margin-top: 0.15rem;
  color: var(--p-text-muted-color, #6b7280);
  flex-shrink: 0;
}

.content-type-banner p {
  margin: 0.15rem 0 0 0;
  font-size: 0.85rem;
}

.multi-screen-warning {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
  background: #fef3c7;
  border: 2px solid #f59e0b;
  border-radius: 8px;
  padding: 1.25rem;
  margin-bottom: 1.25rem;
}

.multi-screen-warning > i {
  font-size: 2.5rem;
  color: #b45309;
  flex-shrink: 0;
}

.multi-screen-warning p {
  margin: 0 0 0.75rem 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: #78350f;
}

.multi-screen-warning-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.multi-screen-warning-help {
  margin-top: 0.75rem !important;
  font-size: 0.85rem !important;
  font-weight: 400 !important;
  color: #92400e !important;
}

/* Dark mode: the light-mode pale-amber banner (background/text all fixed
   dark-on-light amber tones, meant for a light page) needs the pairing
   inverted rather than just a background swap — light-mode dark-amber text
   would be unreadable against a dark card. */
.dark-mode .multi-screen-warning {
  background: var(--p-surface-800, #1e293b);
  border-color: var(--p-amber-600, #d97706);
}

.dark-mode .multi-screen-warning > i {
  color: var(--p-amber-400, #fbbf24);
}

.dark-mode .multi-screen-warning p {
  color: var(--p-amber-200, #fde68a);
}

.dark-mode .multi-screen-warning-help {
  color: var(--p-amber-300, #fcd34d) !important;
}
</style>
