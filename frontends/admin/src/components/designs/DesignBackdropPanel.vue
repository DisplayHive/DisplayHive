<script setup lang="ts">
import { ref } from 'vue'
import type { DesignForm } from '../../types/designForm'
import { useDefaultColors, colorRefFor } from '../../composables/designs/useDefaultColors'
import { useGradients } from '../../composables/designs/useGradients'
import { keywordOptions, type FontOption } from '../../utils/containerFontProperties'
import DesignPanel from './DesignPanel.vue'
import ColorPicker from '../ColorPicker.vue'
import ColorPalettePicker from '../ColorPalettePicker.vue'
import MediaPickerDialog from '../MediaPickerDialog.vue'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'
import MultiSelect from 'primevue/multiselect'

// The body background: Gradients layered on top of a Background image/color.
const form = defineModel<DesignForm>('form', { required: true })
const { resolveColorRef, colorDisplayLabel } = useDefaultColors(form)
const grad = useGradients()

const gradientCollapsed = ref(true)
const backgroundCollapsed = ref(true)

const BACKGROUND_REPEAT_OPTIONS: FontOption[] = [
  { label: '(default: repeat)', value: '' },
  ...keywordOptions('repeat', 'repeat-x', 'repeat-y', 'no-repeat', 'space', 'round'),
]
const BACKGROUND_SIZE_OPTIONS: FontOption[] = [
  { label: '(default: auto)', value: '' },
  ...keywordOptions('auto', 'cover', 'contain'),
]

// color: PrimeVue's ColorPicker works in bare hex ("ff0000"), the stored
// CSS value needs the leading "#" — same conversion as the per-container/
// global font color fields.
const colorHex = (): string => resolveColorRef(form.value.background_color).replace(/^#/, '')
const setColorHex = (hex: string | undefined) => {
  form.value.background_color = hex ? `#${hex}` : ''
}

const showImagePicker = ref(false)
const setImage = (url: string) => {
  form.value.background_image_url = url
}
</script>

<template>
  <DesignPanel
    title="Backdrop"
    description="The body background: Gradients layered on top of a Background image/color — rendered ahead of the CSS editor below, so a manual edit there still wins."
    header-tour="designs-backdrop-header"
  >
    <DesignPanel
      v-model:collapsed="gradientCollapsed"
      nested
      title="Gradient"
      description="Applied as the body background, stacked in the order picked below (first = frontmost layer)."
    >
      <div class="gradient-picker-row">
        <MultiSelect
          :model-value="form.gradient_ids"
          :options="grad.gradients"
          optionLabel="name"
          optionValue="id"
          placeholder="None"
          size="small"
          class="w-full"
          display="chip"
          @update:model-value="grad.setDesignGradients"
        />
        <Button label="Manage Gradients" icon="pi pi-palette" outlined size="small" @click="grad.showManageDialog = true" />
      </div>
      <div
        v-if="grad.selectedGradients.length"
        class="gradient-preview-box"
        :style="{ backgroundImage: grad.combinedCss(grad.selectedGradients) }"
      ></div>
    </DesignPanel>

    <DesignPanel
      v-model:collapsed="backgroundCollapsed"
      nested
      title="Background"
      description="Image, color, repeat/size/opacity for the page background — beneath the Gradient layer above."
    >
      <div class="field">
        <label>Background Image</label>
        <div class="background-image-row">
          <div
            v-if="form.background_image_url"
            class="background-image-preview"
            :style="{ backgroundImage: `url(${form.background_image_url})` }"
          ></div>
          <Button label="Select Image" icon="pi pi-image" outlined size="small" @click="showImagePicker = true" />
          <Button
            v-if="form.background_image_url"
            icon="pi pi-times" label="Clear" text size="small"
            @click="setImage('')"
          />
        </div>
      </div>
      <div v-if="form.background_image_url" class="font-properties-grid">
        <div class="field">
          <label>Repeat</label>
          <Dropdown
            v-model="form.background_repeat"
            :options="BACKGROUND_REPEAT_OPTIONS"
            optionLabel="label"
            optionValue="value"
            editable
            size="small"
            class="w-full"
          />
        </div>
        <div class="field">
          <label>Size</label>
          <Dropdown
            v-model="form.background_size"
            :options="BACKGROUND_SIZE_OPTIONS"
            optionLabel="label"
            optionValue="value"
            editable
            size="small"
            class="w-full"
          />
        </div>
        <div class="field">
          <label>Opacity</label>
          <InputNumber
            v-model="form.background_opacity"
            :min="0" :max="100" suffix=" %" size="small" class="w-full"
          />
        </div>
      </div>
      <div class="field">
        <label>Background Color</label>
        <div class="color-field-row">
          <ColorPicker :model-value="colorHex()" @update:model-value="(v) => setColorHex(v)" />
          <ColorPalettePicker :palette="form.default_colors" @select="(c) => (form.background_color = colorRefFor(c.id))" />
          <span class="color-field-value">{{ colorDisplayLabel(form.background_color) }}</span>
          <Button
            v-if="form.background_color"
            icon="pi pi-times" text size="small" title="Clear"
            @click="form.background_color = ''"
          />
        </div>
      </div>
    </DesignPanel>

    <MediaPickerDialog
      v-model:visible="showImagePicker"
      :selected-url="form.background_image_url"
      @select="(item) => setImage(item.url)"
    />
  </DesignPanel>
</template>

<style scoped>
.gradient-picker-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.gradient-preview-box {
  margin-top: 0.6rem;
  height: 60px;
  border-radius: 6px;
  border: 1px solid var(--p-content-border-color, #ddd);
  background-size: cover;
}

.background-image-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.background-image-preview {
  width: 60px;
  height: 40px;
  border-radius: 6px;
  border: 1px solid var(--p-content-border-color, #ddd);
  background-size: cover;
  background-position: center;
}

.font-properties-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.75rem 1rem;
  margin-top: 0.6rem;
}

.font-properties-grid .field label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #666;
}

.color-field-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.color-field-value {
  font-family: monospace;
  font-size: 0.8rem;
  color: #666;
}
</style>
