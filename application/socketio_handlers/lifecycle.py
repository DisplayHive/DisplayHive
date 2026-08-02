"""Socket.IO handlers for lifecycle events (connect, disconnect)."""

import logging
from datetime import datetime, timezone

from flask import request

logger = logging.getLogger(__name__)


# In-memory tracking of connected screens and devices
connected_screens = {}  # {screen_name: {'sid': sid, 'connected_at': datetime, 'resolution': (w, h), 'devicekey': key}}
connected_devices = {}  # {devicekey: {'sid': sid, 'connected_at': datetime}}


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

        # Find and remove connected_devices entry for this SID
        disconnected_devicekey = None
        for key, info in list(connected_devices.items()):
            if info.get('sid') == sid:
                disconnected_devicekey = key
                del connected_devices[key]
                logger.info("[Disconnect] Device '%s' removed from tracking", key)
                break

        # Find and remove connected_screens entry for this SID
        disconnected_screen_name = None
        for name, info in list(connected_screens.items()):
            if info.get('sid') == sid:
                disconnected_screen_name = name
                del connected_screens[name]
                logger.info("[Disconnect] Screen '%s' removed from tracking", name)
                break

        # Update device record: mark offline
        if disconnected_devicekey:
            try:
                # If the socket was connected in impersonation mode, avoid
                # changing authoritative online/offline state for the device.
                try:
                    if getattr(request, 'args', None):
                        imp = request.args.get('impersonate')
                        if imp and str(imp).lower() in ('1', 'true', 'yes', 'on'):
                            logger.info("[Disconnect] Impersonation session - skipping offline update for %s", disconnected_devicekey)
                            # already removed from connected_devices mapping above
                            return
                except Exception:
                    logger.debug('Failed to read impersonate flag on disconnect for devicekey=%s', disconnected_devicekey, exc_info=True)
                from application.models import Device
                dev = db.session.execute(
                    db.select(Device).where(Device.devicekey == disconnected_devicekey)
                ).scalar_one_or_none()

                if dev:
                    dev.is_online = False
                    dev.last_connected_at = datetime.now(timezone.utc)
                    db.session.commit()
                    logger.info("[Disconnect] Device '%s' marked offline in DB", disconnected_devicekey)

                    # Fire offline alerts
                    try:
                        from application.admin.alerting.sender import fire_alert
                        device_label = dev.name or disconnected_devicekey[:8]
                        if disconnected_screen_name:
                            fire_alert(db, 'screen_offline', f"Screen '{disconnected_screen_name}'")
                        fire_alert(db, 'device_offline', f"Device '{device_label}'")
                    except Exception:
                        logger.exception("[Disconnect] Error firing offline alerts")

                    # Notify admins of device offline status
                    try:
                        from application.admin.devices.helper import get_registered_devices_handler
                        devices_data = get_registered_devices_handler(app, socketio, db)
                        socketio.emit('displayhive:devices:stc:devices_upd_devicelist', {'devices': devices_data}, room='admins')
                        logger.info("[Disconnect] Sent device list update to admins")
                    except Exception:
                        logger.exception("[Disconnect] Error sending device list")

                    # Update screen list for admin UI
                    try:
                        from application.admin.screens.helper import emit_admin_screen
                        emit_admin_screen(socketio, app, db)
                    except Exception:
                        logger.exception("[Disconnect] Error sending screen list")

            except Exception:
                logger.exception("[Disconnect] Error updating device offline status")
                db.session.rollback()

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
