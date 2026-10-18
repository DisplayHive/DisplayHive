<script setup lang="ts">
import { computed } from 'vue'
import type { DesignForm } from '../../types/designForm'
import DesignPanel from './DesignPanel.vue'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import Message from 'primevue/message'
import Select from 'primevue/select'

// The animation between the contents of a container when the next scene replaces it. One setting for the
// whole Design. Browsers that cannot do what an effect needs fall back to a fade; very old kiosks show the new
// content at once. The values are the ones the screen client knows (frontends/screen/ts/screen/transitions.ts)
// and the server accepts (application/admin/designs/helper.py).
const form = defineModel<DesignForm>('form', { required: true })

type Option = { label: string; value: string; effort?: 'light' | 'medium' | 'heavy' }
const GROUPS: Array<{ label: string; items: Option[] }> = [
  { label: 'No animation', items: [{ label: 'None', value: '' }] },
  {
    label: 'Light: movement and fading (fine everywhere)',
    items: [
      { label: 'Fade', value: 'fade', effort: 'light' },
      { label: 'Slide (old moves out, new moves in)', value: 'slide', effort: 'light' },
      { label: 'Push and fade', value: 'push-fade', effort: 'light' },
      { label: 'Slide with bounce', value: 'bounce', effort: 'light' },
      { label: 'Cover (new slides over the old)', value: 'cover', effort: 'light' },
      { label: 'Reveal (old slides away)', value: 'reveal', effort: 'light' },
      { label: 'Parallax (old moves slower)', value: 'parallax', effort: 'light' },
      { label: 'Stack (old sinks back)', value: 'stack', effort: 'light' },
      { label: 'Zoom in', value: 'zoom-in', effort: 'light' },
      { label: 'Zoom out', value: 'zoom-out', effort: 'light' },
      { label: 'Rotate', value: 'rotate', effort: 'light' },
      { label: 'Hinge (old falls away)', value: 'hinge', effort: 'light' },
      { label: 'Skew slide', value: 'skew', effort: 'light' },
    ],
  },
  {
    label: 'Medium: shapes that open (clip-path)',
    items: [
      { label: 'Wipe', value: 'wipe', effort: 'medium' },
      { label: 'Diagonal wipe (from a corner)', value: 'diagonal', effort: 'medium' },
      { label: 'Split open (from the middle line)', value: 'split-open', effort: 'medium' },
      { label: 'Split close (old closes to the middle)', value: 'split-close', effort: 'medium' },
      { label: 'Circle', value: 'circle', effort: 'medium' },
      { label: 'Circle from a corner', value: 'corner-circle', effort: 'medium' },
      { label: 'Diamond', value: 'diamond', effort: 'medium' },
      { label: 'Box (grows from the middle)', value: 'box', effort: 'medium' },
    ],
  },
  {
    label: '⚠ Heavy: masks, filters, 3D (can stutter on weak hardware)',
    items: [
      { label: '⚠ Blinds', value: 'blinds', effort: 'heavy' },
      { label: '⚠ Flash', value: 'flash', effort: 'heavy' },
      { label: '⚠ Flip (3D card)', value: 'flip', effort: 'heavy' },
      { label: '⚠ Cube (3D)', value: 'cube', effort: 'heavy' },
      { label: '⚠ Blur', value: 'blur', effort: 'heavy' },
      { label: '⚠ Glitch', value: 'glitch', effort: 'heavy' },
    ],
  },
  {
    label: 'Random: the same one for all containers at a scene change',
    items: [
      { label: 'Random, light only', value: 'random-light' },
      { label: 'Random, light and medium', value: 'random-medium' },
      { label: '⚠ Random, all (including heavy)', value: 'random' },
    ],
  },
  {
    label: 'Random by container: each container picks its own',
    items: [
      { label: 'Random by container, light only', value: 'random-container-light' },
      { label: 'Random by container, light and medium', value: 'random-container-medium' },
      { label: '⚠ Random by container, all (including heavy)', value: 'random-container' },
    ],
  },
]
const ALL = GROUPS.flatMap((g) => g.items)
const DIRECTIONS = [
  { label: 'To the left', value: 'left' },
  { label: 'To the right', value: 'right' },
  { label: 'Upwards', value: 'up' },
  { label: 'Downwards', value: 'down' },
]
const SCOPES = [
  { label: 'Each container on its own', value: 'container' },
  { label: 'The whole slide (one effect across the screen)', value: 'slide' },
]
const STAGGERS = [
  { label: 'All containers at once', value: '' },
  { label: 'One after another, in layout order', value: 'order' },
  { label: 'Top to bottom', value: 'top-bottom' },
  { label: 'Left to right', value: 'left-right' },
  { label: 'From the middle outwards', value: 'centre-out' },
  { label: 'Random order', value: 'random' },
]
const NO_DIRECTION = ['fade', 'zoom-in', 'zoom-out', 'rotate', 'circle', 'diamond', 'box', 'flash', 'blur', 'glitch']
const hasDirection = computed(() => !!form.value.transition && !NO_DIRECTION.includes(form.value.transition) && !form.value.transition.startsWith('random'))
const selected = computed(() => ALL.find((o) => o.value === form.value.transition))
const heavy = computed(() => selected.value?.effort === 'heavy' || ['random', 'random-container'].includes(form.value.transition))
</script>

