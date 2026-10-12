<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useHelpStore } from '../stores/help'
import { useAdminNavigation } from '../composables/useAdminNavigation'
import Popover from 'primevue/popover'

// Icon, title, a one-line description and the help popover of the current page, plus the
// target PageActions.vue teleports a page's actions into. Styles: assets/shell/page.css.
const route = useRoute()
const helpStore = useHelpStore()
const { pageTitle, pageIcon } = useAdminNavigation()

const pageHelp = computed(() => helpStore.helpFor(`page.${route.name as string}`)?.body || '')

// The first sentence of the page's help text, as the one-line description under the title
// (the whole text stays behind the question mark).
const pageSummary = computed(() => {
  const text = pageHelp.value.trim().replace(/\s+/g, ' ')
  if (!text) return ''
  const sentence = text.match(/^.*?[.!?](?=\s|$)/)?.[0] ?? text
  return sentence.length > 140 ? `${sentence.slice(0, 137).trimEnd()}…` : sentence
})

const helpPopover = ref<InstanceType<typeof Popover> | null>(null)
const toggleHelp = (e: Event) => helpPopover.value?.toggle(e)
</script>

<template>
  <div v-if="pageTitle" class="page-header">
    <span v-if="pageIcon" class="page-title-icon-badge">
      <i :class="[pageIcon, 'page-title-icon']"></i>
    </span>
    <div class="page-title-block">
      <div class="page-title-row">
        <h1>{{ pageTitle }}</h1>
        <i
          v-if="pageHelp"
          class="pi pi-question-circle page-help-icon"
          role="button"
          tabindex="0"
          :aria-label="`Help: ${pageTitle}`"
          @click="toggleHelp"
          @keydown.enter="toggleHelp"
        ></i>
        <Popover ref="helpPopover">
          <p class="page-help-text">{{ pageHelp }}</p>
        </Popover>
      </div>
      <p v-if="pageSummary" class="page-summary" data-testid="page-summary">{{ pageSummary }}</p>
    </div>
    <div id="page-header-actions" class="page-header-actions"></div>
  </div>
</template>
