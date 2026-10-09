<script setup lang="ts">
import { computed } from 'vue'
import { useFieldContext } from '../../composables/fields/useFieldContext'
import { blankPretalxTableValue, type PretalxTableValue } from '../../utils/pretalxTable'
import type { OptionFlags } from '../../utils/optionFlags'
import PretalxTableFieldEditor from '../PretalxTableFieldEditor.vue'

// A Pretalx schedule table. Its settings are `<name>` (the URL) and `<name>__<setting>` for the
// rest; the editor works with its own PretalxTableValue and local setting names, so this
// translates both the values and the hidden/locked flags in and out of the wire keys.
const f = useFieldContext()

const LOCAL_KEYS = [
  'url', 'type', 'roomname', 'fields', 'linecount', 'author_under_title',
  'tracks_by_color', 'today_only', 'separate_days', 'day_prefix', 'empty_text',
  'tracklist_columns', 'tracklist_layout', 'tracklist_exclude', 'invalid_data_text',
] as const

const wireKey = (local: string) => (local === 'url' ? f.name : `${f.name}__${local}`)

const getValue = (): PretalxTableValue => {
  const name = f.name
  const fields = f.fields
  return {
    url: String(fields[name] || ''),
    type: String(fields[name + '__type'] || 'list'),
    roomname: String(fields[name + '__roomname'] || ''),
    fields: String(fields[name + '__fields'] || ''),
    linecount: Number(fields[name + '__linecount'] ?? 10),
    author_under_title: !!fields[name + '__author_under_title'],
    tracks_by_color: !!fields[name + '__tracks_by_color'],
    today_only: !!fields[name + '__today_only'],
    separate_days: !!fields[name + '__separate_days'],
    day_prefix: String(fields[name + '__day_prefix'] || ''),
    empty_text: String(fields[name + '__empty_text'] || ''),
    tracklist_columns: String(fields[name + '__tracklist_columns'] || 'name|Name,color|Color'),
    tracklist_layout: String(fields[name + '__tracklist_layout'] || 'list'),
    tracklist_exclude: String(fields[name + '__tracklist_exclude'] || ''),
    invalid_data_text: String(fields[name + '__invalid_data_text'] || ''),
  }
}

const setValue = (v: PretalxTableValue) => {
  for (const local of LOCAL_KEYS) f.set(wireKey(local), v[local])
}

// A new field starts with the editor's blank value in its bag.
if (!(f.name in f.fields)) setValue(blankPretalxTableValue())

const localFlags = computed((): OptionFlags => {
  const out: OptionFlags = {}
  for (const local of LOCAL_KEYS) {
    const flag = f.optionFlags?.[wireKey(local)]
    if (flag) out[local] = flag
  }
  return out
})

const onFlagsUpdate = (flags: OptionFlags) => {
  const next = { ...f.optionFlags }
  for (const [local, flag] of Object.entries(flags)) next[wireKey(local)] = flag
  f.setOptionFlags(next)
}
</script>

<template>
  <PretalxTableFieldEditor
    :model-value="getValue()"
    @update:model-value="setValue"
    :mode="f.mode"
    :option-flags="localFlags"
    @update:option-flags="onFlagsUpdate"
  />
</template>
