<script setup lang="ts">
// A sandboxed preview of a complete HTML document (design + containers).
//
// Replaces `<iframe :srcdoc="…">`: a srcdoc document inherits the admin page's
// strict Content-Security-Policy, which forbids the inline scripts previews
// need (background effects, clocks, designs' own scripts). Instead this loads
// public/preview-frame.html — served with its own, permissive policy — and
// posts the document to it. `sandbox="allow-scripts"` (no allow-same-origin)
// keeps everything that runs there away from the admin session.
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ContainerTextStyle } from '../../utils/design/designPreview'

const props = defineProps<{ html: string; title?: string }>()
const emit = defineEmits<{ 'container-styles': [styles: Record<string, ContainerTextStyle>] }>()

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

// How the containers' text looks in the document (see designPreview.ts), reported after each load.
let lastStyles = ''
const onMessage = (event: MessageEvent) => {
  if (event.source !== frame.value?.contentWindow) return
  const data = event.data
  if (data && data.type === 'dh-preview-styles' && data.styles && typeof data.styles === 'object') {
    // Only a change is news: the pages that listen re-render on every report.
    const json = JSON.stringify(data.styles)
    if (json === lastStyles) return
    lastStyles = json
    emit('container-styles', data.styles)
  }
}
onMounted(() => window.addEventListener('message', onMessage))
onBeforeUnmount(() => window.removeEventListener('message', onMessage))
</script>

<template>
  <iframe ref="frame" :src="src" sandbox="allow-scripts" :title="title || 'Preview'" @load="onLoad"></iframe>
</template>
