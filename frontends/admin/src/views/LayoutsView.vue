<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useRightsStore } from '../stores/rights'
import type { Layout, ContentContainer } from '../types/models'

import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import Card from 'primevue/card'
import Dropdown from 'primevue/dropdown'
import LayoutCanvasEditor from '../components/LayoutCanvasEditor.vue'

const toast = useToast()
const confirm = useConfirm()
const { on, off, emit, emitWithAck } = useSocket()
const rightsStore = useRightsStore()

const canCreate = computed(() => rightsStore.can('layouts.create'))
const canEdit = computed(() => rightsStore.can('layouts.edit'))
const canDelete = computed(() => rightsStore.can('layouts.delete'))

const containers = ref<ContentContainer[]>([])
const layouts = ref<Layout[]>([])
const loading = ref(true)

// --- Layouts -------------------------------------------------------------

const isNewLayout = ref(false)
const layoutForm = ref({
  id: null as number | null,
  name: '',
  description: '',
})

// The live Layout object (kept fresh by the upd_layouts broadcast) that the
// canvas editor reads/writes its container assignment against. Only
// available once the Layout has actually been created.
const editingLayout = computed(() => layouts.value.find((l) => l.id === layoutForm.value.id) || null)

// Container position edits (drag/resize/modal) are staged locally inside the
// canvas editor and only sent to the server on an explicit Save — i.e. never
// just from switching or starting a new Layout, which discard them instead.
const canvasEditorRef = ref<InstanceType<typeof LayoutCanvasEditor> | null>(null)
// Resolves false if the admin cancelled out of the "also affects layout Y"
// warning — callers should abort whatever they were about to do in that case.
const flushPendingPositions = async () => (await canvasEditorRef.value?.flushPendingPositions()) !== false

// All Layouts, selectable from the dropdown so the admin can switch which
// one they're editing at any time.
const layoutSelectOptions = computed(() => layouts.value.map((l) => ({ label: l.name, value: l.id })))

const onLayoutSelectChange = (id: number | null) => {
  if (id == null) return
  const l = layouts.value.find((x) => x.id === id)
  if (!l) return
  canvasEditorRef.value?.discardPendingPositions()
  isNewLayout.value = false
  layoutForm.value = { id: l.id, name: l.name, description: l.description || '' }
}

// "New" — resets the form to a blank, not-yet-created Layout.
const startNewLayout = () => {
  canvasEditorRef.value?.discardPendingPositions()
  isNewLayout.value = true
  layoutForm.value = { id: null, name: '', description: '' }
}

const saveLayout = async () => {
  if (isNewLayout.value) {
    const ack = await emitWithAck<{ ok: boolean; id?: number; error?: string }>(
      'displayhive:admin:cts:create_layout',
      { name: layoutForm.value.name, description: layoutForm.value.description },
    )
    if (ack?.ok && ack.id) {
      toast.add({ severity: 'success', summary: 'Success', detail: 'Layout created — now add its containers below', life: 3000 })
      isNewLayout.value = false
      layoutForm.value.id = ack.id
      refreshData()
    } else {
      toast.add({ severity: 'error', summary: 'Save failed', detail: ack?.error || 'Unknown error', life: 4000 })
    }
    return
  }
  if (!(await flushPendingPositions())) return
  emit('displayhive:admin:cts:update_layout', {
    id: layoutForm.value.id, name: layoutForm.value.name, description: layoutForm.value.description,
  })
  toast.add({ severity: 'success', summary: 'Success', detail: 'Layout updated', life: 3000 })
}

// Duplicates the currently-open Layout as a brand new one, keeping its
// current set of containers (the containers themselves aren't copied —
// they're shared, standalone entities — the new Layout just references
// the same ones, exactly like assigning an existing container normally does).
const saveLayoutAsNew = async () => {
  if (!layoutForm.value.id) return
  if (!(await flushPendingPositions())) return
  const newName = `${layoutForm.value.name} (copy)`
  const ack = await emitWithAck<{ ok: boolean; id?: number; error?: string }>(
    'displayhive:admin:cts:create_layout',
    {
      name: newName,
      description: layoutForm.value.description,
      container_ids: editingLayout.value?.container_ids || [],
    },
  )
  if (ack?.ok && ack.id) {
    toast.add({ severity: 'success', summary: 'Success', detail: `Saved as "${newName}"`, life: 3000 })
    isNewLayout.value = false
    layoutForm.value = { id: ack.id, name: newName, description: layoutForm.value.description }
    refreshData()
  } else {
    toast.add({ severity: 'error', summary: 'Save failed', detail: ack?.error || 'Unknown error', life: 4000 })
  }
}

