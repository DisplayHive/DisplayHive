"""HTTP route to install an icon library from an uploaded ZIP / TAR file.

    POST /admin/api/icons/upload
    multipart/form-data: file, id, label, license?
    → {success, library} | {success: false, error}      (needs icons.manage)

Like the media upload, the file goes to a temp file in DATA_DIR while it arrives (DataDirRequest) and is
read from there; the installation itself is application/icon_libraries.py.
"""

import logging

from flask import current_app, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from application import icon_libraries

logger = logging.getLogger(__name__)

_MULTIPART_OVERHEAD = 1024 * 1024


def register_icon_routes(app, db, on_change=None):
    from application.admin.auth.routes import require_http_right, require_jwt_auth

    @app.route('/admin/api/icons/upload', methods=['POST'])
    @require_jwt_auth(app)
    @require_http_right(app, 'icons.manage')
    def admin_icons_upload():
        request.max_content_length = icon_libraries.MAX_DOWNLOAD_BYTES + _MULTIPART_OVERHEAD
        try:
            upload = request.files.get('file')
            form = request.form
        except RequestEntityTooLarge:
            return jsonify({'success': False, 'error': 'File too large (max %d MB)' % (icon_libraries.MAX_DOWNLOAD_BYTES // 1024 // 1024)}), 413
        if upload is None or not upload.filename:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        try:
            upload.stream.seek(0)
            data = upload.stream.read(icon_libraries.MAX_DOWNLOAD_BYTES + 1)
            if len(data) > icon_libraries.MAX_DOWNLOAD_BYTES:
                return jsonify({'success': False, 'error': 'File too large'}), 413
            meta = icon_libraries.install(
                current_app.config['ICON_LIBRARIES_FOLDER'], (form.get('id') or '').strip(), data,
                label=form.get('label', ''), license=form.get('license', ''), source='upload',
            )
        except icon_libraries.IconLibraryError as problem:
            return jsonify({'success': False, 'error': str(problem)}), 400
        except Exception:
            logger.exception('icon library upload failed')
            return jsonify({'success': False, 'error': 'Installation failed'}), 500
        finally:
            upload.close()
        if on_change:
            on_change()
        return jsonify({'success': True, 'library': meta})
