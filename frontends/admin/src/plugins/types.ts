import type { Component } from 'vue'

export type FieldValue = string | number | boolean

/**
 * What a plugin's admin side tells the host about one field handler. The host asks these instead
 * of knowing the handlers by name (see docs/developer/plugins.md).
 */
export interface FieldHandlerDef {
  /** The id stored in a content type's field (`TagConfig.field_handler`), the same as the backend's. */
  id: string
  /** Name in the field-handler dropdowns. */
  label: string
  /** The editor of one field; it gets everything through `useFieldContext()`. */
  editor: Component
  /** Props that let one editor component serve several handlers. */
  editorProps?: Record<string, unknown>
  /**
   * The starting values of a field of this handler: its value under `name`, plus the sub-values
   * (`<name>_size`, `<name>__size` …) it keeps next to it. Default: `{ [name]: '' }`.
   */
  defaults?: (name: string) => Record<string, FieldValue>
  /**
   * The value is text a title can be made from ("New <first text>"), and its default length limit.
   */
  titleText?: boolean
  maxLength?: number
  /** Offer the handler in the dropdowns (default true). Off for handlers that exist but are not offered for new fields. */
  selectable?: boolean
  /**
   * A container's default content keeps the field's value packed into ONE string
   * (`ContentContainer.default_content`). `blankDefault` is what that string starts as after the handler
   * is chosen (default: empty). Handlers whose value has several parts pack them as JSON and translate
   * with `container`: `unpack` returns the flat key bag the editor works on, for a field named `default`
   * (`default`, `default__size` …) — the same shape the backend's `default_values` produces — and
   * `pack` turns that bag back into the string. Without `container` the string is the plain value.
   */
  blankDefault?: () => string
  container?: {
    unpack: (packed: string) => Record<string, unknown>
    pack: (fields: Record<string, unknown>) => string
  }
}

/** A page a plugin adds to the admin. */
export interface PageDef {
  /** Route path, e.g. `/pretalx`. */
  path: string
  /** Route name; also the key of its title/icon. */
  name: string
  component: () => Promise<{ default: Component }>
  title: string
  icon: string
  /** The right that lets someone open it (also hides the menu entry). */
  right: string
  /** Menu entry: the group of the Admin menu it appears in. Without it the page has no menu entry. */
  menu?: { group: string; label: string }
}

/** What `register(host)` of a plugin's admin module receives. Everything added is taken back when the plugin is switched off. */
export interface AdminPluginHost {
  readonly pluginId: string
  readonly fieldHandlers: { add: (def: FieldHandlerDef) => void }
  readonly pages: { add: (def: PageDef) => void }
  readonly tours: { add: (def: import('../tour/types').TourDefinition) => void }
  /** For plugins that ship as plain JavaScript (installed ones): the host's building blocks. */
  readonly lib: Record<string, unknown>
}

/** The admin module of a plugin: `export default (host) => { … }`. */
export type AdminPluginModule = { default: (host: AdminPluginHost) => void | Promise<void> }

/** What the server says is active (GET /api/plugins/_active). */
export interface ActivePlugin {
  id: string
  version: string
  name: string
  kind: string
  fieldhandlers: string[]
  admin: string
  screen: string
  source: 'bundled' | 'installed'
}
