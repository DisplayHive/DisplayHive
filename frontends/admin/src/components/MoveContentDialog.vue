<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'

import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import Select from 'primevue/select'

interface Container {
  id?: number
  name: string
  title: string
  order: number
  contentCount?: number
  template_name?: string
}

interface ContentElement {
  id: number
  title: string
  active: boolean
  duration: number
  contentcontainer: string
  contenttypeName: string
}

interface ContentType {
  id: number
  name: string
}

const props = defineProps<{
  visible: boolean
  content: ContentElement | null
  containers: Container[]
  contentTypes: ContentType[]
}>()

const emit = defineEmits<{
  'update:visible': [boolean]
  moved: []
}>()

const toast = useToast()
const { on, off, emit: socketEmit } = useSocket()

const selectedTargetContainer = ref<string | null>(null)

watch(() => props.visible, (val) => {
  if (val && props.content) {
    selectedTargetContainer.value = props.content.contentcontainer || null
  }
})

// `ContentElement.contentcontainer` is stored as a bare name string with no
// template affiliation, so containers are addressed by name only — a name
// that exists in more than one template (props.containers spans every
// template) refers to the same move target either way. Dedupe by name,
// collecting template names for the label.
const dedupedContainers = computed(() => {
  const byName = new Map<string, Container & { templateNames: string[] }>()
  for (const c of props.containers) {
    const existing = byName.get(c.name)
    if (existing) {
      if (c.template_name && !existing.templateNames.includes(c.template_name)) {
        existing.templateNames.push(c.template_name)
      }
    } else {
      byName.set(c.name, { ...c, templateNames: c.template_name ? [c.template_name] : [] })
    }
  }
  return [...byName.values()]
})

const submitMoveContent = () => {
  if (!props.content) return
  const targetContainer = selectedTargetContainer.value || ''
  socketEmit('displayhive:admin:cts:move_content_element_container', {
    content_element_id: props.content.id,
    target_container: targetContainer
  })
}

const handleMoveResult = (data: { success: boolean; content_element_id?: number; container?: string; error?: string }) => {
  if (data.success) {
    toast.add({ severity: 'success', summary: 'Success', detail: 'Content moved successfully', life: 3000 })
    emit('update:visible', false)
    emit('moved')
  } else {
    toast.add({ severity: 'error', summary: 'Error', detail: data.error || 'Failed to move content', life: 5000 })
  }
}

onMounted(() => {
  on('displayhive:admin:stc:move_content_element_result', handleMoveResult)
})

onUnmounted(() => {
  off('displayhive:admin:stc:move_content_element_result', handleMoveResult)
})
</script>

<template>
  <Dialog
    :visible="visible"
    @update:visible="emit('update:visible', $event)"
    :header="`Move Content: ${content?.title || ''}`"
    modal
    :style="{ width: '500px' }"
  >
    <div class="dialog-content">
      <p class="move-info">
        Select a target container to move this content, or select "Unassign" to remove it from all containers.
      </p>
      <div class="field">
        <label for="target-container">Target Container</label>
        <Select
          id="target-container"
          v-model="selectedTargetContainer"
          :options="[
            { name: '(Unassign)', value: null },
            ...dedupedContainers.map(c => ({
              name: c.templateNames.length ? `${c.title} (${c.templateNames.join(', ')})` : c.title,
              value: c.name,
            }))
          ]"
          optionLabel="name"
          optionValue="value"
          placeholder="Select container or unassign"
          class="w-full"
        />
      </div>
    </div>
    <template #footer>
      <Button label="Cancel" @click="emit('update:visible', false)" text />
      <Button
        label="Move"
        @click="submitMoveContent"
        :disabled="selectedTargetContainer === (content?.contentcontainer || null)"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.move-info {
  margin-bottom: 1rem;
  color: #666;
  font-size: 0.875rem;
}
</style>
