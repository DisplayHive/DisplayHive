# Tour content

This folder holds the bundled package(s) the Guided Tour's "Load Tour Content"
action imports (Settings page, and optionally on first boot of a fresh
install — see `_maybe_auto_import_tour_content` in `app.py`).

It works exactly like `examplecontent/` (Demo Mode), just for the Tour
feature: `tourdesc.json` is a JSON array of
`{id, filename, name, description, logo}` entries, and each `filename` must
be a zip sitting next to it in this folder containing a top-level `db.json`
(export-format payload) plus an optional `media/` folder.

`tourdesc.json` currently ships empty (`[]`) — no tour package exists yet.
To add one:

1. Build the desired "defined state" (content types, layouts, content,
   screens, ...) for the mini-tours to point at, through the running admin UI.
2. Export it via the Im-/Export page (full export, or select the relevant
   entities) to produce a `db.json` + `media/` zip.
3. Save it here as e.g. `tour.zip`, and add an entry to `tourdesc.json`
   pointing at it (see `examplecontent/exampledesc.json` for the shape).

Importing this package is destructive: it fully resets the database and
media folder to the package's contents, the same as Demo Mode.
