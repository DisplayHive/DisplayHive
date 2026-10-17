# Plugins

Field handlers (what a field of a content type can hold: text, image, icon, countdown, …) and integrations
(Pretalx) are plugins. You manage them on the **Plugins** page (*Admin → System → Plugins*, `/plugins`). Switching a
plugin on or off, installing, updating and removing take effect at once — no restart.

## What is there

| Plugin | Kind | On by default |
|---|---|---|
| Short text, Long text, Rich text (WYSIWYG), Number, Checkbox, Link / URL, Image, Icon, Arrow, Date / time, Countdown, Marquee, Table, Raw HTML, iFrame | Field handler | yes |
| Pretalx | Integration | no — switched on automatically if you used Pretalx before |

Each field handler is a plugin of its own, so you can switch off the ones you do not need (they then disappear from
the field-handler lists). **Bundled plugins can be switched off but not removed.**

## What happens when you switch one off

* A content type that uses the plugin's handler keeps the field. Content shows it **empty** until the plugin is
  switched on again; nothing that was entered is deleted.
* The plugin's page and menu entry go away. Its tables and data stay in the database.
* Content is rendered again and the screens reload, so the change shows up everywhere within seconds.

## Installing

Under *Install a plugin*:

* **Catalog** — if your administrator set `PLUGIN_CATALOG_URL` (a `catalog.json`), its plugins are listed with an
  *Install* / *Update* button.
* **A ZIP file** — upload it. The checksum field is optional here.
* **A download link** — give the link and the SHA-256 checksum the author published. The file is checked against it
  before anything is unpacked.

A plugin is program code and runs with the rights of the server. There is no signature check: install plugins only
from authors you trust. A new version replaces the old one; the old one stays in the server's memory until a restart.

## Restart

Python cannot take code out of a running server. When you switch off, replace or remove plugins, the page shows how
many old versions are still held in memory and offers **Restart server**. Nothing is wrong until you restart; the
restart only frees the memory. Screens and admin pages reconnect on their own.

## Removing

An installed plugin can be removed: its files are deleted and it disappears from the list. What it stored in the
database (for example the Pretalx addresses) is kept and is there again if you install it again.

## Rights

*View Plugins page* and *Install, switch on and off, update and remove plugins; restart the server*
(`plugins.page`, `plugins.manage`). Plugins add rights of their own (Pretalx: *View Pretalx page*, *Manage Pretalx
settings / API URLs*), prefixed with the plugin's id.

## Export and import

A plugin that owns data offers it as an extra node in the [export and import](import-export.md) tree. Ticked, it
goes along. On import the node appears only if the plugin is active on the importing instance.

## Command line

```bash
flask dh plugins list
flask dh plugins disable displayhive.marquee
flask dh plugins install ./weather-1.2.0.zip --sha256 <checksum>
flask dh plugins remove acme.weather
```

Changes made on the command line are picked up by a running server after a restart; the Plugins page switches at
run time.

## Writing a plugin

See the [developer guide](../developer/plugins.md).
