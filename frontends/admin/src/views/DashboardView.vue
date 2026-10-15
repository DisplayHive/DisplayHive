<script setup lang="ts">
import { links } from '../utils/links'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useDevicesStore } from '../stores/devices'
import { useScreensStore } from '../stores/screens'
import { useScreengroupsStore } from '../stores/screengroups'
import { useMediaStore } from '../stores/media'
import { useContentStore } from '../stores/content'
import { useRightsStore } from '../stores/rights'
import { isWindowed, isFullscreen } from '../composables/useMaximizedFilter'
import { scheduleState } from '../utils/content/contentSchedule'

// PrimeVue components
import Card from 'primevue/card'
import DashboardOverview from '../components/dashboard/DashboardOverview.vue'
import DashboardCommunity from '../components/dashboard/DashboardCommunity.vue'

const router = useRouter()
const { on, off, emit } = useSocket()
const rightsStore = useRightsStore()
const canSeeDemo = computed(() => rightsStore.can('importexport.page'))

const welcomeHeadline = ref('Welcome to DisplayHive Admin')
const welcomeText = ref('Use the navigation menu to manage your digital signage system.')
const hideCommunityLinks = ref(false)
const hideHelpingHand = ref(false)
const hideDemoMode = ref(false)

interface SystemSettings {
  welcome_headline?: string
  welcome_text?: string
  hide_community_links?: boolean | string
  hide_helping_hand?: boolean | string
  hide_demo_mode?: boolean | string
}

const handleSettings = (data: { system_settings?: SystemSettings }) => {
  const sys = data?.system_settings || {}
  if (sys.welcome_headline !== undefined) welcomeHeadline.value = sys.welcome_headline
  if (sys.welcome_text !== undefined) welcomeText.value = sys.welcome_text
  if (sys.hide_community_links !== undefined) hideCommunityLinks.value = sys.hide_community_links === true || sys.hide_community_links === 'true'
  if (sys.hide_helping_hand !== undefined) hideHelpingHand.value = sys.hide_helping_hand === true || sys.hide_helping_hand === 'true'
  if (sys.hide_demo_mode !== undefined) hideDemoMode.value = sys.hide_demo_mode === true || sys.hide_demo_mode === 'true'
}

const demoModeEnabled = computed(() => !hideDemoMode.value)
const devicesStore = useDevicesStore()
const screensStore = useScreensStore()
const screengroupsStore = useScreengroupsStore()
const mediaStore = useMediaStore()
const contentStore = useContentStore()

// Re-judged every minute, so an element that expires drops out of "On air" on an open Dashboard too.
const now = ref(Date.now())
let ticker: ReturnType<typeof setInterval> | undefined

onMounted(() => {
  ticker = setInterval(() => { now.value = Date.now() }, 60_000)
  on('displayhive:admin:stc:admin_settings', handleSettings)
  emit('displayhive:admin:cts:get_admin_settings')
  devicesStore.fetch()
  screensStore.fetch()
  screengroupsStore.fetch()
  mediaStore.fetch()
  contentStore.fetch()
})

onUnmounted(() => {
  clearInterval(ticker)
  off('displayhive:admin:stc:admin_settings', handleSettings)
})

// Derived stats from stores
const screensCount = computed(() => screensStore.monitoredScreens.length)
const onlineScreens = computed(() => screensStore.onlineCount)
const screensInDebug = computed(() => screensStore.screensInDebug)
const windowedScreens = computed(() => screensStore.monitoredScreens.filter(isWindowed).length)
const fullscreenScreens = computed(() => screensStore.monitoredScreens.filter(isFullscreen).length)

const activeDevices = computed(() => devicesStore.activeDevices.length)
const onlineDevices = computed(() => devicesStore.onlineDevices.length)
const screensInFind = computed(() => {
  const findScreens = new Set<number>()
  devicesStore.devices.forEach((d) => {
    if (d.find && d.screen_id) findScreens.add(d.screen_id)
  })
  return findScreens.size
})

const liveContent = computed(() => contentStore.content.filter((c) => scheduleState(c, now.value) === 'live').length)
const expiredContent = computed(() => contentStore.content.filter((c) => scheduleState(c, now.value) === 'expired').length)
const totalContent = computed(() => contentStore.content.length)
const unassignedContent = computed(() => contentStore.unassignedContent.length)
// Every screen also has a hidden one-screen group of its own (is_one_screen) —
// only real groups count here, same as the Screen Groups page lists.
const screengroupsCount = computed(() => screengroupsStore.screengroups.filter((sg) => !sg.is_one_screen).length)
const mediaCount = computed(() => mediaStore.mediaItems.length)

