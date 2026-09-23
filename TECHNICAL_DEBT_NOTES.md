# Technical Debt Notes

Internal corrections/follow-ups to technical-debt analyses. Not part of the
published docs site (`docs/`).

## 2026-09-16 — Correction: "admin_handler decorator half-rolled-out"

**Original finding:** "Halb ausgerollter Error-Handling-Decorator —
admin_handler löst zwar sauber die alte Boilerplate ab, ist aber erst in 7
von 16 Socket-Handler-Modulen übernommen; 129 rohe except Exception-Blöcke
bleiben bestehen."

**Verified (2026-09-16):**

- The "7 of 16 `admin/*/sockethandlers.py` modules use `@admin_handler`"
  count is factually correct as a raw grep, but the framing is misleading.
- The other 9 modules (pretalx, layouts, alerting, designs, settings,
  magictags, plus the devices/matrix/content dispatch stubs) use
  `@require_right(...)` on every handler instead. Per its own docstring
  (`application/socketio_handlers/auth.py:129`), `require_right` **replaces**
  `admin_handler` — it already includes admin auth + exception safety, plus
  a permission check on top. These modules are not unmigrated; they're on
  the stricter of the two equivalent patterns.
- The handlers with *no* admin decorator at all (`handle_device_ping`,
  `handle_upd_viewport` in `devices/management.py`;
  `handle_disconnect`, `logger_connected`, `device_request`,
  `handle_refresh_content`, etc. in `application/socketio_handlers/`) are
  intentionally device-/system-facing, not admin-gated — several are
  explicitly documented as such ("Device-facing (not admin-gated)").
  Wrapping these in `admin_handler` would break the device handshake, not
  fix debt.
- **Do not** blanket-replace `@require_right(...)` with `@admin_handler` —
  that drops the permission check and is a security regression (any
  authenticated admin, regardless of granted rights, could then call the
  handler). See `application/admin/rights/sockethandlers.py:27-41` for the
  correct composition pattern (`_gated_handler`: wraps `admin_handler` and
  adds a right check with an explicit error response) when both an
  admin-handler-style wrapper *and* a right check are wanted together.
- The raw `except Exception` count is real (~100–170 depending on scope,
  in the right ballpark of the reported 129) but is largely unrelated to
  decorator adoption: most are *inner* try/excepts around best-effort
  side effects (firing alerts, notifying admins, pushing config/content)
  inside handlers that are already correctly guarded at the top level.
  Neither `admin_handler` nor `require_right` touches these, since both
  only wrap the outer function.

**Actionable debt that remains:** the sheer number of raw inner
`except Exception` blocks (worst offenders: `application/admin/devices/management.py`
at 25, `application/admin/devices/connection.py` at 21,
`application/admin/pretalx/sockethandlers.py` at 14) — a real cleanup
target, but a different one than "finish the admin_handler rollout".

**Follow-up requested:** next time this analysis runs, add an explicit
auth-coverage check — verify that every socket handler that operates on
admin/privileged data is reachable only via `@admin_handler`,
`@require_right(...)`, or an equivalent composed wrapper (e.g.
`_gated_handler`), and flag any handler touching privileged data that has
neither. This distinguishes real gaps from the device-facing handlers that
are intentionally undecorated.
