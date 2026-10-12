<script setup lang="ts">
import { ref, watch } from 'vue'
import InputNumber from 'primevue/inputnumber'
import Button from 'primevue/button'
import Card from 'primevue/card'

import { useAck } from '../../composables/useAck'
import type { SystemSettings } from './types'

// "Content Editor" card of the Settings page: preview sizes of the content edit page and list.
const props = defineProps<{ settings: SystemSettings; canEdit: boolean }>()

const { request } = useAck()

const contentSaving = ref(false)
const contentEditPreviewSize = ref(35)
const contentListPreviewSize = ref(20)

watch(() => props.settings, (sys) => {
  const previewSize = Number(sys.content_edit_preview_size)
  contentEditPreviewSize.value = Number.isFinite(previewSize) && previewSize > 0 ? previewSize : 35
  const listPreviewSize = Number(sys.content_list_preview_size)
  contentListPreviewSize.value = Number.isFinite(listPreviewSize) && listPreviewSize > 0 ? listPreviewSize : 20
}, { immediate: true })

const saveContentSettings = async () => {
  if (!props.canEdit) return
  contentSaving.value = true
  try {
    await request(
      'displayhive:admin:cts:set_system_settings',
      {
        settings: {
          content_edit_preview_size: String(contentEditPreviewSize.value),
          content_list_preview_size: String(contentListPreviewSize.value),
        },
      },
      { success: 'Content editor settings updated', error: 'Save failed' },
    )
  } finally {
    contentSaving.value = false
  }
}
</script>

<template>
  <Card>
    <template #title>
      <div class="card-header-title">
        <i class="pi pi-file-edit card-header-icon" />
        <span>Content Editor</span>
      </div>
    </template>
    <template #content>
      <div class="settings-form">
        <div class="field-group" data-tour="settings-content-preview-fields">
        <div class="field">
          <label for="content-edit-preview-size">Preview size on the Content edit page</label>
          <div class="flex align-items-center gap-2">
            <InputNumber
              id="content-edit-preview-size"
              v-model="contentEditPreviewSize"
              :min="10"
              :max="90"
              suffix="%"
              :disabled="!canEdit"
            />
          </div>
        </div>
        <div class="field">
          <label for="content-list-preview-size">Preview size in the Content list's expanded rows</label>
          <div class="flex align-items-center gap-2">
            <InputNumber
              id="content-list-preview-size"
              v-model="contentListPreviewSize"
              :min="10"
              :max="80"
              suffix="vh"
              :disabled="!canEdit"
            />
          </div>
        </div>
        </div>
        <div class="field-actions" data-tour="settings-content-save">
          <Button
            v-if="canEdit"
            label="Save"
            icon="pi pi-check"
            :loading="contentSaving"
            @click="saveContentSettings"
          />
        </div>
      </div>
    </template>
  </Card>
</template>

<style scoped src="./settingsForm.css"></style>
