<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useRightsStore } from '../stores/rights'

import Card from 'primevue/card'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Select from 'primevue/select'
import ToggleSwitch from 'primevue/toggleswitch'
import InputNumber from 'primevue/inputnumber'

const { on, off, emit, emitWithAck } = useSocket()
const toast = useToast()
const rightsStore = useRightsStore()

const canEdit = computed(() => rightsStore.can('settings.edit'))

const loading = ref(true)
const saving = ref(false)
const timeSaving = ref(false)

const welcomeHeadline = ref('')
const welcomeText = ref('')
const hideCommunityLinks = ref(false)
const hideHelpingHand = ref(false)
const hidePoweredBy = ref(false)
const hideDemoMode = ref(false)
const contentEditPreviewSize = ref(35)
const contentListPreviewSize = ref(20)
const contentSaving = ref(false)

// Time section
const serverTimeBase = ref<Date | null>(null)
const serverTimeReceivedAt = ref(0)
const displayedServerTime = ref('')
const selectedTimezone = ref('UTC')
const correctedTime = ref('')

const timezoneOptions = (Intl as any).supportedValuesOf('timeZone').map((tz: string) => ({
  label: tz,
  value: tz,
}))

let timeTicker: ReturnType<typeof setInterval> | null = null

const updateDisplayedTimes = () => {
  if (!serverTimeBase.value) return
  const elapsed = Date.now() - serverTimeReceivedAt.value
  const current = new Date(serverTimeBase.value.getTime() + elapsed)

  const fmtOpts: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }

  displayedServerTime.value =
    new Intl.DateTimeFormat('en-GB', { ...fmtOpts, timeZone: 'UTC' }).format(current) + ' UTC'

  try {
    correctedTime.value =
      new Intl.DateTimeFormat('en-GB', { ...fmtOpts, timeZone: selectedTimezone.value }).format(current) +
      ` (${selectedTimezone.value})`
  } catch {
    correctedTime.value = '—'
  }
}

watch(selectedTimezone, updateDisplayedTimes)

const handleSettings = (data: any) => {
  loading.value = false
  const sys = data?.system_settings || {}
  welcomeHeadline.value = sys.welcome_headline ?? 'Welcome to DisplayHive Admin'
  welcomeText.value = sys.welcome_text ?? 'Use the navigation menu to manage your digital signage system.'
  hideCommunityLinks.value = sys.hide_community_links === true || sys.hide_community_links === 'true'
  hideHelpingHand.value = sys.hide_helping_hand === true || sys.hide_helping_hand === 'true'
  hidePoweredBy.value = sys.hide_powered_by === true || sys.hide_powered_by === 'true'
  hideDemoMode.value = sys.hide_demo_mode === true || sys.hide_demo_mode === 'true'
  const previewSize = Number(sys.content_edit_preview_size)
  contentEditPreviewSize.value = Number.isFinite(previewSize) && previewSize > 0 ? previewSize : 35
  const listPreviewSize = Number(sys.content_list_preview_size)
  contentListPreviewSize.value = Number.isFinite(listPreviewSize) && listPreviewSize > 0 ? listPreviewSize : 20

  if (data?.server_time) {
    serverTimeBase.value = new Date(data.server_time)
    serverTimeReceivedAt.value = Date.now()
  }
  selectedTimezone.value = sys.timezone ?? 'UTC'
  updateDisplayedTimes()
}

onMounted(() => {
  on('displayhive:admin:stc:admin_settings', handleSettings)
  emit('displayhive:admin:cts:get_admin_settings')
  timeTicker = setInterval(updateDisplayedTimes, 1000)
})

onUnmounted(() => {
  off('displayhive:admin:stc:admin_settings', handleSettings)
  if (timeTicker) clearInterval(timeTicker)
})

const saveDashboardSettings = async () => {
  if (!canEdit.value) return
  saving.value = true
  try {
    const ack = await emitWithAck<{ success: boolean; error?: string }>(
      'displayhive:admin:cts:set_system_settings',
      {
        settings: {
          welcome_headline: welcomeHeadline.value,
          welcome_text: welcomeText.value,
          hide_community_links: hideCommunityLinks.value ? 'true' : 'false',
          hide_helping_hand: hideHelpingHand.value ? 'true' : 'false',
          hide_powered_by: hidePoweredBy.value ? 'true' : 'false',
          hide_demo_mode: hideDemoMode.value ? 'true' : 'false',
        },
      },
    )
    if (ack?.success) {
      toast.add({ severity: 'success', summary: 'Saved', detail: 'Dashboard settings updated', life: 2500 })
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Save failed', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    saving.value = false
  }
}

const saveContentSettings = async () => {
  if (!canEdit.value) return
  contentSaving.value = true
  try {
    const ack = await emitWithAck<{ success: boolean; error?: string }>(
      'displayhive:admin:cts:set_system_settings',
      {
        settings: {
          content_edit_preview_size: String(contentEditPreviewSize.value),
          content_list_preview_size: String(contentListPreviewSize.value),
        },
      },
    )
    if (ack?.success) {
      toast.add({ severity: 'success', summary: 'Saved', detail: 'Content editor settings updated', life: 2500 })
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Save failed', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    contentSaving.value = false
  }
}

const saveTimeSettings = async () => {
  if (!canEdit.value) return
  timeSaving.value = true
  try {
    const ack = await emitWithAck<{ success: boolean; error?: string }>(
      'displayhive:admin:cts:set_system_settings',
      { settings: { timezone: selectedTimezone.value } },
    )
    if (ack?.success) {
      toast.add({ severity: 'success', summary: 'Saved', detail: 'Timezone updated', life: 2500 })
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Save failed', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    timeSaving.value = false
  }
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('settings.page')" class="settings-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Settings page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="settings-view">

    <div v-if="loading" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
      <p>Loading settings…</p>
    </div>

    <template v-else>
      <Card>
        <template #title>Dashboard</template>
        <template #content>
          <div class="settings-form">
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
            <div class="field-actions">
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

      <Card>
        <template #title>Content Editor</template>
        <template #content>
          <div class="settings-form">
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
            <div class="field-actions">
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

      <Card>
        <template #title>Time</template>
        <template #content>
          <div class="settings-form">
            <div class="field">
              <label>Server time</label>
              <InputText
                :value="displayedServerTime || '—'"
                class="w-full"
                readonly
                tabindex="-1"
              />
            </div>
            <div class="field">
              <label for="timezone">Timezone</label>
              <Select
                id="timezone"
                v-model="selectedTimezone"
                :options="timezoneOptions"
                optionLabel="label"
                optionValue="value"
                filter
                class="w-full"
                placeholder="Select timezone"
                :disabled="!canEdit"
              />
            </div>
            <div class="field">
              <label>Displayhive Time</label>
              <InputText
                :value="correctedTime || '—'"
                class="w-full"
                readonly
                tabindex="-1"
              />
            </div>
            <div class="field-actions">
              <Button
                v-if="canEdit"
                label="Save"
                icon="pi pi-check"
                :loading="timeSaving"
                @click="saveTimeSettings"
              />
            </div>
          </div>
        </template>
      </Card>
    </template>

  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  max-width: 640px;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 3rem;
  color: var(--p-text-muted-color, #9ca3af);
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.field label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.field-actions {
  display: flex;
  justify-content: flex-end;
}

.toggle-field {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
</style>
