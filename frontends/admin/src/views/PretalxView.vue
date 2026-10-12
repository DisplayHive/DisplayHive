<script setup lang="ts">
import PretalxAddUrlDialog from '../components/pretalx/PretalxAddUrlDialog.vue'
import PretalxEditUrlDialog from '../components/pretalx/PretalxEditUrlDialog.vue'
import PretalxCacheDialog from '../components/pretalx/PretalxCacheDialog.vue'
import PretalxTextsCard from '../components/pretalx/PretalxTextsCard.vue'
import PretalxDateTimeCard from '../components/pretalx/PretalxDateTimeCard.vue'
import type { PretalxUrl, PretalxSettings } from '../components/pretalx/types'
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useAck, type Ack } from '../composables/useAck'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useRightsStore } from '../stores/rights'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import ToggleSwitch from 'primevue/toggleswitch'

const { on, off, emit } = useSocket()
const { request } = useAck()
const toast = useToast()
const confirm = useConfirm()
const rightsStore = useRightsStore()
const canManage = computed(() => rightsStore.can('pretalx.manage'))

const urls = ref<PretalxUrl[]>([])
const now = ref(Date.now())
let clockTimer: ReturnType<typeof setInterval>

const pretalxSettings = ref<PretalxSettings>({})
const previewTimezone = ref('UTC')

// ── Add / edit dialogs ────────────────────────────────────────────────────────
const addDialogVisible = ref(false)
const editDialogVisible = ref(false)
const editingUrl = ref<PretalxUrl | null>(null)

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

// ── Add / edit ────────────────────────────────────────────────────────────────

function openAddDialog() {
  addDialogVisible.value = true
}

function openEditDialog(url: PretalxUrl) {
  editingUrl.value = url
  editDialogVisible.value = true
}

// ── Polling toggle (inline) ───────────────────────────────────────────────────

async function onPollingToggle(url: PretalxUrl, val: boolean) {
  const ack = await request('displayhive:admin:pretalx:cts:update_url', {
    id: url.id,
    polling_enabled: val,
  }, { error: 'Update failed' })
  if (!ack) url.polling_enabled = !val
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
      await request('displayhive:admin:pretalx:cts:delete_url', { id: url.id }, { error: 'Delete failed' })
    },
  })
}

// ── Cache viewer ──────────────────────────────────────────────────────────────

function viewCache(url: PretalxUrl) {
  emit('displayhive:admin:pretalx:cts:get_cache', { id: url.id })
}

// ── Socket handlers ───────────────────────────────────────────────────────────

const handleUrls = (data: { urls?: PretalxUrl[] }) => { urls.value = data?.urls || [] }

const handleCache = (data: Partial<Ack> & { name?: string; fetched_at?: string; cached_json?: string }) => {
  if (!data?.success) {
    toast.add({ severity: 'error', summary: 'Error', detail: data?.error || 'No cache available', life: 3000 })
    return
  }
  cacheTitle.value = data.name || ''
  cacheFetchedAt.value = data.fetched_at ? new Date(data.fetched_at).toLocaleString() : '—'
  try {
    cacheContent.value = JSON.stringify(JSON.parse(data.cached_json || ''), null, 2)
  } catch {
    cacheContent.value = data.cached_json || ''
  }
  cacheDialogVisible.value = true
}

const handlePretalxSettings = (data: { settings?: PretalxSettings }) => {
  pretalxSettings.value = data?.settings || {}
}

const handleAdminSettingsForTimezone = (data: { system_settings?: { timezone?: string } }) => {
  const tz = data?.system_settings?.timezone
  if (tz) previewTimezone.value = tz
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
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Pretalx page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="pretalx-page" class="pretalx-view">
    <Card>
      <template #title>
        <div class="card-header">
          <i class="pi pi-calendar card-header-icon" />
          <span>Pretalx API Endpoints</span>
          <Button v-if="canManage" data-tour="pretalx-add-url" label="Add URL" icon="pi pi-plus" size="small" class="add-btn" @click="openAddDialog" />
        </div>
      </template>
      <template #content>
        <DataTable :value="urls" stripedRows size="small" data-tour="pretalx-table">
          <template #empty>
            <div class="empty-state empty-state--compact">
              <i class="pi pi-calendar" />
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
              <div class="row-actions" data-tour="pretalx-row-actions">
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

    <PretalxAddUrlDialog v-model:visible="addDialogVisible" />
    <PretalxEditUrlDialog v-model:visible="editDialogVisible" :url="editingUrl" />
    <PretalxCacheDialog
      v-model:visible="cacheDialogVisible"
      :cache-title="cacheTitle"
      :cache-fetched-at="cacheFetchedAt"
      :cache-content="cacheContent"
    />
    <PretalxTextsCard :settings="pretalxSettings" :can-manage="canManage" />
    <PretalxDateTimeCard :settings="pretalxSettings" :can-manage="canManage" :timezone="previewTimezone" :now="now" />
  </div>
</template>

<style scoped src="../components/pretalx/shared.css"></style>
<style scoped>
.pretalx-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
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
.validity-icon.unknown { color: var(--p-text-muted-color, #94a3b8); }

.row-actions {
  display: flex;
  gap: 0.35rem;
}
</style>
