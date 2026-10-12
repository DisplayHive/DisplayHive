<script setup lang="ts">
import { useRightsStore } from '../stores/rights'
import ExportCard from '../components/importexport/ExportCard.vue'
import ImportCard from '../components/importexport/ImportCard.vue'

import Card from 'primevue/card'
import Message from 'primevue/message'

const rightsStore = useRightsStore()
</script>

<template>
  <div v-if="rightsStore.loaded && !rightsStore.can('importexport.page')" class="importexport-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Im-/Export page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="importexport-page" class="importexport-view">
    <Message severity="warn" :closable="false" class="not-a-backup-notice">
      <strong>This is not a full system backup.</strong> It exports/imports display content
      (screens, designs, layouts, content, media, devices) and general app settings
      only. It never includes admin user accounts, API keys or tokens (Telegram bot token, Pretalx
      credentials), or log files — restoring a file elsewhere will not recreate logins or
      integration credentials.
    </Message>

    <ExportCard />

    <ImportCard />
  </div>
</template>

<style scoped>
.importexport-view {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  max-width: 700px;
}

.not-a-backup-notice {
  width: 100%;
}
</style>
