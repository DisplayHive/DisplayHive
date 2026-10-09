<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useFieldContext } from '../../composables/fields/useFieldContext'
import FieldSlot from './FieldSlot.vue'
import Editor from 'primevue/editor'

const f = useFieldContext()
f.reportVisibleWhen(() => !f.isHidden(f.name))

// Deferred one tick past mount so the Editor only initializes once `fields` already holds its
// final value — otherwise Quill can grab a stale/blank value before a parent's own async load
// finishes populating `fields`.
const editorReady = ref(false)
onMounted(() => { nextTick(() => { editorReady.value = true }) })

// No @types/quill installed (see the same rationale in main.ts) — only the bit of the Quill
// instance actually touched here is typed.
interface QuillInstance {
  clipboard?: { convert: (html: string) => unknown }
  setContents: (delta: unknown, source: string) => void
}

const onEditorLoad = (event: { instance: QuillInstance }) => {
  const quill = event.instance
  const html = String(f.fields[f.name] || '')
  if (html && quill && quill.clipboard) {
    const delta = quill.clipboard.convert(html)
    quill.setContents(delta, 'silent')
  }
}
</script>

<template>
  <FieldSlot v-if="editorReady" :field-key="f.name">
    <Editor
      :id="`field-${f.name}`"
      :modelValue="String(f.fields[f.name] || '')"
      @update:modelValue="(v: string | undefined) => f.set(f.name, v ?? '')"
      editorStyle="height: 220px"
      :readonly="f.isLocked(f.name)"
      @load="(e: { instance: QuillInstance }) => onEditorLoad(e)"
    />
  </FieldSlot>
</template>
