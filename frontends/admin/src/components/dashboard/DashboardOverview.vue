<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Card from 'primevue/card'
import RouteLink from '../RouteLink.vue'
import { useContentStore } from '../../stores/content'
import { useRightsStore } from '../../stores/rights'
import { links } from '../../utils/links'
import { expiringSoon, recentlyChanged, relativeTime, scheduleState, startingSoon } from '../../utils/contentSchedule'

// The Dashboard's working part: quick actions, what is on air / about to expire or start,
// and what was changed last. The stat tiles above it stay in DashboardView.vue; the content
// store is loaded there.
const router = useRouter()
const rights = useRightsStore()
const contentStore = useContentStore()

// Re-judged every minute, so an element expires on the screen of an open Dashboard too.
const now = ref(Date.now())
let ticker: ReturnType<typeof setInterval> | undefined
onMounted(() => { ticker = setInterval(() => { now.value = Date.now() }, 60_000) })
onUnmounted(() => clearInterval(ticker))

const canSeeContent = computed(() => rights.can('content.page'))
const live = computed(() => contentStore.content.filter((c) => scheduleState(c, now.value) === 'live'))
const expiring = computed(() => expiringSoon(contentStore.content, now.value).slice(0, 6))
const starting = computed(() => startingSoon(contentStore.content, now.value).slice(0, 6))
const expired = computed(() => contentStore.content.filter((c) => scheduleState(c, now.value) === 'expired'))
const recent = computed(() => recentlyChanged(contentStore.content, 6))

interface QuickAction { label: string; icon: string; tour: string; run: () => void }
const actions = computed<QuickAction[]>(() => {
  const list: Array<QuickAction | false> = [
    rights.can('content.create') && { label: 'New content', icon: 'pi pi-plus', tour: 'quick-content', run: () => router.push('/content/new') },
    rights.can('media.upload') && { label: 'Upload media', icon: 'pi pi-upload', tour: 'quick-media', run: () => router.push('/media') },
    rights.can('screens.create') && { label: 'Add screen', icon: 'pi pi-window-maximize', tour: 'quick-screen', run: () => router.push('/screens') },
    rights.can('screens.page') && rights.can('screengroups.page') && { label: 'Matrix', icon: 'pi pi-th-large', tour: 'quick-matrix', run: () => router.push('/matrix') },
  ]
  return list.filter((a): a is QuickAction => !!a)
})
</script>

<template>
  <section class="dash-overview" data-tour="dashboard-overview">
    <div v-if="actions.length" class="dash-actions" data-tour="dashboard-quick-actions">
      <Button
        v-for="a in actions"
        :key="a.tour"
        :label="a.label"
        :icon="a.icon"
        :data-tour="a.tour"
        size="small"
        outlined
        @click="a.run()"
      />
    </div>

    <div v-if="canSeeContent" class="dash-panels">
      <Card class="dash-panel" data-testid="dash-onair">
        <template #title><span class="dash-title"><i class="pi pi-play-circle" /> On air</span></template>
        <template #content>
          <div class="dash-big">{{ live.length }}</div>
          <div class="dash-sub">content element(s) shown right now</div>
          <div v-if="expired.length" class="dash-note dash-note--warn">
            <i class="pi pi-exclamation-triangle" /> {{ expired.length }} expired, still switched on
          </div>
        </template>
      </Card>

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

.dash-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
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

.dash-big {
  font-size: 2.2rem;
  font-weight: 700;
  line-height: 1.1;
}

.dash-sub,
.dash-empty,
.dash-when {
  color: var(--p-text-muted-color);
  font-size: 0.85rem;
}

.dash-note--warn {
  margin-top: 0.5rem;
  color: var(--p-amber-400, #f59e0b);
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
