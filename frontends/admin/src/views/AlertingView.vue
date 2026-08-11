<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useRightsStore } from '../stores/rights'

import Card from 'primevue/card'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Checkbox from 'primevue/checkbox'

const { on, off, emit, emitWithAck } = useSocket()
const toast = useToast()
const rightsStore = useRightsStore()
const canManage = computed(() => rightsStore.can('alerting.manage'))
const canShowToken = computed(() => rightsStore.can('alerting.showtoken'))

// ── Settings ─────────────────────────────────────────────────────────────────
const loading = ref(true)
const hasToken = ref(false)
const tokenInput = ref('')
const savingToken = ref(false)

// ── Bot user discovery ────────────────────────────────────────────────────────
const loadingBotUsers = ref(false)
const botUsersLoaded = ref(false)
const botUsersError = ref('')

interface BotUser { id: number; title: string }
const botUsers = ref<BotUser[]>([])

// ── Saved alert users ─────────────────────────────────────────────────────────
interface SavedUser { id: number; name: string; chat_id: string }
const savedUsers = ref<SavedUser[]>([])
const testingId = ref<number | null>(null)
const removingId = ref<number | null>(null)
const addingChatId = ref<string | null>(null)

// ── Alert types & subscriptions ───────────────────────────────────────────────
interface AlertType { key: string; label: string }
const alertTypes = ref<AlertType[]>([])

// Set of "userId:alertType" strings for O(1) lookup
const subscriptionSet = ref<Set<string>>(new Set())
const togglingKey = ref<string | null>(null)

const isSubscribed = (userId: number, alertKey: string): boolean =>
  subscriptionSet.value.has(`${userId}:${alertKey}`)

const showMatrix = computed(() =>
  hasToken.value && savedUsers.value.length > 0 && alertTypes.value.length > 0
)

// ── Socket handlers ───────────────────────────────────────────────────────────
const handleSettings = (data: any) => {
  loading.value = false
  hasToken.value = !!data?.has_telegram_token
  if (hasToken.value) {
    fetchBotUsers()
    fetchSavedUsers()
    fetchAlertSubscriptions()
  }
}

const handleSavedUsers = (data: any) => {
  savedUsers.value = data?.users || []
}

const handleAlertTypes = (data: any) => {
  alertTypes.value = data?.alert_types || []
}

const handleAlertSubscriptions = (data: any) => {
  const subs: Array<{ user_id: number; alert_type: string }> = data?.subscriptions || []
  subscriptionSet.value = new Set(subs.map(s => `${s.user_id}:${s.alert_type}`))
}

