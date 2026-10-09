<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import Menu from 'primevue/menu'

// The page-level actions of a list page, in the app's page header (App.vue,
// #page-header-actions) at the right of the title: ONE primary action as a button, and
// everything else (refresh, reload all, sync …) in a "More actions" menu. Every list page
// uses this, so the primary action is always in the same place.
//
//   <PageActions
//     :primary="canCreate ? { label: 'Add Screen', icon: 'pi pi-plus', tour: 'screens-new', onClick: openCreateDialog } : null"
//     :secondary="[{ label: 'Refresh', icon: 'pi pi-sync', onClick: refreshScreens }]"
//   />
//
// `tour` becomes the element's data-tour attribute (see src/tour). Actions that don't apply
// (no right to do them) are passed as null/false and simply left out; without any secondary
// action there is no menu.

export interface PageAction {
  label: string
  icon?: string
  onClick: () => void
  /** data-tour attribute of the button / menu entry. */
  tour?: string
  /** Tooltip explaining the action. */
  title?: string
  loading?: boolean
}

const props = defineProps<{
  primary?: PageAction | null | false
  secondary?: Array<PageAction | null | false>
}>()

// A Teleport needs its target in the document when it renders. On a fresh load of a page
// the whole app is still being built then, so the header's target is not there yet: wait
// until this component is mounted (by which time it is).
const targetReady = ref(false)
onMounted(() => {
  targetReady.value = true
})

const secondaryActions = computed(() => (props.secondary ?? []).filter((a): a is PageAction => !!a))

const menu = ref<InstanceType<typeof Menu> | null>(null)
const toggle = (event: Event) => menu.value?.toggle(event)

const model = computed(() =>
  secondaryActions.value.map((action) => ({
    label: action.label,
    icon: action.loading ? 'pi pi-spin pi-spinner' : action.icon,
    disabled: !!action.loading,
    tour: action.tour,
    title: action.title,
    command: () => action.onClick(),
  })),
)
</script>

<template>
  <Teleport v-if="targetReady" to="#page-header-actions">
    <Button
      v-if="primary"
      :data-tour="primary.tour"
      :icon="primary.icon"
      :label="primary.label"
      :title="primary.title"
      :loading="primary.loading"
      size="small"
      @click="primary.onClick()"
    />
    <template v-if="secondaryActions.length">
      <Button
        data-tour="page-more-actions"
        icon="pi pi-ellipsis-v"
        aria-label="More actions"
        title="More actions"
        aria-haspopup="true"
        outlined
        size="small"
        @click="toggle"
      />
      <Menu ref="menu" :model="model" popup>
        <template #item="{ item, props: itemProps }">
          <a v-bind="itemProps.action" :data-tour="(item as { tour?: string }).tour" :title="(item as { title?: string }).title">
            <span v-if="item.icon" :class="item.icon" />
            <span class="p-menu-item-label">{{ item.label }}</span>
          </a>
        </template>
      </Menu>
    </template>
  </Teleport>
</template>
