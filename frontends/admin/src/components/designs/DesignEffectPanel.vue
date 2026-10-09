<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import type { DesignForm } from '../../types/designForm'
import { useDefaultColors, colorRefFor, isColorRef } from '../../composables/designs/useDefaultColors'
import {
  BACKGROUND_EFFECTS,
  getEffectDefinition,
  defaultSettingsFor,
  applyEffectAttributes,
  type EffectParam,
} from '../../utils/backgroundEffects'
import type { DefaultColor } from '../../types/models'
import DesignPanel from './DesignPanel.vue'
import ColorPalettePicker from '../ColorPalettePicker.vue'
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'

// An animated canvas effect (beautiful-backgrounds) rendered behind the Backdrop, with a
// live preview while the panel is open.
const form = defineModel<DesignForm>('form', { required: true })
const { resolveColorRef } = useDefaultColors(form)

const collapsed = ref(true)

const EFFECT_OPTIONS = [{ label: 'None', value: '' }, ...BACKGROUND_EFFECTS.map((e) => ({ label: e.label, value: e.key }))]

const selectedEffectDef = computed(() =>
  form.value.background_effect ? getEffectDefinition(form.value.background_effect) : undefined,
)

const selectedPresetLabel = ref('')

const onSelectEffect = (key: string) => {
  form.value.background_effect = key
  const def = key ? getEffectDefinition(key) : undefined
  form.value.background_effect_settings = def ? defaultSettingsFor(def) : {}
  selectedPresetLabel.value = ''
}

const onSelectPreset = (label: string) => {
  const def = selectedEffectDef.value
  const preset = def?.presets?.find((p) => p.label === label)
  if (!def || !preset) return
  form.value.background_effect_settings = {
    ...defaultSettingsFor(def),
    ...preset.values,
  } as Record<string, number | string | string[]>
  selectedPresetLabel.value = label
}

const getParamNumber = (param: EffectParam): number => {
  const v = form.value.background_effect_settings[param.key] ?? param.default
  return typeof v === 'number' ? v : Number(v) || 0
}
const getParamText = (param: EffectParam): string => {
  const v = form.value.background_effect_settings[param.key] ?? param.default
  return Array.isArray(v) ? v.join(', ') : String(v ?? '')
}
const setParamValue = (param: EffectParam, value: string | number | null | undefined) => {
  if (param.type === 'colorArray') {
    form.value.background_effect_settings[param.key] = String(value ?? '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
  } else if (param.type === 'number') {
    form.value.background_effect_settings[param.key] = Number(value ?? 0)
  } else {
    form.value.background_effect_settings[param.key] = String(value ?? '')
  }
}

// Appends a swatch's reference to a comma-separated colorArray param's text
// value (the raw, unresolved tokens — this field's plain-text editing is
// intentionally low-level, see the param's placeholder in the template).
const appendColorToParam = (param: EffectParam, color: DefaultColor) => {
  const current = getParamText(param)
  const ref = colorRefFor(color.id)
  setParamValue(param, current ? `${current}, ${ref}` : ref)
}

// The live effect preview (<bb-neon-rails> etc.) is a plain web component
// that only understands real CSS colors — resolve any "@default:<id>"
// tokens to their current hex before handing settings to it. Mirrors
// resolve_default_colors_deep() server-side (application/admin/designs/helper.py).
const resolveSettingsRefs = (
  settings: Record<string, number | string | string[]>,
): Record<string, number | string | string[]> => {
  const out: Record<string, number | string | string[]> = {}
  for (const [k, v] of Object.entries(settings)) {
    if (Array.isArray(v)) out[k] = v.map((x) => (isColorRef(x) ? resolveColorRef(x) : x))
    else if (typeof v === 'string' && isColorRef(v)) out[k] = resolveColorRef(v)
    else out[k] = v
  }
  return out
}

// Live preview: mounted imperatively (not as a Vue-compiled tag) so no
// isCustomElement compiler config is needed — mirrors how the screen client
// itself manages these elements (frontends/screen/ts/screen/background-effects.ts).
const previewEl = ref<HTMLDivElement | null>(null)
let previewLibraryLoaded = false

const renderPreview = async () => {
  const container = previewEl.value
  if (!container) return
  const def = selectedEffectDef.value
  if (!def) {
    container.replaceChildren()
    return
  }
  if (!previewLibraryLoaded) {
    await import('beautiful-backgrounds')
    previewLibraryLoaded = true
  }
  let el = container.firstElementChild as HTMLElement | null
  if (!el || el.tagName.toLowerCase() !== def.tag) {
    el = document.createElement(def.tag)
    el.style.display = 'block'
    el.style.width = '100%'
    el.style.height = '100%'
    container.replaceChildren(el)
  }
  applyEffectAttributes(el, def, resolveSettingsRefs(form.value.background_effect_settings))
}

watch(
  () => [form.value.background_effect, form.value.background_effect_settings, collapsed.value] as const,
  () => {
    if (collapsed.value) return
    nextTick(renderPreview)
  },
  { deep: true },
)
</script>

<template>
  <DesignPanel
    v-model:collapsed="collapsed"
    title="Background Effect"
    description="An animated canvas effect rendered behind the Backdrop. Runs continuously on the screen client — test on real display hardware before relying on it, it has a real CPU/GPU cost."
    header-tour="designs-effect-header"
  >
    <div class="field">
      <label>Effect</label>
      <Dropdown
        :model-value="form.background_effect"
        :options="EFFECT_OPTIONS"
        optionLabel="label"
        optionValue="value"
        size="small"
        class="w-full"
        @update:model-value="onSelectEffect"
      />
    </div>
    <div class="field" v-if="selectedEffectDef?.presets?.length">
      <label>Preset</label>
      <Dropdown
        :model-value="selectedPresetLabel"
        :options="selectedEffectDef.presets.map((p) => p.label)"
        placeholder="Custom"
        size="small"
        class="w-full"
        @update:model-value="onSelectPreset"
      />
    </div>
    <template v-if="selectedEffectDef">
      <div class="gradient-preview-box effect-preview-box" ref="previewEl"></div>
      <div class="font-properties-grid">
        <div v-for="p in selectedEffectDef.params" :key="p.key" class="field">
          <label>{{ p.label }}</label>
          <InputNumber
            v-if="p.type === 'number'"
            :model-value="getParamNumber(p)"
            :step="p.step ?? 1"
            :min="p.min"
            :max="p.max"
            :max-fraction-digits="6"
            size="small"
            class="w-full"
            @update:model-value="(v) => setParamValue(p, v)"
          />
          <div v-else-if="p.type === 'colorArray'" class="color-field-row">
            <InputText
              :model-value="getParamText(p)"
              size="small"
              class="w-full"
              placeholder="e.g. #ff0000, #00ff00"
              @update:model-value="(v) => setParamValue(p, v)"
            />
            <ColorPalettePicker :palette="form.default_colors" @select="(c) => appendColorToParam(p, c)" />
          </div>
          <InputText
            v-else
            :model-value="getParamText(p)"
            size="small"
            class="w-full"
            @update:model-value="(v) => setParamValue(p, v)"
          />
        </div>
      </div>
    </template>
  </DesignPanel>
</template>

<style scoped>
.gradient-preview-box {
  margin-top: 0.6rem;
  height: 60px;
  border-radius: 6px;
  border: 1px solid var(--p-content-border-color, #ddd);
  background-size: cover;
}

.effect-preview-box {
  height: 220px;
  overflow: hidden;
  background: #000;
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
</style>
