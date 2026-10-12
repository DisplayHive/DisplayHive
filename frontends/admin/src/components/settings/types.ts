/** The system settings the server sends with `displayhive:admin:stc:admin_settings`. */
export interface SystemSettings {
  welcome_headline?: string
  welcome_text?: string
  hide_community_links?: boolean | string
  hide_helping_hand?: boolean | string
  hide_powered_by?: boolean | string
  hide_demo_mode?: boolean | string
  hide_user_tours?: boolean | string
  hide_admin_tours?: boolean | string
  content_edit_preview_size?: number | string
  content_list_preview_size?: number | string
  screen_status_indicator?: boolean | string
  screen_reload_at?: string
  screen_log_max_age_hours?: number | string
  screen_log_max_rows?: number | string
  timezone?: string
}

/** "true" / true both mean on (the server stores settings as strings). */
export const isTrue = (v: boolean | string | undefined): boolean => v === true || v === 'true'
