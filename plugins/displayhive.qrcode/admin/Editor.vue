<script setup lang="ts">
import { computed } from 'vue'
import { useFieldContext } from '@/composables/fields/useFieldContext'
import FieldSlot from '@/components/fields/FieldSlot.vue'
import Checkbox from 'primevue/checkbox'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Textarea from 'primevue/textarea'
import { EC_OPTIONS, QR_TYPE_OPTIONS, qrType, type QrInput } from './fields'

// A QR code: its kind, what that kind needs, and how it looks. Values: `<name>` is the link or the text,
// everything else `<name>__<key>` (see backend/__init__.py).
const f = useFieldContext()

const keyOf = (key: string | null) => (key === null ? f.name : `${f.name}__${key}`)
const str = (key: string | null) => String(f.get(keyOf(key)) ?? '')
const set = (key: string | null, value: unknown) => f.set(keyOf(key), value)

const type = computed(() => qrType(str('type') || 'url'))
const idOf = (input: QrInput) => `field-${f.name}-${input.key ?? 'main'}`
const transparent = computed(() => f.fields[`${f.name}__bg`] === '')
</script>

<template>
  <div class="qr-field" data-testid="qr-field">
    <FieldSlot :field-key="`${f.name}__type`">
      <Select
        :model-value="type.id"
        :options="QR_TYPE_OPTIONS"
        option-label="label"
        option-value="value"
        :disabled="f.isLocked(`${f.name}__type`)"
        class="w-full"
        aria-label="Kind of QR code"
        @update:model-value="(v: string) => set('type', v)"
      />
    </FieldSlot>

    <template v-for="input in type.inputs" :key="`${type.id}-${input.key}`">
      <FieldSlot :field-key="keyOf(input.key)" class="qr-input">
        <label v-if="input.kind !== 'check'" :for="idOf(input)" class="qr-label">{{ input.label }}</label>
        <Select
          v-if="input.kind === 'select'"
          :id="idOf(input)"
          :model-value="str(input.key) || input.options?.[0]?.value"
          :options="input.options"
          option-label="label"
          option-value="value"
          :disabled="f.isLocked(keyOf(input.key))"
          class="w-full"
          @update:model-value="(v: string) => set(input.key, v)"
        />
        <div v-else-if="input.kind === 'check'" class="qr-check">
          <Checkbox
            :input-id="idOf(input)"
            binary
            :model-value="['1', 'true', 'yes', 'on'].includes(str(input.key).toLowerCase())"
            :disabled="f.isLocked(keyOf(input.key))"
            @update:model-value="(v: boolean) => set(input.key, v ? 'true' : '')"
          />
          <label :for="idOf(input)">{{ input.label }}</label>
        </div>
        <Textarea
          v-else-if="input.kind === 'textarea'"
          :id="idOf(input)"
          :model-value="str(input.key)"
          :placeholder="input.placeholder"
          rows="3"
          :disabled="f.isLocked(keyOf(input.key))"
          class="w-full"
          @update:model-value="(v: string | undefined) => set(input.key, v ?? '')"
        />
        <InputText
          v-else
          :id="idOf(input)"
          :type="input.kind === 'text' ? 'text' : input.kind"
          :model-value="str(input.key)"
          :placeholder="input.placeholder"
          :disabled="f.isLocked(keyOf(input.key))"
          class="w-full"
          @update:model-value="(v: string | undefined) => set(input.key, v ?? '')"
        />
      </FieldSlot>
    </template>

    <details class="qr-looks">
      <summary>Appearance</summary>
      <FieldSlot :field-key="`${f.name}__size`" class="qr-input">
        <label :for="`field-${f.name}-size`" class="qr-label">Size (vh, empty: as large as the box)</label>
        <InputNumber
          :input-id="`field-${f.name}-size`"
          :model-value="Number(f.get(`${f.name}__size`)) || null"
          :min="1" :max="100" :max-fraction-digits="1" suffix=" vh" placeholder="fill"
          :disabled="f.isLocked(`${f.name}__size`)"
          style="width: 9rem"
          @update:model-value="(v: number | null) => set('size', v ?? '')"
        />
      </FieldSlot>
      <FieldSlot :field-key="`${f.name}__fg`" class="qr-input qr-color">
        <label :for="`field-${f.name}-fg`" class="qr-label">Code colour</label>
        <input :id="`field-${f.name}-fg`" type="color" :value="str('fg') || '#000000'" :disabled="f.isLocked(`${f.name}__fg`)"
               @input="(e: Event) => set('fg', (e.target as HTMLInputElement).value)" />
      </FieldSlot>
      <FieldSlot :field-key="`${f.name}__bg`" class="qr-input qr-color">
        <label :for="`field-${f.name}-bg`" class="qr-label">Background</label>
        <input :id="`field-${f.name}-bg`" type="color" :value="str('bg') || '#ffffff'" :disabled="transparent || f.isLocked(`${f.name}__bg`)"
               @input="(e: Event) => set('bg', (e.target as HTMLInputElement).value)" />
        <Checkbox
          :input-id="`field-${f.name}-bg-none`" binary :model-value="transparent" :disabled="f.isLocked(`${f.name}__bg`)"
          @update:model-value="(v: boolean) => set('bg', v ? '' : '#ffffff')"
        />
        <label :for="`field-${f.name}-bg-none`">Transparent</label>
      </FieldSlot>
      <small class="qr-hint">A dark code on a light background is read most reliably; a transparent background needs a light surface behind it.</small>
      <FieldSlot :field-key="`${f.name}__ec`" class="qr-input">
        <label :for="`field-${f.name}-ec`" class="qr-label">Error correction</label>
        <Select
          :id="`field-${f.name}-ec`"
          :model-value="str('ec') || 'm'"
          :options="EC_OPTIONS" option-label="label" option-value="value"
          :disabled="f.isLocked(`${f.name}__ec`)"
          class="w-full"
          @update:model-value="(v: string) => set('ec', v)"
        />
      </FieldSlot>
      <FieldSlot :field-key="`${f.name}__border`" class="qr-input">
        <label :for="`field-${f.name}-border`" class="qr-label">Quiet zone (modules)</label>
        <InputNumber
          :input-id="`field-${f.name}-border`"
          :model-value="f.get(`${f.name}__border`) === '' ? 2 : Number(f.get(`${f.name}__border`))"
          :min="0" :max="8"
          :disabled="f.isLocked(`${f.name}__border`)"
          style="width: 7rem"
          @update:model-value="(v: number | null) => set('border', v ?? 2)"
        />
      </FieldSlot>
    </details>
  </div>
</template>

<style scoped>
.qr-field {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.qr-input {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem 0.6rem;
}

.qr-label {
  flex: 0 0 100%;
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #64748b);
}

.qr-check,
.qr-color {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.qr-looks {
  border: 1px solid var(--p-content-border-color, #d1d5db);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
}

.qr-looks > summary {
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
}

.qr-looks[open] > summary {
  margin-bottom: 0.5rem;
}

.qr-hint {
  display: block;
  margin: 0.25rem 0 0.5rem;
  font-size: 0.78rem;
  color: var(--p-text-muted-color, #64748b);
}

/* See the marquee editor: a label placed first must not take the row's flex-grow. */
.fve-slot > .qr-label:first-child {
  flex: 0 0 100%;
}
</style>
