<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useAck } from '../composables/useAck'
import { useRightsStore } from '../stores/rights'

import Card from 'primevue/card'
import ToggleSwitch from 'primevue/toggleswitch'
import Message from 'primevue/message'

// Whether the server may fetch addresses inside private networks (Pretalx sources,
// SSO providers). Backend: application/net.py and
// application/admin/settings/sockethandlers.py (get/set_outbound_policy). Everybody
// who can open Settings sees the state; only a Superadmin can change it.

const { emitWithAck } = useSocket()
const { request } = useAck()
const rightsStore = useRightsStore()

type Policy = { success: boolean; error?: string; allow_private?: boolean; forced_by_env?: boolean }

const allowPrivate = ref(false)
const forcedByEnv = ref(false)
const loading = ref(true)
const saving = ref(false)

const canChange = computed(() => rightsStore.isSuperadmin && !forcedByEnv.value)

const apply = (policy: Policy) => {
  allowPrivate.value = !!policy.allow_private
  forcedByEnv.value = !!policy.forced_by_env
}

onMounted(async () => {
  const policy = await emitWithAck<Policy>('displayhive:admin:cts:get_outbound_policy')
  if (policy?.success) apply(policy)
  loading.value = false
})

const change = async (value: boolean) => {
  if (!canChange.value) return
  saving.value = true
  try {
    const policy = await request<Policy>('displayhive:admin:cts:set_outbound_policy', { allow_private: value }, {
      success: (p) => (p.allow_private ? 'Private networks are now allowed' : 'Private networks are blocked'),
      error: 'Could not save the setting',
    })
    if (policy) apply(policy)
    else allowPrivate.value = !value
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Card data-tour="settings-security">
    <template #title>
      <div class="card-header-title">
        <i class="pi pi-shield card-header-icon" />
        <span>Security</span>
      </div>
    </template>
    <template #content>
      <div class="settings-form">
        <div class="field toggle-field">
          <label for="allow-private-networks">Allow requests to private networks</label>
          <ToggleSwitch
            id="allow-private-networks"
            :model-value="allowPrivate"
            :disabled="loading || saving || !canChange"
            @update:model-value="change"
          />
        </div>
        <p class="op-help">
          Pretalx sources and SSO providers are fetched by the server. Their addresses may not point into your own
          network (10.x.x.x, 192.168.x.x, <code>localhost</code> …) unless this is switched on — otherwise anybody who
          can add a source could make the server reach internal services. Switch it on only if, say, your Pretalx
          really runs inside the network. The cloud metadata address stays blocked in any case.
        </p>
        <Message v-if="forcedByEnv" severity="info" :closable="false">
          Switched on by the server's <code>OUTBOUND_ALLOW_PRIVATE</code> setting; it can't be changed here.
        </Message>
        <Message v-else-if="!rightsStore.isSuperadmin" severity="secondary" :closable="false">
          Only a Superadmin can change this.
        </Message>
      </div>
    </template>
  </Card>
</template>

<style scoped>
.op-help {
  margin: 0;
  font-size: 0.85rem;
  color: var(--p-text-muted-color, #6b7280);
}
</style>
