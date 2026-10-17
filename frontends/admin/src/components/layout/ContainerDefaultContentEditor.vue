<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { DefaultColor } from '../../types/models'
import { fieldHandlerDef } from '../../plugins/registry'
import FieldValueEditor from '../fields/FieldValueEditor.vue'

// The editor of a container's default content for the chosen field handler: the same editor the
// Content page uses for the handler (the one its plugin registered), working on a field named
// `default`. The container stores the value packed into ONE string (`default_content`); the
// handler's plugin says how that string and the editor's key bag translate (`container` in
// plugins/types.ts) — for most handlers the string simply is the value. (The handler itself is
// chosen in the settings card.)
const props = defineProps<{
  handler: string
  /** The active Design's palette, offered by the icon picker. */
  palette: DefaultColor[]
}>()
const content = defineModel<string>('content', { required: true })

const NAME = 'default'
const fields = reactive<Record<string, unknown>>({})
let lastPacked: string | null = null

const unpack = (packed: string): Record<string, unknown> => {
  // Saved as the field's own key bag already ({"default": …, "default__size": …}): use it as it is.
  try {
    const parsed = JSON.parse(packed)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed) && 'default' in parsed) return parsed
  } catch { /* the packed form */ }
  const container = fieldHandlerDef(props.handler)?.container
  return container ? container.unpack(packed) : { [NAME]: packed }
}
const pack = (): string => {
  const container = fieldHandlerDef(props.handler)?.container
  return container ? container.pack(fields) : String(fields[NAME] ?? '')
}

const load = () => {
  for (const key of Object.keys(fields)) delete fields[key]
  Object.assign(fields, unpack(content.value ?? ''))
  lastPacked = content.value ?? ''
}
load()

// The container was changed from outside (another container selected, handler switched): read it again.
watch([content, () => props.handler], () => {
  if (content.value !== lastPacked) load()
})
watch(() => props.handler, load)
// The page may open before the handler's plugin has been loaded: read the value again once it has.
watch(() => fieldHandlerDef(props.handler), load)

// The editor changed something: write it back packed.
watch(fields, () => {
  const packed = pack()
  if (packed === content.value) return
  lastPacked = packed
  content.value = packed
}, { deep: true })
</script>

<template>
  <div v-if="handler" class="field">
    <label>Default Content</label>
    <FieldValueEditor
      :key="handler"
      :tag="{ name: NAME, fieldHandler: handler }"
      :fields="fields"
      :palette="palette"
    />
  </div>
</template>
