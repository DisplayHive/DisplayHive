<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Card from 'primevue/card'
import Message from 'primevue/message'
import ProgressBar from 'primevue/progressbar'
import Select from 'primevue/select'
import SelectButton from 'primevue/selectbutton'
import Tag from 'primevue/tag'
import Tree from 'primevue/tree'
import type { TreeNode } from 'primevue/treenode'
import { useConfirmAction } from '../../composables/useConfirmAction'
import { useAuthStore } from '../../stores/auth'
import { useRightsStore } from '../../stores/rights'
import { buildTree, allCheckedKeys, selectionFromKeys, type Manifest, type SelectionKeys } from '../../utils/importExportTree'

// "Import Database" card of the Im-/Export page: choose a file, preview what it
// holds, pick items, mode and conflict handling, then import.
const toast = useToast()
const { confirmDanger } = useConfirmAction()
const authStore = useAuthStore()
const rightsStore = useRightsStore()
const canImport = computed(() => rightsStore.can('importexport.import'))

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
    confirmDanger({
      message:
        'This will permanently DELETE all existing data and media files, then replace them with the contents of the selected file. Media files are deleted immediately and cannot be recovered even if the import fails. This cannot be undone. Continue?',
      header: 'Confirm Import',
      rejectLabel: 'Cancel',
      acceptLabel: 'Import',
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
</script>

<template>
  <Card v-if="canImport" class="section-card">
    <template #title>
      <div class="card-header">
        <i class="pi pi-download card-header-icon" />
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
        data-tour="importexport-file-picker"
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
          data-tour="importexport-import-tree"
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

        <div class="mode-row" data-tour="importexport-mode-row">
          <label class="mode-label">Import mode</label>
          <SelectButton v-model="importMode" :options="modeOptions" optionLabel="label" optionValue="value" />
        </div>

        <div v-if="hasConflictsInSelection" class="conflict-row" data-tour="importexport-conflict-row">
          <label class="mode-label">Conflicting items already exist locally — default action</label>
          <SelectButton
            v-model="globalConflictResolution"
            :options="conflictOptions"
            optionLabel="label"
            optionValue="value"
          />
          <p class="description mt-2">
            Use the per-item dropdown above to override the default for specific items.
          </p>
        </div>

        <Message v-if="importMode === 'reset'" severity="warn" :closable="false" class="mt-4 mb-4">
          This permanently overwrites the entire database and media folder and cannot be undone.
        </Message>

        <div class="import-actions" data-tour="importexport-import-actions">
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

      <ProgressBar v-if="previewing" mode="indeterminate" class="mt-4 thin-progress" />

      <!-- Result message -->
      <div v-if="importResult" class="mt-4">
        <Message v-if="importResult.success" severity="success" :closable="false">
          Import successful!
          <ul v-if="importResult.counts" class="import-counts-list">
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
</template>

<style scoped src="./importexport.css"></style>
<style scoped>
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
  color: var(--p-text-muted-color, #6b7280);
}

.import-actions {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
}

.import-counts-list {
  margin: 0.5rem 0 0 1rem;
  padding: 0;
}
</style>
