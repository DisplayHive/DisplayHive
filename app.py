import eventlet
eventlet.monkey_patch()

import os
import json
import logging
from flask import Flask, render_template, request, redirect, send_from_directory, send_file, jsonify

# Configure logging once for the whole application. Individual modules use
# `logging.getLogger(__name__)`; INFO-level operational messages (startup,
# content pushes, etc.) go to stdout as the old print() calls did, while the
# level can be tuned via the LOG_LEVEL environment variable.
logging.basicConfig(
    level=getattr(logging, os.environ.get('LOG_LEVEL', 'INFO').upper(), logging.INFO),
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)
from flask_socketio import SocketIO
from application.socketio_handlers import register_all_handlers
from application.admin.auth.routes import register_auth_routes, require_jwt_auth, require_http_right
from application.auth import ensure_bootstrap_admin
from application.permissions import sync_right_definitions, ensure_superadmin_group
from application.help_content import sync_help_topics

# Import database models
from application.models import db, Design, Device

# Set this variable to "threading", "eventlet" or "gevent" to test the
# different async modes, or leave it set to None for the application to choose
# the best option based on installed packages.
async_mode = None                                                       

# Create Flask app
app = Flask(__name__,
            static_folder='static',
            static_url_path='/static',
            template_folder=os.path.join(os.path.dirname(__file__), 'frontends', 'screen', 'templates'))
# Production: set DATABASE_URL to a PostgreSQL connection string.
# Development / tests: fall back to a local SQLite file.
# TEST_DB_PATH lets each Playwright worker point at its own isolated SQLite file.
_database_url = os.environ.get('DATABASE_URL')
if _database_url:
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_url
else:
    db_path = os.environ.get('TEST_DB_PATH') or os.path.join(app.root_path, 'project.db')
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"
app.config['SQLITE_IN_USE'] = not bool(_database_url)
# enable automatic template reloading so changes in templates are picked up
# without a full process restart
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
_secret_key = os.environ.get('SECRET_KEY', 'secret!')
if _secret_key == 'secret!':
    import warnings
    warnings.warn(
        "SECRET_KEY is using the insecure default 'secret!'. "
        "Set the SECRET_KEY environment variable before deploying to production.",
        RuntimeWarning,
        stacklevel=1,
    )
app.config['SECRET_KEY'] = _secret_key
app.config['SECRET_KEY_IS_DEFAULT'] = _secret_key == 'secret!'
# Overwritten in the `__main__` block below when running via `python app.py`
# with the Werkzeug debugger enabled (never true under gunicorn/production).
app.config['DEBUG_ENABLED'] = False
app.config['LOGGER_ROOM'] = 'logger_room'
# Asset version for cache-busting static files (bump on deploy)
app.config['ASSET_VERSION'] = '1'

# Opt-in dev mode: when set, the screen page loads its JS as an ES module
# straight from the Vite dev server (with HMR) instead of the pre-built
# dist/screen/screen.js bundle. This is deliberately a separate flag from
# FLASK_DEBUG/DEBUG_ENABLED — enabling the Werkzeug debugger for backend work
# should not silently break the screen page for anyone who isn't also running
# `npm run dev` in frontends/screen. Opt in explicitly with SCREEN_DEV_SERVER=1
# and start the Vite dev server yourself (frontends/screen: npm run dev).
app.config['SCREEN_DEV_SERVER'] = os.environ.get('SCREEN_DEV_SERVER', '').lower() in ('1', 'true', 'yes', 'on')
app.config['SCREEN_DEV_SERVER_URL'] = os.environ.get('SCREEN_DEV_SERVER_URL', 'http://localhost:5174')

# When deployed behind a reverse proxy, trust X-Forwarded-* headers so that
# request.remote_addr (used for the login rate limiter) reflects the real
# client IP rather than the proxy's — otherwise every client shares one bucket.
# Only trust the headers when TRUSTED_PROXY_COUNT is set to the number of
# proxies in front of the app, to prevent clients from spoofing the header.
try:
    _trusted_proxies = int(os.environ.get('TRUSTED_PROXY_COUNT', '0') or '0')
except ValueError:
    _trusted_proxies = 0
if _trusted_proxies > 0:
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=_trusted_proxies,
        x_proto=_trusted_proxies,
        x_host=_trusted_proxies,
    )
    logger.info('ProxyFix enabled for %s trusted proxy hop(s)', _trusted_proxies)