<template>
  <DesignPanel
    title="Transition"
    description="How the content of a container changes when the next scene starts. The time counts inside the scene's duration."
  >
    <div class="font-properties-grid">
      <div class="field">
        <label for="transition-type">Animation</label>
        <Select
          v-model="form.transition" inputId="transition-type" data-testid="design-transition-type"
          :options="GROUPS" optionGroupLabel="label" optionGroupChildren="items"
          optionLabel="label" optionValue="value" size="small" class="w-full"
        />
      </div>
      <div v-if="hasDirection" class="field">
        <label for="transition-direction">Direction</label>
        <Select
          v-model="form.transition_direction" inputId="transition-direction"
          :options="DIRECTIONS" optionLabel="label" optionValue="value" size="small" class="w-full"
        />
      </div>
      <div v-if="form.transition" class="field">
        <label for="transition-scope">Applies to</label>
        <Select
          v-model="form.transition_scope" inputId="transition-scope" data-testid="design-transition-scope"
          :options="SCOPES" optionLabel="label" optionValue="value" size="small" class="w-full"
        />
      </div>
      <div v-if="form.transition" class="field">
        <label for="transition-stagger">Start order</label>
        <Select
          v-model="form.transition_stagger" inputId="transition-stagger" data-testid="design-transition-stagger"
          :options="STAGGERS" optionLabel="label" optionValue="value" size="small" class="w-full"
        />
      </div>
      <div v-if="form.transition" class="field">
        <label for="transition-duration">Duration</label>
        <InputNumber
          v-model="form.transition_duration_ms" inputId="transition-duration"
          :min="100" :max="5000" :step="100" suffix=" ms" size="small" class="w-full"
        />
      </div>
    </div>
    <Message v-if="heavy" severity="warn" size="small" :closable="false" data-testid="design-transition-warning">
      This effect uses masks, filters or 3D (a random choice may include them). It looks fine on a PC, but it can
      stutter on weak screens such as an older Raspberry Pi or a smart-TV browser. Try it on your real screens first.
      A browser that cannot do it falls back to a fade.
    </Message>
    <div v-if="form.transition" class="field transition-sequential-row">
      <Checkbox v-model="form.transition_sequential" inputId="transition-sequential" binary data-testid="design-transition-sequential" />
      <label for="transition-sequential">The old content leaves at the end of its scene, the new one comes in at the start of the next (each takes half of the duration)</label>
    </div>
    <div v-if="form.transition" class="field transition-sequential-row">
      <Checkbox v-model="form.transition_unchanged" inputId="transition-unchanged" binary data-testid="design-transition-unchanged" />
      <label for="transition-unchanged">Also animate containers whose content stays the same (it is shown again, so a video or page inside restarts)</label>
    </div>
  </DesignPanel>
</template>

<style scoped src="./design-panel.css"></style>
<style scoped>
.transition-sequential-row {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}
</style>
