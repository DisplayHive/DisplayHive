<script setup lang="ts">
import { computed, onBeforeUnmount, toRef, watch } from 'vue'
import DeliverySettings from '../contentEdit/DeliverySettings.vue'
import type { ScreengroupOption } from '../../composables/contentEdit/useScreengroupAssignment'
import { useRowDelivery, type DeliveryRow } from '../../composables/contentEdit/useRowDelivery'
import { registerRowEdit } from '../../composables/contentEdit/useRowEditSession'
import { useRightsStore } from '../../stores/rights'

// The delivery settings of a row of the content list, right of its preview: the very same
// component as on the edit page, working on the row's schedule, duration and assignment. Changes wait
// for the row's Save / Discard (RowSaveBar.vue); only these are written. Without the right
// to edit content (content.edit; the assignment also needs screengroups.manage_content) they are
// shown but cannot be changed.
const props = defineProps<{ row: DeliveryRow; allScreengroups: ScreengroupOption[]; oneScreenGroups: ScreengroupOption[] }>()

const rights = useRightsStore()
const editable = computed(() => rights.can('content.edit'))
const delivery = useRowDelivery(() => props.row, {
  allScreengroups: computed(() => props.allScreengroups),
  oneScreenGroups: computed(() => props.oneScreenGroups),
})

// Saved and discarded together with the row's fields, by the row's one Save / Discard.
onBeforeUnmount(registerRowEdit(props.row.id, {
  dirty: toRef(delivery, 'dirty'),
  saving: toRef(delivery, 'saving'),
  save: delivery.save,
  discard: delivery.discard,
}))

watch(() => JSON.stringify([props.row.duration, props.row.start_time, props.row.end_time, props.row.recurrence, (props.row.screengroups ?? []).map((g) => g.id)]), delivery.refresh)
</script>

<template>
  <div class="row-delivery" data-testid="row-delivery">
    <fieldset class="row-delivery-fields" :disabled="!editable || delivery.saving">
      <DeliverySettings :model="delivery" />
    </fieldset>
  </div>
</template>

<style scoped>
.row-delivery-fields {
  min-width: 0;
  margin: 0;
  padding: 0;
  border: 0;
}
</style>
