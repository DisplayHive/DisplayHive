<script setup lang="ts">
// A sandboxed preview of a complete HTML document (design + containers).
//
// Replaces `<iframe :srcdoc="…">`: a srcdoc document inherits the admin page's
// strict Content-Security-Policy, which forbids the inline scripts previews
// need (background effects, clocks, designs' own scripts). Instead this loads
// public/preview-frame.html — served with its own, permissive policy — and
// posts the document to it. `sandbox="allow-scripts"` (no allow-same-origin)
// keeps everything that runs there away from the admin session.
import { ref, watch } from 'vue'

const props = defineProps<{ html: string; title?: string }>()

const frame = ref<HTMLIFrameElement | null>(null)
const src = `${import.meta.env.BASE_URL}preview-frame.html`
let loaded = false

const post = () => {
  if (!loaded) return
  // The frame has an opaque origin (sandbox without allow-same-origin), so a
  // concrete target origin can't be named; it only accepts messages from us.
  frame.value?.contentWindow?.postMessage({ type: 'dh-preview', html: props.html }, '*')
}

const onLoad = () => {
  loaded = true
  post()
}

watch(() => props.html, post)
</script>

<template>
  <iframe ref="frame" :src="src" sandbox="allow-scripts" :title="title || 'Preview'" @load="onLoad"></iframe>
</template>
