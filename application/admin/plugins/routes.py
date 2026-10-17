"""HTTP side of the plugin system.

    POST /admin/api/plugins/upload        multipart: file             (needs plugins.manage)
    GET  /api/plugins/_active                                          the active plugins' frontends
    GET  /api/plugins/<id>/assets/<version>/<path>                     a plugin's admin/screen/asset files
    ANY  /api/plugins/<id>/<subpath>                                   a route the plugin registered itself

Flask accepts no new routes once the first request was served, so plugins that are loaded while the server
runs cannot add routes of their own. They register under their id with ``api.routes.add`` and this one
dispatcher finds them.
"""

import logging
import mimetypes
from pathlib import Path

from flask import Response, abort, jsonify, request, send_file

from application.plugins import service
from application.plugins.manifest import PluginError
from application.plugins.registry import registry

logger = logging.getLogger(__name__)

_MULTIPART_OVERHEAD = 1024 * 1024
SERVED_FOLDERS = ('admin', 'screen', 'assets')


def register_plugin_routes(app, db):
    from application.admin.auth.routes import require_http_right, require_jwt_auth

    @app.route('/admin/api/plugins/upload', methods=['POST'])
    @require_jwt_auth(app)
    @require_http_right(app, 'plugins.manage')
    def admin_plugins_upload():
        from application.plugins import installer
        request.max_content_length = installer.MAX_DOWNLOAD_BYTES + _MULTIPART_OVERHEAD
        upload = request.files.get('file')
        if upload is None or not upload.filename:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        try:
            upload.stream.seek(0)
            data = upload.stream.read(installer.MAX_DOWNLOAD_BYTES + 1)
            manifest = service.install_zip(db, app, data, sha256=(request.form.get('sha256') or '').strip())
        except PluginError as problem:
            return jsonify({'success': False, 'error': str(problem)}), 400
        except Exception:
            from application.socketio_handlers.actions import new_error_reference, unexpected_error_message
            reference = new_error_reference()
            logger.exception('plugin upload failed (reference %s)', reference)
            return jsonify({'success': False, 'error': f'Installation failed. {unexpected_error_message(reference)}',
                            'error_ref': reference}), 500
        finally:
            upload.close()
        app.extensions['plugins_push']()
        from application.admin.plugins.sockethandlers import refresh_content_of
        from application.plugins.host import socketio
        refresh_content_of(socketio(), app, db, list(manifest.fieldhandlers))
        return jsonify({'success': True, 'id': manifest.id, 'version': manifest.version})

    @app.route('/api/plugins/_active')
    def plugins_active():
        response = jsonify({'plugins': service.public_list(app)})
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.route('/api/plugins/<plugin_id>/assets/<version>/<path:name>')
    def plugin_asset(plugin_id, version, name):
        info = registry.loaded().get(plugin_id)
        if info is None or info.get('version') != version:
            abort(404)
        parts = Path(name).parts
        if not parts or parts[0] not in SERVED_FOLDERS or '..' in parts:
            abort(404)
        base = Path(info['directory']).resolve()
        target = (base / name).resolve()
        if base not in target.parents or not target.is_file():
            abort(404)
        mimetype = 'text/javascript' if target.suffix in ('.js', '.mjs') else (mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        response = send_file(target, mimetype=mimetype, conditional=True)
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response

    @app.route('/api/plugins/<plugin_id>/<path:subpath>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
    def plugin_route(plugin_id, subpath):
        entry = registry.route(plugin_id, subpath)
        if entry is None:
            abort(404)
        methods, view = entry
        if request.method not in methods:
            abort(405)
        result = view()
        return result if isinstance(result, (Response, tuple)) else jsonify(result)
