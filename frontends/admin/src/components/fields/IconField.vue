<script setup lang="ts">
import { computed } from 'vue'
import { useFieldContext } from '../../composables/fields/useFieldContext'
import type { IconPickerValue } from '../../utils/iconLibraries'
import type { OptionFlags } from '../../utils/optionFlags'
import IconPickerField from '../IconPickerField.vue'

// An icon from the installed icon libraries, with size and colour. The picker manages its own
// hidden/locked state per sub-option, so this only translates between its local keys ('icon',
// 'size', 'color') and the field's wire keys (`<name>`, `<name>__size`, `<name>__color`).
const f = useFieldContext()

const value = computed((): IconPickerValue => ({
  icon: String(f.fields[f.name] ?? ''),
  size: Number(f.fields[`${f.name}__size`]) || 5,
  color: String(f.fields[`${f.name}__color`] ?? ''),
}))

const setValue = (v: IconPickerValue) => {
  f.set(f.name, v.icon)
  f.set(`${f.name}__size`, v.size)
  f.set(`${f.name}__color`, v.color)
}

const localFlags = computed((): OptionFlags => {
  const out: OptionFlags = {}
  const iconFlag = f.optionFlags?.[f.name]
  if (iconFlag) out.icon = iconFlag
  const sizeFlag = f.optionFlags?.[`${f.name}__size`]
  if (sizeFlag) out.size = sizeFlag
  const colorFlag = f.optionFlags?.[`${f.name}__color`]
  if (colorFlag) out.color = colorFlag
  return out
})

const onFlagsUpdate = (flags: OptionFlags) => {
  const next = { ...f.optionFlags }
  if (flags.icon) next[f.name] = flags.icon
  if (flags.size) next[`${f.name}__size`] = flags.size
  if (flags.color) next[`${f.name}__color`] = flags.color
  f.setOptionFlags(next)
}
</script>

<template>
  <IconPickerField
    :model-value="value"
    @update:model-value="setValue"
    :mode="f.mode"
    :palette="f.palette"
    :option-flags="localFlags"
    @update:option-flags="onFlagsUpdate"
  />
</template>
