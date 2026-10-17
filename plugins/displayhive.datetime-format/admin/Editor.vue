<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useFieldContext } from '@/composables/fields/useFieldContext'
import { usePreviewClock } from '@/composables/fields/usePreviewClock'
import { useSocket } from '@/composables/useSocket'
import { FORMAT_TOKENS, formatDateString } from '@/utils/content/fieldPreviews'
import FieldSlot from '@/components/fields/FieldSlot.vue'
import FormatPreview from '@/components/fields/FormatPreview.vue'
import InputText from 'primevue/inputtext'

// A date/time format (HH:mm:ss, DD.MM.YYYY …) with the format rendered live in the instance's
// timezone, and the token reference.
const f = useFieldContext()
const { on, off, emit: socketEmit } = useSocket()
const now = usePreviewClock()
const previewTimezone = ref('UTC')

const handleAdminSettings = (data: { system_settings?: { timezone?: string } }) => {
  const tz = data?.system_settings?.timezone
  if (tz) previewTimezone.value = tz
}

onMounted(() => {
  on('displayhive:admin:stc:admin_settings', handleAdminSettings)
  socketEmit('displayhive:admin:cts:get_admin_settings')
})
onUnmounted(() => off('displayhive:admin:stc:admin_settings', handleAdminSettings))

const format = () => String(f.get(f.name) || 'HH:mm:ss')
</script>

<template>
  <div class="datetime-format-wrapper">
    <FieldSlot :field-key="f.name">
      <InputText
        :id="`field-${f.name}`"
        :modelValue="format()"
        @update:modelValue="(v: string | undefined) => f.set(f.name, v ?? '')"
        class="w-full"
        placeholder="HH:mm:ss"
        :disabled="f.isLocked(f.name)"
      />
    </FieldSlot>
    <FormatPreview :value="formatDateString(now, format() || 'HH:mm:ss', previewTimezone)" :note="previewTimezone" :tokens="FORMAT_TOKENS" />
  </div>
</template>

<style scoped>
.datetime-format-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
</style>
