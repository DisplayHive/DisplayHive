<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useSocket } from '../composables/useSocket'
import { useToast } from 'primevue/usetoast'
import { useConfirm } from 'primevue/useconfirm'
import { useMagicTagsStore } from '../stores/magicTags'
import { useMagicTagValueListsStore } from '../stores/magicTagValueLists'
import { useRightsStore } from '../stores/rights'
import type { MagicTag, MagicTagValueList } from '../types/models'

// PrimeVue components
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Dialog from 'primevue/dialog'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Select from 'primevue/select'

const toast = useToast()
const confirm = useConfirm()
const { emit } = useSocket()
const magicTagsStore = useMagicTagsStore()
const magicTagValueListsStore = useMagicTagValueListsStore()
const rightsStore = useRightsStore()

const canMagicTagsPage = computed(() => rightsStore.can('magictags.page'))
const canMagicTagsCreate = computed(() => rightsStore.can('magictags.create'))
const canMagicTagsEdit = computed(() => rightsStore.can('magictags.edit'))
const canMagicTagsDelete = computed(() => rightsStore.can('magictags.delete'))

const canValueListsPage = computed(() => rightsStore.can('magictagvaluelists.page'))
const canValueListsCreate = computed(() => rightsStore.can('magictagvaluelists.create'))
const canValueListsEdit = computed(() => rightsStore.can('magictagvaluelists.edit'))
const canValueListsDelete = computed(() => rightsStore.can('magictagvaluelists.delete'))

const hasPageAccess = computed(() => canMagicTagsPage.value || canValueListsPage.value)

// --- Magic Tags ---

const showTagDialog = ref(false)
const isNewTag = ref(false)
const tagTypeOptions = [
  { label: 'Text', value: 'text' },
  { label: 'List', value: 'list' },
]
const tagForm = ref<{
  id: number | null
  name: string
  type: 'text' | 'list'
  value_list_id: number | null
}>({
  id: null,
  name: '',
  type: 'text',
  value_list_id: null,
})

const openNewTagDialog = () => {
  isNewTag.value = true
  tagForm.value = { id: null, name: '', type: 'text', value_list_id: null }
  showTagDialog.value = true
}

const openEditTagDialog = (v: MagicTag) => {
  isNewTag.value = false
  tagForm.value = {
    id: v.id,
    name: v.name,
    type: v.type || 'text',
    value_list_id: v.value_list_id ?? null,
  }
  showTagDialog.value = true
}

const saveTag = (keepOpen = false) => {
  const event = isNewTag.value
    ? 'displayhive:admin:cts:create_magic_tag'
    : 'displayhive:admin:cts:update_magic_tag'
  emit(event, {
    id: tagForm.value.id,
    name: tagForm.value.name,
    type: tagForm.value.type,
    value_list_id: tagForm.value.type === 'list' ? tagForm.value.value_list_id : null,
  })
  toast.add({ severity: 'success', summary: 'Success', detail: isNewTag.value ? 'Magic tag created' : 'Magic tag updated', life: 3000 })
  if (!keepOpen) showTagDialog.value = false
}

const valueListName = (id: number | null) => {
  if (!id) return '(no list)'
  return magicTagValueListsStore.valueLists.find((l) => l.id === id)?.name || `#${id}`
}

const valueListEntries = (id: number | null) => {
  if (!id) return []
  return magicTagValueListsStore.valueLists.find((l) => l.id === id)?.entries || []
}

const updateMagicTagValue = (tag: MagicTag) => {
  emit('displayhive:admin:cts:update_magic_tag', {
    id: tag.id,
    name: tag.name,
    value: tag.value,
    description: tag.description,
    type: tag.type,
    value_list_id: tag.value_list_id,
  })
  toast.add({ severity: 'success', summary: 'Success', detail: 'Magic tag value updated', life: 2000 })
}

const deleteTag = (v: MagicTag) => {
  confirm.require({
    message: `Are you sure you want to delete "${v.name}"?`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      emit('displayhive:admin:cts:delete_magic_tag', { id: v.id })
      toast.add({ severity: 'success', summary: 'Success', detail: 'Magic tag deleted', life: 3000 })
    },
  })
}

// --- Magic Tag Value Lists ---

const showValueListDialog = ref(false)
const isNewValueList = ref(false)
const valueListForm = ref<{ id: number | null; name: string; entries: { key: string; value: string }[] }>({
  id: null,
  name: '',
  entries: [],
})

