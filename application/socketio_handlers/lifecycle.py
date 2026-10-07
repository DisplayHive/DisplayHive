"""Socket.IO handlers for lifecycle events (connect, disconnect)."""

import logging
import threading
from datetime import datetime, timezone

from flask import request

logger = logging.getLogger(__name__)


# In-memory tracking of connected screens and devices
connected_screens = {}  # {screen_name: {'sid': sid, 'connected_at': datetime, 'resolution': (w, h), 'devicekey': key}}
connected_devices = {}  # {devicekey: {'sid': sid, 'connected_at': datetime}}
# Hold it for any write, and for every find-then-change sequence: connects,
# disconnects and deactivations run in parallel threads, and a disconnect
# that found a screen's old entry must not delete the entry its reconnect
# has just written. Connect and disconnect also write Device.is_online while
# holding it (see handle_disconnect) — so they must not enter it with an open
# DB transaction, or a SQLite reader could block the holder's commit.
# Plain reads can use a snapshot (list(d.items())) instead.
registry_lock = threading.RLock()


def register_lifecycle_handlers(socketio, app, db):
    """Register all lifecycle socket.io event handlers."""

    # Note: The main connect handler with authentication is now in
    # application/admin/devices/sockethandlers.py
    # This module only maintains disconnect handling and connection tracking

    @socketio.on('disconnect')
    def handle_disconnect(reason):
        """Handle client disconnection - mark device offline and clean up tracking"""
        sid = request.sid
        logger.info('[Disconnect] Client disconnected: %s, reason: %s', sid, reason)

        # Drop any admin token registered for this socket (no-op for non-admins).
        # Done first so it always runs, even on the impersonation early-return below.
        try:
            from application.socketio_handlers.auth import clear_admin_session
            clear_admin_session(sid)
        except Exception:
            logger.debug('Failed to clear admin session for sid=%s on disconnect', sid, exc_info=True)

        # An impersonation session never touches a device's authoritative
        # online state (it isn't registered in connected_devices either).
        is_impersonation = False
        try:
            imp = request.args.get('impersonate') if getattr(request, 'args', None) else None
            is_impersonation = bool(imp) and str(imp).lower() in ('1', 'true', 'yes', 'on')
        except Exception:
            logger.debug('Failed to read impersonate flag on disconnect for sid=%s', sid, exc_info=True)

        # Remove this SID's registry entries and mark its device offline as ONE
        # step under registry_lock. The connect handler sets is_online=True and
        # registers under the same lock, so a screen reconnecting while its old
        # socket is still being torn down can't be overwritten as "offline"
        # (and fire a false offline alert) by that old disconnect.
        disconnected_devicekey = None
        disconnected_screen_name = None
        offline_device_label = None
        db.session.commit()  # no open transaction while holding the lock — see connection.py
        with registry_lock:
            for key, info in list(connected_devices.items()):
                if info.get('sid') == sid:
                    disconnected_devicekey = key
                    del connected_devices[key]
                    break
            for name, info in list(connected_screens.items()):
                if info.get('sid') == sid:
                    disconnected_screen_name = name
                    del connected_screens[name]
                    break

            if disconnected_devicekey and not is_impersonation:
                try:
                    from application.models import Device
                    dev = db.session.execute(
                        db.select(Device).where(Device.devicekey == disconnected_devicekey)
                    ).scalar_one_or_none()
                    if dev:
                        dev.is_online = False
                        dev.last_connected_at = datetime.now(timezone.utc)
                        db.session.commit()
                        offline_device_label = dev.name or disconnected_devicekey[:8]
                except Exception:
                    logger.exception("[Disconnect] Error updating device offline status")
                    db.session.rollback()

        if disconnected_devicekey:
            logger.info("[Disconnect] Device '%s' removed from tracking", disconnected_devicekey)
        if disconnected_screen_name:
            logger.info("[Disconnect] Screen '%s' removed from tracking", disconnected_screen_name)

        # Alerts and admin notifications: outside the lock, they're slow.
        if offline_device_label:
            logger.info("[Disconnect] Device '%s' marked offline in DB", disconnected_devicekey)
            try:
                from application.admin.alerting.sender import fire_alert
                if disconnected_screen_name:
                    fire_alert(db, 'screen_offline', f"Screen '{disconnected_screen_name}'")
                fire_alert(db, 'device_offline', f"Device '{offline_device_label}'")
            except Exception:
                logger.exception("[Disconnect] Error firing offline alerts")

            try:
                from application.admin.devices.helper import get_registered_devices_handler
                devices_data = get_registered_devices_handler(app, socketio, db)
                socketio.emit('displayhive:devices:stc:devices_upd_devicelist', {'devices': devices_data}, room='admins')
                logger.info("[Disconnect] Sent device list update to admins")
            except Exception:
                logger.exception("[Disconnect] Error sending device list")

            try:
                from application.admin.screens.helper import emit_admin_screen
                emit_admin_screen(socketio, app, db)
            except Exception:
                logger.exception("[Disconnect] Error sending screen list")

        # Update screen lastseen timestamp if applicable
        if disconnected_screen_name and not disconnected_screen_name.startswith('preview'):
            try:
                from application.models import Screen
                db.session.execute(
                    db.update(Screen)
                    .where(Screen.name == disconnected_screen_name)
                    .values(lastseen=datetime.now())
                )
                db.session.commit()
                logger.info("[Disconnect] Updated lastseen for screen '%s'", disconnected_screen_name)
            except Exception:
                logger.exception("[Disconnect] Error updating screen lastseen")
                db.session.rollback()
