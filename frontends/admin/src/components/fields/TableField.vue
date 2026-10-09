<script setup lang="ts">
import { ref } from 'vue'
import { useFieldContext } from '../../composables/fields/useFieldContext'
import FieldSlot from './FieldSlot.vue'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'

// A table of text cells: columns and rows can be added, removed and dragged into another order.
// Stored as JSON ({columns, rows}) under the field's name.
const f = useFieldContext()
f.reportVisibleWhen(() => !f.isHidden(f.name))

interface TableData { columns: string[]; rows: string[][] }

const parseTableData = (): TableData => {
  try {
    const parsed = JSON.parse(String(f.get(f.name) || ''))
    if (parsed && Array.isArray(parsed.columns) && Array.isArray(parsed.rows)) return parsed
  } catch { /* fall through to the default shape */ }
  return { columns: ['Column 1', 'Column 2'], rows: [['', '']] }
}

const setTableData = (data: TableData) => {
  f.set(f.name, JSON.stringify(data))
}

const updateTableHeader = (ci: number, value: string) => {
  const d = parseTableData(); d.columns[ci] = value; setTableData(d)
}

const updateTableCell = (ri: number, ci: number, value: string) => {
  const d = parseTableData()
  if (d.rows[ri]) d.rows[ri][ci] = value
  setTableData(d)
}

const addTableRow = () => {
  const d = parseTableData()
  d.rows.push(d.columns.map(() => ''))
  setTableData(d)
}

const removeTableRow = (ri: number) => {
  const d = parseTableData(); d.rows.splice(ri, 1); setTableData(d)
}

const addTableColumn = () => {
  const d = parseTableData()
  d.columns.push(`Column ${d.columns.length + 1}`)
  d.rows.forEach((r) => r.push(''))
  setTableData(d)
}

const removeTableColumn = (ci: number) => {
  const d = parseTableData()
  d.columns.splice(ci, 1)
  d.rows.forEach((r) => r.splice(ci, 1))
  setTableData(d)
}

const dragState = ref<{ type: 'row' | 'col'; fromIdx: number } | null>(null)

const onDragStart = (type: 'row' | 'col', idx: number, e: DragEvent) => {
  dragState.value = { type, fromIdx: idx }
  e.dataTransfer?.setData('text/plain', '')
}

const onDrop = (type: 'row' | 'col', toIdx: number) => {
  const s = dragState.value
  if (!s || s.type !== type || s.fromIdx === toIdx) { dragState.value = null; return }
  const d = parseTableData()
  if (type === 'row') {
    const row = d.rows.splice(s.fromIdx, 1)[0] ?? []
    d.rows.splice(toIdx, 0, row)
  } else {
    const hdr = d.columns.splice(s.fromIdx, 1)[0] ?? ''
    d.columns.splice(toIdx, 0, hdr)
    d.rows.forEach((r) => { const cell = r.splice(s.fromIdx, 1)[0] ?? ''; r.splice(toIdx, 0, cell) })
  }
  setTableData(d)
  dragState.value = null
}
</script>

<template>
  <FieldSlot :field-key="f.name">
    <div :class="['fve-slot-control', 'table-editor-wrapper', { 'fve-disabled': f.isLocked(f.name) }]">
      <div class="table-editor-scroll">
        <table class="table-editor-tbl">
          <thead>
            <tr>
              <th class="table-editor-handle-cell"></th>
              <th
                v-for="(col, ci) in parseTableData().columns"
                :key="ci"
                class="table-editor-col-th"
                draggable="true"
                @dragstart="onDragStart('col', ci, $event)"
                @dragover.prevent
                @drop.prevent="onDrop('col', ci)"
              >
                <div class="table-editor-col-header">
                  <span class="table-editor-drag-icon pi pi-bars"></span>
                  <InputText
                    :modelValue="col"
                    @update:modelValue="(v: string | undefined) => updateTableHeader(ci, v ?? '')"
                    size="small"
                    class="table-editor-header-input"
                    placeholder="Header"
                  />
                  <Button
                    icon="pi pi-trash"
                    size="small"
                    text
                    severity="danger"
                    :disabled="parseTableData().columns.length <= 1"
                    @click="removeTableColumn(ci)"
                  />
                </div>
              </th>
              <th class="table-editor-add-col-cell">
                <Button icon="pi pi-plus" size="small" text title="Add column" @click="addTableColumn" />
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, ri) in parseTableData().rows"
              :key="ri"
              draggable="true"
              @dragstart="onDragStart('row', ri, $event)"
              @dragover.prevent
              @drop.prevent="onDrop('row', ri)"
            >
              <td class="table-editor-handle-cell">
                <span class="table-editor-drag-icon pi pi-bars"></span>
              </td>
              <td v-for="(cell, ci) in row" :key="ci" class="table-editor-cell">
                <InputText
                  :modelValue="cell"
                  @update:modelValue="(v: string | undefined) => updateTableCell(ri, ci, v ?? '')"
                  size="small"
                  class="w-full"
                />
              </td>
              <td class="table-editor-add-col-cell">
                <Button
                  icon="pi pi-trash"
                  size="small"
                  text
                  severity="danger"
                  :disabled="parseTableData().rows.length <= 1"
                  @click="removeTableRow(ri)"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <Button label="Add Row" icon="pi pi-plus" size="small" text class="mt-2" @click="addTableRow" />
    </div>
  </FieldSlot>
</template>

<style scoped>
.table-editor-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0;
  width: 100%;
}

.table-editor-scroll {
  overflow-x: auto;
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  border-radius: 6px;
}

.table-editor-tbl {
  border-collapse: collapse;
  min-width: 100%;
}

.table-editor-tbl th,
.table-editor-tbl td {
  border: 1px solid var(--p-inputtext-border-color, #d1d5db);
  padding: 4px;
  vertical-align: middle;
  white-space: nowrap;
}

.table-editor-tbl th {
  background: var(--p-surface-100, #f3f4f6);
}

.table-editor-handle-cell {
  width: 24px;
  text-align: center;
  cursor: grab;
}

.table-editor-add-col-cell {
  width: 32px;
  text-align: center;
  border: none !important;
  background: transparent !important;
}

.table-editor-col-th {
  cursor: grab;
}

.table-editor-col-header {
  display: flex;
  align-items: center;
  gap: 4px;
}

.table-editor-header-input {
  flex: 1;
  min-width: 80px;
}

.table-editor-drag-icon {
  color: var(--p-text-muted-color, #9ca3af);
  font-size: 0.75rem;
  cursor: grab;
}

.table-editor-cell {
  min-width: 100px;
}

/* Dark mode: --p-surface-100..300 are fixed ramp points (always pale, in
   both themes), not semantic tokens — see docs/developer/styleguide.md.
   These shade a header/stripe distinguishable from its surrounding panel,
   so (unlike the content-background swaps above) they need an explicit
   dark surface rather than matching the panel exactly. */
.dark-mode .table-editor-tbl th {
  background: var(--p-surface-800, #1e293b);
}
</style>
