<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import Tag from 'primevue/tag'
import ToggleSwitch from 'primevue/toggleswitch'
import { useAck } from '../composables/useAck'
import { useConfirmAction } from '../composables/useConfirmAction'
import { useSocket } from '../composables/useSocket'
import { useAuthStore } from '../stores/auth'
import { useRightsStore } from '../stores/rights'
import { uploadPlugin } from '../utils/media/uploadPlugin'
import type { CatalogEntry, PluginInfo, PluginsState } from '../components/plugins/types'

// Plugins add field handlers (what a field of a content type can hold) and integrations. They are switched
// on and off, installed and removed here while the server runs; the backend is application/plugins/ and
// application/admin/plugins/. The state comes from the server and is pushed whenever it changes.
const { on, off, whenConnected } = useSocket()
const { request } = useAck()
const { confirmDanger } = useConfirmAction()
const auth = useAuthStore()
const rights = useRightsStore()
const canManage = computed(() => rights.can('plugins.manage'))

const state = ref<PluginsState>({ plugins: [], retired: 0, host_version: '', catalog_url: '', can_restart: false })
const loaded = ref(false)
const handleState = (s: PluginsState) => { state.value = s; loaded.value = true }

onMounted(async () => {
  on('displayhive:admin:stc:plugins', handleState)
  await whenConnected()                  // the page can be opened on a fresh load, before the socket is up
  const ack = await request<PluginsState & { success: boolean }>('displayhive:admin:cts:get_plugins', undefined, { error: 'Could not load the plugins' })
  if (ack) handleState(ack)
  if (ack?.catalog_url) await loadCatalog()
})
onUnmounted(() => off('displayhive:admin:stc:plugins', handleState))

const integrations = computed(() => state.value.plugins.filter((p) => p.kind === 'integration'))
const handlers = computed(() => state.value.plugins.filter((p) => p.kind === 'fieldhandler'))

const busyId = ref('')
const setEnabled = async (plugin: PluginInfo, enabled: boolean) => {
  busyId.value = plugin.id
  await request('displayhive:admin:cts:set_plugin_enabled', { id: plugin.id, enabled },
    { success: `${plugin.name} ${enabled ? 'switched on' : 'switched off'}`, error: `Could not switch ${plugin.name}` })
  busyId.value = ''
}

const remove = (plugin: PluginInfo) => confirmDanger({
  message: `Remove the plugin "${plugin.name}"? Its files are deleted. What it stored in the database stays, and comes back if you install it again.`,
  accept: async () => { await request('displayhive:admin:cts:remove_plugin', { id: plugin.id }, { success: 'Plugin removed', error: 'Could not remove the plugin' }) },
})

// --- Restart -----------------------------------------------------------------------------------
const restarting = ref(false)
const restart = () => confirmDanger({
  message: 'Restart the server now? Screens and admin pages reconnect on their own within a few seconds.',
  accept: async () => {
    const ack = await request('displayhive:admin:cts:restart_server', undefined, { error: 'Could not restart the server' })
    if (ack) restarting.value = true
  },
})

// --- Installing --------------------------------------------------------------------------------
const catalog = ref<CatalogEntry[]>([])
const catalogError = ref('')
const loadCatalog = async () => {
  catalogError.value = ''
  const ack = await request<{ success: boolean; entries: CatalogEntry[] }>('displayhive:admin:cts:get_plugin_catalog', undefined, {
    onError: (m) => { catalogError.value = m },
  })
  if (ack) catalog.value = ack.entries
}
const installedVersion = (id: string) => state.value.plugins.find((p) => p.id === id)?.version
const installFromCatalog = async (entry: CatalogEntry) => {
  busyId.value = entry.id
  await request('displayhive:admin:cts:install_plugin_catalog', { id: entry.id }, { success: `${entry.name} installed`, error: `Could not install ${entry.name}` })
  busyId.value = ''
}

