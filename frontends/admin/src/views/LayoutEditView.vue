<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useRightsStore } from '../stores/rights'
import type { Layout, ContentContainer } from '../types/models'

import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Textarea from 'primevue/textarea'
import LayoutCanvasEditor from '../components/LayoutCanvasEditor.vue'

const router = useRouter()
const route = useRoute()
const goBack = () => router.push({ name: 'layouts' })

const toast = useToast()
const confirm = useConfirm()
const { on, off, emit, emitWithAck } = useSocket()
const rightsStore = useRightsStore()

const canEdit = computed(() => rightsStore.can('layouts.edit'))
const canCreate = computed(() => rightsStore.can('layouts.create'))
const canDelete = computed(() => rightsStore.can('layouts.delete'))

const containers = ref<ContentContainer[]>([])
const layouts = ref<Layout[]>([])
const loading = ref(true)

const isNewLayout = computed(() => route.name === 'layout-new')
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
// canvas editor and only sent to the server on an explicit Save.
const canvasEditorRef = ref<InstanceType<typeof LayoutCanvasEditor> | null>(null)
// Resolves false if the admin cancelled out of the "also affects layout Y"
// warning — callers should abort whatever they were about to do in that case.
const flushPendingPositions = async () => (await canvasEditorRef.value?.flushPendingPositions()) !== false

const initFromRoute = () => {
  if (route.name === 'layout-new') {
    layoutForm.value = { id: null, name: '', description: '' }
    return
  }
  const id = Number(route.params.id)
  if (!id) {
    goBack()
    return
  }
  const existing = layouts.value.find((l) => l.id === id)
  layoutForm.value = { id, name: existing?.name || '', description: existing?.description || '' }
}

const saveLayout = async () => {
  if (isNewLayout.value) {
    const ack = await emitWithAck<{ ok: boolean; id?: number; error?: string }>(
      'displayhive:admin:cts:create_layout',
      { name: layoutForm.value.name, description: layoutForm.value.description },
    )
    if (ack?.ok && ack.id) {
      toast.add({ severity: 'success', summary: 'Success', detail: 'Layout created — now add its containers below', life: 3000 })
      router.replace({ name: 'layout-edit', params: { id: ack.id } })
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

const deleteEditingLayout = () => {
  const l = editingLayout.value
  if (!l) return
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
        goBack()
      } else {
        toast.add({ severity: 'error', summary: 'Delete failed', detail: ack?.error || 'Unknown error', life: 4000 })
      }
    },
  })
}

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
  emit('displayhive:admin:cts:get_containers')
  emit('displayhive:admin:cts:get_layouts')
})

onUnmounted(() => {
  off('displayhive:admin:stc:upd_containers', handleContainersList)
  off('displayhive:admin:stc:upd_layouts', handleLayoutsList)
})

// Re-run route-driven init both on first mount and whenever the route
// changes without unmounting this component.
watch(() => route.fullPath, initFromRoute, { immediate: true })
// The initial `get_layouts` fetch above is async — once it lands, fill in
// the name/description for an edit route that was reached before it arrived.
watch(layouts, () => {
  if (route.name === 'layout-edit' && layoutForm.value.id && !layoutForm.value.name) {
    initFromRoute()
  }
})
</script>

<template>
  <Teleport to="#page-header-actions">
    <Button label="Back to Layouts" icon="pi pi-arrow-left" text @click="goBack" />
  </Teleport>

  <div class="layout-edit-page">
    <div class="field">
      <label for="l-name">Name</label>
      <InputText id="l-name" v-model="layoutForm.name" class="w-full" autofocus />
    </div>
    <div class="field">
      <label for="l-description">Description</label>
      <Textarea id="l-description" v-model="layoutForm.description" rows="1" class="w-full" />
    </div>

    <p v-if="editingLayout" class="hint">
      Drag containers directly on the canvas to move/resize them, draw new ones on empty space,
      or drag existing containers in from the sidebar. Position changes save when you click
      Save — assigning, removing and deleting containers still happen immediately.
    </p>
    <p v-else-if="!loading" class="hint">Save the name above to start adding containers.</p>

    <LayoutCanvasEditor v-if="editingLayout" ref="canvasEditorRef" :layout="editingLayout" :containers="containers" :layouts="layouts" />

    <div class="layout-edit-actions">
      <Button v-if="isNewLayout ? canCreate : canEdit" :label="isNewLayout ? 'Create' : 'Save'" :disabled="isNewLayout && !layoutForm.name.trim()" @click="saveLayout" />
      <Button
        v-if="canDelete && editingLayout"
        label="Delete Layout"
        icon="pi pi-trash"
        severity="danger"
        outlined
        :disabled="editingLayout.in_use"
        :title="editingLayout?.in_use ? 'Used by a Contenttype — cannot delete' : ''"
        @click="deleteEditingLayout"
      />
    </div>
  </div>
</template>

<style scoped>
.layout-edit-page {
  padding: 1.5rem;
  width: 100%;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  margin-bottom: 0.75rem;
}

.layout-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1rem;
}

.hint {
  color: #888;
  font-size: 0.8rem;
  margin-bottom: 0.75rem;
}
</style>
