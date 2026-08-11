<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useRightsStore } from '../stores/rights'

// PrimeVue components
import Card from 'primevue/card'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import Tag from 'primevue/tag'

interface Screen {
  id: number
  name: string
  hasDevice: boolean
  online: boolean
}

interface Screengroup {
  id: number
  name: string
  screen_ids: number[]
}

const toast = useToast()
const { on, off, emit } = useSocket()
const rightsStore = useRightsStore()
const canAccess = computed(() => rightsStore.can('screens.page') && rightsStore.can('screengroups.page'))

const screens = ref<Screen[]>([])
const screengroups = ref<Screengroup[]>([])
const loading = ref(true)

// Track changes locally
const matrixState = ref<Map<string, boolean>>(new Map())

const normalizeScreen = (item: any): Screen => {
  // Support either helper payloads ({ id, name, attached_device })
  // or JSON:API style ({ id, attributes: { name }, relationships })
  try {
    if (item && item.attributes) {
      const id = Number(item.id)
      const name = item.attributes.name || String(item.id)
      const rel = item.relationships || {}
      const hasDevice = !!(rel.device && rel.device.data)
      const online = !!(rel.device && rel.device.data && rel.device.data.is_online)
      return { id, name, hasDevice, online }
    }

    const id = Number(item.id)
    const name = item.name || item.title || String(item.id)
    const attached = item.attached_device || item.device || null
    return { id, name, hasDevice: !!attached, online: !!attached?.is_online }
  } catch (e) {
    return { id: Number(item.id || 0), name: String(item.name || item.id || 'unknown'), hasDevice: false, online: false }
  }
}

const handleScreensList = (data: any) => {
  const arr = data?.screens || data?.data || []
  screens.value = (arr || []).map(normalizeScreen)
  updateMatrixState()
  loading.value = false
}

const normalizeScreengroup = (item: any): Screengroup => {
  try {
    if (item && item.attributes) {
      const id = Number(item.id)
      const name = item.attributes.name || String(item.id)
      const rel = item.relationships || {}
      const screen_refs = (rel.screens && rel.screens.data) || []
      const screen_ids = (screen_refs || []).map((s: any) => Number(s.id))
      return { id, name, screen_ids }
    }

    const id = Number(item.id)
    const name = item.name || String(item.id)
    const screen_ids = item.screen_ids || item.screens || []
    return { id, name, screen_ids }
  } catch (e) {
    return { id: Number(item.id || 0), name: String(item.name || item.id || 'group'), screen_ids: [] }
  }
}

const handleScreengroupsList = (data: any) => {
  const arr = data?.screengroups || data?.data || []
  screengroups.value = (arr || [])
    .filter((item: any) => {
      const attrs = item.attributes || item
      return !(attrs.is_one_screen ?? false)
    })
    .map(normalizeScreengroup)
  updateMatrixState()
}

const updateMatrixState = () => {
  const newState = new Map<string, boolean>()
  screengroups.value.forEach((sg) => {
    screens.value.forEach((screen) => {
      const key = `${screen.id}-${sg.id}`
      newState.set(key, sg.screen_ids?.includes(screen.id) || false)
    })
  })
  matrixState.value = newState
}

const isChecked = (screenId: number, screengroupId: number): boolean => {
  const key = `${screenId}-${screengroupId}`
  return matrixState.value.get(key) || false
}

const toggleAssignment = (screenId: number, screengroupId: number) => {
  const key = `${screenId}-${screengroupId}`
  const currentValue = matrixState.value.get(key) || false
  matrixState.value.set(key, !currentValue)

  // Emit change to server
  if (!currentValue) {
    emit('displayhive:admin:cts:add_screen_to_screengroup', {
      screen_id: screenId,
      screengroup_id: screengroupId,
    })
  } else {
    emit('displayhive:admin:cts:remove_screen_from_screengroup', {
      screen_id: screenId,
      screengroup_id: screengroupId,
    })
  }

  toast.add({
    severity: 'success',
    summary: 'Updated',
    detail: `Screen ${currentValue ? 'removed from' : 'added to'} group`,
    life: 2000,
  })
}

