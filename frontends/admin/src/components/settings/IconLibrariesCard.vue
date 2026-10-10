<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import Button from 'primevue/button'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Message from 'primevue/message'
import ProgressSpinner from 'primevue/progressspinner'
import Tag from 'primevue/tag'
import { useAck } from '../../composables/useAck'
import { useConfirmAction } from '../../composables/useConfirmAction'
import { useSocket } from '../../composables/useSocket'
import { useAuthStore } from '../../stores/auth'
import { useRightsStore } from '../../stores/rights'
import { uploadIconLibrary } from '../../utils/uploadIconLibrary'

// DisplayHive ships no icons: libraries are installed here, from the list of known ones (downloaded
// from the npm registry, checked against a pinned checksum) or from a ZIP file / download link of your
// own. Backend: application/icon_libraries.py, application/admin/icons/. The state comes from the server
// (and is pushed when a download finishes).
const { on, off, emit } = useSocket()
const { request } = useAck()
const { confirmDanger } = useConfirmAction()
const auth = useAuthStore()
const rights = useRightsStore()
const canManage = computed(() => rights.can('icons.manage'))

interface CatalogEntry { id: string; label: string; license: string; homepage: string; version: string; installed: boolean; count: number; installed_version: string }
interface OwnLibrary { id: string; label?: string; license?: string; count?: number; source?: string }
interface Job { running: boolean; current: string | null; queue: string[]; errors: Record<string, string> }
interface State { catalog: CatalogEntry[]; custom: OwnLibrary[]; job: Job }

const state = ref<State>({ catalog: [], custom: [], job: { running: false, current: null, queue: [], errors: {} } })
const loaded = ref(false)

const handleState = (s: State) => { state.value = s; loaded.value = true }

onMounted(async () => {
  on('displayhive:admin:stc:icon_libraries', handleState)
  const ack = await request<State & { success: boolean }>('displayhive:admin:cts:get_icon_libraries', undefined, { error: 'Could not load the icon libraries' })
  if (ack) handleState(ack)
})
onUnmounted(() => off('displayhive:admin:stc:icon_libraries', handleState))

const busy = computed(() => state.value.job.running)
const statusOf = (id: string) => {
  const job = state.value.job
  if (job.current === id) return 'installing'
  if (job.queue.includes(id)) return 'queued'
  return 'idle'
}
const notInstalled = computed(() => state.value.catalog.filter((c) => !c.installed).length)

const install = (entry: CatalogEntry) => request('displayhive:admin:cts:install_icon_library', { id: entry.id }, { error: `Could not start installing ${entry.label}` })
const installAll = () => request('displayhive:admin:cts:install_all_icon_libraries', undefined, { error: 'Could not start the installation' })
const remove = (id: string, label: string) => confirmDanger({
  message: `Remove the icon library "${label}"? Content that uses its icons shows no icon until it is installed again.`,
  accept: async () => { await request('displayhive:admin:cts:remove_icon_library', { id }, { success: 'Library removed', error: 'Could not remove the library' }) },
})

// --- a library of your own ---------------------------------------------------------------------
const custom = ref({ id: '', label: '', license: '', url: '' })
const file = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const uploadPercent = ref(0)
const idValid = computed(() => /^[a-z0-9][a-z0-9-]{0,39}$/.test(custom.value.id))
const formValid = computed(() => idValid.value && custom.value.label.trim() !== '')
const idHint = computed(() => (custom.value.id && !idValid.value ? 'Lowercase letters, digits and dashes only (up to 40).' : ''))

const pickFile = (e: Event) => { file.value = (e.target as HTMLInputElement).files?.[0] ?? null }
const resetCustom = () => {
  custom.value = { id: '', label: '', license: '', url: '' }
  file.value = null
  if (fileInput.value) fileInput.value.value = ''
}