const deleteLayout = (l: Layout, onDeleted?: () => void) => {
  if (l.in_use) {
    toast.add({ severity: 'warn', summary: 'Cannot delete', detail: 'This layout is used by a Contenttype — reassign it first.', life: 4000 })
    return
  }
  confirm.require({
    message: `Are you sure you want to delete layout "${l.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: async () => {
      const ack = await emitWithAck<{ ok: boolean; error?: string }>('displayhive:admin:cts:delete_layout', { id: l.id })
      if (ack?.ok) {
        toast.add({ severity: 'success', summary: 'Success', detail: 'Layout deleted', life: 3000 })
        onDeleted?.()
      } else {
        toast.add({ severity: 'error', summary: 'Delete failed', detail: ack?.error || 'Unknown error', life: 4000 })
      }
    },
  })
}

const deleteEditingLayout = () => {
  if (!editingLayout.value) return
  deleteLayout(editingLayout.value, () => {
    isNewLayout.value = false
    layoutForm.value = { id: null, name: '', description: '' }
    refreshData()
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
          <span>{{ isNewLayout ? 'New Layout' : editingLayout ? editingLayout.name : 'Layouts' }}</span>
          <Button icon="pi pi-refresh" @click="refreshData" size="small" outlined />
        </div>
      </template>
      <template #content>
        <div class="layout-picker-row">
          <div class="field">
            <label for="l-picker">Switch Layout</label>
            <Dropdown
              id="l-picker"
              :model-value="layoutForm.id"
              :options="layoutSelectOptions"
              optionLabel="label"
              optionValue="value"
              placeholder="Select a layout to edit"
              class="w-full"
              :loading="loading"
              @update:model-value="onLayoutSelectChange"
            />
          </div>
          <Button v-if="canCreate" label="New" icon="pi pi-plus" outlined size="small" @click="startNewLayout" />
          <Button
            v-if="canCreate"
            label="Save as New"
            icon="pi pi-copy"
            outlined
            size="small"
            :disabled="!layoutForm.id"
            @click="saveLayoutAsNew"
          />
          <Button
            v-if="canDelete"
            label="Delete Layout"
            icon="pi pi-trash"
            severity="danger"
            outlined
            size="small"
            :disabled="!editingLayout || editingLayout.in_use"
            :title="editingLayout?.in_use ? 'Used by a Contenttype — cannot delete' : ''"
            @click="deleteEditingLayout"
          />
        </div>

        <template v-if="isNewLayout || editingLayout">
          <div class="layout-meta-row">
            <div class="field">
              <label for="l-name">Name</label>
              <InputText id="l-name" v-model="layoutForm.name" class="w-full" />
            </div>
            <div class="field">
              <label for="l-description">Description</label>
              <Textarea id="l-description" v-model="layoutForm.description" rows="1" class="w-full" />
            </div>
            <Button v-if="isNewLayout ? canCreate : canEdit" :label="isNewLayout ? 'Create' : 'Save'" @click="saveLayout" />
          </div>

          <template v-if="editingLayout">
            <p class="hint">
              Drag containers directly on the canvas to move/resize them, draw new ones on empty space,
              or drag existing containers in from the sidebar. Position changes save when you click
              Save — assigning, removing and deleting containers still happen immediately.
            </p>
            <LayoutCanvasEditor ref="canvasEditorRef" :layout="editingLayout" :containers="containers" :layouts="layouts" />
          </template>
          <p v-else class="hint">Save the name above to start adding containers.</p>
        </template>
        <p v-else class="hint">Select a Layout above to edit it, or click "New" to create one.</p>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.layouts-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.hint {
  color: #888;
  font-size: 0.8rem;
  margin-bottom: 0.75rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.layout-meta-row {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  margin-bottom: 0.75rem;
}

.layout-meta-row .field {
  flex: 1;
}

.layout-picker-row {
  display: flex;
  gap: 0.75rem;
  align-items: flex-end;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--p-surface-border, #ddd);
}

.layout-picker-row .field {
  flex: 1;
  max-width: 350px;
}
</style>