const openNewValueListDialog = () => {
  isNewValueList.value = true
  valueListForm.value = { id: null, name: '', entries: [{ key: '', value: '' }] }
  showValueListDialog.value = true
}

const openEditValueListDialog = (l: MagicTagValueList) => {
  isNewValueList.value = false
  valueListForm.value = {
    id: l.id,
    name: l.name,
    entries: l.entries.map((e) => ({ key: e.key, value: e.value })),
  }
  showValueListDialog.value = true
}

const addValueListEntry = () => {
  valueListForm.value.entries.push({ key: '', value: '' })
}

const removeValueListEntry = (index: number) => {
  valueListForm.value.entries.splice(index, 1)
}

const saveValueList = () => {
  const event = isNewValueList.value
    ? 'displayhive:admin:cts:create_magic_tag_value_list'
    : 'displayhive:admin:cts:update_magic_tag_value_list'
  const entries = valueListForm.value.entries.filter((e) => e.key.trim())
  emit(event, { id: valueListForm.value.id, name: valueListForm.value.name, entries })
  toast.add({ severity: 'success', summary: 'Success', detail: isNewValueList.value ? 'Value list created' : 'Value list updated', life: 3000 })
  showValueListDialog.value = false
}

const deleteValueList = (l: MagicTagValueList) => {
  confirm.require({
    message: `Are you sure you want to delete "${l.name}"? Magic tags using it will be reset to no list.`,
    header: 'Confirm Delete',
    icon: 'pi pi-exclamation-triangle',
    acceptClass: 'p-button-danger',
    accept: () => {
      emit('displayhive:admin:cts:delete_magic_tag_value_list', { id: l.id })
      toast.add({ severity: 'success', summary: 'Success', detail: 'Value list deleted', life: 3000 })
    },
  })
}

onMounted(() => {
  if (canMagicTagsPage.value) magicTagsStore.fetch()
  if (canValueListsPage.value) magicTagValueListsStore.fetch()
})
</script>

