/**
 * Shared domain model interfaces.
 *
 * Import from here instead of re-declaring the same shapes per view.
 * All non-primary-key fields are optional so views that receive a subset
 * of the payload from the backend still type-check correctly.
 */

/** A physical device (client hardware) that connects to the socket server. */
export interface Device {
  id: number
  /** Null when the caller lacks the device.showkey right (masked server-side). */
  devicekey: string | null
  is_online: boolean
  name?: string | null
  is_active?: boolean
  screen_id?: number | null
  screen_name?: string | null
  created_at?: string
  last_connected_at?: string
  find?: boolean
  max_resolution_width?: number | null
  max_resolution_height?: number | null
}

/** A registered display screen in the system. */
export interface Screen {
  id: number
  name: string
  resolution?: string
  timestr?: string
  debug?: boolean
  monitoring_enabled?: boolean
  template_id?: number | null
  attached_device?: Device | null
}

/** A group of screens sharing the same content schedule. */
export interface Screengroup {
  id: number
  name: string
  screen_ids?: number[]
  screens_count?: number
  content_count?: number
  is_one_screen?: boolean
}

/** A display template (HTML/CSS layout with named containers). */
export interface Template {
  id: number
  name: string
  description?: string
  html?: string
  css?: string
  is_default?: boolean
  container_count?: number
}

/** A content item (content element) in the system. */
export interface Content {
  id: number
  title: string
  contenttype_name?: string
}

/** A global magic tag (key/value pair) injected into templates and other content. */
export interface MagicTag {
  id: number
  name: string
  value: string
  description?: string
}

/** An item stored in the media library. */
export interface MediaItem {
  id: number
  title: string
  filename: string
  mimetype: string
  folder?: string
  preview_url?: string
  url?: string
  tags?: string[]
}

/** An admin account (username/password login). */
export interface AdminUser {
  id: number
  username: string
  is_active?: boolean
  created_at?: string | null
  last_login_at?: string | null
}

/** A single checkable right in the user-rights system, e.g. "media.upload". */
export interface RightDefinition {
  key: string
  category: string
  label: string
}

/** A group of users; can be nested via parent_group_id. Holds only allow grants. */
export interface RightsGroup {
  id: number
  name: string
  parent_group_id: number | null
  is_superadmin: boolean
  /** Right keys directly granted to this group (not including inherited ones). */
  rights: string[]
}

/** A single override value for a user right: allow/deny always win, inherit falls through to groups. */
export type RightOverrideValue = 'allow' | 'deny' | 'inherit'

/** An admin user's rights-system state, as returned to the Groups & Rights admin page. */
export interface UserRightsRow {
  id: number
  username: string
  group_ids: number[]
  overrides: Record<string, 'allow' | 'deny'>
  effective_rights: Record<string, boolean>
}