# Initialize database
db.init_app(app)

# SQLite does not enforce foreign-key constraints per connection unless this
# pragma is set — without it, every ForeignKey(..., ondelete=...) declared on
# the models is inert on SQLite (only enforced on PostgreSQL). Enable it here
# so FK-constrained deletes fail loudly (IntegrityError) instead of silently
# leaving orphaned rows, matching PostgreSQL's default behavior.
if app.config['SQLITE_IN_USE']:
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, 'connect')
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

# Resolve the set of allowed CORS origins once and share it between flask_cors
# (HTTP /api/*) and Socket.IO below. Defaults to local dev origins only — set
# CORS_ALLOWED_ORIGINS (comma-separated) in production. Use "*" only if you
# explicitly accept that any origin may open a connection.
_cors_env = os.environ.get('CORS_ALLOWED_ORIGINS')
if _cors_env is None:
    _cors_allowed_origins = [
        'http://localhost:5173', 'http://127.0.0.1:5173',
        'http://localhost:5174', 'http://127.0.0.1:5174',
        'http://localhost:5000', 'http://127.0.0.1:5000',
    ]
    # FLASK_PORT overrides the backend's own port (e.g. parallel Playwright
    # test workers). The screen client served by this app connects back to
    # its own origin, so that origin must always be allowed too.
    _own_port = os.environ.get('FLASK_PORT')
    if _own_port and _own_port not in ('5000',):
        _cors_allowed_origins += [f'http://localhost:{_own_port}', f'http://127.0.0.1:{_own_port}']
elif _cors_env.strip() == '*':
    _cors_allowed_origins = '*'
else:
    _cors_allowed_origins = [o.strip() for o in _cors_env.split(',') if o.strip()]
app.config['CORS_WILDCARD'] = _cors_allowed_origins == '*'

# Enable CORS for API endpoints if `flask_cors` is available. This allows
# cross-origin requests (from the admin SPA) to `/api/*` without modifying
# other routes. If `flask_cors` is not installed, continue without failing
# and print a warning so the operator can install it in their environment.
try:
    from flask_cors import CORS

    # Only expose CORS for the API blueprint paths to avoid enabling it
    # unnecessarily for other admin or static routes.
    CORS(app, resources={r"/api/*": {"origins": _cors_allowed_origins}})
    logger.info('CORS enabled for /api/*')
except Exception:
    logger.warning('flask_cors not installed; API CORS not enabled')

# Add custom Jinja filters:
@app.template_filter('from_json')
def from_json_filter(value):
    """Parse a JSON string to a Python dict. Returns {} on error or empty input."""
    try:
        return json.loads(value) if value else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


@app.after_request
def _set_security_headers(resp):
    """Apply conservative security headers to every response.

    A strict Content-Security-Policy is intentionally omitted: both the admin
    SPA and the screen page rely on inline styles/scripts and admin-authored
    template markup, so a wrong CSP would break rendering. These headers are
    safe defaults; setdefault avoids clobbering anything a handler set itself.
    """
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    resp.headers.setdefault('Permissions-Policy', 'geolocation=(), microphone=(), camera=()')
    return resp

# Initialize Socket.IO with optimized connection settings
socketio = SocketIO(
    app,
    async_mode=async_mode,
    logger=False,
    engineio_logger=False,
    ping_interval=25,
    ping_timeout=60,
    reconnection=True,
    reconnection_attempts=10,
    reconnection_delay=1,
    reconnection_delay_max=5,
    cors_allowed_origins=_cors_allowed_origins,
    # Base64 overhead is ~33 %, so 50 MB files arrive as ~67 MB frames.
    # Must be kept in sync with MAX_FILE_SIZE in media/sockethandlers.py.
    max_http_buffer_size=100 * 1024 * 1024,
)

def _startup_step(label, fn):
    """Run a best-effort startup step, logging success/failure without aborting boot.

    Rolls the DB session back on failure so a broken step cannot poison the
    session for the next one.
    """
    try:
        fn()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        logger.warning('Startup step failed (%s): %s', label, e)


def _reset_devices_online():
    db.session.execute(db.update(Device).values(is_online=False))
    db.session.commit()
    logger.info('Reset Device.is_online for all devices to False on startup')


