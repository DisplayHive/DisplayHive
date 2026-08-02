"""Socket.IO connection / authentication handler for devices.

Implements the handshake flow (adoption key, admin key, screen devicekey).
Split out of the devices ``sockethandlers`` module because it is a large,
self-contained concern separate from admin device management.
"""

import logging

logger = logging.getLogger(__name__)


def _mask(key):
    """Return a short, non-sensitive prefix of a handshake key for logging."""
    if key and len(key) > 8:
        return key[:8] + '...'
    return key


def register_device_connection_handlers(socketio, app, db):
    """Register the socket ``connect`` authentication/adoption handler."""
    from flask import request
    from datetime import datetime, timezone
    from application.utils import emit_screengroups_update
    from application.auth import user_from_token

    @socketio.on('connect')
    def _auto_join_admins_on_connect(auth=None):
        """Socket connection authentication handler.

        Adoption & Login workflow:
        - If client sends 'adoptionkey' in handshake:
          * Server validates adoptionkey (matches Device.registration_token)
          * If valid: generate/return devicekey via socket event, accept connection
          * If invalid: raise ConnectionRefusedError('invalid_key')
        - If client sends a 'token' in the handshake `auth` payload:
          * Server verifies the JWT (see application.auth.decode_token)
          * If valid: Admin connection → join 'admins' room
          * If invalid/expired: raise ConnectionRefusedError('invalid_token')
        - If client sends 'devicekey' in handshake:
          * If devicekey in DB and active: Screen connection → authenticate
          * If invalid: raise ConnectionRefusedError('invalid_key')
        - If none of the above provided: raise ConnectionRefusedError('no_key')
        """
        sid_info = getattr(request, "sid", None)
        adoptionkey = None
        devicekey = None
        token = (auth or {}).get('token') if isinstance(auth, dict) else None
        try:
            # Check query string / handshake args for adoptionkey or devicekey
            if getattr(request, 'args', None):
                adoptionkey = request.args.get('adoptionkey')
                devicekey = request.args.get('devicekey')
                # NB: never log the raw handshake args — they carry the
                # adoptionkey / devicekey / admin token in cleartext.
        except Exception as e:
            logger.warning("[Auth] Error reading keys from request.args: %s", e)

        logger.info("[Auth] Connection attempt - sid=%s, adoptionkey=%s, devicekey=%s, token=%s",
                    sid_info, _mask(adoptionkey), _mask(devicekey), 'present' if token else None)

        # --- ADOPTION FLOW: client connects with adoptionkey ---
        if adoptionkey:
            try:
                from application.models import Device
                import uuid

                # Find device with matching registration_token
                dev = db.session.execute(
                    db.select(Device).where(Device.registration_token == adoptionkey)
                ).scalar_one_or_none()

                if dev:
                    # Valid adoption key: generate devicekey if not already present
                    if not dev.devicekey or dev.devicekey == '':
                        dev.devicekey = str(uuid.uuid4())
                        dev.is_active = True
                        try:
                            db.session.commit()
                            logger.info("[Auth] Generated devicekey for adoption: %s", _mask(dev.devicekey))
                        except Exception as e:
                            logger.warning("[Auth] Error committing devicekey: %s", e)
                            db.session.rollback()
                            raise ConnectionRefusedError('db_error')

                    # Send devicekey to client
                    try:
                        socketio.emit('displayhive:devices:stc:adoption_approved', {
                            'success': True,
                            'devicekey': dev.devicekey
                        }, room=sid_info)
                        logger.info("[Auth] Adoption approved, sent devicekey to client")
                    except Exception as e:
                        logger.warning("[Auth] Error emitting adoption_approved: %s", e)

                    # Accept connection (client will reconnect with devicekey)
                    return
                else:
                    # Invalid adoption key
                    logger.info("[Auth] Connection rejected: invalid adoptionkey")
                    raise ConnectionRefusedError('invalid_key')
            except ConnectionRefusedError:
                raise
            except Exception:
                logger.exception("[Auth] Connection rejected: error during adoption")
                raise ConnectionRefusedError('db_error')

        # Admin connection: client presents a JWT obtained via /admin/api/auth/login
        if token:
            admin_user = user_from_token(app, db, token)
            if not admin_user:
                logger.info("[Auth] Connection rejected: invalid/expired/revoked admin token")
                raise ConnectionRefusedError('invalid_token')

            try:
                from flask_socketio import join_room
                from application.socketio_handlers.auth import register_admin_session
                join_room('admins')
                # Remember the token so require_admin() can re-validate it on
                # every subsequent event, not just at connect time.
                register_admin_session(sid_info, token)
                socketio.emit('displayhive:admin:stc:joined_admins', {'success': True}, room=sid_info)
                logger.info("[Auth] Admin connection accepted (user=%s), joined 'admins' room", admin_user.username)
            except Exception as e:
                logger.warning("[Auth] Error joining admins room: %s", e)

            # Proactively send screengroups and other admin payloads
            try:
                emit_screengroups_update(socketio, app, db, room=sid_info)
            except Exception:
                logger.debug('Failed to send initial screengroups update to admin sid=%s', sid_info, exc_info=True)

            # Report security-sensitive config state (insecure defaults, debug mode, etc.)
            try:
                socketio.emit(
                    'displayhive:system:stc:security_status',
                    {
                        'secret_key_is_default': bool(app.config.get('SECRET_KEY_IS_DEFAULT')),
                        'cors_wildcard': bool(app.config.get('CORS_WILDCARD')),
                        'sqlite_in_use': bool(app.config.get('SQLITE_IN_USE')),
                        'debug_enabled': bool(app.config.get('DEBUG_ENABLED')),
                    },
                    room=sid_info,
                )
            except Exception:
                logger.debug('Failed to send security_status to admin sid=%s', sid_info, exc_info=True)
            return  # Accept connection for admin

        elif devicekey:
            # Screen connection: validate devicekey against DB
            # Note: Socket.IO handlers already run within Flask app context
            try:
                from application.models import Device
                dev = db.session.execute(
                    db.select(Device).where(Device.devicekey == devicekey)
                ).scalar_one_or_none()

                if dev:
                    # Check if device is active - reject gracefully if deactivated
                    # Note: We must ACCEPT the connection first, send the rejection message,
                    # and then disconnect. If we raise ConnectionRefusedError directly,
                    # polling transports often mask the error message as a generic 500/403
                    # or transport error, and the client never sees the "device_inactive" reason.
                    if not getattr(dev, 'is_active', True):
                        logger.info("[Auth] Device is inactive (devicekey=%s) - sending rejection and disconnecting", _mask(devicekey))
                        try:
                            # Send rejection message first
                            socketio.emit('displayhive:devices:stc:connection_rejected', {
                                'reason': 'device_inactive',
                                'message': 'Device is deactivated by administrator'
                            }, room=sid_info)

                            # Disconnect in background to allow message to flush
                            def disconnect_delayed(sid):
                                """Disconnect an inactive device after a brief delay so the rejection message can flush."""
                                socketio.sleep(0.5)
                                try:
                                    logger.info("[Auth] Disconnecting inactive device %s", sid)
                                    # Use the underlying server disconnect method which takes sid
                                    if hasattr(socketio, 'server'):
                                        socketio.server.disconnect(sid)
                                    else:
                                        # Fallback for standard Flask-SocketIO disconnect (context-aware, might fail here)
                                        # usually flask_socketio.disconnect(sid=sid) works
                                        from flask_socketio import disconnect
                                        disconnect(sid=sid)
                                except Exception as e:
                                    logger.warning("[Auth] Error disconnecting %s: %s", sid, e)

                            socketio.start_background_task(disconnect_delayed, sid_info)
                            # Return to accept the connection momentarily so the emit is sent
                            return
                        except Exception as e:
                            logger.warning("[Auth] Error handling inactive device rejection: %s", e)
                            return

                    # Device exists and is active - proceed with normal setup
                    try:
                        # Join the device-specific room so it can receive targeted messages
                        from flask_socketio import join_room
                        join_room(f'device_{devicekey}')
                        logger.info("[Auth] Device joined room: device_%s", devicekey)
                    except Exception as e:
                        logger.warning("[Auth] Error joining device room: %s", e)
                    # Detect impersonation flag from handshake args; if impersonating
                    # we should not persist presence state or register the session in
                    # the authoritative connected_devices/connected_screens mapping.
                    is_impersonation = False
                    try:
                        if getattr(request, 'args', None):
                            imp = request.args.get('impersonate')
                            if imp and str(imp).lower() in ('1', 'true', 'yes', 'on'):
                                is_impersonation = True
                    except Exception:
                        is_impersonation = False

                    if is_impersonation:
                        logger.info("[Auth] Impersonation connection detected for devicekey=%s — will not update presence or notify admins for this session", _mask(devicekey))

                    # Update device record and register tracking only for non-impersonation sessions
                    if not is_impersonation:
                        try:
                            dev.is_online = True
                            dev.last_connected_at = datetime.now(timezone.utc)
                            if getattr(dev, 'registration_token', None):
                                dev.registration_token = None
                            db.session.commit()
                            # Re-fetch dev so screen_id and all attributes are fresh after commit
                            from application.models import Device as _Device
                            dev = db.session.execute(
                                db.select(_Device).where(_Device.devicekey == devicekey)
                            ).scalar_one_or_none() or dev
                            logger.info("[Auth] Updated device record: is_online=True, cleared registration_token")
                        except Exception as e:
                            logger.warning("[Auth] Error updating device record: %s", e)
                            db.session.rollback()

                        # Register this devicekey in connected_devices tracking
                        try:
                            from application.socketio_handlers.lifecycle import connected_devices
                            connected_devices[devicekey] = {'sid': sid_info, 'connected_at': datetime.now(timezone.utc)}
                            logger.info("[Auth] Registered in connected_devices tracking")
                        except Exception as e:
                            logger.warning("[Auth] Error registering in connected_devices: %s", e)

                    # Emit authentication ack to client regardless of impersonation
                    try:
                        socketio.emit('displayhive:devices:stc:device_authenticated', {'success': True, 'device_id': dev.id}, room=sid_info)
                        logger.info("[Auth] Screen connection accepted (device_id=%s, devicekey=%s)", dev.id, _mask(devicekey))
                    except Exception as e:
                        logger.warning("[Auth] Error emitting device_authenticated: %s", e)

                    # Send device config immediately after authentication
                    try:
                        from application.socketio_handlers.devconfig import send_upd_deviceconfig
                        from application.models import Screen
                        from sqlalchemy.orm import joinedload

                        screen = None
                        if dev.screen_id:
                            screen = db.session.execute(
                                db.select(Screen)
                                .options(joinedload(Screen.screengroups))
                                .where(Screen.id == dev.screen_id)
                            ).unique().scalar_one_or_none()

                        send_upd_deviceconfig(socketio, db, room=f'device_{devicekey}', device=dev, screen=screen)
                        logger.info("[Auth] Sent upd_deviceconfig to device_%s", devicekey)

                        # Register in connected_screens only for non-impersonation
                        if not is_impersonation and screen:
                            try:
                                from application.socketio_handlers.lifecycle import connected_screens
                                w = getattr(screen, 'resolution_width', None)
                                h = getattr(screen, 'resolution_height', None)
                                connected_screens[screen.name] = {
                                    'sid': sid_info,
                                    'connected_at': datetime.now(timezone.utc),
                                    'resolution': (w, h) if w and h else None,
                                    'devicekey': devicekey
                                }
                                logger.info("[Auth] Registered screen '%s' in connected_screens", screen.name)
                            except Exception as e:
                                logger.warning("[Auth] Error registering in connected_screens: %s", e)

                        # Send content if screen is assigned. Always send content
                        # so impersonation sessions receive the current playlist
                        # and can play the slideshow, even though we do not
                        # persist presence for them.
                        try:
                            from application.socketio_handlers.upd_content import send_upd_content
                            send_upd_content(socketio, db, screens=[screen])
                            if is_impersonation:
                                logger.info("[Auth] Sent upd_content to impersonation session device_%s", devicekey)
                            else:
                                logger.info("[Auth] Sent upd_content to device_%s", devicekey)
                        except Exception as e:
                            logger.warning("[Auth] Error sending upd_content: %s", e)
                    except Exception:
                        logger.exception("[Auth] Error sending device config")
                    # Notify admins of device connection (only for non-impersonation sessions)
                    if not is_impersonation:
                        try:
                            from application.admin.devices.helper import get_registered_devices_handler
                            devices_data = get_registered_devices_handler(app, socketio, db)
                            socketio.emit('displayhive:devices:stc:devices_upd_devicelist', {'devices': devices_data}, room='admins')
                            logger.info("[Auth] Sent device list update to admins")
                        except Exception as e:
                            logger.warning("[Auth] Error sending device list to admins: %s", e)

                        # Also emit updated admin screen list
                        try:
                            from application.admin.screens.helper import emit_admin_screen
                            emit_admin_screen(socketio, app, db)
                        except Exception as e:
                            logger.warning("[Auth] Error sending screen list to admins: %s", e)

                        # Fire online alerts
                        try:
                            from application.admin.alerting.sender import fire_alert
                            device_label = dev.name or devicekey[:8]
                            if screen:
                                fire_alert(db, 'screen_online', f"Screen '{screen.name}'")
                            fire_alert(db, 'device_online', f"Device '{device_label}'")
                        except Exception:
                            logger.exception("[Auth] Error firing online alerts")

                    return  # Accept connection for valid device
                else:
                    # Invalid or inactive devicekey
                    logger.info("[Auth] Connection rejected: devicekey not found or inactive (devicekey=%s)", _mask(devicekey))
                    raise ConnectionRefusedError('invalid_key')
            except ConnectionRefusedError:
                raise
            except Exception:
                # On unexpected errors treat as auth failure
                logger.exception("[Auth] Connection rejected: DB error during devicekey validation")
                raise ConnectionRefusedError('db_error')
        else:
            # No adoptionkey, token or devicekey provided: reject connection
            logger.info("[Auth] Connection rejected: no key provided")
            raise ConnectionRefusedError('no_key')
