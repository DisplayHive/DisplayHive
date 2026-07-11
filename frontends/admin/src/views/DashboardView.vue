<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useDevicesStore } from '../stores/devices'
import { useScreensStore } from '../stores/screens'
import { useScreengroupsStore } from '../stores/screengroups'
import { useMediaStore } from '../stores/media'
import { useContentStore } from '../stores/content'
import { isWindowed, isFullscreen } from '../composables/useMaximizedFilter'

// PrimeVue components
import Card from 'primevue/card'
import ToggleSwitch from 'primevue/toggleswitch'

const router = useRouter()
const { on, off, emit, emitWithAck } = useSocket()

const welcomeHeadline = ref('Welcome to DisplayHive Admin')
const welcomeText = ref('Use the navigation menu to manage your digital signage system.')
const hideCommunityLinks = ref(false)
const hideHelpingHand = ref(false)
const hideDemoMode = ref(false)
const demoModeSaving = ref(false)

const handleSettings = (data: any) => {
  const sys = data?.system_settings || {}
  if (sys.welcome_headline !== undefined) welcomeHeadline.value = sys.welcome_headline
  if (sys.welcome_text !== undefined) welcomeText.value = sys.welcome_text
  if (sys.hide_community_links !== undefined) hideCommunityLinks.value = sys.hide_community_links === true || sys.hide_community_links === 'true'
  if (sys.hide_helping_hand !== undefined) hideHelpingHand.value = sys.hide_helping_hand === true || sys.hide_helping_hand === 'true'
  if (sys.hide_demo_mode !== undefined) hideDemoMode.value = sys.hide_demo_mode === true || sys.hide_demo_mode === 'true'
}

const demoModeEnabled = computed({
  get: () => !hideDemoMode.value,
  set: async (value: boolean) => {
    const previous = hideDemoMode.value
    hideDemoMode.value = !value
    demoModeSaving.value = true
    try {
      const ack = await emitWithAck<{ success: boolean; error?: string }>(
        'displayhive:admin:cts:set_system_settings',
        { settings: { hide_demo_mode: hideDemoMode.value ? 'true' : 'false' } },
      )
      if (!ack?.success) {
        hideDemoMode.value = previous
      }
    } catch {
      hideDemoMode.value = previous
    } finally {
      demoModeSaving.value = false
    }
  },
})
const devicesStore = useDevicesStore()
const screensStore = useScreensStore()
const screengroupsStore = useScreengroupsStore()
const mediaStore = useMediaStore()
const contentStore = useContentStore()

onMounted(() => {
  on('displayhive:admin:stc:admin_settings', handleSettings)
  emit('displayhive:admin:cts:get_admin_settings')
  devicesStore.fetch()
  screensStore.fetch()
  screengroupsStore.fetch()
  mediaStore.fetch()
  contentStore.fetch()
})

