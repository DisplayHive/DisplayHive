<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useRightsStore } from '../stores/rights'
import type { Layout, ContentContainer } from '../types/models'

import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import InputNumber from 'primevue/inputnumber'
import Dialog from 'primevue/dialog'
import Card from 'primevue/card'
import MultiSelect from 'primevue/multiselect'

const toast = useToast()
const confirm = useConfirm()
const { on, off, emit } = useSocket()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('layouts.create'))
const canEdit = computed(() => rightsStore.can('layouts.edit'))
const canDelete = computed(() => rightsStore.can('layouts.delete'))

const containers = ref<ContentContainer[]>([])
const layouts = ref<Layout[]>([])
const loading = ref(true)

const containerOptions = computed(() =>
  containers.value.map((c) => ({ label: c.title || c.name, value: c.id }))
)

const containerName = (id: number) => containers.value.find((c) => c.id === id)?.name || `#${id}`

// --- Containers ---------------------------------------------------------

const showContainerDialog = ref(false)
const isNewContainer = ref(false)
const containerForm = ref({
  id: null as number | null,
  name: '',
  title: '',
  order: 0,
  top: 0,
  left: 0,
  width: 100,
  height: 100,
})

const openNewContainerDialog = () => {
  isNewContainer.value = true
  containerForm.value = { id: null, name: '', title: '', order: 0, top: 0, left: 0, width: 100, height: 100 }
  showContainerDialog.value = true
}

const openEditContainerDialog = (c: ContentContainer) => {
  isNewContainer.value = false
  containerForm.value = {
    id: c.id, name: c.name, title: c.title || '', order: c.order || 0,
    top: c.top, left: c.left, width: c.width, height: c.height,
  }
  showContainerDialog.value = true
}

const saveContainer = () => {
  const event = isNewContainer.value
    ? 'displayhive:admin:cts:create_container'
    : 'displayhive:admin:cts:update_container'
  emit(event, { ...containerForm.value })
  toast.add({ severity: 'success', summary: 'Success', detail: isNewContainer.value ? 'Container created' : 'Container updated', life: 3000 })
  showContainerDialog.value = false
}

const deleteContainer = (c: ContentContainer) => {
  confirm.require({
    message: `Are you sure you want to delete container "${c.title || c.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      emit('displayhive:admin:cts:delete_container', { id: c.id })
      toast.add({ severity: 'success', summary: 'Success', detail: 'Container deleted', life: 3000 })
    },
  })
}

// --- Layouts -------------------------------------------------------------

const showLayoutDialog = ref(false)
const isNewLayout = ref(false)
const layoutForm = ref({
  id: null as number | null,
  name: '',
  description: '',
  container_ids: [] as number[],
})

const openNewLayoutDialog = () => {
  isNewLayout.value = true
  layoutForm.value = { id: null, name: '', description: '', container_ids: [] }
  showLayoutDialog.value = true
}

const openEditLayoutDialog = (l: Layout) => {
  isNewLayout.value = false
  layoutForm.value = { id: l.id, name: l.name, description: l.description || '', container_ids: l.container_ids || [] }
  showLayoutDialog.value = true
}

const saveLayout = () => {
  const event = isNewLayout.value
    ? 'displayhive:admin:cts:create_layout'
    : 'displayhive:admin:cts:update_layout'
  emit(event, { ...layoutForm.value })
  toast.add({ severity: 'success', summary: 'Success', detail: isNewLayout.value ? 'Layout created' : 'Layout updated', life: 3000 })
  showLayoutDialog.value = false
}

const deleteLayout = (l: Layout) => {
  confirm.require({
    message: `Are you sure you want to delete layout "${l.name}"? Contenttypes using it will need to be reassigned.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      emit('displayhive:admin:cts:delete_layout', { id: l.id })
      toast.add({ severity: 'success', summary: 'Success', detail: 'Layout deleted', life: 3000 })
    },
  })
}

// --- Data loading ---------------------------------------------------------

const handleContainersList = (data: any) => {
  containers.value = data?.data || []
}

const handleLayoutsList = (data: any) => {
  layouts.value = data?.data || []
  loading.value = false
}

onMounted(() => {
  on('displayhive:admin:stc:upd_containers', handleContainersList)
  on('displayhive:admin:stc:upd_layouts', handleLayoutsList)
  refreshData()
})

onUnmounted(() => {
  off('displayhive:admin:stc:upd_containers', handleContainersList)
  off('displayhive:admin:stc:upd_layouts', handleLayoutsList)
})

