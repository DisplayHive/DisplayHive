<script setup lang="ts">
import { ref, watch } from 'vue'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import ToggleSwitch from 'primevue/toggleswitch'
import Button from 'primevue/button'
import Card from 'primevue/card'

import { useAck } from '../../composables/useAck'
import type { SystemSettings } from './types'
import { isTrue } from './types'

// "Dashboard" card of the Settings page: welcome text and what to hide (community links, badge, Demo Mode, tours).
const props = defineProps<{ settings: SystemSettings; canEdit: boolean }>()

const { request } = useAck()

const saving = ref(false)
const welcomeHeadline = ref('')
const welcomeText = ref('')
const hideCommunityLinks = ref(false)
const hideHelpingHand = ref(false)
const hidePoweredBy = ref(false)
const hideDemoMode = ref(false)
const hideUserTours = ref(false)
const hideAdminTours = ref(false)

watch(() => props.settings, (sys) => {
  welcomeHeadline.value = sys.welcome_headline ?? 'Welcome to DisplayHive Admin'
  welcomeText.value = sys.welcome_text ?? 'Use the navigation menu to manage your digital signage system.'
  hideCommunityLinks.value = isTrue(sys.hide_community_links)
  hideHelpingHand.value = isTrue(sys.hide_helping_hand)
  hidePoweredBy.value = isTrue(sys.hide_powered_by)
  hideDemoMode.value = isTrue(sys.hide_demo_mode)
  hideUserTours.value = isTrue(sys.hide_user_tours)
  hideAdminTours.value = isTrue(sys.hide_admin_tours)
}, { immediate: true })

const saveDashboardSettings = async () => {
  if (!props.canEdit) return
  saving.value = true
  try {
    await request(
      'displayhive:admin:cts:set_system_settings',
      {
        settings: {
          welcome_headline: welcomeHeadline.value,
          welcome_text: welcomeText.value,
          hide_community_links: hideCommunityLinks.value ? 'true' : 'false',
          hide_helping_hand: hideHelpingHand.value ? 'true' : 'false',
          hide_powered_by: hidePoweredBy.value ? 'true' : 'false',
          hide_demo_mode: hideDemoMode.value ? 'true' : 'false',
          hide_user_tours: hideUserTours.value ? 'true' : 'false',
          hide_admin_tours: hideAdminTours.value ? 'true' : 'false',
        },
      },
      { success: 'Dashboard settings updated', error: 'Save failed' },
    )
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Card>
    <template #title>
      <div class="card-header-title">
        <i class="pi pi-home card-header-icon" />
        <span>Dashboard</span>
      </div>
    </template>
    <template #content>
      <div class="settings-form">
        <div class="field-group" data-tour="settings-welcome-fields">
        <div class="field">
          <label for="welcome-headline">Welcome headline</label>
          <InputText
            id="welcome-headline"
            v-model="welcomeHeadline"
            class="w-full"
            placeholder="Welcome to DisplayHive Admin"
            :disabled="!canEdit"
          />
        </div>
        <div class="field">
          <label for="welcome-text">Welcome text</label>
          <Textarea
            id="welcome-text"
            v-model="welcomeText"
            class="w-full"
            rows="3"
            autoResize
            placeholder="Use the navigation menu to manage your digital signage system."
            :disabled="!canEdit"
          />
        </div>
        </div>
        <div class="toggle-group" data-tour="settings-visibility-toggles">
        <div class="field toggle-field">
          <label for="hide-community-links">Hide community links</label>
          <ToggleSwitch id="hide-community-links" v-model="hideCommunityLinks" :disabled="!canEdit" />
        </div>
        <div class="field toggle-field">
          <label for="hide-helping-hand">Hide "Where a helping hand goes a long way" section</label>
          <ToggleSwitch id="hide-helping-hand" v-model="hideHelpingHand" :disabled="!canEdit" />
        </div>
        <div class="field toggle-field">
          <label for="hide-powered-by">Hide "powered by DisplayHive" badge on screens</label>
          <ToggleSwitch id="hide-powered-by" v-model="hidePoweredBy" :disabled="!canEdit" />
        </div>
        <div class="field toggle-field">
          <label for="hide-demo-mode">Hide Demo Mode (removes it from the top bar and blocks the API)</label>
          <ToggleSwitch id="hide-demo-mode" v-model="hideDemoMode" :disabled="!canEdit" />
        </div>
        <div class="field toggle-field">
          <label for="hide-user-tours">Hide User tours (removes the "User" section from the Guided Tour page)</label>
          <ToggleSwitch id="hide-user-tours" v-model="hideUserTours" :disabled="!canEdit" />
        </div>
        <div class="field toggle-field">
          <label for="hide-admin-tours">Hide Admin Path tours (removes the "Admin Path" section from the Guided Tour page)</label>
          <ToggleSwitch id="hide-admin-tours" v-model="hideAdminTours" :disabled="!canEdit" />
        </div>
        </div>
        <div class="field-actions" data-tour="settings-dashboard-save">
          <Button
            v-if="canEdit"
            label="Save"
            icon="pi pi-check"
            :loading="saving"
            @click="saveDashboardSettings"
          />
        </div>
      </div>
    </template>
  </Card>
</template>

<style scoped src="./settingsForm.css"></style>
