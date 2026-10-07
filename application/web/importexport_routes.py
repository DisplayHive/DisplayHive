"""HTTP endpoints for export, selective import and demo content.

Thin: authenticate, read the request, call application/admin/importexport/
service.py, build the response. Registered via a function (not a Blueprint)
because the auth decorators (`require_jwt_auth(app)`) take the app.
"""

import os
import zipfile

from flask import jsonify, request, send_file

from application.admin.auth.routes import require_http_right, require_jwt_auth
from application.admin.importexport import service
from application.web import PROJECT_ROOT

_EXAMPLECONTENT_FOLDER = str(PROJECT_ROOT / 'examplecontent')
_EXAMPLECONTENT_DESC = os.path.join(_EXAMPLECONTENT_FOLDER, 'exampledesc.json')


def register_importexport_routes(app, db, socketio):
    def media_folder():
        return app.config['MEDIA_FOLDER']

    def renditions_folder():
        return app.config['MEDIA_RENDITIONS_FOLDER']

    def stage_dir():
        return app.config['UPLOAD_STAGING_DIR']

    @app.route('/admin/export/tree')
    @require_jwt_auth(app)
    @require_http_right(app, 'importexport.export')
    def admin_export_tree():
        """Per-entity-type listing (uuid/id/label) for building the export selection tree."""
        from application.admin.importexport.helper import export_manifest
        return jsonify(export_manifest(app, db))

    @app.route('/admin/export/download', methods=['POST'])
    @require_jwt_auth(app)
    @require_http_right(app, 'importexport.export')
    def admin_export_download():
        """Build a ZIP with db.json + the matching media files for the selected
        entities (selection omitted/null = everything) and stream it."""
        payload = request.get_json(silent=True) or {}
        selection = payload.get('selection')  # dict[type, [uuid,...]] or None = everything
        buf = service.build_export_zip(app, db, selection, media_folder())
        return send_file(
            buf,
            as_attachment=True,
            download_name=service.export_filename(),
            mimetype='application/zip',
        )

    @app.route('/admin/import/preview', methods=['POST'])
    @require_jwt_auth(app)
    @require_http_right(app, 'importexport.import')
    def admin_import_preview():
        """Parse an uploaded ZIP/JSON export and stage it server-side under a
        short-lived token, returning a manifest for the selection tree."""
        from application.admin.importexport.helper import import_manifest, prepare_import_payload

        service.cleanup_stale_stages(stage_dir())

        file = request.files.get('file')
        if not file:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400
        try:
            db_payload, zip_bytes = service.parse_import_upload(file.filename or '', file.read())
        except service.ImportUploadError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        is_legacy = db_payload.get('export_version', 1) < 9
        prepare_import_payload(db_payload)  # backfills uuids + upgrades pre-v4 shape, in place
        token = service.stage_import(stage_dir(), db_payload, zip_bytes)
        manifest = import_manifest(db_payload, app, db)
        return jsonify({'token': token, 'is_legacy': is_legacy, 'manifest': manifest})

    @app.route('/admin/import/confirm', methods=['POST'])
    @require_jwt_auth(app)
    @require_http_right(app, 'importexport.import')
    def admin_import_confirm():
        """Finish a staged import: apply the chosen selection/mode/conflict
        resolution, restore matching media files, then discard the staged upload."""
        payload = request.get_json(silent=True) or {}
        result = service.apply_staged_import(
            stage_dir(), payload.get('token') or '',
            selection=payload.get('selection'),
            mode=payload.get('mode') or 'reset',
            conflict_resolution=payload.get('conflict_resolution') or 'skip',
            app=app, db=db, socketio=socketio,
            media_folder=media_folder(), renditions_folder=renditions_folder(),
        )
        if result is None:
            return jsonify({'success': False,
                            'error': 'Import session expired or not found — please re-upload the file.'}), 400
        return jsonify(result)

    @app.route('/admin/demo/list')
    @require_jwt_auth(app)
    @require_http_right(app, 'importexport.page')
    def admin_demo_list():
        """List the available demo-content packages described in exampledesc.json."""
        if service.demo_mode_hidden(db):
            return "Not Found", 404
        return jsonify(service.load_demo_catalog(_EXAMPLECONTENT_DESC) or [])

    @app.route('/admin/demo/import', methods=['POST'])
    @require_jwt_auth(app)
    @require_http_right(app, 'importexport.import')
    def admin_demo_import():
        """Wipe the database (except user accounts) and media, then import a bundled demo package."""
        if service.demo_mode_hidden(db):
            return "Not Found", 404

        filename = (request.get_json(silent=True) or {}).get('filename') or ''

        catalog = service.load_demo_catalog(_EXAMPLECONTENT_DESC)
        if catalog is None:
            return jsonify({'success': False, 'error': 'No demo content available'}), 404

        # Only filenames explicitly listed in exampledesc.json are allowed — guards
        # against path traversal via an arbitrary `filename` value in the request.
        if filename not in {entry['filename'] for entry in catalog}:
            return jsonify({'success': False, 'error': 'Unknown demo package'}), 400

        zip_path = os.path.join(_EXAMPLECONTENT_FOLDER, filename)
        if not os.path.isfile(zip_path):
            return jsonify({'success': False, 'error': 'Demo package file missing on server'}), 404

        with open(zip_path, 'rb') as f:
            raw = f.read()
        try:
            result = service.restore_from_zip_bytes(
                raw, app=app, db=db, socketio=socketio,
                media_folder=media_folder(), renditions_folder=renditions_folder(),
            )
        except zipfile.BadZipFile:
            return jsonify({'success': False, 'error': 'Invalid ZIP file'}), 400
        return jsonify(result)
