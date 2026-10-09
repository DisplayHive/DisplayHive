<script setup lang="ts">
import { onMounted, ref } from 'vue'

// Puts its content into the page header's action area (components/PageHeader.vue,
// #page-header-actions). A Teleport needs its target in the document when it renders; on a
// fresh load of a page (reload, a link) the whole app is still being built then, so the target
// is not there yet and a plain <Teleport> crashes the page. Wait until this component is
// mounted, by which time it is.
const targetReady = ref(false)
onMounted(() => {
  targetReady.value = true
})
</script>

<template>
  <Teleport v-if="targetReady" to="#page-header-actions">
    <slot />
  </Teleport>
</template>
