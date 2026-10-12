/**
 * Shared value shape for the `pretalx_table` field handler — used by
 * PretalxTableFieldEditor.vue and its two callers (ContentEditView.vue,
 * LayoutCanvasEditor.vue). Kept in a plain module (not the component file)
 * because `<script setup>` SFCs can't have runtime (non-type) exports.
 */
export interface PretalxTableValue {
  url: string
  type: string
  roomname: string
  fields: string
  linecount: number
  author_under_title: boolean
  tracks_by_color: boolean
  today_only: boolean
  separate_days: boolean
  day_prefix: string
  empty_text: string
  tracklist_columns: string
  tracklist_layout: string
  tracklist_exclude: string
  invalid_data_text: string
}

export const blankPretalxTableValue = (): PretalxTableValue => ({
  url: '',
  type: 'list',
  roomname: '',
  fields: '',
  linecount: 10,
  author_under_title: false,
  tracks_by_color: false,
  today_only: false,
  separate_days: false,
  day_prefix: '',
  empty_text: '',
  tracklist_columns: 'name|Name,color|Color',
  tracklist_layout: 'list',
  tracklist_exclude: '',
  invalid_data_text: '',
})