const installFromUrl = async () => {
  const ack = await request('displayhive:admin:cts:install_icon_library_url', { ...custom.value }, { error: 'Could not start the installation' })
  if (ack) resetCustom()
}
const installFromFile = async () => {
  if (!file.value) return
  uploading.value = true
  uploadPercent.value = 0
  try {
    const result = await uploadIconLibrary(
      file.value,
      { id: custom.value.id, label: custom.value.label, license: custom.value.license },
      auth.authHeader(),
      (loaded, total) => { uploadPercent.value = Math.round((loaded / total) * 100) },
    )
    if (result.success) {
      resetCustom()
      const ack = await request<State & { success: boolean }>('displayhive:admin:cts:get_icon_libraries')
      if (ack) handleState(ack)
    } else {
      emit('displayhive:admin:cts:get_icon_libraries') // keep the list current
      throw new Error(result.error)
    }
  } catch (e) {
    errorText.value = (e as Error).message
  } finally {
    uploading.value = false
  }
}
const errorText = ref('')
</script>

<template>
  <Card data-tour="settings-icon-libraries">
    <template #title>
      <div class="card-header-title">
        <i class="pi pi-image card-header-icon" />
        <span>Icon libraries</span>
      </div>
    </template>
    <template #content>
      <div class="settings-form">
        <p class="hint">
          The icon field of content types offers the icons of the libraries installed here. Install the libraries you
          want; nothing is installed by default. A downloaded library is checked against the checksum DisplayHive
          expects. Content that uses an icon of a library that is not installed shows no icon.
        </p>

        <div v-if="!loaded" class="hint"><ProgressSpinner style="width: 1.5rem; height: 1.5rem" /> Loading…</div>

        <template v-else>
          <div v-if="canManage" class="icon-lib-actions">
            <Button
              label="Install all known libraries"
              icon="pi pi-download"
              size="small"
              :disabled="busy || notInstalled === 0"
              data-testid="icon-lib-install-all"
              @click="installAll"
            />
          </div>

          <table class="icon-lib-table" data-testid="icon-lib-table">
            <thead>
              <tr><th>Library</th><th>License</th><th>Version</th><th>Icons</th><th /></tr>
            </thead>
            <tbody>
              <tr v-for="c in state.catalog" :key="c.id" :data-testid="`icon-lib-${c.id}`">
                <td><a :href="c.homepage" target="_blank" rel="noopener">{{ c.label }}</a></td>
                <td>{{ c.license }}</td>
                <td>{{ c.installed ? (c.installed_version || '—') : c.version }}</td>
                <td>
                  <Tag v-if="c.installed" :value="`${c.count} installed`" severity="success" />
                  <Tag v-else value="not installed" severity="secondary" />
                </td>
                <td class="icon-lib-row-actions">
                  <span v-if="statusOf(c.id) === 'installing'" class="hint"><ProgressSpinner style="width: 1.2rem; height: 1.2rem" /> installing…</span>
                  <span v-else-if="statusOf(c.id) === 'queued'" class="hint">waiting…</span>
                  <template v-else-if="canManage">
                    <Button
                      :label="c.installed ? 'Reinstall' : 'Install'"
                      :icon="c.installed ? 'pi pi-refresh' : 'pi pi-download'"
                      size="small"
                      :outlined="c.installed"
                      :disabled="busy"
                      :data-testid="`icon-lib-install-${c.id}`"
                      @click="install(c)"
                    />
                    <Button v-if="c.installed" icon="pi pi-trash" size="small" severity="danger" outlined :disabled="busy" title="Remove" @click="remove(c.id, c.label)" />
                  </template>
                  <small v-if="state.job.errors[c.id]" class="icon-lib-error">{{ state.job.errors[c.id] }}</small>
                </td>
              </tr>
              <tr v-for="l in state.custom" :key="l.id" :data-testid="`icon-lib-${l.id}`">
                <td>{{ l.label || l.id }} <small class="hint">({{ l.id }})</small></td>
                <td>{{ l.license || '—' }}</td>
                <td>—</td>
                <td><Tag :value="`${l.count ?? 0} installed`" severity="success" /></td>
                <td class="icon-lib-row-actions">
                  <span v-if="statusOf(l.id) === 'installing'" class="hint"><ProgressSpinner style="width: 1.2rem; height: 1.2rem" /> installing…</span>
                  <Button v-else-if="canManage" icon="pi pi-trash" size="small" severity="danger" outlined :disabled="busy" title="Remove" @click="remove(l.id, l.label || l.id)" />
                </td>
              </tr>
              <tr v-for="(message, id) in state.job.errors" v-show="!state.catalog.some((c) => c.id === id)" :key="`err-${id}`">
                <td colspan="5" class="icon-lib-error">{{ id }}: {{ message }}</td>
              </tr>
            </tbody>
          </table>

          <div v-if="canManage" class="icon-lib-own" data-testid="icon-lib-own">
            <h4>Your own library</h4>
            <p class="hint">
              A ZIP (or .tar.gz) file with SVG icons, uploaded or downloaded from a link. Only plain drawings are kept:
              scripts, event handlers and external references are removed. Make sure the license allows you to use the icons.
              Downloads from private networks need to be allowed under Security.
            </p>
            <div class="icon-lib-form">
              <div class="field">
                <label for="icon-lib-id">Id</label>
                <InputText id="icon-lib-id" v-model="custom.id" placeholder="my-icons" :invalid="!!idHint" />
                <small v-if="idHint" class="icon-lib-error">{{ idHint }}</small>
                <small v-else class="hint">Stored in the icon value: <code>{{ custom.id || 'my-icons' }}/home</code></small>
              </div>
              <div class="field">
                <label for="icon-lib-label">Name</label>
                <InputText id="icon-lib-label" v-model="custom.label" placeholder="My icons" />
              </div>
              <div class="field">
                <label for="icon-lib-license">License</label>
                <InputText id="icon-lib-license" v-model="custom.license" placeholder="MIT" />
              </div>
            </div>
            <div class="icon-lib-form">
              <div class="field icon-lib-source">
                <label for="icon-lib-file">ZIP / TAR file</label>
                <input id="icon-lib-file" ref="fileInput" type="file" accept=".zip,.tar,.tgz,.gz,application/zip,application/gzip" data-testid="icon-lib-file" @change="pickFile" />
              </div>
              <Button label="Upload and install" icon="pi pi-upload" size="small" :disabled="!formValid || !file || uploading || busy" :loading="uploading" data-testid="icon-lib-upload" @click="installFromFile" />
            </div>
            <div v-if="uploading" class="hint">Uploading… {{ uploadPercent }} %</div>
            <div class="icon-lib-form">
              <div class="field icon-lib-source">
                <label for="icon-lib-url">or a download link</label>
                <InputText id="icon-lib-url" v-model="custom.url" placeholder="https://example.org/icons.zip" data-testid="icon-lib-url" />
              </div>
              <Button label="Download and install" icon="pi pi-download" size="small" :disabled="!formValid || !custom.url.trim() || busy" data-testid="icon-lib-download" @click="installFromUrl" />
            </div>
            <Message v-if="errorText" severity="error" :closable="true" @close="errorText = ''">{{ errorText }}</Message>
          </div>
        </template>
      </div>
    </template>
  </Card>
</template>

<style scoped>
.icon-lib-actions {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.icon-lib-table {
  width: 100%;
  border-collapse: collapse;
}

.icon-lib-table th,
.icon-lib-table td {
  text-align: left;
  padding: 0.4rem 0.5rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.icon-lib-row-actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.icon-lib-error {
  color: var(--p-red-500, #ef4444);
}

.icon-lib-own h4 {
  margin: 1rem 0 0.25rem;
}

.icon-lib-form {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 0.75rem;
  margin-top: 0.5rem;
}

.icon-lib-source {
  flex: 1;
  min-width: 14rem;
}

.hint {
  color: var(--p-text-muted-color);
  font-size: 0.85rem;
}
</style>
