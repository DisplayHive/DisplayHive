<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useRightsStore } from '../stores/rights'
import type { Screen } from '../types/models'

// PrimeVue components
import Card from 'primevue/card'
import Select from 'primevue/select'
import Button from 'primevue/button'
import Tag from 'primevue/tag'

const rightsStore = useRightsStore()

interface LogEntry {
  timestamp: string
  severity: string
  message: string
  screen: string
  function: string
}

const { on, off, emit } = useSocket()

const logs = ref<LogEntry[]>([])
const logContainer = ref<HTMLElement | null>(null)
const screens = ref<Screen[]>([])
const selectedSeverity = ref<string | null>(null)
const selectedScreen = ref<string | null>(null)
const autoScroll = ref(true)
const maxLogs = 1000

const severityOptions = [
  { label: 'All', value: null },
  { label: 'Debug', value: 'debug' },
  { label: 'Info', value: 'info' },
  { label: 'Warn', value: 'warn' },
  { label: 'Error', value: 'error' },
]

const screenOptions = computed(() => {
  const options: { label: string; value: string | null }[] = [{ label: 'All Screens', value: null }]
  screens.value.forEach((s) => {
    options.push({ label: s.name, value: s.name })
  })
  return options
})

const filteredLogs = computed(() => {
  return logs.value.filter((log) => {
    if (selectedSeverity.value && log.severity !== selectedSeverity.value) {
      return false
    }
    if (selectedScreen.value && log.screen !== selectedScreen.value) {
      return false
    }
    return true
  })
})

const handleLogEntry = (data: LogEntry) => {
  logs.value.push(data)
  if (logs.value.length > maxLogs) {
    logs.value.shift()
  }
  if (autoScroll.value) {
    scrollToBottom()
  }
}

const handleScreensList = (data: { screens: Screen[] }) => {
  screens.value = data.screens || []
}

const handleLogHistory = (data: { logs: LogEntry[] }) => {
  logs.value = data.logs || []
}

onMounted(() => {
  on('displayhive:logger:stc:log_entry', handleLogEntry)
  on('displayhive:logger:stc:log_history', handleLogHistory)
  on('displayhive:admin:stc:screens_list', handleScreensList)

  emit('displayhive:logger:cts:subscribe')
  emit('displayhive:logger:cts:get_history')
  emit('displayhive:admin:cts:get_screens')
})

onUnmounted(() => {
  off('displayhive:logger:stc:log_entry', handleLogEntry)
  off('displayhive:logger:stc:log_history', handleLogHistory)
  off('displayhive:admin:stc:screens_list', handleScreensList)
  emit('displayhive:logger:cts:unsubscribe')
})

const clearLogs = () => {
  logs.value = []
}

const scrollToBottom = () => {
  if (logContainer.value) {
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
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
    timestamp: new Date().toISOString(),
    severity: 'info',
    message: 'Test log from admin logger view',
    screen: 'admin',
    function: 'sendTestLog'
  })
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('logger.page')" class="logger-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Logger page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="logger-view">
    <Card>
      <template #title>
        <div class="card-header">
          <div class="header-actions">
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
        <div class="filter-bar">
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
          <div class="log-count">
            <Tag :value="`${filteredLogs.length} logs`" />
          </div>
        </div>

        <div class="log-container" ref="logContainer">
          <div
            v-for="(log, index) in filteredLogs"
            :key="index"
            class="log-entry"
            :class="`log-${log.severity}`"
          >
            <span class="log-time">{{ formatTimestamp(log.timestamp) }}</span>
            <Tag :value="log.severity" :severity="getSeverityClass(log.severity)" class="log-severity" />
            <span class="log-screen" v-if="log.screen">{{ log.screen }}</span>
            <span class="log-function" v-if="log.function">[{{ log.function }}]</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
          <div v-if="filteredLogs.length === 0" class="no-logs">
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