def _enforce_default_design():
    has_default = db.session.execute(
        db.select(Design).where(Design.isDefault == True)
    ).scalar()
    if not has_default:
        d1 = db.session.get(Design, 1)
        if d1:
            d1.isDefault = True
            db.session.commit()
            logger.info('No default design found on startup; set Design ID 1 as default')


def _prune_screen_logs_startup():
    from application.utils import prune_screen_logs
    deleted_by_age, deleted_by_cap = prune_screen_logs(db)
    if deleted_by_age or deleted_by_cap:
        logger.info('Pruned screen_log on startup: %s by age, %s by row cap', deleted_by_age, deleted_by_cap)


# Create database tables
with app.app_context():
    # In production, "alembic upgrade head" (run as ExecStartPre) manages the
    # schema.  db.create_all() is kept here as a convenience for development
    # (SQLite) when alembic is not being used.  It is a no-op when all tables
    # already exist.
    if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql"):
        db.create_all()

    _startup_step('reset Device.is_online', _reset_devices_online)
    _startup_step('enforce default design', _enforce_default_design)
    _startup_step('prune screen_log', _prune_screen_logs_startup)
    _startup_step('ensure bootstrap admin user', lambda: ensure_bootstrap_admin(app, db))
    _startup_step('sync right definitions', lambda: sync_right_definitions(db))
    _startup_step('ensure superadmin group', lambda: ensure_superadmin_group(db))
    _startup_step('sync help topics', lambda: sync_help_topics(db))

# Register Socket.IO event handlers
register_all_handlers(socketio, app, db)

# Register admin authentication HTTP routes (/admin/api/auth/*)
register_auth_routes(app, db)


def _screen_log_retention_loop():
    """Periodically re-enforce screen_log retention while the process is running."""
    from application.utils import prune_screen_logs
    while True:
        socketio.sleep(3600)  # hourly
        try:
            with app.app_context():
                deleted_by_age, deleted_by_cap = prune_screen_logs(db)
                if deleted_by_age or deleted_by_cap:
                    logger.info('Pruned screen_log: %s by age, %s by row cap', deleted_by_age, deleted_by_cap)
        except Exception as e:
            try:
                db.session.rollback()
            except Exception:
                pass
            logger.warning('Failed to prune screen_log: %s', e)


socketio.start_background_task(_screen_log_retention_loop)


@app.route('/')
def index():
    """Serve the screen/kiosk page with the active Design's HTML/CSS background.

    Design is a single, instance-wide setting (no per-screen override).
    Containers are no longer baked into the Design's markup — they're
    created dynamically client-side, positioned via vh/vw, from the
    `upd_content` socket payload (see application/socketio_handlers/upd_content.py).

    Supports an optional ?preview=true&content_id=<id>&container=<name> query string
    so the admin UI can render a single content item for preview without the normal
    playlist logic.
    """
    preview_mode = request.args.get('preview', 'false').lower() == 'true'
    content_id = request.args.get('content_id', type=int)
    preview_container = request.args.get('container', 'maincontent')

    from application.utils import get_default_design
    design = get_default_design(db)

    if design:
        design_html = design.html or ''
        design_css = design.css or ''

        # Substitute {{ var_<name> }} placeholders in HTML and CSS.
        try:
            from application.admin.magictags.helper import load_magic_tags, substitute_magic_tags
            _tvars = load_magic_tags(db)
            design_html = substitute_magic_tags(design_html, _tvars)
            design_css = substitute_magic_tags(design_css, _tvars)
        except Exception:
            pass
    else:
        design_html = ''
        design_css = ''

    try:
        from application.models import SystemSetting as _SS
        _row = db.session.execute(db.select(_SS).where(_SS.key == 'hide_powered_by')).scalar_one_or_none()
        hide_powered_by = (_row.value if _row else '') in ('true', '1', 'yes')
    except Exception:
        hide_powered_by = False

    return render_template('index.html',
                         async_mode=socketio.async_mode,
                         design_html=design_html,
                         design_css=design_css,
                         preview_mode=preview_mode,
                         preview_content_id=content_id,
                         preview_container=preview_container,
                         hide_powered_by=hide_powered_by)

@app.route('/admin')
def admin_redirect():
    """Redirect /admin (no trailing slash) to the admin SPA"""
    return redirect('/admin/')

