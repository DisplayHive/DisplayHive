<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useAuthStore } from '../stores/auth'
import { useRightsStore } from '../stores/rights'

import Card from 'primevue/card'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import Message from 'primevue/message'
import Tree from 'primevue/tree'
import SelectButton from 'primevue/selectbutton'
import Select from 'primevue/select'
import Tag from 'primevue/tag'
import type { TreeNode } from 'primevue/treenode'

const toast = useToast()
const confirm = useConfirm()
const authStore = useAuthStore()
const rightsStore = useRightsStore()

const canExport = computed(() => rightsStore.can('importexport.export'))
const canImport = computed(() => rightsStore.can('importexport.import'))

// Entity types, in the same order/keys as application/admin/importexport/registry.py.
const ENTITY_TYPE_LABELS: Record<string, string> = {
  screens: 'Screens',
  screengroups: 'Screen Groups',
  gradients: 'Gradients',
  contentcontainers: 'Content Containers',
  designs: 'Designs',
  layouts: 'Layouts',
  contenttypes: 'Content Types',
  content_elements: 'Content Elements',
  media: 'Media',
  devices: 'Devices',
  magic_tag_value_lists: 'Magic Tag Value Lists',
  magic_tags: 'Magic Tags',
}
const ENTITY_TYPE_ORDER = Object.keys(ENTITY_TYPE_LABELS)

type ManifestItem = { uuid: string; id: number; label: string; conflict?: boolean }
type Manifest = Record<string, ManifestItem[]>
type SelectionKeys = Record<string, { checked: boolean; partialChecked: boolean }>

function buildTree(manifest: Manifest, itemKeyPrefix = ''): TreeNode[] {
  return ENTITY_TYPE_ORDER.filter((key) => (manifest[key] || []).length > 0).map((key) => ({
    key: `${itemKeyPrefix}type:${key}`,
    label: `${ENTITY_TYPE_LABELS[key]} (${(manifest[key] || []).length})`,
    selectable: true,
    children: (manifest[key] || []).map((item) => ({
      key: `${itemKeyPrefix}item:${key}:${item.uuid}`,
      label: item.label,
      selectable: true,
      data: { typeKey: key, uuid: item.uuid, conflict: !!item.conflict },
    })),
  }))
}

function allCheckedKeys(tree: TreeNode[]): SelectionKeys {
  const keys: SelectionKeys = {}
  for (const node of tree) {
    keys[node.key as string] = { checked: true, partialChecked: false }
    for (const child of node.children || []) {
      keys[child.key as string] = { checked: true, partialChecked: false }
    }
  }
  return keys
}

/** Collect {typeKey: [uuid, ...]} for every leaf item currently checked. */
function selectionFromKeys(tree: TreeNode[], keys: SelectionKeys): Record<string, string[]> {
  const out: Record<string, string[]> = {}
  for (const node of tree) {
    for (const child of node.children || []) {
      const typeKey = (child.data as { typeKey: string })?.typeKey
      if (!typeKey) continue
      if (!out[typeKey]) out[typeKey] = []
      if (keys[child.key as string]?.checked) {
        out[typeKey].push((child.data as { uuid: string }).uuid)
      }
    }
  }
  return out
}

// ---------------------------------------------------------------------------
// Export
// ---------------------------------------------------------------------------

const exportTree = ref<TreeNode[]>([])
const exportSelectionKeys = ref<SelectionKeys>({})
const exportTreeLoaded = ref(false)
const exportTreeLoading = ref(false)
const exporting = ref(false)

const loadExportTree = async () => {
  if (!canExport.value || exportTreeLoading.value) return
  exportTreeLoading.value = true
  try {
    const response = await fetch('/admin/export/tree', { headers: authStore.authHeader() })
    if (!response.ok) throw new Error(`Server error: ${response.status}`)
    const manifest: Manifest = await response.json()
    exportTree.value = buildTree(manifest)
    exportSelectionKeys.value = allCheckedKeys(exportTree.value)
    exportTreeLoaded.value = true
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Could not load export tree', detail: String(e), life: 5000 })
  } finally {
    exportTreeLoading.value = false
  }
}

