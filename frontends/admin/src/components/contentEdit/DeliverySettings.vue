<script setup lang="ts">
import { useContentEditor } from '../../composables/contentEdit/useContentEditor'
import { SG_PAGE_SIZE } from '../../composables/contentEdit/useScreengroupAssignment'
import Button from 'primevue/button'
import Checkbox from 'primevue/checkbox'
import DatePicker from 'primevue/datepicker'
import InputNumber from 'primevue/inputnumber'
import InputText from 'primevue/inputtext'
import Paginator from 'primevue/paginator'

// The "Delivery settings" section: scheduling, duration and the screen groups / screens the
// content is assigned to (three collapsible blocks, each with a summary of its value).
const ed = useContentEditor()
</script>

<template>
  <section class="form-section">
    <h3 class="form-section-title">Delivery settings</h3>

    <!-- Scheduling -->
    <details class="scheduling-collapsible" data-tour="content-scheduling">
      <summary class="scheduling-summary">
        <i class="pi pi-clock summary-icon"></i>
        Scheduling
        <small class="text-muted">— {{ ed.schedulingSummary }}</small>
      </summary>
      <div class="scheduling-fields">
        <div class="field">
          <label for="create-start-time">Start Time</label>
          <DatePicker
            id="create-start-time"
            v-model="ed.createForm.start_time"
            showTime
            hourFormat="24"
            showClear
            dateFormat="dd.mm.yy"
            placeholder="No start restriction"
            class="w-full"
          />
        </div>
        <div class="field">
          <label for="create-end-time">End Time</label>
          <DatePicker
            id="create-end-time"
            v-model="ed.createForm.end_time"
            showTime
            hourFormat="24"
            showClear
            dateFormat="dd.mm.yy"
            placeholder="No end restriction"
            class="w-full"
          />
        </div>
      </div>
    </details>

    <!-- Duration -->
    <details class="scheduling-collapsible" data-tour="content-duration">
      <summary class="scheduling-summary">
        <i class="pi pi-stopwatch summary-icon"></i>
        Duration
        <small class="text-muted">— {{ ed.durationSummary }}</small>
      </summary>
      <div class="scheduling-fields">
        <div class="field">
          <div class="duration-fields">
            <InputNumber v-model="ed.durationMinutes" :min="0" :max="99" placeholder="0" />
            <span class="duration-unit-label">minutes</span>
            <InputNumber v-model="ed.durationSeconds" :min="0" :max="59" :use-grouping="false" placeholder="00" />
            <span class="duration-unit-label">seconds</span>
            <Button
              v-for="val in [10, 20, 30]"
              :key="val"
              :label="`${val}s`"
              size="small"
              outlined
              @click="ed.createForm.duration = val"
            />
          </div>
        </div>
      </div>
    </details>

    <!-- Screen Groups & Screens -->
    <details class="scheduling-collapsible" data-tour="content-screens">
      <summary class="scheduling-summary">
        <i class="pi pi-desktop summary-icon"></i>
        Screen Groups &amp; Screens
        <small class="text-muted">— {{ ed.assignmentSummary }}</small>
      </summary>
      <div class="scheduling-fields">
        <!-- Screengroup assignment -->
        <div class="screengroup-assignment-section">
          <h4 v-if="ed.allScreengroups.length > 0">Screen Groups</h4>
          <p v-if="ed.allScreengroups.length === 0" class="text-muted">No screen groups available.</p>
          <template v-else>
            <InputText v-model="ed.sgSearchText" placeholder="Search screen groups…" class="screengroup-search" />
            <div class="screengroup-checkboxes">
              <div v-for="sg in ed.pagedScreengroups" :key="sg.id" class="screengroup-checkbox-row">
                <Checkbox :inputId="`sg-${sg.id}`" :value="sg.id" v-model="ed.formScreengroupIds" />
                <label :for="`sg-${sg.id}`" class="screengroup-checkbox-label">{{ sg.name }}</label>
              </div>
              <p v-if="ed.filteredScreengroups.length === 0" class="text-muted">No results.</p>
            </div>
            <Paginator
              v-if="ed.filteredScreengroups.length > SG_PAGE_SIZE"
              :rows="SG_PAGE_SIZE"
              :totalRecords="ed.filteredScreengroups.length"
              :first="ed.sgPage * SG_PAGE_SIZE"
              @page="(e: any) => ed.sgPage = e.page"
              class="sg-paginator"
            />
          </template>
        </div>

        <!-- Screens assignment (is_one_screen groups only) -->
        <div class="screengroup-assignment-section" v-if="ed.oneScreenGroups.length > 0">
          <h4>Screens</h4>
          <InputText v-model="ed.screenSearchText" placeholder="Search screens…" class="screengroup-search" />
          <div class="screengroup-checkboxes">
            <div v-for="sg in ed.pagedOneScreenGroups" :key="sg.id" class="screengroup-checkbox-row">
              <Checkbox :inputId="`screen-${sg.id}`" :value="sg.id" v-model="ed.formScreengroupIds" />
              <label :for="`screen-${sg.id}`" class="screengroup-checkbox-label">{{ sg.name }}</label>
            </div>
            <p v-if="ed.filteredOneScreenGroups.length === 0" class="text-muted">No results.</p>
          </div>
          <Paginator
            v-if="ed.filteredOneScreenGroups.length > SG_PAGE_SIZE"
            :rows="SG_PAGE_SIZE"
            :totalRecords="ed.filteredOneScreenGroups.length"
            :first="ed.screenPage * SG_PAGE_SIZE"
            @page="(e: any) => ed.screenPage = e.page"
            class="sg-paginator"
          />
        </div>
      </div>
    </details>
  </section>
</template>

<style scoped>
.form-section {
  margin-bottom: 1.5rem;
}

.form-section-title {
  margin: 0 0 0.75rem 0;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--p-content-border-color, #e5e7eb);
  font-size: 0.95rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  color: var(--p-text-muted-color, #6b7280);
}

.summary-icon {
  margin-right: 0.4rem;
  font-size: 0.85rem;
}

.duration-fields {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.duration-unit-label {
  font-size: 0.875rem;
  color: var(--p-text-muted-color, #888);
  white-space: nowrap;
}

.scheduling-collapsible {
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  border-radius: 6px;
  margin-bottom: 1rem;
}

.scheduling-summary {
  padding: 0.6rem 0.75rem;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  list-style: none;
  user-select: none;
}

.scheduling-summary::-webkit-details-marker { display: none; }

.scheduling-summary::before {
  content: '▶';
  display: inline-block;
  margin-right: 0.5rem;
  font-size: 0.7rem;
  transition: transform 0.2s;
}

details[open] .scheduling-summary::before {
  transform: rotate(90deg);
}

.scheduling-fields {
  padding: 0.75rem;
  border-top: 1px solid var(--p-inputtext-border-color, #d1d5db);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.scheduling-fields .field {
  margin: 0;
}

.screengroup-assignment-section {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid var(--p-content-border-color, #ddd);
}

.screengroup-assignment-section h4 {
  margin: 0 0 0.75rem 0;
  font-size: 1rem;
}

.screengroup-search {
  width: 100%;
  margin-bottom: 0.5rem;
}

.screengroup-checkboxes {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.screengroup-checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.screengroup-checkbox-label {
  cursor: pointer;
  font-size: 0.9rem;
}
</style>