const url = ref('')
const sha256 = ref('')
const file = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const installing = ref(false)
const uploadPercent = ref(0)
const errorText = ref('')
const pickFile = (e: Event) => { file.value = (e.target as HTMLInputElement).files?.[0] ?? null }
const reset = () => {
  url.value = ''
  sha256.value = ''
  file.value = null
  if (fileInput.value) fileInput.value.value = ''
}

const installFromUrl = async () => {
  installing.value = true
  const ack = await request('displayhive:admin:cts:install_plugin_url', { url: url.value, sha256: sha256.value },
    { success: 'Plugin installed', error: 'Could not install the plugin' })
  installing.value = false
  if (ack) reset()
}
const installFromFile = async () => {
  if (!file.value) return
  installing.value = true
  uploadPercent.value = 0
  errorText.value = ''
  const result = await uploadPlugin(file.value, sha256.value.trim(), auth.authHeader(), (l, t) => { uploadPercent.value = Math.round((l / t) * 100) })
  installing.value = false
  if (result.success) reset()
  else errorText.value = result.error
}
</script>

<template>
  <div v-if="rights.loaded && !rights.can('plugins.page') && !canManage" class="plugins-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Plugins page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="plugins-view" data-tour="plugins-page">
    <Message v-if="restarting" severity="info" :closable="false">The server is restarting. This page reconnects by itself.</Message>
    <Message v-else-if="state.retired > 0" severity="warn" :closable="false" data-tour="plugins-restart" data-testid="plugins-restart">
      <div class="restart-row">
        <span>
          {{ state.retired }} switched-off or replaced plugin version{{ state.retired === 1 ? ' is' : 's are' }} still held in the server's memory
          (its code cannot be taken out of a running server). A restart frees it; nothing is wrong until then.
        </span>
        <Button v-if="canManage && state.can_restart" label="Restart server" icon="pi pi-refresh" size="small" severity="warn" @click="restart" />
      </div>
    </Message>

    <Card v-for="group in [{ title: 'Integrations', icon: 'pi-share-alt', items: integrations }, { title: 'Field handlers', icon: 'pi-sliders-h', items: handlers }]" :key="group.title" :data-tour="`plugins-${group.title === 'Integrations' ? 'integrations' : 'handlers'}`">
      <template #title>
        <div class="card-header-title">
          <i :class="['pi', group.icon, 'card-header-icon']" />
          <span>{{ group.title }}</span>
        </div>
      </template>
      <template #content>
        <p v-if="!loaded" class="hint">Loading…</p>
        <p v-else-if="!group.items.length" class="hint">None installed.</p>
        <ul v-else class="plugin-list">
          <li v-for="p in group.items" :key="p.id" class="plugin-row" :data-testid="`plugin-${p.id}`">
            <div class="plugin-main">
              <div class="plugin-title">
                <strong>{{ p.name }}</strong>
                <span class="plugin-version">{{ p.version }}</span>
                <Tag :value="p.source === 'bundled' ? 'Bundled' : 'Installed'" :severity="p.source === 'bundled' ? 'secondary' : 'info'" />
                <Tag v-if="p.enabled && !p.loaded" value="Failed to load" severity="danger" />
                <Tag v-if="!p.compatible" value="Not compatible" severity="warn" />
              </div>
              <p v-if="p.description" class="hint">{{ p.description }}</p>
              <p v-if="p.enabled && !p.loaded && p.error" class="plugin-error" :data-testid="`plugin-error-${p.id}`">{{ p.error }}</p>
              <small class="plugin-meta">
                {{ p.id }}
                <template v-if="p.fieldhandlers.length"> · field handler{{ p.fieldhandlers.length === 1 ? '' : 's' }}: {{ p.fieldhandlers.join(', ') }}</template>
                <template v-if="p.author"> · {{ p.author }}</template>
                <template v-if="p.license"> · {{ p.license }}</template>
              </small>
            </div>
            <div class="plugin-actions">
              <ToggleSwitch
                :model-value="p.enabled"
                :disabled="!canManage || busyId === p.id || (!p.enabled && !p.compatible)"
                :aria-label="`${p.name} on or off`"
                @update:model-value="(v: boolean) => setEnabled(p, v)"
              />
              <Button v-if="p.removable && canManage" :data-testid="`plugin-remove-${p.id}`" icon="pi pi-trash" severity="danger" text rounded size="small" :aria-label="`Remove ${p.name}`" @click="remove(p)" />
            </div>
          </li>
        </ul>
      </template>
    </Card>

    <Card v-if="canManage" data-tour="plugins-install">
      <template #title>
        <div class="card-header-title">
          <i class="pi pi-download card-header-icon" />
          <span>Install a plugin</span>
        </div>
      </template>
      <template #content>
        <Message severity="warn" :closable="false">
          A plugin is program code that runs with the rights of the server. Install only plugins from authors you trust.
          DisplayHive checks the file against the checksum you give (or the catalog's) — that proves the file is the one
          published, not that it is harmless.
        </Message>

        <div v-if="state.catalog_url" class="catalog">
          <h4>Catalog</h4>
          <Message v-if="catalogError" severity="error" :closable="false">{{ catalogError }}</Message>
          <p v-else-if="!catalog.length" class="hint">The catalog has no plugins.</p>
          <ul v-else class="plugin-list">
            <li v-for="e in catalog" :key="e.id" class="plugin-row">
              <div class="plugin-main">
                <div class="plugin-title"><strong>{{ e.name }}</strong><span class="plugin-version">{{ e.version }}</span></div>
                <p v-if="e.description" class="hint">{{ e.description }}</p>
                <small class="plugin-meta">{{ e.id }}<template v-if="e.author"> · {{ e.author }}</template></small>
              </div>
              <Button
                :label="installedVersion(e.id) === e.version ? 'Installed' : installedVersion(e.id) ? 'Update' : 'Install'"
                size="small"
                :disabled="busyId === e.id || installedVersion(e.id) === e.version"
                @click="installFromCatalog(e)"
              />
            </li>
          </ul>
        </div>

        <div class="own settings-form">
          <h4>From a file or a link</h4>
          <div class="field">
            <label for="plugin-file">ZIP file</label>
            <input id="plugin-file" ref="fileInput" data-testid="plugin-file" type="file" accept=".zip" @change="pickFile" />
          </div>
          <div class="field">
            <label for="plugin-url">…or a download link</label>
            <InputText id="plugin-url" v-model="url" placeholder="https://example.org/plugin-1.0.0.zip" class="w-full" :disabled="!!file" />
          </div>
          <div class="field">
            <label for="plugin-sha">SHA-256 checksum {{ url ? '(required for a link)' : '(optional for a file)' }}</label>
            <InputText id="plugin-sha" v-model="sha256" placeholder="64 hex characters" class="w-full" />
          </div>
          <Message v-if="errorText" severity="error" :closable="false" data-testid="plugin-error">{{ errorText }}</Message>
          <div class="actions">
            <Button v-if="file" data-testid="plugin-install-file" :label="installing ? `Uploading ${uploadPercent}%` : 'Install file'" icon="pi pi-upload" :disabled="installing" @click="installFromFile" />
            <Button v-else label="Install from link" icon="pi pi-link" :disabled="installing || !url.trim() || !sha256.trim()" @click="installFromUrl" />
          </div>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.plugins-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 900px;
}
.plugin-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
}
.plugin-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 0;
  border-bottom: 1px solid var(--p-content-border-color);
}
.plugin-row:last-child {
  border-bottom: none;
}
.plugin-main {
  min-width: 0;
}
.plugin-title {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.plugin-version,
.plugin-meta {
  color: var(--p-text-muted-color);
}
.plugin-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}
.plugin-error {
  margin: 0.25rem 0;
  color: var(--p-red-500, #dc2626);
  font-size: 0.85rem;
}
.restart-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}
.catalog,
.own {
  margin-top: 1rem;
}
.hint {
  margin: 0.25rem 0;
  color: var(--p-text-muted-color);
}
.empty-state {
  text-align: center;
  color: var(--p-text-muted-color);
}
</style>
