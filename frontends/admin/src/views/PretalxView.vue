<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useRightsStore } from '../stores/rights'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import ToggleSwitch from 'primevue/toggleswitch'
import DatePicker from 'primevue/datepicker'

interface PretalxUrl {
  id: number
  name: string
  url: string
  polling_enabled: boolean
  polling_interval: number
  last_success: string | null
  last_failure: string | null
  is_valid: boolean | null
  next_fetch: string | null
  has_cache: boolean
}

const { on, off, emit, emitWithAck } = useSocket()
const toast = useToast()
const confirm = useConfirm()
const rightsStore = useRightsStore()
const canManage = computed(() => rightsStore.can('pretalx.manage'))

const urls = ref<PretalxUrl[]>([])
const now = ref(Date.now())
let clockTimer: ReturnType<typeof setInterval>

// ── Date/Time settings ────────────────────────────────────────────────────────
const pretalxTimeFormat = ref('HH:mm')
const pretalxEndOfDay = ref('23:59')
const pretalxSimDatetime = ref<Date | null>(null)
const pretalxNoSessionText = ref('No session running')
const pretalxComingUpText = ref('Coming up next')
const pretalxInvalidDataText = ref('Invalid API data')
const settingsSaving = ref(false)
const textsSaving = ref(false)
const previewTimezone = ref('UTC')

const FORMAT_TOKENS = [
  { token: 'YYYY',  desc: 'Year (4 digits)',        example: '2024'   },
  { token: 'YY',    desc: 'Year (2 digits)',         example: '24'     },
  { token: 'MM',    desc: 'Month (01–12)',           example: '06'     },
  { token: 'M',     desc: 'Month (1–12)',            example: '6'      },
  { token: 'DD',    desc: 'Day (01–31)',             example: '07'     },
  { token: 'D',     desc: 'Day (1–31)',              example: '7'      },
  { token: 'HH',    desc: 'Hour 24h (00–23)',        example: '14'     },
  { token: 'H',     desc: 'Hour 24h (0–23)',         example: '14'     },
  { token: 'hh',    desc: 'Hour 12h (01–12)',        example: '02'     },
  { token: 'h',     desc: 'Hour 12h (1–12)',         example: '2'      },
  { token: 'mm',    desc: 'Minute (00–59)',          example: '05'     },
  { token: 'ss',    desc: 'Second (00–59)',          example: '09'     },
  { token: 'A',     desc: 'AM / PM',                example: 'PM'     },
  { token: 'dddd',  desc: 'Weekday (full)',          example: 'Monday' },
  { token: 'ddd',   desc: 'Weekday (short)',         example: 'Mon'    },
]

function _formatDateStr(d: Date, fmt: string, timezone: string): string {
  try {
    const tz = timezone || 'UTC'
    const p = new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
      hour12: false, weekday: 'long',
    }).formatToParts(d)
    const p12 = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, hour: 'numeric', hour12: true,
    }).formatToParts(d)
    const wdShort = new Intl.DateTimeFormat('en-US', {
      timeZone: tz, weekday: 'short',
    }).format(d)
    const get   = (type: string) => p.find(x => x.type === type)?.value ?? ''
    const get12 = (type: string) => p12.find(x => x.type === type)?.value ?? ''
    const year   = get('year')
    const month  = get('month')
    const day    = get('day')
    const h24    = parseInt(get('hour'), 10) % 24
    const minute = get('minute')
    const second = get('second')
    const wdFull = get('weekday')
    const h12r   = parseInt(get12('hour'), 10)
    const h12    = h12r === 0 ? 12 : h12r
    const period = (get12('dayPeriod') || (h24 < 12 ? 'AM' : 'PM')).toUpperCase()
    return fmt.replace(/YYYY|YY|dddd|ddd|MM|M|DD|D|HH|H|hh|h|mm|m|ss|s|A|a/g, t => {
      switch (t) {
        case 'YYYY': return year
        case 'YY':   return year.slice(-2)
        case 'dddd': return wdFull
        case 'ddd':  return wdShort
        case 'MM':   return month
        case 'M':    return String(parseInt(month, 10))
        case 'DD':   return day
        case 'D':    return String(parseInt(day, 10))
        case 'HH':   return String(h24).padStart(2, '0')
        case 'H':    return String(h24)
        case 'hh':   return String(h12).padStart(2, '0')
        case 'h':    return String(h12)
        case 'mm':   return minute
        case 'm':    return String(parseInt(minute, 10))
        case 'ss':   return second
        case 's':    return String(parseInt(second, 10))
        case 'A':    return period
        case 'a':    return period.toLowerCase()
        default:     return t
      }
    })
  } catch { return fmt }
}