# =====================================================
# Screen bundle: serve dist/screen/ under /dist/screen/
# =====================================================
@app.route('/dist/screen/<path:filename>')
def screen_dist(filename):
    """Serve compiled screen TypeScript bundle from dist/screen/."""
    dist_dir = os.path.join(os.path.dirname(__file__), 'dist', 'screen')
    return send_from_directory(dist_dir, filename)

# =====================================================
# Screen static assets (CSS etc.) from frontends/screen/assets/
# =====================================================
@app.route('/screen/assets/<path:filename>')
def screen_assets(filename):
    """Serve static screen assets directly from source (not via dist)."""
    assets_dir = os.path.join(os.path.dirname(__file__), 'frontends', 'screen', 'assets')
    return send_from_directory(assets_dir, filename)

# =====================================================
# Logo: serve from root path as well (e.g. /logo_wh.png)
# =====================================================
@app.route('/logo_wh.png')
def logo():
    """Serve the application logo from the admin dist folder."""
    dist_dir = os.path.join(os.path.dirname(__file__), 'dist', 'admin')
    return send_from_directory(dist_dir, 'logo_wh.png')

@app.route('/logo_bl.png')
def logo_bl():
    """Serve the dark/colour logo from the admin dist folder."""
    dist_dir = os.path.join(os.path.dirname(__file__), 'dist', 'admin')
    return send_from_directory(dist_dir, 'logo_bl.png')

# =====================================================
# Admin SPA: Vue 3 + PrimeVue (served under /admin/)
# =====================================================
@app.route('/admin/')
@app.route('/admin/<path:filename>')
def admin_spa(filename='index.html'):
    """Serve files from dist/admin for the Vue 3 + PrimeVue admin SPA."""
    project_root = os.path.dirname(__file__)
    dist_dir = os.path.join(project_root, 'dist', 'admin')
    if not os.path.isdir(dist_dir):
        return "Admin dist not built. Run: nix-shell --run 'cd frontends/admin && npm run build'", 404

    if not filename:
        filename = 'index.html'

    try:
        candidate = os.path.join(dist_dir, filename)
        if os.path.isfile(candidate):
            resp = send_from_directory(dist_dir, filename)
            if filename == 'index.html':
                resp.headers['Cache-Control'] = 'no-store'
            return resp

        # For SPA client-side routing, return index.html for non-asset paths
        _, ext = os.path.splitext(filename)
        if ext:
            return "Not Found", 404

        resp = send_from_directory(dist_dir, 'index.html')
        resp.headers['Cache-Control'] = 'no-store'
        return resp
    except Exception:
        return "Not Found", 404


_MEDIA_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'media')
_EXAMPLECONTENT_FOLDER = os.path.join(os.path.dirname(__file__), 'examplecontent')
_EXAMPLECONTENT_DESC = os.path.join(_EXAMPLECONTENT_FOLDER, 'exampledesc.json')


def _demo_mode_hidden() -> bool:
    """Whether the 'hide_demo_mode' system setting is enabled.

    When enabled, Demo Mode must be unreachable through the API too — not
    just hidden in the nav — so both /admin/demo/* routes check this and
    404 rather than relying on the frontend alone to hide the page.
    """
    from application.models import SystemSetting
    row = db.session.execute(
        db.select(SystemSetting).where(SystemSetting.key == 'hide_demo_mode')
    ).scalar_one_or_none()
    return row is not None and row.value == 'true'


def _broadcast_import_update():
    """Notify already-connected admin tabs and screen clients that the
    database was just replaced/merged via import, so they refetch instead of
    continuing to show stale in-memory state.

    Admin tabs: re-emit the same list broadcasts used after normal
    layout/container/contenttype/content edits, to the whole 'admins' room.
    Screens: force every connected device to hard-reload, which re-runs its
    normal connect-time upd_content flow and picks up everything fresh.
    """
    from application.admin.layouts.helper import emit_layouts_update, emit_containers_update
    from application.admin.contenttypes.helper import emit_contenttypes_update
    from application.admin.content.queries import emit_all_content_element
    from application.utils import reload_devices_on_all_screens

    try:
        emit_layouts_update(socketio, app, db, room='admins')
        emit_containers_update(socketio, app, db, room='admins')
        emit_contenttypes_update(socketio, app, db, room='admins')
        emit_all_content_element(socketio, db, room='admins')
    except Exception:
        logging.exception('Error broadcasting admin update after import')

    try:
        reload_devices_on_all_screens(socketio, db)
    except Exception:
        logging.exception('Error reloading screens after import')


