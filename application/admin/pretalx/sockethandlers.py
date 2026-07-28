import json as json_module
import logging
from datetime import datetime, timezone, timedelta

import requests
from flask import request

logger = logging.getLogger(__name__)


def register_admin_pretalx_handlers(socketio, app, db):
    """Register socket handlers and background poller for the Pretalx admin page."""
    from application.socketio_handlers.auth import require_right

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _ensure_utc(dt):
        if dt is None:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    def _url_to_dict(u):
        next_fetch = None
        if u.polling_enabled and u.polling_interval:
            last_attempt = _ensure_utc(u.last_success or u.last_failure)
            if last_attempt is None:
                next_fetch = datetime.now(timezone.utc).isoformat()
            else:
                next_fetch = (last_attempt + timedelta(seconds=u.polling_interval)).isoformat()
        return {
            'id': u.id,
            'name': u.name,
            'url': u.url,
            'polling_enabled': u.polling_enabled,
            'polling_interval': u.polling_interval,
            'last_success': _ensure_utc(u.last_success).isoformat() if u.last_success else None,
            'last_failure': _ensure_utc(u.last_failure).isoformat() if u.last_failure else None,
            'is_valid': u.is_valid,
            'next_fetch': next_fetch,
            'has_cache': u.cache is not None,
        }

    def _emit_urls(sid=None):
        from application.models import PretalxApiUrl
        try:
            urls = db.session.execute(db.select(PretalxApiUrl)).scalars().all()
            payload = {'urls': [_url_to_dict(u) for u in urls]}
            socketio.emit('displayhive:admin:pretalx:stc:urls', payload, room=sid or None)
        except Exception:
            logger.exception('Failed to emit pretalx urls')

    # ── Content refresh after successful fetch ────────────────────────────────

    def _rerender_and_push(affected_ids):
        """Re-render the given ContentElement ids and push the update to screens."""
        import json
        from application.models import ContentElement
        from application.admin.content.helper import render_content_fields
        from application.socketio_handlers.upd_content import send_upd_content

        for mc_id in affected_ids:
            try:
                mc = db.session.get(ContentElement, mc_id)
                if not mc:
                    continue
                tagconfigs = getattr(mc.contenttype, 'tagconfigs', None) or []
                rendered_by_container = render_content_fields(tagconfigs, mc.serialized_input or '{}', db=db)
                mc.html = json.dumps(rendered_by_container, ensure_ascii=False)
                db.session.add(mc)
            except Exception:
                logger.exception('Failed to re-render content element %s', mc_id)

        db.session.commit()
        send_upd_content(socketio, db, content_ids=affected_ids)
        logger.info('Pushed screen update for content ids=%s', affected_ids)

    def _pretalx_tagconfigs_by_contenttype():
        """Return {contenttype_id: [pretalx_table field_name, ...]} for all such TagConfigs."""
        from application.models import TagConfig
        pretalx_tcs = db.session.execute(
            db.select(TagConfig).where(TagConfig.field_handler == 'pretalx_table')
        ).scalars().all()
        ct_fields: dict[int, list[str]] = {}
        for tc in pretalx_tcs:
            ct_fields.setdefault(tc.contenttype_id, []).append(tc.field_name)
        return ct_fields

    def _refresh_pretalx_content(url_id):
        """Re-render every ContentElement that references url_id and push to screens.

        Must be called inside an active app context (e.g. from _fetch_url).
        """
        try:
            from application.models import ContentElement

            ct_fields = _pretalx_tagconfigs_by_contenttype()
            if not ct_fields:
                return

            url_id_str = str(url_id)
            content_elements = db.session.execute(
                db.select(ContentElement).where(
                    ContentElement.contenttype_id.in_(list(ct_fields.keys()))
                )
            ).scalars().all()

            # Keep only those whose serialized_input references this endpoint
            affected_ids = []
            for mc in content_elements:
                try:
                    si = json_module.loads(mc.serialized_input or '{}')
                except Exception:
                    continue
                field_names = ct_fields.get(mc.contenttype_id, [])
                if any(str(si.get(fn, '')) == url_id_str for fn in field_names):
                    affected_ids.append(mc.id)

            if not affected_ids:
                logger.debug('No content items reference endpoint id=%s', url_id)
                return

            logger.info('Re-rendering %s content item(s) for endpoint id=%s', len(affected_ids), url_id)
            _rerender_and_push(affected_ids)

        except Exception:
            logger.exception('Failed to refresh pretalx content for url %s', url_id)
            try:
                db.session.rollback()
            except Exception:
                pass

    def _refresh_all_pretalx_content():
        """Re-render every ContentElement that has any pretalx_table field and push to screens."""
        try:
            from application.models import ContentElement

            ct_fields = _pretalx_tagconfigs_by_contenttype()
            if not ct_fields:
                return

            content_elements = db.session.execute(
                db.select(ContentElement).where(ContentElement.contenttype_id.in_(list(ct_fields.keys())))
            ).scalars().all()

            affected_ids = [mc.id for mc in content_elements]
            if not affected_ids:
                return

            logger.info('Re-rendering %s content item(s) after settings change', len(affected_ids))
            _rerender_and_push(affected_ids)
        except Exception:
            logger.exception('Failed to refresh all pretalx content')
            try:
                db.session.rollback()
            except Exception:
                pass

    # ── Background fetch ──────────────────────────────────────────────────────

    def _fetch_url(url_id):
        """Fetch a Pretalx API URL, update cache and timestamps."""
        from application.models import PretalxApiUrl, PretalxApiCache

        # Read the URL string inside its own context to avoid holding the
        # session open during the HTTP request.
        fetch_target = None
        with app.app_context():
            try:
                obj = db.session.get(PretalxApiUrl, url_id)
                if not obj:
                    return
                fetch_target = obj.url
            except Exception:
                logger.exception('Failed to load pretalx url %s', url_id)
                return

        success = False
        json_data = None
        try:
            resp = requests.get(fetch_target, timeout=15)
            resp.raise_for_status()
            json_data = resp.json()
            success = True
        except Exception:
            pass

        with app.app_context():
            try:
                obj = db.session.get(PretalxApiUrl, url_id)
                if not obj:
                    return
                now = datetime.now(timezone.utc)
                if success:
                    obj.last_success = now
                    obj.is_valid = True
                    if obj.cache:
                        obj.cache.cached_json = json_module.dumps(json_data)
                        obj.cache.fetched_at = now
                    else:
                        db.session.add(PretalxApiCache(
                            api_url_id=url_id,
                            cached_json=json_module.dumps(json_data),
                            fetched_at=now,
                        ))
                    db.session.commit()
                    _emit_urls()
                    _refresh_pretalx_content(url_id)
                else:
                    obj.last_failure = now
                    db.session.commit()
                    _emit_urls()
            except Exception:
                logger.exception('Failed to persist pretalx fetch result for %s', url_id)
                db.session.rollback()

    # ── Polling loop ──────────────────────────────────────────────────────────

    def _polling_loop():
        from application.models import PretalxApiUrl
        while True:
            socketio.sleep(10)
            ids_to_fetch = []
            try:
                with app.app_context():
                    now_utc = datetime.now(timezone.utc)
                    try:
                        rows = db.session.execute(
                            db.select(PretalxApiUrl).where(PretalxApiUrl.polling_enabled == True)
                        ).scalars().all()
                    except Exception:
                        db.session.rollback()
                        continue

                    for u in rows:
                        last = _ensure_utc(u.last_success or u.last_failure)
                        if last is None or (now_utc - last).total_seconds() >= u.polling_interval:
                            ids_to_fetch.append(u.id)
            except Exception:
                logger.exception('Pretalx polling loop error')

            for uid in ids_to_fetch:
                socketio.start_background_task(_fetch_url, uid)

    socketio.start_background_task(_polling_loop)

    # ── Pretalx settings helpers ──────────────────────────────────────────────

    def _get_or_create_settings():
        from application.models import PretalxSettings
        obj = db.session.execute(db.select(PretalxSettings)).scalar_one_or_none()
        if obj is None:
            obj = PretalxSettings()
            db.session.add(obj)
            db.session.flush()
        return obj

    def _settings_to_dict(obj):
        return {
            'time_format':       obj.time_format,
            'end_of_day':        obj.end_of_day,
            'no_session_text':   obj.no_session_text,
            'coming_up_text':    obj.coming_up_text,
            'invalid_data_text': obj.invalid_data_text,
            'sim_datetime':      obj.sim_datetime or '',
        }

    def _emit_settings(sid=None):
        try:
            payload = {'settings': _settings_to_dict(_get_or_create_settings())}
            socketio.emit('displayhive:admin:pretalx:stc:settings', payload, room=sid or None)
        except Exception:
            logger.exception('Failed to emit pretalx settings')

    # ── Socket event handlers ─────────────────────────────────────────────────

    @socketio.on('displayhive:admin:pretalx:cts:get_settings')
    @require_right('pretalx.page')
    def handle_get_settings(data=None):
        _emit_settings(request.sid)

    @socketio.on('displayhive:admin:pretalx:cts:save_settings')
    @require_right('pretalx.manage')
    def handle_save_settings(data=None):
        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        obj = _get_or_create_settings()
        if 'time_format' in data:
            obj.time_format = (data['time_format'] or 'HH:mm').strip()
        if 'end_of_day' in data:
            obj.end_of_day = (data['end_of_day'] or '23:59').strip()
        if 'no_session_text' in data:
            obj.no_session_text = (data['no_session_text'] or '').strip()
        if 'coming_up_text' in data:
            obj.coming_up_text = (data['coming_up_text'] or '').strip()
        if 'invalid_data_text' in data:
            obj.invalid_data_text = (data['invalid_data_text'] or '').strip()
        sim_changed = False
        if 'sim_datetime' in data:
            new_sim = (data['sim_datetime'] or '').strip() or None
            if new_sim != obj.sim_datetime:
                sim_changed = True
            obj.sim_datetime = new_sim
        db.session.commit()
        _emit_settings(request.sid)
        if sim_changed:
            def _bg_refresh_all():
                with app.app_context():
                    _refresh_all_pretalx_content()
            socketio.start_background_task(_bg_refresh_all)
        return {'ok': True}

    @socketio.on('displayhive:admin:pretalx:cts:get_urls')
    @require_right('pretalx.page')
    def handle_get_urls(data=None):
        _emit_urls(request.sid)

    @socketio.on('displayhive:admin:pretalx:cts:add_url')
    @require_right('pretalx.manage')
    def handle_add_url(data=None):
        from application.models import PretalxApiUrl, PretalxApiCache

        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        name = (data.get('name') or '').strip()
        url = (data.get('url') or '').strip()
        if not name or not url:
            return {'ok': False, 'error': 'name and url are required'}

        is_valid = False
        json_data = None
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            json_data = resp.json()
            is_valid = True
        except Exception:
            pass

        now = datetime.now(timezone.utc)
        obj = PretalxApiUrl(
            name=name,
            url=url,
            polling_enabled=False,
            polling_interval=300,
            is_valid=is_valid,
            last_success=now if is_valid else None,
            last_failure=now if not is_valid else None,
        )
        db.session.add(obj)
        db.session.flush()

        if is_valid and json_data is not None:
            db.session.add(PretalxApiCache(
                api_url_id=obj.id,
                cached_json=json_module.dumps(json_data),
                fetched_at=now,
            ))

        db.session.commit()
        _emit_urls(request.sid)
        return {'ok': True, 'is_valid': is_valid}

    @socketio.on('displayhive:admin:pretalx:cts:update_url')
    @require_right('pretalx.manage')
    def handle_update_url(data=None):
        from application.models import PretalxApiUrl

        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        url_id = data.get('id')
        if url_id is None:
            return {'ok': False, 'error': 'id is required'}

        obj = db.session.get(PretalxApiUrl, url_id)
        if not obj:
            return {'ok': False, 'error': 'Not found'}

        if 'name' in data:
            obj.name = (data['name'] or '').strip() or obj.name
        if 'polling_enabled' in data:
            obj.polling_enabled = bool(data['polling_enabled'])
        if 'polling_interval' in data:
            obj.polling_interval = max(30, int(data['polling_interval']))

        db.session.commit()
        _emit_urls(request.sid)
        return {'ok': True}

    @socketio.on('displayhive:admin:pretalx:cts:delete_url')
    @require_right('pretalx.manage')
    def handle_delete_url(data=None):
        from application.models import PretalxApiUrl

        if not data or not isinstance(data, dict):
            return {'ok': False, 'error': 'Invalid payload'}
        url_id = data.get('id')
        if url_id is None:
            return {'ok': False, 'error': 'id is required'}

        obj = db.session.get(PretalxApiUrl, url_id)
        if obj:
            db.session.delete(obj)
            db.session.commit()

        _emit_urls(request.sid)
        return {'ok': True}

    @socketio.on('displayhive:admin:pretalx:cts:get_rooms')
    @require_right('pretalx.page')
    def handle_get_rooms(data=None):
        from application.models import PretalxApiUrl
        url_id = (data or {}).get('id')
        if not url_id:
            return {'ok': False, 'rooms': []}
        obj = db.session.get(PretalxApiUrl, url_id)
        if not obj or not obj.cache:
            return {'ok': True, 'rooms': []}
        cached = json_module.loads(obj.cache.cached_json)
        rooms: set[str] = set()
        for day in cached.get('schedule', {}).get('conference', {}).get('days', []):
            rooms.update(day.get('rooms', {}).keys())
        return {'ok': True, 'rooms': sorted(rooms)}

    @socketio.on('displayhive:admin:pretalx:cts:get_cache')
    @require_right('pretalx.page')
    def handle_get_cache(data=None):
        from application.models import PretalxApiUrl

        if not data or not isinstance(data, dict):
            return
        url_id = data.get('id')
        if url_id is None:
            return

        obj = db.session.get(PretalxApiUrl, url_id)
        if not obj or not obj.cache:
            socketio.emit(
                'displayhive:admin:pretalx:stc:cache',
                {'ok': False, 'error': 'No cache available'},
                room=request.sid,
            )
            return

        socketio.emit(
            'displayhive:admin:pretalx:stc:cache',
            {
                'ok': True,
                'url_id': url_id,
                'name': obj.name,
                'cached_json': obj.cache.cached_json,
                'fetched_at': _ensure_utc(obj.cache.fetched_at).isoformat() if obj.cache.fetched_at else None,
            },
            room=request.sid,
        )
