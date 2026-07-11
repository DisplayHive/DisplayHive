<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useAuthStore } from '../stores/auth'

import Card from 'primevue/card'
import Button from 'primevue/button'
import ProgressBar from 'primevue/progressbar'
import Message from 'primevue/message'

interface DemoPackage {
  id: number
  filename: string
  name: string
  description: string
}

const toast = useToast()
const confirm = useConfirm()
const authStore = useAuthStore()

const packages = ref<DemoPackage[]>([])
const loading = ref(false)
const loadError = ref<string | null>(null)
const importingFilename = ref<string | null>(null)

const loadPackages = async () => {
  loading.value = true
  loadError.value = null
  try {
    const response = await fetch('/admin/demo/list', { headers: authStore.authHeader() })
    if (!response.ok) throw new Error(`Server error: ${response.status}`)
    packages.value = await response.json()
  } catch (e) {
    loadError.value = String(e)
  } finally {
    loading.value = false
  }
}

onMounted(loadPackages)

const runImport = async (pkg: DemoPackage) => {
  importingFilename.value = pkg.filename
  try {
    const response = await fetch('/admin/demo/import', {
      method: 'POST',
      headers: { ...authStore.authHeader(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: pkg.filename }),
    })
    const result = await response.json()
    if (result.success) {
      toast.add({
        severity: 'success',
        summary: 'Demo Imported',
        detail: `"${pkg.name}" demo content imported successfully.`,
        life: 4000,
      })
    } else {
      toast.add({ severity: 'error', summary: 'Import Failed', detail: result.error || 'Unknown error', life: 6000 })
    }
  } catch (e) {
    toast.add({ severity: 'error', summary: 'Import Failed', detail: String(e), life: 6000 })
  } finally {
    importingFilename.value = null
  }
}

const confirmImport = (pkg: DemoPackage) => {
  confirm.require({
    message:
      'WARNING, this will overwrite ALL the content in your Database except of the Useraccounts. Continue?',
    header: 'Confirm Demo Import',
    icon: 'pi pi-exclamation-triangle',
    rejectLabel: 'Cancel',
    acceptLabel: 'Import',
    acceptClass: 'p-button-danger',
    accept: () => runImport(pkg),
  })
}
</script>

<template>
  <div class="demo-mode-view">
    <Message severity="warn" :closable="false" class="intro-message">
      Importing a demo package overwrites all existing content, screens, templates and media —
      everything except your user accounts.
    </Message>

    <ProgressBar v-if="loading" mode="indeterminate" style="height: 6px" />
    <Message v-if="loadError" severity="error" :closable="false">
      Failed to load demo content: {{ loadError }}
    </Message>

    <div class="demo-list">
      <Card v-for="pkg in packages" :key="pkg.id" class="demo-card">
        <template #title>
          <div class="card-header">
            <i class="pi pi-box" style="margin-right: 0.5rem" />
            <span>{{ pkg.name }}</span>
          </div>
        </template>
        <template #content>
          <p class="description">{{ pkg.description }}</p>
          <Button
            label="Import Demo"
            icon="pi pi-cloud-download"
            severity="danger"
            outlined
            :loading="importingFilename === pkg.filename"
            :disabled="importingFilename !== null"
            @click="confirmImport(pkg)"
          />
        </template>
      </Card>
    </div>
  </div>
</template>

<style scoped>
.demo-mode-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 900px;
}

.intro-message {
  margin: 0;
}

.demo-list {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.demo-card {
  width: 100%;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  text-align: left;
}

.description {
  margin-bottom: 1rem;
  color: var(--text-color-secondary);
}
</style>