def _restore_from_zip_bytes(raw: bytes) -> dict:
    """Replace the media folder + database from an export-format ZIP's bytes.

    Used by the demo-content importer, which always does a full reset: pull
    db.json out of the zip, wipe the media folder and restore any files it
    contains, then run import_database with selection=None, mode='reset'.
    """
    import io
    import zipfile
    import shutil
    from application.admin.importexport.helper import import_database

    with zipfile.ZipFile(io.BytesIO(raw), 'r') as zf:
        if 'db.json' not in zf.namelist():
            return {'success': False, 'error': 'ZIP does not contain db.json'}

        db_payload = json.loads(zf.read('db.json').decode('utf-8'))

        # Clear existing media files before restoring.
        # shutil.rmtree on the folder itself fails when it is a Docker volume
        # mount point (EBUSY), so delete only the contents.
        if os.path.isdir(_MEDIA_FOLDER):
            for entry in os.scandir(_MEDIA_FOLDER):
                if entry.is_dir(follow_symlinks=False):
                    shutil.rmtree(entry.path)
                else:
                    os.remove(entry.path)
        os.makedirs(_MEDIA_FOLDER, exist_ok=True)

        for name in zf.namelist():
            if name.startswith('media/') and not name.endswith('/'):
                rel = name[len('media/'):]
                target = os.path.join(_MEDIA_FOLDER, rel)
                # Guard against path traversal
                if not os.path.realpath(target).startswith(os.path.realpath(_MEDIA_FOLDER) + os.sep):
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(name) as src, open(target, 'wb') as dst:
                    dst.write(src.read())

    result = import_database(app, db, db_payload, selection=None, mode='reset')
    if result.get('success'):
        _broadcast_import_update()
    return result


# ---------------------------------------------------------------------------
# Selective import staging: a preview/confirm two-step flow. The preview
# parses an uploaded file and stages it server-side under a random token
# (so the full payload doesn't have to round-trip through the browser
# again), returning a manifest for the tree-selection UI; confirm loads the
# staged payload by token and actually applies the import.
# ---------------------------------------------------------------------------

import tempfile
import secrets
import time

_IMPORT_STAGE_DIR = tempfile.gettempdir()
_IMPORT_STAGE_MAX_AGE = 3600  # seconds


def _import_stage_paths(token: str):
    safe_token = ''.join(c for c in (token or '') if c.isalnum() or c == '-')
    return (
        os.path.join(_IMPORT_STAGE_DIR, f'displayhive-import-{safe_token}.json'),
        os.path.join(_IMPORT_STAGE_DIR, f'displayhive-import-{safe_token}.zip'),
    )