onMounted(() => {
  // Listen for both the older/newer event names the backend may emit
  on('displayhive:admin:stc:screens_list', handleScreensList)
  on('displayhive:admin:stc:upd_admin_screen', handleScreensList)

  on('displayhive:admin:stc:screengroups_list', handleScreengroupsList)
  on('displayhive:admin:stc:upd_screengroups', handleScreengroupsList)

  // Emit the expected request events; backend handlers use `get_admin_screen`
  // and `get_screengroups` namespaced handlers.
  emit('displayhive:admin:cts:get_admin_screen')
  emit('get_admin_screen')
  emit('displayhive:admin:cts:get_screengroups')
  emit('get_screengroups')
})

onUnmounted(() => {
  off('displayhive:admin:stc:screens_list', handleScreensList)
  off('displayhive:admin:stc:upd_admin_screen', handleScreensList)

  off('displayhive:admin:stc:screengroups_list', handleScreengroupsList)
  off('displayhive:admin:stc:upd_screengroups', handleScreengroupsList)
})

const refreshData = () => {
  loading.value = true
  emit('displayhive:admin:cts:get_admin_screen')
  emit('get_admin_screen')
  emit('displayhive:admin:cts:get_screengroups')
  emit('get_screengroups')
}

</script>

<template>
  <div v-if="rightsStore.loaded && !canAccess" class="matrix-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Matrix page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="matrix-view">
    <Card>
      <template #content>
        <div class="matrix-info-row">
          <p class="matrix-description">
            Assign screens to screengroups by checking the corresponding boxes. Changes are saved automatically.
          </p>
          <div class="header-actions">
            <Tag :value="`${screens.length} screens`" severity="info" />
            <Tag :value="`${screengroups.length} groups`" severity="secondary" />
            <Button icon="pi pi-refresh" @click="refreshData" size="small" outlined />
          </div>
        </div>

        <div class="matrix-container" v-if="!loading">
          <table class="matrix-table">
            <thead>
              <tr>
                <th class="screen-header">Screen</th>
                <th
                  v-for="sg in screengroups"
                  :key="sg.id"
                  class="group-header"
                >
                  <div class="group-name">{{ sg.name }}</div>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="screen in screens" :key="screen.id">
                <td class="screen-name">
                  <div class="screen-name-inner">
                    <span>{{ screen.name }}</span>
                    <Tag
                      v-if="screen.hasDevice"
                      :value="screen.online ? 'Online' : 'Offline'"
                      :severity="screen.online ? 'success' : 'danger'"
                      size="small"
                    />
                    <Tag v-else value="No device" severity="secondary" size="small" />
                  </div>
                </td>
                <td
                  v-for="sg in screengroups"
                  :key="sg.id"
                  class="matrix-cell"
                  @click="rightsStore.can('screengroups.manage_screens') && toggleAssignment(screen.id, sg.id)"
                >
                  <Checkbox
                    :modelValue="isChecked(screen.id, sg.id)"
                    :binary="true"
                    :disabled="!rightsStore.can('screengroups.manage_screens')"
                    @click.stop="rightsStore.can('screengroups.manage_screens') && toggleAssignment(screen.id, sg.id)"
                  />
                </td>
              </tr>
            </tbody>
          </table>

          <div v-if="screens.length === 0" class="empty-state">
            <i class="pi pi-desktop" style="font-size: 3rem"></i>
            <p>No screens available</p>
          </div>

          <div v-if="screengroups.length === 0" class="empty-state">
            <i class="pi pi-th-large" style="font-size: 3rem"></i>
            <p>No screengroups defined</p>
          </div>
        </div>

        <div class="loading-state" v-if="loading">
          <i class="pi pi-spin pi-spinner" style="font-size: 2rem"></i>
          <p>Loading matrix...</p>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.matrix-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.matrix-info-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.matrix-description {
  color: #666;
  font-size: 0.9rem;
  margin: 0;
}

.matrix-container {
  overflow-x: auto;
}

.matrix-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 600px;
}

.matrix-table th,
.matrix-table td {
  border: 1px solid #e0e0e0;
  padding: 0.75rem;
  text-align: center;
}

.screen-header {
  background: #f5f5f5;
  font-weight: 600;
  text-align: left;
  min-width: 200px;
}

.group-header {
  background: #f5f5f5;
  font-weight: 600;
  min-width: 120px;
}

.group-name {
  writing-mode: horizontal-tb;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 120px;
}

.screen-name {
  text-align: left;
  font-weight: 500;
}

.screen-name-inner {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.matrix-cell {
  cursor: pointer;
  transition: background-color 0.2s;
}

.matrix-cell:hover {
  background-color: #f0f0f0;
}

</style>
