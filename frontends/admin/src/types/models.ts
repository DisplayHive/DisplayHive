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
  /** "W:H" — which Layout variation this screen is sent (best match); default 16:9. */
  aspect_ratio?: string
  /** Clockwise rotation of everything the screen renders, in degrees: 0, 90, 180 or 270 (-90). */
  rotation?: number
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
  /** JSON-encoded list of {name, hex} — a named color palette scoped to this Design, offered as quick-pick swatches by every other color field in its editor. */
  default_colors?: string
  /** JSON-encoded list of extra aspect ratios ("W:H") — 16:9 is the implicit base. */
  aspect_ratios?: string
  /** Progress indicator along the bottom of the screen (fills over a scene's duration). */
  indicator_enabled?: boolean
  indicator_color?: string
  indicator_height?: number | null
  indicator_direction?: 'ltr' | 'rtl'
  is_default?: boolean
}

/** One named swatch in a Design's default color palette. */
export interface DefaultColor {
  /** Stable id (independent of `name`, which can be renamed) — referenced by other color fields as "@default:<id>". */
  id: string
  name: string
  hex: string
}

/** One color stop in a Gradient, position in percent (0-100). */
export interface GradientStop {
  /** Bare hex (no '#'), matching PrimeVue ColorPicker's convention. Also the fallback used when `ref` doesn't resolve (a different Design than the one it was picked in, or a since-deleted color). */
  color: string
  position: number
  /** Percent (0-100, default 100/opaque). Lets stacked gradient layers show through to layers listed after them. */
  opacity?: number
  /** If set, `color` is a last-picked fallback and the live value should come from that Design's default_colors instead, when currently editing/rendering that same Design (a Gradient is shared across Designs, so this only applies there). */
  ref?: { design_id: number; color_id: string }
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
  /** Member containers of the base (16:9) variant. */
  container_ids?: number[]
  /** Per-aspect-ratio variants beyond the base, each with its own member containers. */
  variations?: LayoutVariation[]
  /** True if at least one Contenttype is bound to this Layout. */
  in_use?: boolean
  /** The Contenttypes bound to this Layout. */
  contenttypes?: { id: number; name: string }[]
}

/** A Layout at one non-base aspect ratio. */
export interface LayoutVariation {
  aspect_ratio: string
  container_ids: number[]
}

/** A container's position/size (vh/vw) at one aspect ratio. */
export interface ContainerPositionData {
  top: number
  left: number
  width: number
  height: number
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
  /** When true, the Layout editor blocks drag/resize on this container. */
  locked?: boolean
  /** Field handler used to render `default_content` as this container's fallback. */
  default_field_handler?: string | null
  /** Shown (via default_field_handler's transform) when no active scene targets this container. */
  default_content?: string | null
  /** Dedicated positions at non-base aspect ratios, keyed by ratio ("4:3"); missing = falls back to the base top/left/width/height. */
  positions?: Record<string, ContainerPositionData>
  /** When true, screens show this container (its Container Design background/border) even with no content. */
  show_when_empty?: boolean
  /** True if at least one Contenttype field (TagConfig) renders into it. */
  in_use?: boolean
}

/** A content item (content element) in the system. */
export interface Content {
  id: number
  title: string
  contenttype_name?: string
}

/** Something that uses a media file (see application/admin/media/usage.py). */
export interface MediaUsage {
  kind: 'content' | 'contenttype' | 'layout' | 'container' | 'design' | 'setting'
  id: number
  name: string
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
  /** Where the file is used; empty = unused. */
  used_by?: MediaUsage[]
}

/** An SSO (OpenID Connect) identity linked to an admin account. */
export interface AdminUserIdentity {
  id: number
  issuer: string
  subject: string
  /** Name of the login provider it last logged in through (null if since deleted). */
  provider_name: string | null
  /** Email / username from the provider — for telling identities apart only. */
  display_name: string | null
  created_at: string | null
  last_login_at: string | null
}

/** An admin account (password and/or SSO login). */
export interface AdminUser {
  id: number
  username: string
  is_active?: boolean
  /** Set by an admin: the account must pick a new password on its next login. */
  must_change_password?: boolean
  /** Whether username + password login is allowed (off for SSO-created accounts). */
  password_login_allowed?: boolean
  /** Whether a password is set at all. */
  has_password?: boolean
  identities?: AdminUserIdentity[]
  created_at?: string | null
  last_login_at?: string | null
}

/** An SSO login provider (Settings → Login providers). The secret never comes back. */
export interface AuthProvider {
  id: number
  slug: string
  name: string
  issuer: string
  client_id: string
  has_client_secret: boolean
  scopes: string
  enabled: boolean
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
