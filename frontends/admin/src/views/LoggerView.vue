<script setup lang="ts">
import RouteLink from '../components/RouteLink.vue'
import { links } from '../utils/links'
import { useRightsStore } from '../stores/rights'
import { useScreensStore } from '../stores/screens'
import { useAck } from '../composables/useAck'
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useSocket } from '../composables/useSocket'

// PrimeVue components
import Card from 'primevue/card'
import Select from 'primevue/select'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'

const rightsStore = useRightsStore()
const screensStore = useScreensStore()
const { request } = useAck()

// The screen log is stored on the server (kept for the time set on the Settings page); this page
// shows its newest lines, older ones on demand, and new ones live. An admin's own test line is
// only shown, never stored (id null).
interface LogEntry {
  id: number | null
  timestamp: string
  severity: string
  message: string
  screen: string
  screen_id: number | null
  function: string
}

const { on, off, emit, isConnected } = useSocket()

const logs = ref<LogEntry[]>([])
const hasMore = ref(false)
const loading = ref(false)
const logContainer = ref<HTMLElement | null>(null)
const selectedSeverity = ref<string | null>(null)
const selectedScreen = ref<number | null>(null)
const search = ref('')
const autoScroll = ref(true)
const maxLogs = 1000

const severityOptions = [
  { label: 'All', value: null },
  { label: 'Debug', value: 'debug' },
  { label: 'Info', value: 'info' },
  { label: 'Warn', value: 'warn' },
  { label: 'Error', value: 'error' },
]

const screenOptions = computed(() => [
  { label: 'All Screens', value: null as number | null },
  ...screensStore.screens.map((s) => ({ label: s.name, value: s.id as number | null })),
])
const screenIdByName = computed(() => new Map(screensStore.screens.map((s) => [s.name, s.id])))

const filters = () => ({
  screen_id: selectedScreen.value,
  severities: selectedSeverity.value ? [selectedSeverity.value] : [],
  search: search.value.trim(),
})

const matches = (entry: LogEntry) => {
  const f = filters()
  if (f.screen_id !== null && entry.screen_id !== f.screen_id) return false
  if (f.severities.length && !f.severities.includes(entry.severity)) return false
  if (f.search && !entry.message.toLowerCase().includes(f.search.toLowerCase())) return false
  return true
}

const oldestStoredId = () => logs.value.find((l) => l.id !== null)?.id ?? null

/** Replace the list with the newest stored lines matching the filters. */
const reload = async () => {
  loading.value = true
  try {
    const ack = await request<{ success: boolean; logs?: LogEntry[]; has_more?: boolean }>(
      'displayhive:logger:cts:query', filters(), { error: 'Could not load the log' })
    if (!ack) return
    logs.value = ack.logs ?? []
    hasMore.value = !!ack.has_more
    if (autoScroll.value) scrollToBottom()
  } finally {
    loading.value = false
  }
}

const loadOlder = async () => {
  const before = oldestStoredId()
  if (before === null || loading.value) return
  loading.value = true
  try {
    const ack = await request<{ success: boolean; logs?: LogEntry[]; has_more?: boolean }>(
      'displayhive:logger:cts:query', { ...filters(), before_id: before }, { error: 'Could not load older lines' })
    if (!ack) return
    logs.value = [...(ack.logs ?? []), ...logs.value]
    hasMore.value = !!ack.has_more
  } finally {
    loading.value = false
  }
}

const handleLogEntry = (data: LogEntry) => {
  if (!matches(data)) return
  logs.value.push(data)
  if (logs.value.length > maxLogs) {
    logs.value.shift()
    hasMore.value = true
  }
  if (autoScroll.value) scrollToBottom()
}

onMounted(() => {
  on('displayhive:logger:stc:log_entry', handleLogEntry)
  screensStore.fetch()
})

// (Re)join the live feed and load the stored lines whenever the socket comes up: a reconnect
// drops the room, and lines that arrived meanwhile are only in the stored log.
watch(isConnected, (connected) => {
  if (!connected) return
  emit('displayhive:logger:cts:subscribe')
  reload()
}, { immediate: true })

onUnmounted(() => {
  off('displayhive:logger:stc:log_entry', handleLogEntry)
  emit('displayhive:logger:cts:unsubscribe')
  clearTimeout(searchTimer)
})

watch([selectedSeverity, selectedScreen], reload)
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(reload, 300)
})

const clearLogs = () => {
  logs.value = []
  hasMore.value = false
}

const scrollToBottom = () => {
  // after the new lines are drawn
  setTimeout(() => {
    if (logContainer.value) logContainer.value.scrollTop = logContainer.value.scrollHeight
  })
}

const getSeverityClass = (severity: string): 'success' | 'info' | 'warn' | 'danger' | 'secondary' => {
  switch (severity) {
    case 'debug':
      return 'secondary'
    case 'info':
      return 'info'
    case 'warn':
      return 'warn'
    case 'error':
      return 'danger'
    default:
      return 'secondary'
  }
}