onUnmounted(() => {
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

const totalContent = computed(() => contentStore.content.length)
const unassignedContent = computed(() => contentStore.unassignedContent.length)
const screengroupsCount = computed(() => screengroupsStore.screengroups.length)
const mediaCount = computed(() => mediaStore.mediaItems.length)

// Warning indicators
const screensWarn = computed(() => screensCount.value > 0 && onlineScreens.value < screensCount.value)
const devicesWarn = computed(() => activeDevices.value > 0 && onlineDevices.value < activeDevices.value)
const contentWarn = computed(() => unassignedContent.value >= 1)
const findWarn = computed(() => screensInFind.value > 0)
const debugWarn = computed(() => screensInDebug.value > 0)
</script>

<template>
  <div class="dashboard">

    <!-- Demo mode hint -->
    <Card v-if="demoModeEnabled" class="demo-hint-card">
      <template #content>
        <div class="demo-hint-body">
          <i class="pi pi-sparkles demo-hint-icon"></i>
          <div class="demo-hint-text">
            <div class="demo-hint-title">Demo mode is active on this instance</div>
            <p>
              You can import example configurations from the
              <a href="#" @click.prevent="router.push('/demo')">Demo page</a>.
              Please note that, with the exception of user accounts, this will overwrite
              <strong>all</strong> content previously created on this instance — system-wide.
              You can back up your current data beforehand via
              <a href="#" @click.prevent="router.push('/importexport')">Import / Export</a>.
            </p>
          </div>
        </div>
        <div class="demo-hint-footer">
          <ToggleSwitch v-model="demoModeEnabled" :disabled="demoModeSaving" class="demo-hint-switch" />
          <span class="demo-hint-switch-desc">
            Turn off to disable access to demo mode. It can be re-enabled later in Settings.
          </span>
        </div>
      </template>
    </Card>

    <!-- Welcome card -->
    <Card class="welcome-card">
      <template #content>
        <div class="welcome-body">
          <i class="pi pi-home welcome-icon"></i>
          <div>
            <div class="welcome-headline">{{ welcomeHeadline }}</div>
            <p class="welcome-text">{{ welcomeText }}</p>
          </div>
        </div>
      </template>
    </Card>

    <!-- Status cards grid -->
    <div class="stats-grid">

      <!-- Screens -->
      <Card :class="['stat-card', screensWarn || windowedScreens > 0 ? 'stat-card--warn' : 'stat-card--ok']" style="cursor:pointer" @click="router.push('/screens')">
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
      <Card :class="['stat-card', devicesWarn ? 'stat-card--warn' : 'stat-card--ok']" style="cursor:pointer" @click="router.push('/devices')">
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
      <Card :class="['stat-card', contentWarn ? 'stat-card--warn' : 'stat-card--ok']" style="cursor:pointer" @click="router.push('/content')">
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
      <Card class="stat-card stat-card--ok" style="cursor:pointer" @click="router.push('/screengroups')">
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
      <Card class="stat-card stat-card--ok" style="cursor:pointer" @click="router.push('/media')">
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
      <Card :class="['stat-card', findWarn ? 'stat-card--warn' : 'stat-card--ok']" style="cursor:pointer" @click="router.push('/screens')">
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
      <Card :class="['stat-card', debugWarn ? 'stat-card--warn' : 'stat-card--ok']" style="cursor:pointer" @click="router.push('/screens')">
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

    <!-- Community & Links -->
    <div v-if="!hideCommunityLinks" class="community-section">
      <div class="community-heading">
        <i class="pi pi-users"></i>
        <span>Community &amp; Links</span>
      </div>
      <div class="community-grid">

        <a href="https://displayhive.org" target="_blank" rel="noopener" class="link-card link-card--web">
          <div class="link-card-icon"><i class="pi pi-globe"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Website</span>
            <span class="link-card-sub">displayhive.org</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://github.com/DisplayHive" target="_blank" rel="noopener" class="link-card link-card--github">
          <div class="link-card-icon"><i class="pi pi-github"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">GitHub</span>
            <span class="link-card-sub">DisplayHive</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://t.me/DisplayHive" target="_blank" rel="noopener" class="link-card link-card--telegram">
          <div class="link-card-icon"><i class="pi pi-send"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Telegram</span>
            <span class="link-card-sub">Information channel</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://t.me/DisplayHiveDicussion" target="_blank" rel="noopener" class="link-card link-card--telegram">
          <div class="link-card-icon"><i class="pi pi-comments"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Telegram</span>
            <span class="link-card-sub">Discussion &amp; Support</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

        <a href="https://chaos.social/@DisplayHive" target="_blank" rel="noopener" class="link-card link-card--mastodon">
          <div class="link-card-icon"><i class="pi pi-at"></i></div>
          <div class="link-card-body">
            <span class="link-card-title">Mastodon</span>
            <span class="link-card-sub">@DisplayHive@chaos.social</span>
          </div>
          <i class="pi pi-arrow-up-right link-card-arrow"></i>
        </a>

      </div>
    </div>

    <!-- Support us -->
    <div v-if="!hideCommunityLinks" class="support-section">
      <div class="community-heading">
        <i class="pi pi-heart"></i>
        <span>Support the Project</span>
      </div>
      <p class="support-intro">
        DisplayHive is free and open source. If you enjoy using it, here are a few ways to help — no pressure, every bit counts.
      </p>
      <div class="support-grid">

        <a href="https://t.me/DisplayHiveDicussion" target="_blank" rel="noopener" class="support-card">
          <div class="support-card-icon support-card-icon--bug"><i class="pi pi-bug"></i></div>
          <div class="support-card-body">
            <span class="support-card-title">Found a bug?</span>
            <p class="support-card-desc">Let us know in the Telegram discussion chat so we can fix it.</p>
          </div>
        </a>

        <a href="https://t.me/DisplayHiveDicussion" target="_blank" rel="noopener" class="support-card">
          <div class="support-card-icon support-card-icon--idea"><i class="pi pi-lightbulb"></i></div>
          <div class="support-card-body">
            <span class="support-card-title">Have an idea?</span>
            <p class="support-card-desc">Share your feature requests — we'd love to hear what would make your life easier.</p>
          </div>
        </a>

        <a href="https://github.com/DisplayHive" target="_blank" rel="noopener" class="support-card">
          <div class="support-card-icon support-card-icon--star"><i class="pi pi-star"></i></div>
          <div class="support-card-body">
            <span class="support-card-title">Give us a star</span>
            <p class="support-card-desc">A GitHub star helps others discover the project. It only takes a second.</p>
          </div>
        </a>

        <a href="https://chaos.social/@DisplayHive" target="_blank" rel="noopener" class="support-card">
          <div class="support-card-icon support-card-icon--share"><i class="pi pi-share-alt"></i></div>
          <div class="support-card-body">
            <span class="support-card-title">Spread the word</span>
            <p class="support-card-desc">Using DisplayHive somewhere cool? Tell people about it — word of mouth matters.</p>
          </div>
        </a>

        <a href="https://github.com/DisplayHive" target="_blank" rel="noopener" class="support-card">
          <div class="support-card-icon support-card-icon--code"><i class="pi pi-code"></i></div>
          <div class="support-card-body">
            <span class="support-card-title">Contribute code</span>
            <p class="support-card-desc">If you feel like it, pull requests are always welcome — big or small.</p>
          </div>
        </a>

        <a href="https://github.com/DisplayHive" target="_blank" rel="noopener" class="support-card">
          <div class="support-card-icon support-card-icon--audit"><i class="pi pi-eye"></i></div>
          <div class="support-card-body">
            <span class="support-card-title">Audit the software</span>
            <p class="support-card-desc">Curious about what's under the hood? Feel free to read through the code and let us know if anything looks off — a fresh pair of eyes is always welcome.</p>
          </div>
        </a>

        <a href="mailto:security@displayhive.org" class="support-card">
          <div class="support-card-icon support-card-icon--security"><i class="pi pi-lock"></i></div>
          <div class="support-card-body">
            <span class="support-card-title">Found a security issue?</span>
            <p class="support-card-desc">If you've spotted something that looks like a security concern, please reach out privately rather than opening a public issue. We'll take it from there.</p>
            <span class="support-card-contact">security@displayhive.org</span>
          </div>
        </a>

      </div>
    </div>

    <!-- Help wanted -->
    <div v-if="!hideHelpingHand" class="help-section">
      <div class="community-heading">
        <i class="pi pi-compass"></i>
        <span>Where a helping hand goes a long way</span>
      </div>
      <p class="support-intro">
        DisplayHive is still finding its shape. If you'd like to pitch in, these are the areas that would benefit most right now — no commitment needed, every contribution counts.
      </p>
      <ul class="help-list">
        <li>
          <i class="pi pi-bug help-list-icon help-list-icon--test"></i>
          <span><strong>Testing &amp; Bug Reports</strong> — run it, break it, tell us. Real-world usage is the best test suite there is.</span>
        </li>
        <li>
          <i class="pi pi-palette help-list-icon help-list-icon--template"></i>
          <span><strong>Default Templates &amp; Content Types</strong> — a handful of ready-to-use layouts would make getting started much easier for everyone.</span>
        </li>
        <li>
          <i class="pi pi-desktop help-list-icon help-list-icon--sample"></i>
          <span><strong>Sample Applications</strong> — entrance signs, schedule boards, wayfinding displays … if you've built something, sharing it inspires others.</span>
        </li>
        <li>
          <i class="pi pi-shield help-list-icon help-list-icon--security"></i>
          <span><strong>Security &amp; Code Quality</strong> — a careful read-through of the codebase is always appreciated. Fresh eyes catch what familiar ones miss.</span>
        </li>
      </ul>
    </div>

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

.demo-hint-footer {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-top: 0.85rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--p-amber-200, #fde68a);
}

.demo-hint-switch {
  flex-shrink: 0;
}

.demo-hint-switch-desc {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #6b7280);
  line-height: 1.4;
}

.welcome-card :deep(.p-card-body) {
  padding: 1.25rem 1.5rem;
}

.welcome-body {
  display: flex;
  align-items: flex-start;
  gap: 1rem;
}

.welcome-icon {
  font-size: 1.5rem;
  color: var(--p-primary-color, #667eea);
  margin-top: 0.15rem;
  flex-shrink: 0;
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

/* Community section */
.community-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.community-heading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--p-text-muted-color, #9ca3af);
  padding-bottom: 0.25rem;
  border-bottom: 1px solid var(--p-surface-200, #e5e7eb);
}

.community-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0.75rem;
}

.link-card {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  border-radius: 0.65rem;
  border: 1px solid var(--p-surface-200, #e5e7eb);
  border-left: 4px solid transparent;
  background: var(--p-surface-0, #fff);
  text-decoration: none;
  color: inherit;
  transition: box-shadow 0.15s, transform 0.15s;
}

.link-card:hover {
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
  text-decoration: none;
}

.link-card--web    { border-left-color: #06b6d4; }
.link-card--github { border-left-color: #374151; }
.link-card--telegram { border-left-color: #2ca5e0; }
.link-card--mastodon { border-left-color: #6364ff; }

.link-card-icon {
  font-size: 1.4rem;
  flex-shrink: 0;
  width: 2rem;
  text-align: center;
}

.link-card--web      .link-card-icon { color: #06b6d4; }
.link-card--github   .link-card-icon { color: #374151; }
.link-card--telegram .link-card-icon { color: #2ca5e0; }
.link-card--mastodon .link-card-icon { color: #6364ff; }

.link-card-body {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
  flex: 1;
  min-width: 0;
}

.link-card-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--p-text-color, #111827);
  white-space: nowrap;
}

.link-card-sub {
  font-size: 0.75rem;
  color: var(--p-text-muted-color, #9ca3af);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.link-card-arrow {
  font-size: 0.75rem;
  color: var(--p-text-muted-color, #d1d5db);
  flex-shrink: 0;
}

/* Help wanted section */
.help-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.help-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.help-list li {
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
  font-size: 0.85rem;
  color: var(--p-text-muted-color, #6b7280);
  line-height: 1.5;
}

.help-list li strong {
  color: var(--p-text-color, #111827);
  font-weight: 600;
}

.help-list-icon {
  flex-shrink: 0;
  font-size: 0.8rem;
  margin-top: 0.15rem;
}

.help-list-icon--test     { color: #ef4444; }
.help-list-icon--template { color: #8b5cf6; }
.help-list-icon--sample   { color: #06b6d4; }
.help-list-icon--security { color: #f97316; }

/* Support section */
.support-section {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.support-intro {
  margin: 0;
  font-size: 0.85rem;
  color: var(--p-text-muted-color, #9ca3af);
  font-style: italic;
}

.support-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 0.85rem;
}

.support-card {
  display: flex;
  gap: 1rem;
  padding: 1rem 1.1rem;
  border-radius: 0.75rem;
  background: var(--p-surface-50, #f9fafb);
  border: 1px dashed var(--p-surface-300, #d1d5db);
  text-decoration: none;
  color: inherit;
  transition: background 0.15s, border-color 0.15s, transform 0.15s;
}

.support-card:hover {
  background: var(--p-surface-0, #fff);
  border-color: var(--p-surface-400, #9ca3af);
  border-style: solid;
  transform: translateY(-2px);
  text-decoration: none;
}

.support-card-icon {
  font-size: 1.35rem;
  flex-shrink: 0;
  width: 2rem;
  text-align: center;
  margin-top: 0.1rem;
}

.support-card-icon--bug      { color: #ef4444; }
.support-card-icon--idea     { color: #f59e0b; }
.support-card-icon--star     { color: #eab308; }
.support-card-icon--share    { color: #8b5cf6; }
.support-card-icon--code     { color: #10b981; }
.support-card-icon--audit    { color: #06b6d4; }
.support-card-icon--security { color: #f97316; }

.support-card-body {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.support-card-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--p-text-color, #111827);
}

.support-card-desc {
  margin: 0;
  font-size: 0.78rem;
  color: var(--p-text-muted-color, #9ca3af);
  line-height: 1.45;
}

.support-card-contact {
  font-size: 0.75rem;
  font-weight: 600;
  color: #f97316;
  margin-top: 0.35rem;
  display: block;
}
</style>