const totalExportItems = computed(() => exportTree.value.reduce((sum, n) => sum + (n.children?.length || 0), 0))

const triggerExport = async () => {
  if (!canExport.value) return
  exporting.value = true
  try {
    const selection = selectionFromKeys(exportTree.value, exportSelectionKeys.value)
    const response = await fetch('/admin/export/download', {
      method: 'POST',
      headers: { ...authStore.authHeader(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ selection }),
    })
    if (!response.ok) throw new Error(`Server error: ${response.status}`)
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const cd = response.headers.get('Content-Disposition') || ''
    const match = cd.match(/filename="?([^"]+)"?/)
    a.download = match?.[1] ?? 'displayhive-export.zip'
    a.href = url
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    toast.add({ severity: 'success', summary: 'Export Complete', detail: 'Selected data exported as ZIP file.', life: 3000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Export Failed', detail: String(e), life: 5000 })
  } finally {
    exporting.value = false
  }
}

// ---------------------------------------------------------------------------
// Import
// ---------------------------------------------------------------------------

const fileInput = ref<HTMLInputElement | null>(null)
const previewing = ref(false)
const importing = ref(false)
const importResult = ref<{ success: boolean; error?: string; counts?: Record<string, number> } | null>(null)

const importToken = ref<string | null>(null)
const importIsLegacy = ref(false)
const importTree = ref<TreeNode[]>([])
const importSelectionKeys = ref<SelectionKeys>({})

const importMode = ref<'merge' | 'reset'>('merge')
const modeOptions = [
  { label: 'Merge into existing data', value: 'merge' },
  { label: 'Reset whole database', value: 'reset' },
]

const globalConflictResolution = ref<'skip' | 'overwrite'>('skip')
const conflictOptions = [
  { label: 'Skip existing', value: 'skip' },
  { label: 'Overwrite existing', value: 'overwrite' },
]
const perItemOverrides = ref<Record<string, 'skip' | 'overwrite'>>({})

const conflictByUuid = computed<Record<string, boolean>>(() => {
  const out: Record<string, boolean> = {}
  for (const node of importTree.value) {
    for (const child of node.children || []) {
      const data = child.data as { uuid: string; conflict: boolean }
      out[data.uuid] = data.conflict
    }
  }
  return out
})

const checkedConflictUuids = computed(() => {
  const selection = selectionFromKeys(importTree.value, importSelectionKeys.value)
  const uuids: string[] = []
  for (const key of Object.keys(selection)) {
    for (const uuid of selection[key] || []) {
      if (conflictByUuid.value[uuid]) uuids.push(uuid)
    }
  }
  return uuids
})

const hasConflictsInSelection = computed(() => importMode.value === 'merge' && checkedConflictUuids.value.length > 0)

const resetImportStagingState = () => {
  importToken.value = null
  importIsLegacy.value = false
  importTree.value = []
  importSelectionKeys.value = {}
  perItemOverrides.value = {}
  importResult.value = null
}

const onFilePicked = () => {
  if (!canImport.value) return
  fileInput.value?.click()
}

const onFileSelected = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file || !canImport.value) return

  resetImportStagingState()
  previewing.value = true

  try {
    const formData = new FormData()
    formData.append('file', file)
    const response = await fetch('/admin/import/preview', {
      method: 'POST',
      headers: authStore.authHeader(),
      body: formData,
    })
    const result = await response.json()
    if (!response.ok || result.error) {
      throw new Error(result.error || `Server error: ${response.status}`)
    }
    importToken.value = result.token
    importIsLegacy.value = !!result.is_legacy
    const manifest: Manifest = result.manifest || {}
    importTree.value = buildTree(manifest, 'import-')
    importSelectionKeys.value = allCheckedKeys(importTree.value)
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Could not read file', detail: String(e), life: 6000 })
    resetImportStagingState()
  } finally {
    previewing.value = false
  }
}

const totalImportItems = computed(() => importTree.value.reduce((sum, n) => sum + (n.children?.length || 0), 0))

