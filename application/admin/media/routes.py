"""HTTP route for media uploads: multipart, streamed to disk.

    POST /admin/api/media/upload
    Authorization: Bearer <jwt>         (needs media.upload)
    multipart/form-data: file, folder?, title?, tags?
    → {success, id, filename} | {success: false, error}

One file per request, so the browser can report progress per file. The
file part never sits in memory: DataDirRequest (below, installed in app.py)
makes Werkzeug write it to a temp file in DATA_DIR's staging directory while
it arrives, and storage.ingest_upload() then hard-links it into the media
folder. Replaces the old base64-over-Socket.IO upload, which held every file
in memory several times over and forced Socket.IO's message limit to 100 MB
for every connection.
"""

import logging
import tempfile

from flask import Request, current_app, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from application.admin.media import storage

logger = logging.getLogger(__name__)

# Room for the multipart framing and the small text fields around the file.
_MULTIPART_OVERHEAD = 1024 * 1024


class DataDirRequest(Request):
    """Flask request class that spools every uploaded file to DATA_DIR.

    Werkzeug's default keeps small parts in memory and writes larger ones to
    the system temp dir, which may be a small tmpfs and is shared with every
    local user. Here every file part goes to UPLOAD_STAGING_DIR (0700,
    application/paths.py) — on the same filesystem as the media folder, so
    a finished upload is moved in with a hard link instead of a copy. The
    temp file is deleted when the request closes it.
    """

    def _get_file_stream(self, total_content_length, content_type, filename=None, content_length=None):
        staging = current_app.config.get('UPLOAD_STAGING_DIR')
        return tempfile.NamedTemporaryFile('wb+', dir=staging, prefix='upload-')


def register_media_routes(app, db):
    from application.admin.auth.routes import require_jwt_auth, require_http_right

    @app.route('/admin/api/media/upload', methods=['POST'])
    @require_jwt_auth(app)
    @require_http_right(app, 'media.upload')
    def admin_media_upload():
        # Checked against Content-Length before anything is read, and enforced
        # while streaming for chunked requests.
        request.max_content_length = storage.MAX_FILE_SIZE + _MULTIPART_OVERHEAD
        too_large = jsonify({
            'success': False,
            'error': f'File too large (max {storage.MAX_FILE_SIZE // 1024 // 1024} MB)',
        }), 413
        try:
            upload = request.files.get('file')
            form = request.form
        except RequestEntityTooLarge:
            return too_large
        if upload is None or not upload.filename:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        try:
            upload.stream.flush()  # ingest_upload links the file by path
            media = storage.ingest_upload(
                db,
                current_app.config,
                staged_path=upload.stream.name,
                filename=upload.filename,
                folder_path=form.get('folder', ''),
                title=form.get('title', ''),
                tags=form.get('tags', ''),
                mime_type=upload.mimetype or '',
            )
        except storage.UploadError as e:
            return jsonify({'success': False, 'error': str(e)}), e.status
        except Exception:
            db.session.rollback()
            logger.exception('media upload failed')
            return jsonify({'success': False, 'error': 'Upload failed'}), 500
        finally:
            upload.close()

        return jsonify({'success': True, 'id': media.id, 'filename': media.filename})
