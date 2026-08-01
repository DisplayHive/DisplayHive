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

/** A Design: the single global screen skin (HTML/CSS). Exactly one is active/default. */
export interface Design {
  id: number
  name: string
  description?: string
  html?: string
  css?: string
  /** Backdrop: body background-color, a background image URL (beneath any Gradients), and how that image tiles/scales/fades. */
  background_color?: string
  background_image_url?: string
  background_repeat?: string
  background_size?: string
  /** Percent (0-100, default 100/fully visible) — faked via a color overlay, see render_backdrop_css(). */
  background_opacity?: number
  /** Animated canvas background effect (beautiful-backgrounds), registry key or '' for none — see utils/backgroundEffects.ts. Not part of the Backdrop CSS; delivered to the screen client as data. */
  background_effect?: string
  /** JSON-encoded settings object for background_effect, opaque here — parsed/edited via the registry's per-effect param list. */
  background_effect_settings?: string
  is_default?: boolean
}

/** One color stop in a Gradient, position in percent (0-100). */
export interface GradientStop {
  color: string
  position: number
  /** Percent (0-100, default 100/opaque). Lets stacked gradient layers show through to layers listed after them. */
  opacity?: number
}

/**
 * A reusable, named CSS gradient — a Design can apply several, stacked as
 * layered `background-image` values. Covers the three widely-supported
 * gradient functions and their `repeating-` variants.
 */
export interface Gradient {
  id: number
  name: string
  type: 'linear' | 'radial' | 'conic'
  repeating: boolean
  /** Direction (linear) or start angle (conic), in degrees. Unused for radial. */
  angle: number
  /** Radial only: 'circle' | 'ellipse' (blank = CSS default). */
  shape: string
  /** Radial only: e.g. 'closest-side' (blank = CSS default). */
  size: string
  /** Percent (0-100); radial/conic `at <x> <y>` origin. */
  position_x: number
  position_y: number
  stops: GradientStop[]
}

/** A named, reusable group of positioned ContentContainers. */
export interface Layout {
  id: number
  name: string
  description?: string
  container_ids?: number[]
  /** True if at least one Contenttype is bound to this Layout. */
  in_use?: boolean
}

/** A standalone content container: a screen-relative position (vh/vw) and size. */
export interface ContentContainer {
  id: number
  name: string
  order?: number
  top: number
  left: number
  width: number
  height: number
  /** Field handler used to render `default_content` as this container's fallback. */
  default_field_handler?: string | null
  /** Shown (via default_field_handler's transform) when no active scene targets this container. */
  default_content?: string | null
  /** True if at least one Contenttype field (TagConfig) renders into it. */
  in_use?: boolean
}

/** A content item (content element) in the system. */
export interface Content {
  id: number
  title: string
  contenttype_name?: string
}

/** A global magic tag injected into templates and other content.
 *
 * A 'text' tag renders `value` literally. A 'list' tag renders the value of
 * the entry in `value_list_id` whose key matches `value`.
 */
export interface MagicTag {
  id: number
  name: string
  value: string
  description?: string
  type: 'text' | 'list'
  value_list_id: number | null
}

/** A single key/value entry belonging to a MagicTagValueList. */
export interface MagicTagValueListEntry {
  id: number
  key: string
  value: string
}

/** A named list of key/value entries a 'list'-type MagicTag can draw from. */
export interface MagicTagValueList {
  id: number
  name: string
  entries: MagicTagValueListEntry[]
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