const runImport = async () => {
  if (!canImport.value || !importToken.value) return
  importing.value = true
  importResult.value = null
  try {
    const selection = importIsLegacy.value ? null : selectionFromKeys(importTree.value, importSelectionKeys.value)
    const conflict_resolution =
      importMode.value === 'merge'
        ? { default: globalConflictResolution.value, overrides: perItemOverrides.value }
        : 'skip'

    const response = await fetch('/admin/import/confirm', {
      method: 'POST',
      headers: { ...authStore.authHeader(), 'Content-Type': 'application/json' },
      body: JSON.stringify({
        token: importToken.value,
        selection,
        mode: importMode.value,
        conflict_resolution,
      }),
    })
    const result = await response.json()
    if (result.success) {
      toast.add({ severity: 'success', summary: 'Import Complete', detail: 'Data imported successfully.', life: 4000 })
      resetImportStagingState()
      importResult.value = result
    } else {
      importResult.value = result
      toast.add({ severity: 'error', summary: 'Import Failed', detail: result.error || 'Unknown error', life: 6000 })
    }
  } catch (e) {
    importResult.value = { success: false, error: String(e) }
    toast.add({ severity: 'error', summary: 'Import Failed', detail: String(e), life: 6000 })
  } finally {
    importing.value = false
  }
}

const triggerImport = () => {
  if (!canImport.value || !importToken.value) return
  if (importMode.value === 'reset') {
    confirm.require({
      message:
        'This will permanently DELETE all existing data and media files, then replace them with the contents of the selected file. Media files are deleted immediately and cannot be recovered even if the import fails. This cannot be undone. Continue?',
      header: 'Confirm Import',
      icon: 'pi pi-exclamation-triangle',
      rejectLabel: 'Cancel',
      acceptLabel: 'Import',
      acceptClass: 'p-button-danger',
      accept: () => {
        runImport()
      },
    })
  } else {
    runImport()
  }
}

// Reset per-item overrides whenever the checked conflict set changes, so
// stale overrides for now-unchecked items don't linger.
watch(checkedConflictUuids, (uuids) => {
  const kept: Record<string, 'skip' | 'overwrite'> = {}
  for (const uuid of uuids) {
    if (perItemOverrides.value[uuid]) kept[uuid] = perItemOverrides.value[uuid]
  }
  perItemOverrides.value = kept
})