const formatDatePreview = (format: string): string =>
  _formatDateStr(new Date(now.value), format || 'HH:mm', previewTimezone.value)

// ── Add dialog ────────────────────────────────────────────────────────────────
const addDialogVisible = ref(false)
const newName = ref('')
const newUrl = ref('')
const addLoading = ref(false)

// ── Edit dialog ───────────────────────────────────────────────────────────────
const editDialogVisible = ref(false)
const editId = ref<number | null>(null)
const editName = ref('')
const editUrl = ref('')
const editInterval = ref(300)
const editLoading = ref(false)

// ── Cache dialog ──────────────────────────────────────────────────────────────
const cacheDialogVisible = ref(false)
const cacheTitle = ref('')
const cacheFetchedAt = ref('')
const cacheContent = ref('')

// ── Formatting ────────────────────────────────────────────────────────────────

function formatNextFetch(url: PretalxUrl): string {
  if (!url.polling_enabled || !url.next_fetch) return '—'
  const diff = Math.floor((new Date(url.next_fetch).getTime() - now.value) / 1000)
  if (diff <= 0) return 'soon'
  const m = Math.floor(diff / 60)
  const s = diff % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

// ── Add ───────────────────────────────────────────────────────────────────────

function openAddDialog() {
  newName.value = ''
  newUrl.value = ''
  addDialogVisible.value = true
}

async function addUrl() {
  const name = newName.value.trim()
  const url = newUrl.value.trim()
  if (!name || !url) return
  addLoading.value = true
  try {
    const ack = await emitWithAck<any>('displayhive:admin:pretalx:cts:add_url', { name, url })
    addDialogVisible.value = false
    if (ack?.ok) {
      if (ack.is_valid) {
        toast.add({ severity: 'success', summary: 'Added', detail: 'URL added and returned valid JSON', life: 3000 })
      } else {
        toast.add({ severity: 'warn', summary: 'Added', detail: 'URL saved but did not return valid JSON', life: 4000 })
      }
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Failed to add URL', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    addLoading.value = false
  }
}

// ── Edit ──────────────────────────────────────────────────────────────────────

function openEditDialog(url: PretalxUrl) {
  editId.value = url.id
  editName.value = url.name
  editUrl.value = url.url
  editInterval.value = url.polling_interval
  editDialogVisible.value = true
}

async function saveEdit(keepOpen = false) {
  if (!editId.value || !editName.value.trim()) return
  editLoading.value = true
  try {
    const ack = await emitWithAck<any>('displayhive:admin:pretalx:cts:update_url', {
      id: editId.value,
      name: editName.value.trim(),
      polling_interval: editInterval.value,
    })
    if (ack?.ok) {
      if (!keepOpen) editDialogVisible.value = false
      toast.add({ severity: 'success', summary: 'Saved', detail: 'URL updated', life: 2500 })
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Update failed', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    editLoading.value = false
  }
}

// ── Polling toggle (inline) ───────────────────────────────────────────────────

async function onPollingToggle(url: PretalxUrl, val: boolean) {
  const ack = await emitWithAck<any>('displayhive:admin:pretalx:cts:update_url', {
    id: url.id,
    polling_enabled: val,
  })
  if (!ack?.ok) {
    url.polling_enabled = !val
    toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Update failed', life: 3000 })
  }
}

// ── Delete ────────────────────────────────────────────────────────────────────

function deleteUrl(url: PretalxUrl) {
  confirm.require({
    message: `Delete "${url.name}"? This will also remove its cached data.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    rejectProps: { label: 'Cancel', severity: 'secondary', outlined: true },
    acceptProps: { label: 'Delete', severity: 'danger' },
    accept: async () => {
      const ack = await emitWithAck<any>('displayhive:admin:pretalx:cts:delete_url', { id: url.id })
      if (!ack?.ok) {
        toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Delete failed', life: 4000 })
      }
    },
  })
}

// ── Cache viewer ──────────────────────────────────────────────────────────────

function viewCache(url: PretalxUrl) {
  emit('displayhive:admin:pretalx:cts:get_cache', { id: url.id })
}

// ── Socket handlers ───────────────────────────────────────────────────────────

const handleUrls = (data: any) => { urls.value = data?.urls || [] }

const handleCache = (data: any) => {
  if (!data?.ok) {
    toast.add({ severity: 'error', summary: 'Error', detail: data?.error || 'No cache available', life: 3000 })
    return
  }
  cacheTitle.value = data.name
  cacheFetchedAt.value = data.fetched_at ? new Date(data.fetched_at).toLocaleString() : '—'
  try {
    cacheContent.value = JSON.stringify(JSON.parse(data.cached_json), null, 2)
  } catch {
    cacheContent.value = data.cached_json || ''
  }
  cacheDialogVisible.value = true
}

const handlePretalxSettings = (data: any) => {
  const s = data?.settings || {}
  pretalxTimeFormat.value      = s.time_format      ?? 'HH:mm'
  pretalxEndOfDay.value        = s.end_of_day       ?? '23:59'
  pretalxNoSessionText.value   = s.no_session_text  ?? 'No session running'
  pretalxComingUpText.value    = s.coming_up_text   ?? 'Coming up next'
  pretalxInvalidDataText.value = s.invalid_data_text ?? 'Invalid API data'
  pretalxSimDatetime.value     = s.sim_datetime ? new Date(s.sim_datetime) : null
}

const handleAdminSettingsForTimezone = (data: any) => {
  const tz = data?.system_settings?.timezone
  if (tz) previewTimezone.value = tz
}

const savePretalxSettings = async () => {
  settingsSaving.value = true
  try {
    const _d = pretalxSimDatetime.value
    const pad = (n: number) => String(n).padStart(2, '0')
    const simIso = _d
      ? `${_d.getFullYear()}-${pad(_d.getMonth() + 1)}-${pad(_d.getDate())}T${pad(_d.getHours())}:${pad(_d.getMinutes())}`
      : ''
    const ack = await emitWithAck<any>('displayhive:admin:pretalx:cts:save_settings', {
      time_format:   pretalxTimeFormat.value,
      end_of_day:    pretalxEndOfDay.value,
      sim_datetime:  simIso,
    })
    if (ack?.ok) {
      toast.add({ severity: 'success', summary: 'Saved', detail: 'Date/Time settings updated', life: 2500 })
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Save failed', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    settingsSaving.value = false
  }
}

const savePretalxTexts = async () => {
  textsSaving.value = true
  try {
    const ack = await emitWithAck<any>('displayhive:admin:pretalx:cts:save_settings', {
      no_session_text:   pretalxNoSessionText.value,
      coming_up_text:    pretalxComingUpText.value,
      invalid_data_text: pretalxInvalidDataText.value,
    })
    if (ack?.ok) {
      toast.add({ severity: 'success', summary: 'Saved', detail: 'Default texts updated', life: 2500 })
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Save failed', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    textsSaving.value = false
  }
}

onMounted(() => {
  on('displayhive:admin:pretalx:stc:urls', handleUrls)
  on('displayhive:admin:pretalx:stc:cache', handleCache)
  on('displayhive:admin:pretalx:stc:settings', handlePretalxSettings)
  on('displayhive:admin:stc:admin_settings', handleAdminSettingsForTimezone)
  emit('displayhive:admin:pretalx:cts:get_urls')
  emit('displayhive:admin:pretalx:cts:get_settings')
  emit('displayhive:admin:cts:get_admin_settings')
  clockTimer = setInterval(() => { now.value = Date.now() }, 1000)
})

onUnmounted(() => {
  off('displayhive:admin:pretalx:stc:urls', handleUrls)
  off('displayhive:admin:pretalx:stc:cache', handleCache)
  off('displayhive:admin:pretalx:stc:settings', handlePretalxSettings)
  off('displayhive:admin:stc:admin_settings', handleAdminSettingsForTimezone)
  clearInterval(clockTimer)
})
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('pretalx.page')" class="pretalx-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Pretalx page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="pretalx-view">
    <Card>
      <template #title>
        <div class="card-header">
          <i class="pi pi-calendar" />
          <span>Pretalx API Endpoints</span>
          <Button v-if="canManage" label="Add URL" icon="pi pi-plus" size="small" class="add-btn" @click="openAddDialog" />
        </div>
      </template>
      <template #content>
        <DataTable :value="urls" stripedRows size="small">
          <template #empty>
            <div class="empty-state">
              <i class="pi pi-calendar" style="font-size: 1.5rem" />
              <p>No API URLs configured. Click "Add URL" to get started.</p>
            </div>
          </template>

          <Column header="Name" field="name" />

          <Column header="Polling" style="width: 80px">
            <template #body="{ data }">
              <ToggleSwitch
                v-model="data.polling_enabled"
                :disabled="!canManage"
                @update:modelValue="(val) => onPollingToggle(data, val)"
              />
            </template>
          </Column>

          <Column header="Next Fetch" style="width: 110px">
            <template #body="{ data }">
              {{ formatNextFetch(data) }}
            </template>
          </Column>

          <Column header="" style="width: 30px">
            <template #body="{ data }">
              <i
                v-if="data.is_valid === true"
                class="pi pi-check-circle validity-icon valid"
                v-tooltip.top="'Returns valid JSON'"
              />
              <i
                v-else-if="data.is_valid === false"
                class="pi pi-times-circle validity-icon invalid"
                v-tooltip.top="'Invalid or unreachable'"
              />
              <i
                v-else
                class="pi pi-question-circle validity-icon unknown"
                v-tooltip.top="'Not yet validated'"
              />
            </template>
          </Column>

          <Column header="" style="width: 120px">
            <template #body="{ data }">
              <div class="row-actions">
                <Button
                  v-if="canManage"
                  icon="pi pi-pencil"
                  size="small"
                  outlined
                  severity="secondary"
                  v-tooltip.top="'Edit'"
                  @click="openEditDialog(data)"
                />
                <Button
                  icon="pi pi-eye"
                  size="small"
                  outlined
                  severity="secondary"
                  :disabled="!data.has_cache"
                  v-tooltip.top="'View cached response'"
                  @click="viewCache(data)"
                />
                <Button
                  v-if="canManage"
                  icon="pi pi-trash"
                  size="small"
                  outlined
                  severity="danger"
                  v-tooltip.top="'Delete'"
                  @click="deleteUrl(data)"
                />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Add dialog -->
    <Dialog v-model:visible="addDialogVisible" header="Add Pretalx API URL" :modal="true" style="width: 480px">
      <div class="edit-form">
        <div class="field">
          <label>Name</label>
          <InputText v-model="newName" placeholder="e.g. Main Conference" style="width: 100%" autofocus />
        </div>
        <div class="field">
          <label>API URL</label>
          <InputText
            v-model="newUrl"
            placeholder="https://pretalx.example.com/api/events/conf/talks/"
            style="width: 100%"
            @keydown.enter="addUrl"
          />
          <small class="hint">The URL is fetched immediately — it must return JSON to be marked as valid.</small>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" outlined @click="addDialogVisible = false" />
        <Button
          label="Add & Validate"
          icon="pi pi-plus"
          :loading="addLoading"
          :disabled="!newName.trim() || !newUrl.trim()"
          @click="addUrl"
        />
      </template>
    </Dialog>

    <!-- Edit dialog -->
    <Dialog v-model:visible="editDialogVisible" header="Edit Pretalx API URL" :modal="true" style="width: 480px">
      <div class="edit-form">
        <div class="field">
          <label>Name</label>
          <InputText v-model="editName" style="width: 100%" autofocus />
        </div>
        <div class="field">
          <label>API URL</label>
          <InputText v-model="editUrl" style="width: 100%" disabled />
          <small class="hint">URL cannot be changed after creation. Delete and re-add to use a different URL.</small>
        </div>
        <div class="field">
          <label>Polling Interval (seconds)</label>
          <InputNumber v-model="editInterval" :min="30" :max="86400" style="width: 100%" />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" severity="secondary" outlined @click="editDialogVisible = false" />
        <Button label="Update" severity="secondary" outlined :loading="editLoading" :disabled="!editName.trim()" @click="saveEdit(true)" />
        <Button label="Save" icon="pi pi-check" :loading="editLoading" :disabled="!editName.trim()" @click="saveEdit()" />
      </template>
    </Dialog>

    <!-- Cache viewer dialog -->
    <Dialog
      v-model:visible="cacheDialogVisible"
      :header="`Cached Response — ${cacheTitle}`"
      :modal="true"
      style="width: min(900px, 95vw)"
    >
      <div class="cache-meta">Fetched at: {{ cacheFetchedAt }}</div>
      <pre class="cache-json">{{ cacheContent }}</pre>
    </Dialog>

    <!-- Default Texts card -->
    <Card>
      <template #title>
        <div class="card-header">
          <i class="pi pi-comment" />
          <span>Default Texts</span>
        </div>
      </template>
      <template #content>
        <p class="settings-hint">All settings are only default values. They may be overwritten in the content.</p>
        <div class="settings-form">
          <div class="field">
            <label for="pretalx-no-session">No Session Running</label>
            <InputText id="pretalx-no-session" v-model="pretalxNoSessionText" class="w-full" :disabled="!canManage" />
          </div>
          <div class="field">
            <label for="pretalx-coming-up">Coming Up Next</label>
            <InputText id="pretalx-coming-up" v-model="pretalxComingUpText" class="w-full" :disabled="!canManage" />
          </div>
          <div class="field">
            <label for="pretalx-invalid-data">Invalid API Data</label>
            <InputText id="pretalx-invalid-data" v-model="pretalxInvalidDataText" class="w-full" :disabled="!canManage" />
          </div>
          <div class="field-actions">
            <Button v-if="canManage" label="Save" icon="pi pi-check" :loading="textsSaving" @click="savePretalxTexts" />
          </div>
        </div>
      </template>
    </Card>

    <!-- Date/Time Settings card -->
    <Card>
      <template #title>
        <div class="card-header">
          <i class="pi pi-clock" />
          <span>Date / Time Settings</span>
        </div>
      </template>
      <template #content>
        <p class="settings-hint">All settings are only default values. They may be overwritten in the content.</p>
        <div class="settings-form">
          <div class="field">
            <label for="pretalx-time-format">Display Time Format</label>
            <div class="datetime-format-wrapper">
              <InputText id="pretalx-time-format" v-model="pretalxTimeFormat" placeholder="HH:mm" class="w-full" :disabled="!canManage" />
              <div class="datetime-preview">
                <span class="datetime-preview-label">Preview</span>
                <span class="datetime-preview-value">{{ formatDatePreview(pretalxTimeFormat) }}</span>
                <span class="datetime-preview-tz">({{ previewTimezone }})</span>
              </div>
              <div class="datetime-tokens">
                <p class="datetime-tokens-title">Format tokens</p>
                <table class="token-table">
                  <thead>
                    <tr><th>Token</th><th>Description</th><th>Example</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="t in FORMAT_TOKENS" :key="t.token">
                      <td><code>{{ t.token }}</code></td>
                      <td>{{ t.desc }}</td>
                      <td>{{ t.example }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
          <div class="field">
            <label for="pretalx-end-of-day">End of Day</label>
            <InputText id="pretalx-end-of-day" v-model="pretalxEndOfDay" placeholder="23:59" class="w-full" :disabled="!canManage" />
          </div>
          <div class="field">
            <label for="pretalx-sim-datetime">Simulation Datetime</label>
            <small class="field-description">If set, rendering uses this time instead of the current time. Leave empty to use live time.</small>
            <DatePicker
              id="pretalx-sim-datetime"
              v-model="pretalxSimDatetime"
              showTime
              hourFormat="24"
              showClear
              dateFormat="dd.mm.yy"
              placeholder="Use current time"
              class="w-full"
              :disabled="!canManage"
            />
          </div>
          <div class="field-actions">
            <Button v-if="canManage" label="Save" icon="pi pi-check" :loading="settingsSaving" @click="savePretalxSettings" />
          </div>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.pretalx-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.datetime-format-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.datetime-preview {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.45rem 0.75rem;
  background: var(--p-surface-100, #f3f4f6);
  border-radius: 6px;
  font-family: monospace;
}

.datetime-preview-label {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--p-text-muted-color, #6b7280);
}

.datetime-preview-value {
  font-size: 1rem;
  font-weight: 600;
}

.datetime-preview-tz {
  margin-left: auto;
  font-size: 0.7rem;
  color: var(--p-text-muted-color, #9ca3af);
}

.datetime-tokens { margin-top: 0.1rem; }

.datetime-tokens-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
  margin: 0 0 0.35rem;
}

.token-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
}

.token-table th {
  text-align: left;
  padding: 0.2rem 0.5rem;
  border-bottom: 1px solid var(--p-surface-300, #d1d5db);
  font-size: 0.7rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.token-table td {
  padding: 0.18rem 0.5rem;
  border-bottom: 1px solid var(--p-surface-200, #e5e7eb);
}

.token-table td code {
  background: var(--p-surface-200, #e5e7eb);
  padding: 0 0.3rem;
  border-radius: 3px;
  font-size: 0.74rem;
}

.settings-hint {
  font-size: 0.82rem;
  color: var(--p-text-muted-color, #6b7280);
  margin-bottom: 1rem;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.field-actions {
  display: flex;
  justify-content: flex-end;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  text-align: left;
  gap: 0.5rem;
  width: 100%;
}

.add-btn { margin-left: auto; }

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.75rem;
  padding: 2rem;
  color: var(--p-text-muted-color, #9ca3af);
}

.validity-icon {
  font-size: 1.1rem;
}
.validity-icon.valid   { color: #22c55e; }
.validity-icon.invalid { color: #ef4444; }
.validity-icon.unknown { color: #94a3b8; }

.row-actions {
  display: flex;
  gap: 0.35rem;
}

.edit-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding-top: 0.5rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.field label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.hint {
  font-size: 0.78rem;
  color: var(--p-text-muted-color, #9ca3af);
}

.cache-meta {
  font-size: 0.8rem;
  color: var(--p-text-muted-color, #6b7280);
  margin-bottom: 0.75rem;
}

.cache-json {
  background: #1a1a2e;
  color: #e2e8f0;
  padding: 1rem;
  border-radius: 6px;
  overflow: auto;
  max-height: 65vh;
  font-size: 0.78rem;
  font-family: 'Courier New', 'Consolas', monospace;
  white-space: pre;
  line-height: 1.5;
}
</style>
