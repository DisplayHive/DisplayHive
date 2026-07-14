# Real-time content push

This traces exactly what happens between an admin editing content in the
browser and a screen updating — the core loop that makes DisplayHive "live".

## The trace

1. **Admin panel** — a Pinia store action emits a mutation event, e.g.
   `displayhive:admin:cts:update_content_element_active` when toggling a
   content item active/inactive.
2. **Backend handler** — the corresponding function in
   `application/admin/content/mutations.py` receives the event, updates the
   `ContentElement` row in the database, then calls
   `send_upd_content(socketio, db, content_ids=[content_id])`.
3. **Payload build** — `send_upd_content`
   (`application/socketio_handlers/upd_content.py`) resolves which screens
   are affected via the content's screen groups, then builds a
   per-screen payload (`_build_payload`) containing the screen's template
   HTML/CSS, per-container playlists, and rendered content HTML/CSS.
4. **Emit** — for each affected device, it emits:

   ```
   socketio.emit('upd_content', payload, room=f'device_{devicekey}')
   ```

   Each device has its own private Socket.IO room (`device_<devicekey>`),
   so only the screens that actually need the update receive it.
5. **Screen client** — `frontends/screen/ts/screen/socket-handlers.ts`
   listens for `upd_content` and hands the payload to `content-display.ts`,
   which re-renders the affected containers in place.

Every content, template, container, and content-type mutation across
`application/admin/*` follows this same pattern: mutate the DB, then call
`send_upd_content` with the affected content/screen IDs. If you add a new
mutation that should appear on screens immediately, call it the same way.

## Self-refreshing content

Some content re-renders itself after being shown rather than waiting for an
admin edit — for example, an image with randomized selection, or a Pretalx
table that should reflect the current time. These are flagged
`update_after_show: true` in the payload. After displaying such an item, the
screen client emits `displayhive:screen:cts:refresh_content`, handled by
`application/socketio_handlers/refresh_content.py`, which re-renders just
that item and replies with `displayhive:screen:stc:content_updated`. This
path is throttled and scoped so a device can only refresh content belonging
to its own screen.

## Other realtime events worth knowing

- `displayhive:screens:cts:reload_screen` / `reload_all_screens` — forces a
  full reload (`RELOAD` command) rather than an in-place content swap.
- `displayhive:screen:cts:get_server_time` /
  `displayhive:screen:stc:server_time` — clock sync, used by scheduling and
  active-window logic.
- `displayhive:logger:*` — remote log streaming from a device back to the
  admin panel, for the debug panel.