const refreshData = () => {
  loading.value = true
  emit('displayhive:admin:cts:get_containers')
  emit('displayhive:admin:cts:get_layouts')
}
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('layouts.page')" class="layouts-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Layouts page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="layouts-view">
    <Card>
      <template #title>
        <div class="card-header">
          <span>Content Containers</span>
          <div class="header-actions">
            <Button v-if="canCreate" icon="pi pi-plus" label="New Container" @click="openNewContainerDialog" size="small" />
            <Button icon="pi pi-refresh" @click="refreshData" size="small" outlined />
          </div>
        </div>
      </template>
      <template #content>
        <p class="hint">A container is a screen-relative position (vh/vw) and size, rendered as an overlay on top of the active Design.</p>
        <DataTable :value="containers" :loading="loading" sortField="order" :sortOrder="1" stripedRows size="small" responsiveLayout="scroll">
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="title" header="Title" sortable>
            <template #body="{ data }">{{ data.title || data.name }}</template>
          </Column>
          <Column field="name" header="Name" sortable />
          <Column header="Position (top / left)" style="width: 160px">
            <template #body="{ data }">{{ data.top }}vh / {{ data.left }}vw</template>
          </Column>
          <Column header="Size (w / h)" style="width: 140px">
            <template #body="{ data }">{{ data.width }}vw / {{ data.height }}vh</template>
          </Column>
          <Column header="Actions" style="width: 120px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button v-if="canEdit" icon="pi pi-pencil" @click="openEditContainerDialog(data)" size="small" outlined title="Edit" />
                <Button v-if="canDelete" icon="pi pi-trash" @click="deleteContainer(data)" size="small" severity="danger" outlined title="Delete" />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <Card>
      <template #title>
        <div class="card-header">
          <span>Layouts</span>
          <div class="header-actions">
            <Button v-if="canCreate" icon="pi pi-plus" label="New Layout" @click="openNewLayoutDialog" size="small" />
          </div>
        </div>
      </template>
      <template #content>
        <p class="hint">A Layout groups containers together and scopes which containers a Contenttype's handlers may target — it has no runtime meaning on its own.</p>
        <DataTable :value="layouts" :loading="loading" sortField="name" :sortOrder="1" stripedRows size="small" responsiveLayout="scroll">
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="name" header="Name" sortable />
          <Column field="description" header="Description" />
          <Column header="Containers">
            <template #body="{ data }">
              <span v-for="(id, i) in data.container_ids" :key="id">
                {{ containerName(id) }}<span v-if="i < data.container_ids.length - 1">, </span>
              </span>
              <span v-if="!data.container_ids?.length" class="hint">none</span>
            </template>
          </Column>
          <Column header="Actions" style="width: 120px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button v-if="canEdit" icon="pi pi-pencil" @click="openEditLayoutDialog(data)" size="small" outlined title="Edit" />
                <Button v-if="canDelete" icon="pi pi-trash" @click="deleteLayout(data)" size="small" severity="danger" outlined title="Delete" />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Container Dialog -->
    <Dialog v-model:visible="showContainerDialog" :header="isNewContainer ? 'New Container' : 'Edit Container'" modal :style="{ width: '500px' }">
      <div class="dialog-content">
        <div class="field">
          <label for="c-name">Name</label>
          <InputText id="c-name" v-model="containerForm.name" class="w-full" />
        </div>
        <div class="field">
          <label for="c-title">Title</label>
          <InputText id="c-title" v-model="containerForm.title" class="w-full" />
        </div>
        <div class="field">
          <label for="c-order">Order</label>
          <InputNumber id="c-order" v-model="containerForm.order" class="w-full" />
        </div>
        <div class="position-grid">
          <div class="field">
            <label for="c-top">Top (vh)</label>
            <InputNumber id="c-top" v-model="containerForm.top" class="w-full" :min="0" :max="100" />
          </div>
          <div class="field">
            <label for="c-left">Left (vw)</label>
            <InputNumber id="c-left" v-model="containerForm.left" class="w-full" :min="0" :max="100" />
          </div>
          <div class="field">
            <label for="c-width">Width (vw)</label>
            <InputNumber id="c-width" v-model="containerForm.width" class="w-full" :min="0" :max="100" />
          </div>
          <div class="field">
            <label for="c-height">Height (vh)</label>
            <InputNumber id="c-height" v-model="containerForm.height" class="w-full" :min="0" :max="100" />
          </div>
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="showContainerDialog = false" text />
        <Button label="Save" @click="saveContainer" />
      </template>
    </Dialog>

    <!-- Layout Dialog -->
    <Dialog v-model:visible="showLayoutDialog" :header="isNewLayout ? 'New Layout' : 'Edit Layout'" modal :style="{ width: '500px' }">
      <div class="dialog-content">
        <div class="field">
          <label for="l-name">Name</label>
          <InputText id="l-name" v-model="layoutForm.name" class="w-full" />
        </div>
        <div class="field">
          <label for="l-description">Description</label>
          <Textarea id="l-description" v-model="layoutForm.description" rows="2" class="w-full" />
        </div>
        <div class="field">
          <label for="l-containers">Containers</label>
          <MultiSelect
            id="l-containers"
            v-model="layoutForm.container_ids"
            :options="containerOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="Select containers"
            class="w-full"
          />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="showLayoutDialog = false" text />
        <Button label="Save" @click="saveLayout" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.layouts-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.hint {
  color: #888;
  font-size: 0.8rem;
  margin-bottom: 0.75rem;
}

.position-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem 1rem;
}
</style>
