<script setup lang="ts">
// The per-container "Font" style fields (DesignContainerStyle rows) as a
// self-contained, controlled form: the parent owns the values and persists
// each change. Used by the Layout editor's "Container Design" card; mirrors the
// Designs page's Per-Container Styles panel via the shared property list.
import Dropdown from 'primevue/dropdown'
import InputNumber from 'primevue/inputnumber'
import ColorPicker from './ColorPicker.vue'
import Button from 'primevue/button'
import ColorPalettePicker from './ColorPalettePicker.vue'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import { CONTAINER_STYLE_GROUPS, type FontProperty, type FontOption } from '../utils/containerFontProperties'
import type { DefaultColor } from '../types/models'

const props = defineProps<{
  /** property -> CSS value for the selected container */
  styles: Record<string, string>
  /** The active Design's default-color palette (for "@default:<id>" refs). */
  palette: DefaultColor[]
}>()

const emit = defineEmits<{
  change: [prop: string, value: string]
}>()

// Same "@default:<id>" reference convention as the Designs page.
const DEFAULT_COLOR_PREFIX = '@default:'
const isColorRef = (v: string) => v.startsWith(DEFAULT_COLOR_PREFIX)
const findColor = (v: string) => props.palette.find((c) => c.id === v.slice(DEFAULT_COLOR_PREFIX.length))

// A value equal to the property's system default is the same as unset: shown
// as the "(Systemdefault)" entry and never stored (an already-stored one is
// dropped the next time the field is touched, since selecting it emits '').
const isDefault = (p: FontProperty, v: string) => !!p.systemDefault && v.trim().toLowerCase() === p.systemDefault

const commit = (p: FontProperty, value: string | undefined) => emit('change', p.key, isDefault(p, value ?? '') ? '' : (value ?? ''))

const getValue = (p: FontProperty): string => {
  const raw = get(p.key)
  return isDefault(p, raw) ? '' : raw
}

const defaultLabel = (p: FontProperty): string => (p.systemDefault ? `${p.systemDefault} (Systemdefault)` : '(not set)')

// "(not set)" becomes "<default> (Systemdefault)", and the preset that equals
// the default is dropped from the list (it would be a duplicate of it).
const optionsFor = (p: FontProperty): FontOption[] =>
  (p.options ?? [])
    .filter((o) => !(p.systemDefault && o.value === p.systemDefault))
    .map((o) => (o.value === '' ? { ...o, label: defaultLabel(p) } : o))

const getNumber = (p: FontProperty): number | null => {
  const unit = p.unit ?? ''
  const raw = getValue(p)
  if (!raw || (unit && !raw.endsWith(unit))) return null
  const n = parseFloat(raw)
  return isNaN(n) ? null : n
}

const get = (prop: string) => props.styles[prop] ?? ''

const getVh = (prop: string): number | null => {
  const n = parseFloat(get(prop))
  return isNaN(n) ? null : n
}

const getColorHex = (prop: string): string => {
  const raw = get(prop)
  const resolved = isColorRef(raw) ? findColor(raw)?.hex || '' : raw
  return resolved.replace(/^#/, '')
}

const colorLabel = (prop: string): string => {
  const raw = get(prop)
  if (!raw) return '(not set)'
  if (!isColorRef(raw)) return raw
  const c = findColor(raw)
  return c ? `🎨 ${c.name || c.hex}` : '(deleted default color)'
}
</script>

<template>
  <Tabs value="font" class="container-design-tabs">
    <TabList>
      <Tab v-for="g in CONTAINER_STYLE_GROUPS" :key="g.key" :value="g.key">
        <i :class="['pi', g.icon]" /> {{ g.label }}
      </Tab>
    </TabList>
    <TabPanels>
      <TabPanel v-for="g in CONTAINER_STYLE_GROUPS" :key="g.key" :value="g.key">
  <div class="container-design-fields">
    <div v-for="p in g.properties" :key="p.key" class="field">
      <label>{{ p.label }}</label>
      <InputNumber
        v-if="p.type === 'vh-number'"
        :model-value="getVh(p.key)"
        :min="0" :max="50" :step="0.1" :max-fraction-digits="2"
        suffix=" vh"
        size="small"
        class="w-full"
        @update:model-value="(v: number | null | undefined) => emit('change', p.key, v == null ? '' : `${v}vh`)"
      />
      <InputNumber
        v-else-if="p.type === 'number'"
        :model-value="getNumber(p)"
        :placeholder="p.systemDefault ? defaultLabel(p) : undefined"
        :min="p.min" :max="p.max" :step="p.step" :max-fraction-digits="2"
        :suffix="p.unit ? ` ${p.unit}` : undefined"
        size="small"
        class="w-full"
        @update:model-value="(v: number | null | undefined) => commit(p, v == null ? '' : `${v}${p.unit ?? ''}`)"
      />
      <div v-else-if="p.type === 'color'" class="color-field-row">
        <ColorPicker
          :model-value="getColorHex(p.key)"
          @update:model-value="(v: string | undefined) => emit('change', p.key, v ? `#${v}` : '')"
        />
        <ColorPalettePicker :palette="palette" @select="(c) => emit('change', p.key, `${DEFAULT_COLOR_PREFIX}${c.id}`)" />
        <span class="color-field-value">{{ colorLabel(p.key) }}</span>
        <Button
          v-if="get(p.key)"
          icon="pi pi-times" text size="small" title="Clear"
          @click="emit('change', p.key, '')"
        />
      </div>
      <Dropdown
        v-else
        :model-value="getValue(p)"
        :options="optionsFor(p)"
        :placeholder="defaultLabel(p)"
        optionLabel="label"
        optionValue="value"
        editable
        size="small"
        class="w-full"
        @update:model-value="(v: string | undefined) => commit(p, v)"
      />
    </div>
  </div>
      </TabPanel>
    </TabPanels>
  </Tabs>
</template>

<style scoped>
.container-design-fields {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.6rem 1rem;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.field label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}
.color-field-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.color-field-value {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #6b7280);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
