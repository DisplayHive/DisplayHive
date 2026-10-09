<script setup lang="ts">
import { provideUsersPage } from '../composables/users/useUsersPage'
import AccountsTab from '../components/users/AccountsTab.vue'
import GroupsTab from '../components/users/GroupsTab.vue'
import Card from 'primevue/card'
import Tab from 'primevue/tab'
import TabList from 'primevue/tablist'
import TabPanel from 'primevue/tabpanel'
import TabPanels from 'primevue/tabpanels'
import Tabs from 'primevue/tabs'
import { useRightsStore } from '../stores/rights'

// Users & Rights: the Accounts and Groups tabs. What they share — the rights gates, the account
// list and the rights data — comes from composables/users/useUsersPage.ts (provided here, injected
// by the tabs and their dialogs in components/users/).
const rightsStore = useRightsStore()
const page = provideUsersPage()
</script>

<template>
  <div v-if="rightsStore.loaded && !page.canViewUsers && !page.canViewRights" class="users-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock"></i>
          <p>You don't have access to the Users &amp; Rights page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else data-tour="users-page" class="users-view">
    <Tabs :value="page.defaultTab">
      <TabList>
        <Tab v-if="page.canViewUsers" value="accounts">Accounts</Tab>
        <Tab v-if="page.canViewRights" data-tour="users-tab-groups" value="groups">Groups</Tab>
      </TabList>
      <TabPanels>
        <TabPanel v-if="page.canViewUsers" value="accounts">
          <AccountsTab />
        </TabPanel>
        <TabPanel v-if="page.canViewRights" value="groups">
          <GroupsTab />
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<style scoped>
.users-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
</style>