def _open_stage_file(path: str, binary: bool):
    """Create a staged-import file with owner-only permissions (0600).

    ``tempfile.gettempdir()`` is a directory shared by every local user on
    the host; a plain ``open(path, 'w')`` would create it at the default
    0o644 (world-readable), exposing staged import contents — which can
    include Device credentials (devicekey/registration_token) — to any
    other local user until cleanup runs (up to _IMPORT_STAGE_MAX_AGE).
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    return os.fdopen(fd, 'wb' if binary else 'w', encoding=None if binary else 'utf-8')


def _cleanup_stale_import_stages():
    """Best-effort delete of staged import files older than _IMPORT_STAGE_MAX_AGE."""
    try:
        now = time.time()
        for name in os.listdir(_IMPORT_STAGE_DIR):
            if not name.startswith('displayhive-import-'):
                continue
            path = os.path.join(_IMPORT_STAGE_DIR, name)
            try:
                if now - os.path.getmtime(path) > _IMPORT_STAGE_MAX_AGE:
                    os.remove(path)
            except OSError:
                pass
    except OSError:
        pass


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
    """Build a ZIP archive containing db.json + matching media files for the
    selected entities (selection omitted/null = everything) and stream it."""
    import io
    import zipfile
    from datetime import datetime, timezone
    from application.admin.importexport.helper import export_database

    payload = request.get_json(silent=True) or {}
    selection = payload.get('selection')  # dict[type, [uuid,...]] or None = everything

    export_data = export_database(app, db, selection)

    # When a selection was given, only bundle media files that belong to the
    # (dependency-resolved) selected Media rows — export_data['media'] already
    # reflects that resolution.
    selected_rel_paths = None
    if selection is not None:
        selected_rel_paths = {
            os.path.join(m.get('folder_path') or '', m['filename']).replace(os.sep, '/')
            for m in export_data.get('media', [])
        }

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('db.json', json.dumps(export_data, indent=2))
        if os.path.isdir(_MEDIA_FOLDER):
            for root, _dirs, files in os.walk(_MEDIA_FOLDER):
                for fname in files:
                    abs_path = os.path.join(root, fname)
                    rel = os.path.relpath(abs_path, _MEDIA_FOLDER)
                    if selected_rel_paths is not None and rel.replace(os.sep, '/') not in selected_rel_paths:
                        continue
                    arcname = os.path.join('media', rel)
                    zf.write(abs_path, arcname)

    buf.seek(0)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
    return send_file(
        buf,
        as_attachment=True,
        download_name=f'displayhive-export-{now}.zip',
        mimetype='application/zip',
    )


@app.route('/admin/import/preview', methods=['POST'])
@require_jwt_auth(app)
@require_http_right(app, 'importexport.import')
def admin_import_preview():
    """Parse an uploaded ZIP/JSON export and stage it server-side under a
    short-lived token, returning a manifest for the selection tree."""
    import io
    import zipfile
    from application.admin.importexport.helper import prepare_import_payload, import_manifest

    _cleanup_stale_import_stages()

    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    filename = file.filename or ''
    raw = file.read()
    zip_bytes = None

    if filename.lower().endswith('.zip'):
        try:
            with zipfile.ZipFile(io.BytesIO(raw), 'r') as zf:
                if 'db.json' not in zf.namelist():
                    return jsonify({'success': False, 'error': 'ZIP does not contain db.json'}), 400
                db_payload = json.loads(zf.read('db.json').decode('utf-8'))
        except zipfile.BadZipFile:
            return jsonify({'success': False, 'error': 'Invalid ZIP file'}), 400
        zip_bytes = raw
    elif filename.lower().endswith('.json'):
        try:
            db_payload = json.loads(raw.decode('utf-8'))
        except Exception as exc:
            return jsonify({'success': False, 'error': f'Invalid JSON: {exc}'}), 400
    else:
        return jsonify({'success': False, 'error': 'Unsupported file type — upload a .zip or .json file'}), 400

    version = db_payload.get('export_version', 1)
    is_legacy = version < 9
    prepare_import_payload(db_payload)  # backfills uuids + upgrades pre-v4 shape, in place

    token = secrets.token_urlsafe(24)
    json_path, zip_path = _import_stage_paths(token)
    with _open_stage_file(json_path, binary=False) as f:
        json.dump(db_payload, f)
    if zip_bytes is not None:
        with _open_stage_file(zip_path, binary=True) as f:
            f.write(zip_bytes)

    manifest = import_manifest(db_payload, app, db)

    return jsonify({'token': token, 'is_legacy': is_legacy, 'manifest': manifest})


@app.route('/admin/import/confirm', methods=['POST'])
@require_jwt_auth(app)
@require_http_right(app, 'importexport.import')
def admin_import_confirm():
    """Finish a staged import: apply the chosen selection/mode/conflict
    resolution, restore matching media files, then discard the staged upload."""
    import shutil
    import zipfile
    from application.admin.importexport.helper import import_database

    payload = request.get_json(silent=True) or {}
    token = payload.get('token') or ''
    selection = payload.get('selection')
    mode = payload.get('mode') or 'reset'
    conflict_resolution = payload.get('conflict_resolution') or 'skip'

    json_path, zip_path = _import_stage_paths(token)
    if not os.path.isfile(json_path):
        return jsonify({'success': False, 'error': 'Import session expired or not found — please re-upload the file.'}), 400

    with open(json_path, 'r', encoding='utf-8') as f:
        db_payload = json.load(f)

    has_zip = os.path.isfile(zip_path)

    try:
        # Reset implies a full media-folder wipe first, matching the old
        # whole-database-reset behaviour; merge leaves existing files alone.
        if mode == 'reset':
            if os.path.isdir(_MEDIA_FOLDER):
                for entry in os.scandir(_MEDIA_FOLDER):
                    if entry.is_dir(follow_symlinks=False):
                        shutil.rmtree(entry.path)
                    else:
                        os.remove(entry.path)
            os.makedirs(_MEDIA_FOLDER, exist_ok=True)

        if has_zip:
            selected_media_uuids = set(selection.get('media') or []) if selection is not None else None
            with zipfile.ZipFile(zip_path, 'r') as zf:
                names = set(zf.namelist())
                for media_row in db_payload.get('media', []):
                    if selected_media_uuids is not None and media_row.get('uuid') not in selected_media_uuids:
                        continue
                    rel = os.path.join(media_row.get('folder_path') or '', media_row['filename'])
                    arcname = 'media/' + rel.replace(os.sep, '/')
                    if arcname not in names:
                        continue
                    target = os.path.join(_MEDIA_FOLDER, rel)
                    real_target = os.path.realpath(target)
                    real_root = os.path.realpath(_MEDIA_FOLDER)
                    if real_target != real_root and not real_target.startswith(real_root + os.sep):
                        continue
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with zf.open(arcname) as src, open(target, 'wb') as dst:
                        dst.write(src.read())

        result = import_database(app, db, db_payload, selection=selection, mode=mode, conflict_resolution=conflict_resolution)
        if result.get('success'):
            _broadcast_import_update()
    finally:
        for path in (json_path, zip_path):
            try:
                os.remove(path)
            except OSError:
                pass

    return jsonify(result)


@app.route('/admin/demo/list')
@require_jwt_auth(app)
@require_http_right(app, 'importexport.page')
def admin_demo_list():
    """List the available demo-content packages described in exampledesc.json."""
    if _demo_mode_hidden():
        return "Not Found", 404
    if not os.path.isfile(_EXAMPLECONTENT_DESC):
        return jsonify([])
    with open(_EXAMPLECONTENT_DESC, 'r', encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/admin/demo/import', methods=['POST'])
@require_jwt_auth(app)
@require_http_right(app, 'importexport.import')
def admin_demo_import():
    """Wipe the database (except user accounts) and media, then import a bundled demo package."""
    import zipfile

    if _demo_mode_hidden():
        return "Not Found", 404

    payload = request.get_json(silent=True) or {}
    filename = payload.get('filename') or ''

    if not os.path.isfile(_EXAMPLECONTENT_DESC):
        return jsonify({'success': False, 'error': 'No demo content available'}), 404

    with open(_EXAMPLECONTENT_DESC, 'r', encoding='utf-8') as f:
        available = {entry['filename'] for entry in json.load(f)}

    # Only allow filenames explicitly listed in exampledesc.json — guards
    # against path traversal via an arbitrary `filename` value in the request.
    if filename not in available:
        return jsonify({'success': False, 'error': 'Unknown demo package'}), 400

    zip_path = os.path.join(_EXAMPLECONTENT_FOLDER, filename)
    if not os.path.isfile(zip_path):
        return jsonify({'success': False, 'error': 'Demo package file missing on server'}), 404

    with open(zip_path, 'rb') as f:
        raw = f.read()

    try:
        result = _restore_from_zip_bytes(raw)
    except zipfile.BadZipFile:
        return jsonify({'success': False, 'error': 'Invalid ZIP file'}), 400
    return jsonify(result)


# End of application routes


if __name__ == '__main__':
    # Listen on all interfaces so the app is reachable from the network.
    # Allow the port to be overridden via FLASK_PORT for parallel test workers.
    flask_port = int(os.environ.get('FLASK_PORT', 5000))

    # The Werkzeug debugger allows arbitrary code execution if ever exposed to
    # the network, so it is OFF by default. Opt in explicitly with FLASK_DEBUG=1
    # for local development only (never on a network-reachable host).
    _flask_debug_env = os.environ.get('FLASK_DEBUG')
    if _flask_debug_env is not None:
        debug_mode = str(_flask_debug_env).lower() in ('1', 'true', 'yes', 'on')
    else:
        debug_mode = False
    app.config['DEBUG_ENABLED'] = debug_mode

    socketio.run(
        app,
        host='0.0.0.0',
        port=flask_port,
        debug=debug_mode,
        use_reloader=False,  # reloader forks the process, incompatible with worker-per-port isolation
        allow_unsafe_werkzeug=debug_mode,  # only needed when debug=True outside of the Werkzeug reloader
    )
