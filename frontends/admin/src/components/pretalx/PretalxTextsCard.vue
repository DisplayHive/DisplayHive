<script setup lang="ts">
import { ref, watch } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import { useAck } from '../../composables/useAck'
import type { PretalxSettings } from './types'

// "Default Texts" card of the Pretalx page: the fallback texts shown when no
// session is running, what is coming up and when the API data is invalid.
const props = defineProps<{ settings: PretalxSettings; canManage: boolean }>()

const { request } = useAck()
const pretalxNoSessionText = ref('No session running')
const pretalxComingUpText = ref('Coming up next')
const pretalxInvalidDataText = ref('Invalid API data')
const textsSaving = ref(false)

watch(() => props.settings, (s) => {
  pretalxNoSessionText.value   = s.no_session_text  ?? 'No session running'
  pretalxComingUpText.value    = s.coming_up_text   ?? 'Coming up next'
  pretalxInvalidDataText.value = s.invalid_data_text ?? 'Invalid API data'
}, { immediate: true })

const savePretalxTexts = async () => {
  textsSaving.value = true
  try {
    await request('displayhive:admin:pretalx:cts:save_settings', {
      no_session_text:   pretalxNoSessionText.value,
      coming_up_text:    pretalxComingUpText.value,
      invalid_data_text: pretalxInvalidDataText.value,
    }, { success: 'Default texts updated', error: 'Save failed' })
  } finally {
    textsSaving.value = false
  }
}
</script>

<template>
  <Card>
    <template #title>
      <div class="card-header">
        <i class="pi pi-comment card-header-icon" />
        <span>Default Texts</span>
      </div>
    </template>
    <template #content>
      <p class="settings-hint">All settings are only default values. They may be overwritten in the content.</p>
      <div class="settings-form" data-tour="pretalx-texts-fields">
        <div class="field">
          <label for="pretalx-no-session">No Session Running</label>
          <InputText id="pretalx-no-session" v-model="pretalxNoSessionText" class="w-full" :disabled="!canManage" />
        </div>
        <div class="field">
          <label for="pretalx-coming-up">Coming Up Next</label>
          <InputText id="pretalx-coming-up" v-model="pretalxComingUpText" class="w-full" :disabled="!canManage" />
        </div>
        <div class="field">
          <label for="pretalx-invalid-data">Invalid API Data</label>
          <InputText id="pretalx-invalid-data" v-model="pretalxInvalidDataText" class="w-full" :disabled="!canManage" />
        </div>
        <div class="field-actions">
          <Button v-if="canManage" label="Save" icon="pi pi-check" :loading="textsSaving" @click="savePretalxTexts" />
        </div>
      </div>
    </template>
  </Card>
</template>

<style scoped src="./shared.css"></style>
