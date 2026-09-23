<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDevicesStore } from '../stores/devices'
import { useScreensStore } from '../stores/screens'
import { useRightsStore } from '../stores/rights'
import { useToast } from 'primevue/usetoast'

import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Button from 'primevue/button'

const route = useRoute()
const router = useRouter()
const toast = useToast()
const devicesStore = useDevicesStore()
const screensStore = useScreensStore()
const rightsStore = useRightsStore()

const canAdopt = computed(() => rightsStore.can('device.adopt'))

const isAdopting = ref(false)
const form = ref({
  name: '',
  adoptiontoken: (route.query.token as string) || '',
  screen_id: null as number | null,
})

const screenOptions = computed(() => {
  const assigned = new Set<number>()
  devicesStore.devices.forEach((d) => { if (d.screen_id) assigned.add(d.screen_id) })
  return [
    { label: '-- No Screen --', value: null as number | null },
    ...screensStore.screens
      .filter((s) => !assigned.has(s.id))
      .map((s) => ({ label: s.name, value: s.id as number | null })),
  ]
})

onMounted(() => {
  devicesStore.fetch()
  screensStore.fetch()
})

const adoptDevice = async () => {
  isAdopting.value = true
  const screenName = form.value.screen_id
    ? screensStore.screens.find((s) => s.id === form.value.screen_id)?.name ?? null
    : null

  try {
    const result = await devicesStore.adoptDevice({
      token: form.value.adoptiontoken,
      device_name: form.value.name,
      screen_name: screenName ?? null,
    })

    if (result?.success) {
      toast.add({ severity: 'success', summary: 'Success', detail: 'Device adopted', life: 3000 })
      router.push({ name: 'devices' })
    } else {
      toast.add({ severity: 'error', summary: 'Error', detail: result?.error || 'Failed to adopt device', life: 5000 })
    }
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to adopt device', life: 5000 })
  } finally {
    isAdopting.value = false
  }
}
</script>

<template>
  <div class="manualadopt-view">
    <div v-if="!rightsStore.loaded" class="loading-state">
      <i class="pi pi-spin pi-spinner"></i>
      <span>Checking permissions...</span>
    </div>
    <Card v-else-if="!canAdopt">
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have permission to adopt devices.</p>
        </div>
      </template>
    </Card>
    <Card v-else>
      <template #title>Adopt Device</template>
      <template #content>
        <div class="dialog-content">
          <div class="field">
            <label for="adopt-name">Device Name</label>
            <InputText id="adopt-name" v-model="form.name" class="w-full" />
          </div>
          <div class="field">
            <label for="adopt-key">Adoptiontoken</label>
            <InputText id="adopt-key" v-model="form.adoptiontoken" class="w-full" placeholder="Enter or scan adoption token" />
          </div>
          <div class="field">
            <label for="adopt-screen">Assign to Screen</label>
            <Select
              id="adopt-screen"
              v-model="form.screen_id"
              :options="screenOptions"
              optionLabel="label"
              optionValue="value"
              class="w-full"
            />
          </div>
          <Button
            label="Adopt"
            @click="adoptDevice"
            :loading="isAdopting"
            :disabled="isAdopting || !form.adoptiontoken"
          />
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.manualadopt-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 500px;
  margin: 0 auto;
}
</style>