loadExportTree()
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('importexport.page')" class="importexport-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Im-/Export page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="importexport-view">
    <!-- Export -->
    <Card class="section-card">
      <template #title>
        <div class="card-header">
          <i class="pi pi-upload" style="margin-right: 0.5rem" />
          <span>Export Database</span>
        </div>
      </template>
      <template #content>
        <p class="description">
          Pick exactly what to export — by type, or individual items within a type. Dependencies
          (e.g. a Content Type's Layout) are pulled in automatically. The download is a ZIP
          archive containing <code>db.json</code> and a <code>media/</code> folder.
        </p>
        <template v-if="canExport">
          <ProgressBar v-if="exportTreeLoading" mode="indeterminate" style="height: 6px; margin-bottom: 1rem" />
          <Tree
            v-else-if="exportTreeLoaded"
            v-model:selectionKeys="exportSelectionKeys"
            :value="exportTree"
            selectionMode="checkbox"
            class="importexport-tree"
          />
          <p v-if="exportTreeLoaded && totalExportItems === 0" class="description">
            Nothing to export yet.
          </p>
          <Button
            label="Download Export"
            icon="pi pi-download"
            :loading="exporting"
            :disabled="exporting || !exportTreeLoaded"
            style="margin-top: 1rem"
            @click="triggerExport"
          />
        </template>
        <p v-else class="description">You don't have permission to export the database.</p>
      </template>
    </Card>

    <!-- Import -->
    <Card v-if="canImport" class="section-card">
      <template #title>
        <div class="card-header">
          <i class="pi pi-download" style="margin-right: 0.5rem" />
          <span>Import Database</span>
        </div>
      </template>
      <template #content>
        <p class="description">
          Select a previously exported ZIP or JSON file to see what it contains, then choose what
          to import and how. Legacy exports from older versions are also accepted.
        </p>

        <input
          ref="fileInput"
          type="file"
          accept=".zip,application/zip,.json,application/json"
          style="display: none"
          @change="onFileSelected"
        />

        <Button
          v-if="!importToken"
          label="Select ZIP or JSON File…"
          icon="pi pi-folder-open"
          outlined
          :loading="previewing"
          :disabled="previewing"
          @click="onFilePicked"
        />

        <div v-else class="import-staging">
          <Message v-if="importIsLegacy" severity="info" :closable="false">
            This is a legacy export from an older version — it has no per-item selection, so the
            entire file will be imported.
          </Message>
          <Tree
            v-else
            v-model:selectionKeys="importSelectionKeys"
            :value="importTree"
            selectionMode="checkbox"
            class="importexport-tree"
          >
            <template #default="{ node }">
              <span class="tree-item-label">
                {{ node.label }}
                <Tag v-if="node.data?.conflict" severity="warn" value="exists" class="conflict-tag" />
                <Select
                  v-if="node.data?.conflict && importMode === 'merge'"
                  v-model="perItemOverrides[node.data.uuid]"
                  :options="conflictOptions"
                  optionLabel="label"
                  optionValue="value"
                  :placeholder="`Default: ${globalConflictResolution === 'overwrite' ? 'Overwrite' : 'Skip'}`"
                  size="small"
                  class="conflict-override"
                  @click.stop
                />
              </span>
            </template>
          </Tree>
          <p v-if="!importIsLegacy && totalImportItems === 0" class="description">
            This file has nothing to import.
          </p>

          <div class="mode-row">
            <label class="mode-label">Import mode</label>
            <SelectButton v-model="importMode" :options="modeOptions" optionLabel="label" optionValue="value" />
          </div>

          <div v-if="hasConflictsInSelection" class="conflict-row">
            <label class="mode-label">Conflicting items already exist locally — default action</label>
            <SelectButton
              v-model="globalConflictResolution"
              :options="conflictOptions"
              optionLabel="label"
              optionValue="value"
            />
            <p class="description" style="margin-top: 0.5rem">
              Use the per-item dropdown above to override the default for specific items.
            </p>
          </div>

          <Message v-if="importMode === 'reset'" severity="warn" :closable="false" style="margin: 1rem 0">
            This permanently overwrites the entire database and media folder and cannot be undone.
          </Message>

          <div class="import-actions">
            <Button
              label="Import"
              icon="pi pi-check"
              :severity="importMode === 'reset' ? 'danger' : undefined"
              :outlined="importMode === 'reset'"
              :loading="importing"
              :disabled="importing"
              @click="triggerImport"
            />
            <Button
              label="Cancel"
              severity="secondary"
              text
              :disabled="importing"
              @click="resetImportStagingState"
            />
          </div>
        </div>

        <ProgressBar v-if="previewing" mode="indeterminate" style="margin-top: 1rem; height: 6px" />

        <!-- Result message -->
        <div v-if="importResult" style="margin-top: 1rem">
          <Message v-if="importResult.success" severity="success" :closable="false">
            Import successful!
            <ul v-if="importResult.counts" style="margin: 0.5rem 0 0 1rem; padding: 0">
              <li v-for="(count, key) in importResult.counts" :key="key">
                {{ key }}: {{ count }}
              </li>
            </ul>
          </Message>
          <Message v-else severity="error" :closable="false">
            Import failed: {{ importResult.error }}
          </Message>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.importexport-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 700px;
}

.section-card {
  width: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  text-align: left;
  width: 100%;
}

.description {
  margin-bottom: 1rem;
  color: var(--text-color-secondary);
}

.importexport-tree {
  max-height: 360px;
  overflow-y: auto;
  border: 1px solid var(--surface-border, #ddd);
  border-radius: 6px;
}

.tree-item-label {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.conflict-tag {
  font-size: 0.7rem;
}

.conflict-override {
  width: 10rem;
}

.mode-row,
.conflict-row {
  margin-top: 1rem;
}

.mode-label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.import-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
}
</style>
