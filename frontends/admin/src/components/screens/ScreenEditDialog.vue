<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import Checkbox from 'primevue/checkbox'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import DialogTitle from '../ui/DialogTitle.vue'
import DialogFooter from '../ui/DialogFooter.vue'
import { useAck } from '../../composables/useAck'
import { useAspectRatios } from '../../composables/useAspectRatios'
import { useSocket } from '../../composables/useSocket'
import { useScreengroupsStore } from '../../stores/screengroups'
import type { Screen } from '../../types/models'

// "Rename Screen" dialog of the Screens page: name, aspect ratio, rotation and
// screen group membership of `screen`. Fills itself each time it opens.
const props = defineProps<{ screen: Screen | null }>()
const visible = defineModel<boolean>('visible', { default: false })

const { on, off, emit } = useSocket()
const { request } = useAck()
const screengroupsStore = useScreengroupsStore()

const isRenaming = ref(false)
const renameForm = ref({
  name: '',
  screengroup_ids: [] as number[],
  aspect_ratio: '16:9',
  rotation: 0,
})
const { ratios: aspectRatios } = useAspectRatios()
const ROTATION_OPTIONS = [
  { label: 'None (0°)', value: 0 },
  { label: '+90° (clockwise)', value: 90 },
  { label: '-90° (counter-clockwise)', value: 270 },
  { label: '180°', value: 180 },
]

// Every screen also has a hidden one-screen group; only real groups are offered.
const editableGroups = computed(() => screengroupsStore.screengroups.filter(sg => !sg.is_one_screen))

// Receives the current screengroup membership for the screen being edited
const handleScreengroupsData = (data: { all_screengroups: unknown[]; current_screengroups: number[] }) => {
  if (props.screen && data.current_screengroups) {
    renameForm.value.screengroup_ids = data.current_screengroups
  }
}

onMounted(() => {
  on('displayhive:screens:stc:screen_screengroups', handleScreengroupsData)
})

onUnmounted(() => {
  off('displayhive:screens:stc:screen_screengroups', handleScreengroupsData)
})

watch(visible, (open) => {
  if (!open || !props.screen) return
  const screen = props.screen
  renameForm.value = {
    name: screen.name,
    screengroup_ids: [],
    aspect_ratio: screen.aspect_ratio || '16:9',
    rotation: screen.rotation || 0,
  }
  emit('displayhive:screens:cts:get_screen_screengroups', { screen_id: screen.id })
})

const saveRename = async (keepOpen = false) => {
  if (!props.screen) return
  isRenaming.value = true
  try {
    const ack = await request('displayhive:screens:cts:rename_screen', {
      id: props.screen.id,
      old_name: props.screen.name,
      new_name: renameForm.value.name,
      screengroup_ids: renameForm.value.screengroup_ids,
      aspect_ratio: renameForm.value.aspect_ratio,
      rotation: renameForm.value.rotation,
    }, { success: `Screen "${renameForm.value.name}" saved`, error: 'Could not save the screen' })
    if (ack && !keepOpen) visible.value = false
  } finally {
    isRenaming.value = false
  }
}
</script>

<template>
  <Dialog v-model:visible="visible" modal :style="{ width: '600px' }">
    <template #header>
      <DialogTitle icon="pi-pencil" title="Rename Screen" />
    </template>
    <div class="dialog-content">
      <div class="field">
        <label for="rename-name">Screen Name</label>
        <InputText id="rename-name" v-model="renameForm.name" class="w-full" />
      </div>
      <div class="field">
        <label for="rename-aspect-ratio">Aspect Ratio</label>
        <Select
          id="rename-aspect-ratio"
          v-model="renameForm.aspect_ratio"
          :options="aspectRatios.includes(renameForm.aspect_ratio) ? aspectRatios : [...aspectRatios, renameForm.aspect_ratio]"
          class="w-full"
        />
        <small class="hint">The Layout variation closest to this ratio is sent to the screen. Ratios are added on the Designs page.</small>
      </div>
      <div class="field">
        <label for="rename-rotation">Rotation</label>
        <Select
          id="rename-rotation"
          v-model="renameForm.rotation"
          :options="ROTATION_OPTIONS"
          optionLabel="label"
          optionValue="value"
          class="w-full"
        />
        <small class="hint">Turns everything the screen shows, as one piece, for displays mounted sideways or upside-down. The layout is laid out at the aspect ratio above first, then rotated. The screen reloads when this changes.</small>
      </div>
      <div class="field" data-tour="rename-screengroups-field">
        <label>Screengroups</label>
        <div class="screengroup-checkboxes">
          <div v-for="sg in editableGroups" :key="sg.id" class="checkbox-item">
            <Checkbox
              :inputId="`sg-${sg.id}`"
              v-model="renameForm.screengroup_ids"
              :value="sg.id"
            />
            <label :for="`sg-${sg.id}`">{{ sg.name }}</label>
          </div>
        </div>
      </div>
    </div>
    <template #footer>
      <DialogFooter show-update :loading="isRenaming" :cancel-disabled="isRenaming" @cancel="visible = false" @update="saveRename(true)" @confirm="saveRename()" />
    </template>
  </Dialog>
</template>

<style scoped>
.screengroup-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 300px;
  overflow-y: auto;
  padding: 0.5rem;
  border: 1px solid var(--p-content-border-color, #dee2e6);
  border-radius: 4px;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.checkbox-item label {
  margin: 0;
  cursor: pointer;
}
</style>
