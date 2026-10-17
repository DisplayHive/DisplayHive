"""The Pretalx page's server side: API addresses, settings, the cache viewer, and the poller that fetches the schedules.

The page talks to the plugin through the plugin dispatcher (``displayhive:plugin:call`` with this plugin's
id and one of the event names below); what the server pushes arrives as
``displayhive:plugin:displayhive.pretalx:stc:<name>``.
"""

import json as json_module
import logging
import threading
from datetime import datetime, timedelta, timezone

from application.security import net
from application.socketio_handlers.actions import Fail, ok

from .models import load_models

logger = logging.getLogger(__name__)

PLUGIN_ID = 'displayhive.pretalx'
PAGE_RIGHT = 'displayhive.pretalx.page'
MANAGE_RIGHT = 'displayhive.pretalx.manage'
POLL_EVERY_SECONDS = 10


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


def _settings_to_dict(obj):
    return {
        'time_format': obj.time_format,
        'end_of_day': obj.end_of_day,
        'no_session_text': obj.no_session_text,
        'coming_up_text': obj.coming_up_text,
        'invalid_data_text': obj.invalid_data_text,
        'sim_datetime': obj.sim_datetime or '',
    }


def register_events(api):
    """Register the page's events and start the poller; stopped again when the plugin is switched off."""
    from application.plugins import host

    def db():
        return host.db()

    def models():
        return load_models()

    def pushed(name):
        return f'displayhive:plugin:{PLUGIN_ID}:stc:{name}'

    # ── Pushes ───────────────────────────────────────────────────────────────

    def urls_payload():
        rows = db().session.execute(db().select(models().PretalxApiUrl)).scalars().all()
        return {'urls': [_url_to_dict(u) for u in rows]}

    def push_urls():
        try:
            api.emit_admins(pushed('urls'), urls_payload())
        except Exception:
            logger.exception('Failed to push the Pretalx URLs')

    def get_or_create_settings():
        obj = db().session.execute(db().select(models().PretalxSettings)).scalar_one_or_none()
        if obj is None:
            obj = models().PretalxSettings()
            db().session.add(obj)
            db().session.flush()
        return obj

    def push_settings():
        try:
            api.emit_admins(pushed('settings'), {'settings': _settings_to_dict(get_or_create_settings())})
        except Exception:
            logger.exception('Failed to push the Pretalx settings')

    # ── Content refresh after a successful fetch ─────────────────────────────

    def rerender_and_push(affected_ids):
        """Render the given ContentElement ids again and push the update to the screens."""
        from application.admin.content.helper import render_content_fields
        from application.models import ContentElement
        from application.socketio_handlers.upd_content import send_upd_content

        for content_id in affected_ids:
            try:
                element = db().session.get(ContentElement, content_id)
                if not element:
                    continue
                tagconfigs = getattr(element.contenttype, 'tagconfigs', None) or []
                rendered = render_content_fields(tagconfigs, element.serialized_input or '{}', db=db())
                element.html = json_module.dumps(rendered, ensure_ascii=False)
                db().session.add(element)
            except Exception:
                logger.exception('Failed to render content element %s again', content_id)
        db().session.commit()
        send_upd_content(host.socketio(), db(), content_ids=affected_ids)
        logger.info('Pushed screen update for content ids=%s', affected_ids)

    def pretalx_fields_by_contenttype():
        """``{contenttype_id: [field name, …]}`` of the fields that use the Pretalx handler."""
        from application.models import TagConfig
        rows = db().session.execute(db().select(TagConfig).where(TagConfig.field_handler == 'pretalx_table')).scalars().all()
        by_type: dict[int, list[str]] = {}
        for tc in rows:
            by_type.setdefault(tc.contenttype_id, []).append(tc.field_name)
        return by_type

    def refresh_content(url_id=None):
        """Render again every content element that shows a Pretalx table (of one address, or any) and push it."""
        try:
            from application.models import ContentElement
            by_type = pretalx_fields_by_contenttype()
            if not by_type:
                return
            elements = db().session.execute(
                db().select(ContentElement).where(ContentElement.contenttype_id.in_(list(by_type)))
            ).scalars().all()
            affected = []
            for element in elements:
                if url_id is None:
                    affected.append(element.id)
                    continue
                try:
                    stored = json_module.loads(element.serialized_input or '{}')
                except Exception:
                    logger.warning('Content %s has unreadable serialized_input; skipped', element.id)
                    continue
                if any(str(stored.get(name, '')) == str(url_id) for name in by_type.get(element.contenttype_id, [])):
                    affected.append(element.id)
            if affected:
                logger.info('Rendering %s content item(s) again (endpoint %s)', len(affected), url_id)
                rerender_and_push(affected)
        except Exception:
            logger.exception('Failed to refresh the Pretalx content')
            try:
                db().session.rollback()
            except Exception:
                pass

    # ── Fetching ─────────────────────────────────────────────────────────────

    def fetch_url(url_id):
        """Fetch a Pretalx API address; keep the answer and the time of the attempt."""
        application = host.app()
        m = models()
        target = None
        with application.app_context():
            try:
                obj = db().session.get(m.PretalxApiUrl, url_id)
                if not obj:
                    return
                target = obj.url          # read before the request, so no session is held during it
            except Exception:
                logger.exception('Failed to load pretalx url %s', url_id)
                return

        success, data = False, None
        try:
            response = net.get(target, timeout=15)
            response.raise_for_status()
            data = response.json()
            success = True
        except net.OutboundBlocked as exc:
            logger.warning('Pretalx URL %s (id %s) is not fetched: %s', target, url_id, exc)
        except Exception:
            logger.debug('Pretalx fetch failed for url_id=%s target=%s', url_id, target, exc_info=True)

        with application.app_context():
            try:
                obj = db().session.get(m.PretalxApiUrl, url_id)
                if not obj:
                    return
                now = datetime.now(timezone.utc)
                if success:
                    obj.last_success = now
                    obj.is_valid = True
                    if obj.cache:
                        obj.cache.cached_json = json_module.dumps(data)
                        obj.cache.fetched_at = now
                    else:
                        db().session.add(m.PretalxApiCache(api_url_id=url_id, cached_json=json_module.dumps(data), fetched_at=now))
                    db().session.commit()
                    push_urls()
                    refresh_content(url_id)
                else:
                    obj.last_failure = now
                    db().session.commit()
                    push_urls()
            except Exception:
                logger.exception('Failed to persist the Pretalx fetch result for %s', url_id)
                db().session.rollback()

    # ── The poller ───────────────────────────────────────────────────────────

    stop = threading.Event()

    def polling_loop():
        sio = host.socketio()
        m = models()
        while not stop.is_set():
            sio.sleep(POLL_EVERY_SECONDS)
            if stop.is_set():
                break
            due = []
            try:
                with host.app().app_context():
                    now = datetime.now(timezone.utc)
                    try:
                        rows = db().session.execute(db().select(m.PretalxApiUrl).where(m.PretalxApiUrl.polling_enabled == True)).scalars().all()  # noqa: E712
                    except Exception:
                        logger.exception('Pretalx polling: could not read the URLs to fetch')
                        db().session.rollback()
                        continue
                    for u in rows:
                        last = _ensure_utc(u.last_success or u.last_failure)
                        if last is None or (now - last).total_seconds() >= u.polling_interval:
                            due.append(u.id)
            except Exception:
                logger.exception('Pretalx polling loop error')
            for url_id in due:
                sio.start_background_task(fetch_url, url_id)

    def start_poller():
        # The Socket.IO server exists once the app is fully built; a plugin loaded earlier waits for it.
        def wait_then_run():
            while host.socketio() is None and not stop.is_set():
                threading.Event().wait(0.2)
            if not stop.is_set() and host.app().config.get('PLUGIN_BACKGROUND_JOBS', True):
                polling_loop()
        threading.Thread(target=wait_then_run, name='pretalx-poller', daemon=True).start()

    # (a plain thread would not run under every Socket.IO async mode; the loop itself sleeps with socketio.sleep
    #  and starts its fetches as background tasks, as before.)
    start_poller()
    api.on_unload(stop.set)

    # ── Events ───────────────────────────────────────────────────────────────

    def payload_or_fail(data):
        if not data or not isinstance(data, dict):
            raise Fail('Invalid payload')
        return data

    @api.events.on('get_settings')
    def get_settings(data=None):
        api.require(PAGE_RIGHT)
        return ok(settings=_settings_to_dict(get_or_create_settings()))

    @api.events.on('save_settings')
    def save_settings(data=None):
        api.require(MANAGE_RIGHT)
        data = payload_or_fail(data)
        obj = get_or_create_settings()
        if 'time_format' in data:
            obj.time_format = (data['time_format'] or 'HH:mm').strip()
        if 'end_of_day' in data:
            obj.end_of_day = (data['end_of_day'] or '23:59').strip()
        for key in ('no_session_text', 'coming_up_text', 'invalid_data_text'):
            if key in data:
                setattr(obj, key, (data[key] or '').strip())
        sim_changed = False
        if 'sim_datetime' in data:
            new_sim = (data['sim_datetime'] or '').strip() or None
            sim_changed = new_sim != obj.sim_datetime
            obj.sim_datetime = new_sim
        db().session.commit()
        push_settings()
        if sim_changed:
            def refresh_all():
                with host.app().app_context():
                    refresh_content()
            host.socketio().start_background_task(refresh_all)
        return ok()

    @api.events.on('get_urls')
    def get_urls(data=None):
        api.require(PAGE_RIGHT)
        return ok(**urls_payload())

    @api.events.on('add_url')
    def add_url(data=None):
        api.require(MANAGE_RIGHT)
        data = payload_or_fail(data)
        name = (data.get('name') or '').strip()
        url = (data.get('url') or '').strip()
        if not name or not url:
            raise Fail('name and url are required')
        m = models()

        is_valid, payload = False, None
        try:
            response = net.get(url, timeout=10)
            response.raise_for_status()
            payload = response.json()
            is_valid = True
        except net.OutboundBlocked as exc:
            # Not saved at all: an address DisplayHive would never fetch (see application/security/net.py).
            raise Fail(str(exc))
        except Exception:
            logger.debug('Initial validation fetch failed for new pretalx url=%s', url, exc_info=True)

        now = datetime.now(timezone.utc)
        obj = m.PretalxApiUrl(
            name=name, url=url, polling_enabled=False, polling_interval=300, is_valid=is_valid,
            last_success=now if is_valid else None, last_failure=now if not is_valid else None,
        )
        db().session.add(obj)
        db().session.flush()
        if is_valid and payload is not None:
            db().session.add(m.PretalxApiCache(api_url_id=obj.id, cached_json=json_module.dumps(payload), fetched_at=now))
        db().session.commit()
        push_urls()
        return ok(is_valid=is_valid)

    @api.events.on('update_url')
    def update_url(data=None):
        api.require(MANAGE_RIGHT)
        data = payload_or_fail(data)
        url_id = data.get('id')
        if url_id is None:
            raise Fail('id is required')
        obj = db().session.get(models().PretalxApiUrl, url_id)
        if not obj:
            raise Fail('Not found')
        if 'name' in data:
            obj.name = (data['name'] or '').strip() or obj.name
        if 'polling_enabled' in data:
            obj.polling_enabled = bool(data['polling_enabled'])
        if 'polling_interval' in data:
            obj.polling_interval = max(30, int(data['polling_interval']))
        db().session.commit()
        push_urls()
        return ok()

    @api.events.on('delete_url')
    def delete_url(data=None):
        api.require(MANAGE_RIGHT)
        data = payload_or_fail(data)
        url_id = data.get('id')
        if url_id is None:
            raise Fail('id is required')
        obj = db().session.get(models().PretalxApiUrl, url_id)
        if obj:
            db().session.delete(obj)
            db().session.commit()
        push_urls()
        return ok()

    @api.events.on('get_rooms')
    def get_rooms(data=None):
        api.require(PAGE_RIGHT)
        url_id = (data or {}).get('id')
        if not url_id:
            return {'success': False, 'rooms': []}
        obj = db().session.get(models().PretalxApiUrl, url_id)
        if not obj or not obj.cache:
            return ok(rooms=[])
        cached = json_module.loads(obj.cache.cached_json)
        rooms: set[str] = set()
        for day in cached.get('schedule', {}).get('conference', {}).get('days', []):
            rooms.update(day.get('rooms', {}).keys())
        return ok(rooms=sorted(rooms))

    @api.events.on('get_cache')
    def get_cache(data=None):
        api.require(PAGE_RIGHT)
        url_id = (data or {}).get('id') if isinstance(data, dict) else None
        if url_id is None:
            raise Fail('id is required')
        obj = db().session.get(models().PretalxApiUrl, url_id)
        if not obj or not obj.cache:
            raise Fail('No cache available')
        return ok(
            url_id=url_id, name=obj.name, cached_json=obj.cache.cached_json,
            fetched_at=_ensure_utc(obj.cache.fetched_at).isoformat() if obj.cache.fetched_at else None,
        )