<template>
  <div v-if="rightsStore.loaded && !hasPageAccess" class="magictags-view">
    <Card>
      <template #content>
        <div class="empty-state">
          <i class="pi pi-lock" style="font-size: 3rem"></i>
          <p>You don't have access to the Magic Tags page.</p>
        </div>
      </template>
    </Card>
  </div>
  <div v-else class="magictags-view">
    <!-- Magic Tags Card -->
    <Card v-if="canMagicTagsPage">
      <template #title>
        <div class="card-header">
          <span>Magic Tags</span>
          <div class="header-actions">
            <Button v-if="canMagicTagsCreate" icon="pi pi-plus" label="New Magic Tag" @click="openNewTagDialog" size="small" />
            <Button icon="pi pi-refresh" @click="magicTagsStore.fetch()" size="small" outlined />
          </div>
        </div>
      </template>
      <template #content>
        <DataTable
          :value="magicTagsStore.magicTags"
          :loading="magicTagsStore.loading"
          sortField="name"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="magicTagsStore.magicTags.length > 10"
          :rows="10"
          responsiveLayout="scroll"
        >
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="name" header="Name" sortable />
          <Column field="type" header="Type" style="width: 90px" sortable>
            <template #body="{ data }">
              <Tag :severity="data.type === 'list' ? 'info' : 'secondary'" :value="data.type === 'list' ? 'List' : 'Text'" />
            </template>
          </Column>
          <Column header="Value" style="min-width: 220px">
            <template #body="{ data }">
              <Select
                v-if="data.type === 'list'"
                v-model="data.value"
                :options="valueListEntries(data.value_list_id)"
                optionLabel="key"
                optionValue="key"
                :placeholder="data.value_list_id ? 'Select a key' : 'No value list assigned'"
                :title="`List: ${valueListName(data.value_list_id)}`"
                :disabled="!canMagicTagsEdit || !data.value_list_id"
                class="w-full"
                @change="updateMagicTagValue(data)"
              />
              <InputText
                v-else
                v-model="data.value"
                :disabled="!canMagicTagsEdit"
                class="w-full"
                @change="updateMagicTagValue(data)"
              />
            </template>
          </Column>
          <Column field="description" header="Description">
            <template #body="{ data }">
              {{ data.description && data.description.length > 80 ? data.description.substring(0, 80) + '...' : (data.description || '-') }}
            </template>
          </Column>
          <Column header="Actions" style="width: 120px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button v-if="canMagicTagsEdit" icon="pi pi-pencil" @click="openEditTagDialog(data)" size="small" outlined title="Edit" />
                <Button v-if="canMagicTagsDelete" icon="pi pi-trash" @click="deleteTag(data)" size="small" severity="danger" outlined title="Delete" />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Magic Tag Value Lists Card -->
    <Card v-if="canValueListsPage">
      <template #title>
        <div class="card-header">
          <span>Magic Tag Value Lists</span>
          <div class="header-actions">
            <Button v-if="canValueListsCreate" icon="pi pi-plus" label="New Value List" @click="openNewValueListDialog" size="small" />
            <Button icon="pi pi-refresh" @click="magicTagValueListsStore.fetch()" size="small" outlined />
          </div>
        </div>
      </template>
      <template #content>
        <DataTable
          :value="magicTagValueListsStore.valueLists"
          :loading="magicTagValueListsStore.loading"
          sortField="name"
          :sortOrder="1"
          stripedRows
          size="small"
          :paginator="magicTagValueListsStore.valueLists.length > 10"
          :rows="10"
          responsiveLayout="scroll"
        >
          <Column field="id" header="ID" style="width: 60px" sortable />
          <Column field="name" header="Name" sortable />
          <Column header="Entries" style="width: 100px">
            <template #body="{ data }">{{ data.entries.length }}</template>
          </Column>
          <Column header="Actions" style="width: 120px">
            <template #body="{ data }">
              <div class="action-buttons">
                <Button v-if="canValueListsEdit" icon="pi pi-pencil" @click="openEditValueListDialog(data)" size="small" outlined title="Edit" />
                <Button v-if="canValueListsDelete" icon="pi pi-trash" @click="deleteValueList(data)" size="small" severity="danger" outlined title="Delete" />
              </div>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>

    <!-- Magic Tag Edit Dialog -->
    <Dialog
      v-model:visible="showTagDialog"
      :header="isNewTag ? 'New Magic Tag' : 'Edit Magic Tag'"
      modal
      :style="{ width: '480px' }"
    >
      <div class="dialog-content">
        <div class="field">
          <label for="var-name">Name</label>
          <InputText id="var-name" v-model="tagForm.name" class="w-full" />
        </div>
        <div class="field">
          <label for="var-type">Type</label>
          <Select id="var-type" v-model="tagForm.type" :options="tagTypeOptions" optionLabel="label" optionValue="value" class="w-full" />
        </div>
        <div class="field" v-if="tagForm.type === 'list'">
          <label for="var-value-list">Value List</label>
          <Select
            id="var-value-list"
            v-model="tagForm.value_list_id"
            :options="magicTagValueListsStore.valueLists"
            optionLabel="name"
            optionValue="id"
            placeholder="Select a value list"
            class="w-full"
          />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="showTagDialog = false" text />
        <Button v-if="!isNewTag" label="Update" severity="secondary" outlined @click="saveTag(true)" />
        <Button label="Save" @click="saveTag()" />
      </template>
    </Dialog>

    <!-- Magic Tag Value List Edit Dialog -->
    <Dialog
      v-model:visible="showValueListDialog"
      :header="isNewValueList ? 'New Value List' : 'Edit Value List'"
      modal
      :style="{ width: '560px' }"
    >
      <div class="dialog-content">
        <div class="field">
          <label for="vl-name">Name</label>
          <InputText id="vl-name" v-model="valueListForm.name" class="w-full" />
        </div>
        <div class="field">
          <label>Entries</label>
          <div class="vl-entries">
            <div v-for="(entry, i) in valueListForm.entries" :key="i" class="vl-entry-row">
              <InputText v-model="entry.key" placeholder="Key" class="vl-entry-key" />
              <InputText v-model="entry.value" placeholder="Value" class="vl-entry-value" />
              <Button icon="pi pi-trash" severity="danger" outlined size="small" @click="removeValueListEntry(i)" title="Remove entry" />
            </div>
          </div>
          <Button icon="pi pi-plus" label="Add Entry" size="small" outlined @click="addValueListEntry" />
        </div>
      </div>
      <template #footer>
        <Button label="Cancel" @click="showValueListDialog = false" text />
        <Button label="Save" @click="saveValueList()" :disabled="!valueListForm.name.trim()" />
      </template>
    </Dialog>
  </div>
</template>

<style scoped>
.magictags-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.ml-2 {
  margin-left: 0.5rem;
}

.vl-entries {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
}

.vl-entry-row {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.vl-entry-key {
  flex: 1;
}

.vl-entry-value {
  flex: 2;
}
</style>
