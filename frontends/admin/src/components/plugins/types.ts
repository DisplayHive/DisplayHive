export interface PluginInfo {
  id: string
  name: string
  kind: 'fieldhandler' | 'integration'
  version: string
  description: string
  author: string
  license: string
  homepage: string
  source: 'bundled' | 'installed'
  enabled: boolean
  loaded: boolean
  preinstalled: boolean
  fieldhandlers: string[]
  removable: boolean
  has_admin: boolean
  has_screen: boolean
  requires_host: string
  compatible: boolean
  /** Why a plugin that is switched on is not running. */
  error: string
}

export interface PluginsState {
  plugins: PluginInfo[]
  /** Unloaded plugin versions whose code is still in the server's memory until it restarts. */
  retired: number
  host_version: string
  catalog_url: string
  can_restart: boolean
}

export interface CatalogEntry {
  id: string
  name: string
  version: string
  description: string
  url: string
  sha256: string
  author: string
  license: string
  homepage: string
  kind: string
}
