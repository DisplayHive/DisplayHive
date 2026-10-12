<script setup lang="ts">
import { ref, computed } from 'vue'
import { useToast } from 'primevue/usetoast'
import Button from 'primevue/button'
import Card from 'primevue/card'
import ProgressBar from 'primevue/progressbar'
import Tree from 'primevue/tree'
import type { TreeNode } from 'primevue/treenode'
import { useAuthStore } from '../../stores/auth'
import { useRightsStore } from '../../stores/rights'
import { onRightsReady } from '../../composables/useRightsReady'
import { buildTree, allCheckedKeys, selectionFromKeys, type Manifest, type SelectionKeys } from '../../utils/importExportTree'

// "Export Database" card of the Im-/Export page: pick items in a checkbox tree
// and download them as a ZIP.
const toast = useToast()
const authStore = useAuthStore()
const rightsStore = useRightsStore()
const canExport = computed(() => rightsStore.can('importexport.export'))

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

// loadExportTree() gates on canExport (rightsStore.can()), which stays false
// until rightsStore.loaded resolves — calling it unconditionally here at
// setup time loses that race on a fresh page load. See useRightsReady.
onRightsReady(loadExportTree)
</script>

<template>
  <Card class="section-card">
    <template #title>
      <div class="card-header">
        <i class="pi pi-upload card-header-icon" />
        <span>Export Database</span>
      </div>
    </template>
    <template #content>
      <p class="description">
        Pick exactly what to export — by type, or individual items within a type. Dependencies
        (e.g. a Content Type's Layout) are pulled in automatically. The download is a ZIP
        archive containing <code>db.json</code> and a <code>media/</code> folder. General app
        settings (e.g. timezone, welcome text, branding toggles) are always included and aren't
        shown in the tree below.
      </p>
      <template v-if="canExport">
        <ProgressBar v-if="exportTreeLoading" mode="indeterminate" class="thin-progress mb-4" />
        <Tree
          v-else-if="exportTreeLoaded"
          v-model:selectionKeys="exportSelectionKeys"
          :value="exportTree"
          selectionMode="checkbox"
          class="importexport-tree"
          data-tour="importexport-export-tree"
        />
        <p v-if="exportTreeLoaded && totalExportItems === 0" class="description">
          Nothing to export yet.
        </p>
        <Button
          label="Download Export"
          icon="pi pi-download"
          data-tour="importexport-download-button"
          :loading="exporting"
          :disabled="exporting || !exportTreeLoaded"
          class="mt-4"
          @click="triggerExport"
        />
      </template>
      <p v-else class="description">You don't have permission to export the database.</p>
    </template>
  </Card>
</template>

<style scoped src="./importexport.css"></style>
