<script setup lang="ts">
import { computed } from 'vue'
import { useAlerting } from '../composables/useAlerting'
import { useRightsStore } from '../stores/rights'

import Card from 'primevue/card'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Checkbox from 'primevue/checkbox'

const {
  loading, hasToken, tokenInput, savingToken,
  loadingBotUsers, botUsersLoaded, botUsersError, botUsers,
  savedUsers, testingId, removingId, addingChatId,
  alertTypes, togglingKey, showMatrix,
  isSubscribed, saveToken, fetchBotUsers, addUser, removeUser, sendTest, toggleSubscription,
} = useAlerting()
const rightsStore = useRightsStore()
const canManage = computed(() => rightsStore.can('alerting.manage'))
const canShowToken = computed(() => rightsStore.can('alerting.showtoken'))
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('alerting.page')" class="alerting-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Alerting page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="alerting-page" class="alerting-view">

    <div v-if="loading" class="loading-state">
      <i class="pi pi-spin pi-spinner"></i>
      <p>Loading…</p>
    </div>

    <template v-else>

      <!-- Telegram bot token -->
      <Card>
        <template #title>
          <div class="card-header">
            <i class="pi pi-send card-header-icon" />
            <span>Telegram</span>
          </div>
        </template>
        <template #content>
          <div class="settings-form">
            <div class="field" data-tour="alerting-token-field">
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
                data-tour="alerting-saved-users"
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

              <div v-else class="empty-state empty-state--compact">
                <i class="pi pi-users" />
                <p>No alert users configured. Add users from the list below.</p>
              </div>

              <!-- Users detected from bot -->
              <div class="section-header" data-tour="alerting-bot-users">
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

                <div v-else class="empty-state empty-state--compact">
                  <i class="pi pi-comments" />
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
            <i class="pi pi-table card-header-icon" />
            <span>Alert Routing</span>
          </div>
        </template>
        <template #content>
          <p class="matrix-hint">Check which alerts each user should receive.</p>
          <div class="matrix-wrapper" data-tour="alerting-matrix">
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
            <i class="pi pi-table card-header-icon" />
            <span>Alert Routing</span>
          </div>
        </template>
        <template #content>
          <div class="empty-state empty-state--compact">
            <i class="pi pi-users" />
            <p>Add alert users above to configure routing.</p>
          </div>
        </template>
      </Card>

      <!-- Matrix -->
      <Card>
        <template #title>
          <div class="card-header">
            <i class="pi pi-th-large card-header-icon" />
            <span>Matrix</span>
          </div>
        </template>
        <template #content>
          <div class="coming-soon">
            <i class="pi pi-clock" />
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

.coming-soon i {
  font-size: 2rem;
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

/* Dark mode: --p-surface-50 is a fixed ramp point (always pale gray, in both
   themes), not a semantic token — see docs/developer/styleguide.md. Give the
   header columns and zebra-striping an explicit dark surface instead. */
.dark-mode .matrix-label-col,
.dark-mode .matrix-user-col,
.dark-mode .matrix-table tbody tr:nth-child(even) {
  background: var(--p-surface-800, #1e293b);
}
</style>
