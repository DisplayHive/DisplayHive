"""Admin socket handlers for the icon libraries (Settings → Icon libraries).

The libraries themselves are application/icon_libraries.py. Downloads run in a background task, one at
a time (a library can be tens of megabytes), and the state is pushed to every admin:

    displayhive:admin:stc:icon_libraries  {catalog: [...], custom: [...], job: {running, current, queue, errors}}
"""

import logging
import threading

from flask import current_app

from application import icon_libraries as icons
from application.socketio_handlers.actions import Fail, admin_action, ok
from application.socketio_handlers.auth import fields

logger = logging.getLogger(__name__)

_job_lock = threading.Lock()
_job = {'running': False, 'current': None, 'queue': [], 'errors': {}}


def build_state(icons_dir: str) -> dict:
    """The payload the Settings card shows: the known libraries with their state, and the own ones."""
    installed = icons.installed(icons_dir)
    catalog_ids = {c['id'] for c in icons.CATALOG}
    catalog = [{
        'id': c['id'], 'label': c['label'], 'license': c['license'], 'homepage': c['homepage'], 'version': c['version'],
        'installed': c['id'] in installed, 'count': installed.get(c['id'], {}).get('count', 0),
        'installed_version': installed.get(c['id'], {}).get('version', ''),
    } for c in icons.CATALOG]
    custom = [{'id': i, **meta} for i, meta in sorted(installed.items()) if i not in catalog_ids]
    with _job_lock:
        job = {'running': _job['running'], 'current': _job['current'], 'queue': list(_job['queue']), 'errors': dict(_job['errors'])}
    return {'catalog': catalog, 'custom': custom, 'job': job}


def register_admin_icon_handlers(socketio, app, db):
    def icons_dir():
        return app.config['ICON_LIBRARIES_FOLDER']

    def push():
        with app.app_context():
            socketio.emit('displayhive:admin:stc:icon_libraries', build_state(icons_dir()), room='admins')

    def run_job(work):
        """Run *work(app)* — a list of ``(library id, callable)`` — one after the other, pushing the state."""
        def task():
            for library_id, fn in work:
                with _job_lock:
                    _job['current'] = library_id
                    _job['errors'].pop(library_id, None)
                push()
                try:
                    with app.app_context():
                        fn()
                except icons.IconLibraryError as problem:
                    with _job_lock:
                        _job['errors'][library_id] = str(problem)
                except Exception:
                    logger.exception('Installing icon library %s failed', library_id)
                    with _job_lock:
                        _job['errors'][library_id] = 'Installation failed (see the server log).'
                with _job_lock:
                    if library_id in _job['queue']:
                        _job['queue'].remove(library_id)
                push()
            with _job_lock:
                _job['running'], _job['current'] = False, None
            push()
        socketio.start_background_task(task)

    def start(ids_and_fns):
        with _job_lock:
            if _job['running']:
                raise Fail('Another installation is still running.')
            _job.update(running=True, current=None, queue=[i for i, _ in ids_and_fns])
        run_job(ids_and_fns)

    app.extensions['icon_libraries_push'] = push

    @socketio.on('displayhive:admin:cts:get_icon_libraries')
    @admin_action('settings.page', 'icons.manage')
    def get_icon_libraries(data=None):
        return ok(**build_state(icons_dir()))

    @socketio.on('displayhive:admin:cts:install_icon_library')
    @admin_action('icons.manage')
    def install_icon_library(data):
        (library_id,) = fields(data, 'id')
        if icons.catalog_entry(library_id) is None:
            raise Fail('Unknown library.')
        start([(library_id, lambda: icons.install_from_catalog(icons_dir(), library_id))])
        return ok()

    @socketio.on('displayhive:admin:cts:install_all_icon_libraries')
    @admin_action('icons.manage')
    def install_all_icon_libraries(data=None):
        have = icons.installed(icons_dir())
        todo = [c['id'] for c in icons.CATALOG if c['id'] not in have]
        if not todo:
            raise Fail('All known libraries are installed.')
        start([(i, (lambda i=i: icons.install_from_catalog(icons_dir(), i))) for i in todo])
        return ok(queued=len(todo))

    @socketio.on('displayhive:admin:cts:install_icon_library_url')
    @admin_action('icons.manage')
    def install_icon_library_url(data):
        library_id, label, license_text, url = fields(data, 'id', 'label', 'license', 'url')
        library_id = (library_id or '').strip()
        if not icons.ID_PATTERN.match(library_id):
            raise Fail('The library id may contain lowercase letters, digits and dashes (at most 40).')
        if not isinstance(url, str) or not url.strip():
            raise Fail('Enter the download link.')
        start([(library_id, lambda: icons.install_from_url(
            icons_dir(), library_id, url.strip(), label=label or library_id, license=license_text or ''))])
        return ok()

    @socketio.on('displayhive:admin:cts:remove_icon_library')
    @admin_action('icons.manage')
    def remove_icon_library(data):
        (library_id,) = fields(data, 'id')
        try:
            icons.remove(icons_dir(), library_id)
        except icons.IconLibraryError as problem:
            raise Fail(str(problem)) from None
        push()
        return ok()
