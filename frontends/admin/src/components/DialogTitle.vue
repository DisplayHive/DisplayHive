<script setup lang="ts">
// The header every dialog uses: a round icon badge and the title. Use it in a Dialog's
// `#header` slot — the classes it renders are styled globally (assets/main.css).
defineProps<{
  /** PrimeIcons class of the badge, e.g. `pi-pencil`. */
  icon: string
  title: string
}>()
</script>

<template>
  <div class="dialog-title">
    <span class="dialog-title-icon-badge"><i :class="['pi', icon, 'dialog-title-icon']"></i></span>
    <span class="p-dialog-title">{{ title }}</span>
  </div>
</template>
