<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Card from 'primevue/card'
import RouteLink from '../ui/RouteLink.vue'
import { useContentStore } from '../../stores/content'
import { useRightsStore } from '../../stores/rights'
import { links } from '../../utils/links'
import { expiringSoon, recentlyChanged, relativeTime, startingSoon } from '../../utils/content/contentSchedule'

// The Dashboard's working part: what is about to expire or start, and what was
// changed last. The stat tiles above it ("On air" included) stay in DashboardView.vue;
// the content store is loaded there.
const rights = useRightsStore()
const contentStore = useContentStore()

// Re-judged every minute, so an element expires on the screen of an open Dashboard too.
const now = ref(Date.now())
let ticker: ReturnType<typeof setInterval> | undefined
onMounted(() => { ticker = setInterval(() => { now.value = Date.now() }, 60_000) })
onUnmounted(() => clearInterval(ticker))

const canSeeContent = computed(() => rights.can('content.page'))
const expiring = computed(() => expiringSoon(contentStore.content, now.value).slice(0, 6))
const starting = computed(() => startingSoon(contentStore.content, now.value).slice(0, 6))
const recent = computed(() => recentlyChanged(contentStore.content, 6))
</script>

<template>
  <section class="dash-overview" data-tour="dashboard-overview">
    <div v-if="canSeeContent" class="dash-panels">
      <Card class="dash-panel" data-testid="dash-expiring">
        <template #title><span class="dash-title"><i class="pi pi-clock" /> Ending soon</span></template>
        <template #content>
          <ul v-if="expiring.length" class="dash-list">
            <li v-for="c in expiring" :key="c.id">
              <RouteLink :to="links.content(c.id)">{{ c.title }}</RouteLink>
              <span class="dash-when">{{ relativeTime(c.endsAt, now) }}</span>
            </li>
          </ul>
          <span v-else class="dash-empty">Nothing ends within the next 7 days.</span>
        </template>
      </Card>

      <Card class="dash-panel" data-testid="dash-starting">
        <template #title><span class="dash-title"><i class="pi pi-calendar" /> Starting soon</span></template>
        <template #content>
          <ul v-if="starting.length" class="dash-list">
            <li v-for="c in starting" :key="c.id">
              <RouteLink :to="links.content(c.id)">{{ c.title }}</RouteLink>
              <span class="dash-when">{{ relativeTime(c.startsAt, now) }}</span>
            </li>
          </ul>
          <span v-else class="dash-empty">Nothing starts within the next 7 days.</span>
        </template>
      </Card>

      <Card class="dash-panel" data-testid="dash-recent">
        <template #title><span class="dash-title"><i class="pi pi-history" /> Recently changed</span></template>
        <template #content>
          <ul v-if="recent.length" class="dash-list">
            <li v-for="c in recent" :key="c.id">
              <RouteLink :to="links.content(c.id)">{{ c.title }}</RouteLink>
              <span class="dash-when">{{ relativeTime(c.changedAt, now) }}</span>
            </li>
          </ul>
          <span v-else class="dash-empty">No changes recorded yet.</span>
        </template>
      </Card>
    </div>
  </section>
</template>

<style scoped>
.dash-overview {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.dash-panels {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1rem;
}

.dash-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1rem;
}

.dash-empty,
.dash-when {
  color: var(--p-text-muted-color);
  font-size: 0.85rem;
}

.dash-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.dash-list li {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
}

.dash-list a {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-decoration: underline;
}

.dash-when {
  white-space: nowrap;
}
</style>
