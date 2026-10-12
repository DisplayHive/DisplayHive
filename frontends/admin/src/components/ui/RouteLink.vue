<script setup lang="ts">
// A real <a href> that navigates through the router (so middle-click /
// "open in new tab" work too) — for cross-page links in tables and dialogs.
// See utils/links.ts for the target locations.
import { computed } from 'vue'
import { useRouter, type RouteLocationRaw } from 'vue-router'

const props = defineProps<{ to: RouteLocationRaw }>()
const router = useRouter()
const href = computed(() => router.resolve(props.to).href)
const go = (e: MouseEvent) => {
  // Let modified clicks (new tab/window) use the browser's own handling.
  if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return
  e.preventDefault()
  router.push(props.to)
}
</script>

<template>
  <a :href="href" class="route-link" @click="go"><slot /></a>
</template>

<style>
/* Unscoped on purpose, and via :where() (zero specificity): a link inherits its
   surroundings' color by default, but any class on it — e.g. ContentTable's
   coloured membership chips — keeps full control of its own color. */
:where(a.route-link) {
  color: inherit;
  text-decoration: none;
}

:where(a.route-link:hover) {
  text-decoration: underline;
}
</style>