// Warning indicators
const screensWarn = computed(() => screensCount.value > 0 && onlineScreens.value < screensCount.value)
const devicesWarn = computed(() => activeDevices.value > 0 && onlineDevices.value < activeDevices.value)
const onAirWarn = computed(() => expiredContent.value > 0)
const contentWarn = computed(() => unassignedContent.value >= 1)
const findWarn = computed(() => screensInFind.value > 0)
const debugWarn = computed(() => screensInDebug.value > 0)
</script>

<template>
  <div class="dashboard">

    <!-- Demo mode hint -->
    <Card v-if="demoModeEnabled && canSeeDemo" class="demo-hint-card">
      <template #content>
        <div class="demo-hint-body">
          <i class="pi pi-sparkles demo-hint-icon"></i>
          <div class="demo-hint-text">
            <div class="demo-hint-title">Demo mode and Guided Tours are available on this instance</div>
            <p>
              You can import example configurations from the
              <a href="#" @click.prevent="router.push('/demo')">Demo page</a>.
              Please note that, with the exception of user accounts, this will overwrite
              <strong>all</strong> content previously created on this instance — system-wide.
              You can back up your current data beforehand via
              <a href="#" @click.prevent="router.push('/importexport')">Import / Export</a>.
            </p>
            <p>
              The <a href="#" @click.prevent="router.push('/tour')">Guided Tours</a> walk through
              the admin UI step by step. Demo projects and Guided Tours can each be disabled from
              <a href="#" @click.prevent="router.push('/settings')">Settings</a>.
            </p>
          </div>
        </div>
      </template>
    </Card>

    <!-- Welcome card -->
    <Card class="welcome-card">
      <template #content>
        <div class="welcome-body">
          <div>
            <div class="welcome-headline">{{ welcomeHeadline }}</div>
            <p class="welcome-text">{{ welcomeText }}</p>
          </div>
        </div>
      </template>
    </Card>

    <!-- Status cards grid -->
    <div class="stats-grid" data-tour="dashboard-stats-grid">

      <!-- On air -->
      <Card v-if="rightsStore.can('content.page')" data-tour="stat-onair" data-testid="dash-onair" :class="['stat-card', onAirWarn ? 'stat-card--warn' : 'stat-card--ok']" @click="router.push('/content')">
        <template #content>
          <div class="stat-header">
            <i class="pi pi-play-circle stat-icon"></i>
            <span class="stat-label">On air</span>
            <i v-if="onAirWarn" class="pi pi-exclamation-triangle warn-icon" :title="`${expiredContent} expired element(s) still switched on`"></i>
          </div>
          <div class="stat-value">{{ liveContent }}</div>
          <div class="stat-detail">
            <span>content element(s) shown right now</span>
          </div>
          <div class="stat-detail" v-if="expiredContent > 0">
            <span class="detail-warn">{{ expiredContent }} expired, still switched on</span>
          </div>
        </template>
      </Card>

      <!-- Screens -->
      <Card v-if="rightsStore.can('screens.page')" data-tour="stat-screens" :class="['stat-card', screensWarn || windowedScreens > 0 ? 'stat-card--warn' : 'stat-card--ok']" @click="router.push('/screens')">
        <template #content>
          <div class="stat-header">
            <i class="pi pi-desktop stat-icon"></i>
            <span class="stat-label">Screens</span>
            <i v-if="screensWarn" class="pi pi-exclamation-triangle warn-icon" title="One or more screens are offline"></i>
          </div>
          <div class="stat-value">{{ screensCount }}</div>
          <div class="stat-detail">
            <span :class="onlineScreens === screensCount && screensCount > 0 ? 'detail-ok' : 'detail-warn'">
              {{ onlineScreens }} online
            </span>
            <span class="detail-sep">/</span>
            <span>{{ screensCount - onlineScreens }} offline</span>
          </div>
          <div class="stat-detail" v-if="windowedScreens + fullscreenScreens > 0">
            <span :class="windowedScreens > 0 ? 'detail-warn' : 'detail-ok'">
              {{ fullscreenScreens }} fullscreen
            </span>
            <span class="detail-sep">/</span>
            <span :class="windowedScreens > 0 ? 'detail-warn' : ''">{{ windowedScreens }} windowed</span>
          </div>
        </template>
      </Card>

      <!-- Devices -->
      <Card v-if="rightsStore.can('device.page')" data-tour="stat-devices" :class="['stat-card', devicesWarn ? 'stat-card--warn' : 'stat-card--ok']" @click="router.push('/devices')">
        <template #content>
          <div class="stat-header">
            <i class="pi pi-tablet stat-icon"></i>
            <span class="stat-label">Devices</span>
            <i v-if="devicesWarn" class="pi pi-exclamation-triangle warn-icon" title="One or more active devices are offline"></i>
          </div>
          <div class="stat-value">{{ activeDevices }}</div>
          <div class="stat-detail">
            <span :class="onlineDevices === activeDevices && activeDevices > 0 ? 'detail-ok' : 'detail-warn'">
              {{ onlineDevices }} online
            </span>
            <span class="detail-sep">/</span>
            <span>{{ activeDevices - onlineDevices }} offline</span>
          </div>
        </template>
      </Card>

      <!-- Content -->
      <Card v-if="rightsStore.can('content.page')" data-tour="stat-content" :class="['stat-card', contentWarn ? 'stat-card--warn' : 'stat-card--ok']" @click="router.push('/content')">
        <template #content>
          <div class="stat-header">
            <i class="pi pi-file stat-icon"></i>
            <span class="stat-label">Content</span>
            <i v-if="contentWarn" class="pi pi-exclamation-triangle warn-icon" :title="`${unassignedContent} item(s) unassigned`"></i>
          </div>
          <div class="stat-value">{{ totalContent }}</div>
          <div class="stat-detail">
            <span v-if="unassignedContent === 0" class="detail-ok">all assigned</span>
            <span v-else class="detail-warn">{{ unassignedContent }} unassigned</span>
          </div>
        </template>
      </Card>

      <!-- Screen Groups -->
      <Card v-if="rightsStore.can('screengroups.page')" data-tour="stat-screengroups" class="stat-card stat-card--ok" @click="router.push('/screengroups')">
        <template #content>
          <div class="stat-header">
            <i class="pi pi-th-large stat-icon"></i>
            <span class="stat-label">Screen Groups</span>
          </div>
          <div class="stat-value">{{ screengroupsCount }}</div>
          <div class="stat-detail">&nbsp;</div>
        </template>
      </Card>

      <!-- Media -->
      <Card v-if="rightsStore.can('media.page')" data-tour="stat-media" class="stat-card stat-card--ok" @click="router.push('/media')">
        <template #content>
          <div class="stat-header">
            <i class="pi pi-images stat-icon"></i>
            <span class="stat-label">Media</span>
          </div>
          <div class="stat-value">{{ mediaCount }}</div>
          <div class="stat-detail">&nbsp;</div>
        </template>
      </Card>

      <!-- Screens in Find Mode -->
      <Card v-if="rightsStore.can('device.page')" data-tour="stat-find" :class="['stat-card', findWarn ? 'stat-card--warn' : 'stat-card--ok']" @click="router.push(links.screensFiltered('find'))">
        <template #content>
          <div class="stat-header">
            <i class="pi pi-search stat-icon"></i>
            <span class="stat-label">Find Mode</span>
            <i v-if="findWarn" class="pi pi-exclamation-triangle warn-icon" :title="`${screensInFind} screen(s) in find mode`"></i>
          </div>
          <div class="stat-value">{{ screensInFind }}</div>
          <div class="stat-detail">
            <span v-if="screensInFind > 0" class="detail-warn">screens in find</span>
            <span v-else class="detail-ok">none active</span>
          </div>
        </template>
      </Card>

      <!-- Screens in Debug Mode -->
      <Card v-if="rightsStore.can('screens.page')" data-tour="stat-debug" :class="['stat-card', debugWarn ? 'stat-card--warn' : 'stat-card--ok']" @click="router.push(links.screensFiltered('debug'))">
        <template #content>
          <div class="stat-header">
            <i class="pi pi-wrench stat-icon"></i>
            <span class="stat-label">Debug Mode</span>
            <i v-if="debugWarn" class="pi pi-exclamation-triangle warn-icon" :title="`${screensInDebug} screen(s) in debug mode`"></i>
          </div>
          <div class="stat-value">{{ screensInDebug }}</div>
          <div class="stat-detail">
            <span v-if="screensInDebug > 0" class="detail-warn">screens in debug</span>
            <span v-else class="detail-ok">none active</span>
          </div>
        </template>
      </Card>

    </div>

    <DashboardOverview />

    <DashboardCommunity :hide-community-links="hideCommunityLinks" :hide-helping-hand="hideHelpingHand" />

  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 0.5rem;
}
.demo-hint-card {
  border: 1px solid var(--p-amber-300, #fcd34d);
  background: var(--p-amber-50, #fffbeb);
}
.demo-hint-card :deep(.p-card-body) {
  padding: 1.1rem 1.4rem;
}
.demo-hint-body {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}
.demo-hint-icon {
  font-size: 1.4rem;
  color: var(--p-amber-500, #f59e0b);
  margin-top: 0.15rem;
  flex-shrink: 0;
}
.demo-hint-text {
  flex: 1;
  min-width: 0;
}
.demo-hint-title {
  font-weight: 600;
  margin-bottom: 0.4rem;
  color: var(--p-text-color, #111827);
}
.demo-hint-text p {
  margin: 0 0 0.5rem 0;
  font-size: 0.85rem;
  color: var(--p-text-muted-color, #6b7280);
  line-height: 1.5;
}
.demo-hint-text p:last-child {
  margin-bottom: 0;
}
.welcome-card :deep(.p-card-body) {
  padding: 1.25rem 1.5rem;
}
.welcome-body {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}
.welcome-headline {
  font-size: 1.15rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: var(--p-text-color, #111827);
}
.welcome-text {
  margin: 0;
  color: var(--p-text-muted-color, #6b7280);
  font-size: 0.9rem;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
}
/* Base card */
.stat-card {
  text-align: center;
  border-radius: 0.75rem;
  border-top: 4px solid transparent;
  transition: border-color 0.2s;
  cursor: pointer;
}
.stat-card--ok {
  border-top-color: var(--p-green-500, #22c55e);
}
.stat-card--warn {
  border-top-color: var(--p-amber-400, #f59e0b);
}
.stat-card :deep(.p-card-body) {
  padding: 1.25rem 1rem;
}
/* Card header row: icon + label + optional warning */
.stat-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}
.stat-icon {
  font-size: 1rem;
  color: var(--p-text-muted-color, #6b7280);
}
.stat-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.warn-icon {
  font-size: 0.9rem;
  color: var(--p-amber-400, #f59e0b);
}
/* Big number */
.stat-value {
  font-size: 2.75rem;
  font-weight: 700;
  line-height: 1;
  color: var(--p-primary-color, #667eea);
  margin-bottom: 0.4rem;
}
/* Sub-line detail */
.stat-detail {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #9ca3af);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
  min-height: 1.2em;
}
.detail-ok {
  color: var(--p-green-500, #22c55e);
  font-weight: 600;
}
.detail-warn {
  color: var(--p-amber-400, #f59e0b);
  font-weight: 600;
}
.detail-sep {
  color: var(--p-surface-300, #d1d5db);
}
/* Dark mode: --p-surface-0 and --p-amber-50 are fixed points on PrimeVue's
   ramp (always white/pale-amber in both themes) rather than semantic tokens
   that swap with the dark selector, unlike --p-text-color/--p-text-muted-color
   above (which do swap and already read correctly against a dark card). Since
   these two backgrounds were pinned to that fixed ramp, the already-lightened
   text ended up on an unchanged light card — hence the unreadable/low-contrast
   community, support and demo-hint cards. Give them an explicit dark surface. */
.dark-mode .demo-hint-card {
  background: var(--p-surface-800, #1e293b);
  border-color: var(--p-amber-700, #b45309);
}
/* Dark mode: PrimeVue's own dark Card background (--p-content-background,
   here resolving very close to the page's own dark background set in
   App.vue) leaves the card barely distinguishable from the page behind it.
   Bump these two up to the same explicit surface used for the link/demo
   cards above so they read as raised elements again. */
.welcome-card,
.stat-card {
  transition: background-color 0.2s, border-color 0.2s;
}
.dark-mode .welcome-card {
  background: var(--p-surface-800, #1e293b);
  border: 1px solid var(--p-surface-700, #334155);
}
/* box-shadow rather than border: .stat-card/--ok/--warn already own
   border-top (the green/amber status color) via the shorthand `border-top`
   property, so a plain `border` here would need higher specificity than
   .stat-card--ok/--warn to win and would wipe out that colored top border
   in the process. An inset ring achieves the same "raised card" outline
   without touching border-top at all. */
.dark-mode .stat-card {
  background: var(--p-surface-800, #1e293b);
  box-shadow: inset 0 0 0 1px var(--p-surface-700, #334155);
}
</style>