const formatTimestamp = (ts: string) => {
  const date = new Date(ts)
  return date.toLocaleTimeString()
}

const sendTestLog = () => {
  emit('displayhive:logger:cts:log_entry', {
    severity: 'info',
    message: 'Test log from admin logger view',
    function: 'sendTestLog'
  })
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('logger.page')" class="logger-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Logger page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="logger-page" class="logger-view">
    <Card>
      <template #title>
        <div class="card-header">
          <div class="header-actions" data-tour="logger-controls">
            <Button
              :icon="autoScroll ? 'pi pi-lock' : 'pi pi-lock-open'"
              :label="autoScroll ? 'Auto-scroll On' : 'Auto-scroll Off'"
              @click="autoScroll = !autoScroll"
              size="small"
              :severity="autoScroll ? 'success' : 'secondary'"
              outlined
            />
            <Button icon="pi pi-send" label="Test Log" @click="sendTestLog" size="small" outlined />
            <Button icon="pi pi-trash" label="Clear" @click="clearLogs" size="small" severity="danger" outlined />
          </div>
        </div>
      </template>
      <template #content>
        <div class="filter-bar" data-tour="logger-filters">
          <div class="filter-item">
            <label>Severity</label>
            <Select
              v-model="selectedSeverity"
              :options="severityOptions"
              optionLabel="label"
              optionValue="value"
              placeholder="All"
              class="filter-select"
            />
          </div>
          <div class="filter-item">
            <label>Screen</label>
            <Select
              v-model="selectedScreen"
              :options="screenOptions"
              optionLabel="label"
              optionValue="value"
              placeholder="All Screens"
              class="filter-select"
            />
          </div>
          <div class="filter-item">
            <label>Search</label>
            <InputText v-model="search" placeholder="Text in the message" class="filter-search" data-testid="logger-search" />
          </div>
          <div class="log-count">
            <Tag :value="`${logs.length} logs`" />
          </div>
        </div>

        <div class="log-container" data-tour="logger-log-container" ref="logContainer">
          <div v-if="hasMore" class="load-older">
            <Button label="Load older lines" icon="pi pi-arrow-up" size="small" text :loading="loading" data-testid="logger-load-older" @click="loadOlder" />
          </div>
          <div
            v-for="(log, index) in logs"
            :key="log.id ?? `live-${index}`"
            class="log-entry"
            :class="`log-${log.severity}`"
          >
            <span class="log-time">{{ formatTimestamp(log.timestamp) }}</span>
            <Tag :value="log.severity" :severity="getSeverityClass(log.severity)" class="log-severity" />
            <span class="log-screen" v-if="log.screen">
              <RouteLink v-if="rightsStore.can('screens.page') && screenIdByName.get(log.screen)" :to="links.screen(screenIdByName.get(log.screen)!)" title="Open this screen">{{ log.screen }}</RouteLink>
              <template v-else>{{ log.screen }}</template>
            </span>
            <span class="log-function" v-if="log.function">[{{ log.function }}]</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
          <div v-if="logs.length === 0" class="no-logs">
            <i class="pi pi-inbox"></i>
            <p>No logs to display</p>
          </div>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.logger-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  height: calc(100vh - 200px);
}

/* No title text left in the card header — keep the action buttons
   right-aligned instead of collapsing to the start. */
.card-header {
  justify-content: flex-end;
}

.filter-bar {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  align-items: flex-end;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.filter-item label {
  font-size: 0.75rem;
  font-weight: 600;
  color: #666;
}

.filter-select {
  width: 150px;
}

.filter-search {
  width: 220px;
}

.load-older {
  display: flex;
  justify-content: center;
  padding-bottom: 0.5rem;
}

.log-count {
  margin-left: auto;
}

.log-container {
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
  font-size: 0.8rem;
  border-radius: 8px;
  padding: 1rem;
  height: calc(100vh - 350px);
  overflow-y: auto;
  min-height: 400px;
}

.log-entry {
  display: flex;
  gap: 0.75rem;
  padding: 0.25rem 0;
  border-bottom: 1px solid #333;
  align-items: center;
  flex-wrap: wrap;
}

.log-entry:last-child {
  border-bottom: none;
}

.log-time {
  color: #888;
  min-width: 80px;
}

.log-severity {
  min-width: 60px;
  font-size: 0.7rem;
}

.log-screen {
  color: #569cd6;
  font-weight: 500;
}

.log-function {
  color: #dcdcaa;
}

.log-message {
  color: #d4d4d4;
  flex: 1;
  word-break: break-word;
}

.log-debug { border-left: 3px solid #888; padding-left: 0.5rem; }
.log-info { border-left: 3px solid #4fc3f7; padding-left: 0.5rem; }
.log-warn { border-left: 3px solid #ffc107; padding-left: 0.5rem; }
.log-error { border-left: 3px solid #f44336; padding-left: 0.5rem; }

.no-logs {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #666;
}

.no-logs i {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}
</style>