// ── Actions ───────────────────────────────────────────────────────────────────
const saveToken = async () => {
  savingToken.value = true
  try {
    const ack = await emitWithAck<any>('displayhive:admin:alerting:cts:save_telegram_token', { token: tokenInput.value })
    if (ack?.ok) {
      tokenInput.value = ''
      toast.add({ severity: 'success', summary: 'Saved', detail: 'Telegram token saved', life: 2500 })
      if (hasToken.value) {
        fetchBotUsers()
        fetchSavedUsers()
        fetchAlertSubscriptions()
      }
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Save failed', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    savingToken.value = false
  }
}

const fetchBotUsers = async () => {
  loadingBotUsers.value = true
  botUsersError.value = ''
  try {
    const ack = await emitWithAck<any>('displayhive:admin:alerting:cts:get_telegram_users_from_bot')
    botUsersLoaded.value = true
    if (ack?.ok) {
      botUsers.value = ack.users || []
    } else {
      botUsersError.value = ack?.error || 'Failed to fetch users'
      botUsers.value = []
    }
  } catch {
    botUsersError.value = 'Request failed'
    botUsersLoaded.value = true
  } finally {
    loadingBotUsers.value = false
  }
}

const fetchSavedUsers = () => emit('displayhive:admin:alerting:cts:get_telegram_users')
const fetchAlertSubscriptions = () => emit('displayhive:admin:alerting:cts:get_alert_subscriptions')

const addUser = async (user: BotUser) => {
  addingChatId.value = String(user.id)
  try {
    const ack = await emitWithAck<any>('displayhive:admin:alerting:cts:add_telegram_user', {
      name: user.title,
      chat_id: String(user.id),
    })
    if (ack?.ok) {
      toast.add({ severity: 'success', summary: 'Added', detail: `${user.title} added`, life: 2000 })
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Failed to add user', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    addingChatId.value = null
  }
}

const removeUser = async (user: SavedUser) => {
  removingId.value = user.id
  try {
    const ack = await emitWithAck<any>('displayhive:admin:alerting:cts:remove_telegram_user', { id: user.id })
    if (!ack?.ok) {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Failed to remove', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    removingId.value = null
  }
}

const sendTest = async (user: SavedUser) => {
  testingId.value = user.id
  try {
    const ack = await emitWithAck<any>('displayhive:admin:alerting:cts:send_telegram_test', { chat_id: user.chat_id })
    if (ack?.ok) {
      toast.add({ severity: 'success', summary: 'Sent', detail: `Test message sent to ${user.name}`, life: 2500 })
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Failed to send', life: 4000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    testingId.value = null
  }
}

const toggleSubscription = async (userId: number, alertKey: string) => {
  const key = `${userId}:${alertKey}`
  if (togglingKey.value === key) return
  togglingKey.value = key

  const enabled = !isSubscribed(userId, alertKey)
  // Optimistic update
  const next = new Set(subscriptionSet.value)
  if (enabled) next.add(key); else next.delete(key)
  subscriptionSet.value = next

  try {
    const ack = await emitWithAck<any>('displayhive:admin:alerting:cts:toggle_alert_subscription', {
      user_id: userId,
      alert_type: alertKey,
      enabled,
    })
    if (!ack?.ok) {
      // Revert on failure
      const reverted = new Set(subscriptionSet.value)
      if (enabled) reverted.delete(key); else reverted.add(key)
      subscriptionSet.value = reverted
      toast.add({ severity: 'error', summary: 'Error', detail: ack?.error || 'Failed to save', life: 4000 })
    }
  } catch {
    const reverted = new Set(subscriptionSet.value)
    if (enabled) reverted.delete(key); else reverted.add(key)
    subscriptionSet.value = reverted
    toast.add({ severity: 'error', summary: 'Error', detail: 'Request failed', life: 4000 })
  } finally {
    togglingKey.value = null
  }
}

onMounted(() => {
  on('displayhive:admin:alerting:stc:settings', handleSettings)
  on('displayhive:admin:alerting:stc:telegram_users', handleSavedUsers)
  on('displayhive:admin:alerting:stc:alert_types', handleAlertTypes)
  on('displayhive:admin:alerting:stc:alert_subscriptions', handleAlertSubscriptions)
  emit('displayhive:admin:alerting:cts:get_settings')
  emit('displayhive:admin:alerting:cts:get_alert_types')
})

onUnmounted(() => {
  off('displayhive:admin:alerting:stc:settings', handleSettings)
  off('displayhive:admin:alerting:stc:telegram_users', handleSavedUsers)
  off('displayhive:admin:alerting:stc:alert_types', handleAlertTypes)
  off('displayhive:admin:alerting:stc:alert_subscriptions', handleAlertSubscriptions)
})
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('alerting.page')" class="alerting-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Alerting page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="alerting-view">

    <div v-if="loading" class="loading-state">
      <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
      <p>Loading…</p>
    </div>

    <template v-else>

      <!-- Telegram bot token -->
      <Card>
        <template #title>
          <div class="card-header">
            <i class="pi pi-send" />
            <span>Telegram</span>
          </div>
        </template>
        <template #content>
          <div class="settings-form">
            <div class="field">
              <label for="telegram-token">Bot Token</label>
              <div class="token-row">
                <InputText
                  id="telegram-token"
                  v-model="tokenInput"
                  class="w-full"
                  :placeholder="hasToken ? '••••••• (token configured — enter new token to replace)' : '123456789:ABCdef...'"
                  type="password"
                  :disabled="!canShowToken"
                />
                <Button
                  v-if="canShowToken"
                  label="Save"
                  icon="pi pi-check"
                  :loading="savingToken"
                  :disabled="!tokenInput"
                  @click="saveToken"
                />
              </div>
            </div>

            <template v-if="hasToken">
              <!-- Saved alert users -->
              <div class="section-header">
                <span class="section-label">Alert Users</span>
              </div>

              <DataTable
                v-if="savedUsers.length"
                :value="savedUsers"
                size="small"
                stripedRows
                class="users-table"
              >
                <Column field="name" header="Name" />
                <Column field="chat_id" header="Chat ID" style="width: 130px" />
                <Column header="" style="width: 110px">
                  <template #body="{ data }">
                    <div class="action-buttons">
                      <Button
                        v-if="canManage"
                        icon="pi pi-envelope"
                        size="small"
                        outlined
                        severity="secondary"
                        v-tooltip="'Send test message'"
                        :loading="testingId === data.id"
                        @click="sendTest(data)"
                      />
                      <Button
                        v-if="canManage"
                        icon="pi pi-minus"
                        size="small"
                        outlined
                        severity="danger"
                        v-tooltip="'Remove'"
                        :loading="removingId === data.id"
                        @click="removeUser(data)"
                      />
                    </div>
                  </template>
                </Column>
              </DataTable>

              <div v-else class="empty-state">
                <i class="pi pi-users" style="font-size: 1.5rem" />
                <p>No alert users configured. Add users from the list below.</p>
              </div>

              <!-- Users detected from bot -->
              <div class="section-header">
                <span class="section-label">Users who messaged the bot</span>
                <Button
                  icon="pi pi-refresh"
                  size="small"
                  outlined
                  :loading="loadingBotUsers"
                  @click="fetchBotUsers"
                />
              </div>

              <div v-if="loadingBotUsers" class="inline-loading">
                <i class="pi pi-spin pi-spinner" />
                <span>Fetching users…</span>
              </div>

              <div v-else-if="botUsersError" class="inline-error">
                <i class="pi pi-exclamation-triangle" />
                {{ botUsersError }}
              </div>

              <template v-else-if="botUsersLoaded">
                <DataTable
                  v-if="botUsers.length"
                  :value="botUsers"
                  size="small"
                  stripedRows
                  class="users-table"
                >
                  <Column field="title" header="Name" />
                  <Column field="id" header="Chat ID" style="width: 130px" />
                  <Column header="" style="width: 60px">
                    <template #body="{ data }">
                      <Button
                        v-if="canManage"
                        icon="pi pi-plus"
                        size="small"
                        outlined
                        v-tooltip="'Add to alert users'"
                        :loading="addingChatId === String(data.id)"
                        @click="addUser(data)"
                      />
                    </template>
                  </Column>
                </DataTable>

                <div v-else class="empty-state">
                  <i class="pi pi-comments" style="font-size: 1.5rem" />
                  <p>No users found. Send a message to the bot first.</p>
                </div>
              </template>
            </template>
          </div>
        </template>
      </Card>

      <!-- Alert routing matrix -->
      <Card v-if="showMatrix">
        <template #title>
          <div class="card-header">
            <i class="pi pi-table" />
            <span>Alert Routing</span>
          </div>
        </template>
        <template #content>
          <p class="matrix-hint">Check which alerts each user should receive.</p>
          <div class="matrix-wrapper">
            <table class="matrix-table">
              <thead>
                <tr>
                  <th class="matrix-label-col">Alert</th>
                  <th
                    v-for="user in savedUsers"
                    :key="user.id"
                    class="matrix-user-col"
                  >
                    <span class="matrix-user-name" :title="user.name">{{ user.name }}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="at in alertTypes" :key="at.key">
                  <td class="matrix-alert-label">{{ at.label }}</td>
                  <td
                    v-for="user in savedUsers"
                    :key="user.id"
                    class="matrix-check-cell"
                  >
                    <Checkbox
                      :modelValue="isSubscribed(user.id, at.key)"
                      :binary="true"
                      :disabled="!canManage || togglingKey === `${user.id}:${at.key}`"
                      @change="toggleSubscription(user.id, at.key)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
      </Card>

      <!-- Matrix placeholder when no users yet -->
      <Card v-else-if="hasToken && savedUsers.length === 0">
        <template #title>
          <div class="card-header">
            <i class="pi pi-table" />
            <span>Alert Routing</span>
          </div>
        </template>
        <template #content>
          <div class="empty-state">
            <i class="pi pi-users" style="font-size: 1.5rem" />
            <p>Add alert users above to configure routing.</p>
          </div>
        </template>
      </Card>

      <!-- Matrix -->
      <Card>
        <template #title>
          <div class="card-header">
            <i class="pi pi-th-large" />
            <span>Matrix</span>
          </div>
        </template>
        <template #content>
          <div class="coming-soon">
            <i class="pi pi-clock" style="font-size: 2rem" />
            <p>Matrix integration coming soon.</p>
          </div>
        </template>
      </Card>

    </template>
  </div>
</template>

<style scoped>
.alerting-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  max-width: 900px;
}

.loading-state,
.inline-loading,
.coming-soon,
.empty-state {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  color: var(--p-text-muted-color, #9ca3af);
}

.loading-state {
  flex-direction: column;
  padding: 3rem;
  justify-content: center;
}

.coming-soon,
.empty-state {
  flex-direction: column;
  padding: 1.5rem 0;
  justify-content: center;
  text-align: center;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}

.field label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.token-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  text-align: left;
  gap: 0.5rem;
  width: 100%;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 0.25rem;
}

.section-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--p-text-muted-color, #6b7280);
}

.inline-error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--p-red-500, #ef4444);
  font-size: 0.875rem;
}

.users-table {
  font-size: 0.875rem;
}

.action-buttons {
  display: flex;
  gap: 0.35rem;
}

/* Alert routing matrix */
.matrix-hint {
  font-size: 0.85rem;
  color: var(--p-text-muted-color, #6b7280);
  margin-bottom: 1rem;
}

.matrix-wrapper {
  overflow-x: auto;
}

.matrix-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 0.875rem;
}

.matrix-table th,
.matrix-table td {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--p-content-border-color, #e5e7eb);
  text-align: center;
  vertical-align: middle;
}

.matrix-label-col {
  text-align: left;
  width: 220px;
  font-weight: 600;
  background: var(--p-surface-50, #f9fafb);
}

.matrix-user-col {
  min-width: 90px;
  background: var(--p-surface-50, #f9fafb);
  font-weight: 600;
}

.matrix-user-name {
  display: block;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.matrix-alert-label {
  text-align: left;
  white-space: nowrap;
}

.matrix-table tbody tr:nth-child(even) {
  background: var(--p-surface-50, #f9fafb);
}

.matrix-check-cell {
  width: 80px;
}
</style>
