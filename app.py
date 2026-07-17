import eventlet
eventlet.monkey_patch()

import os
import re
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

# Import database models
from application.models import db, Template, ContentContainer, Device

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


def _enforce_default_template():
    has_default = db.session.execute(
        db.select(Template).where(Template.isDefault == True)
    ).scalar()
    if not has_default:
        t1 = db.session.get(Template, 1)
        if t1:
            t1.isDefault = True
            db.session.commit()
            logger.info('No default template found on startup; set Template ID 1 as default')


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
    _startup_step('enforce default template', _enforce_default_template)
    _startup_step('prune screen_log', _prune_screen_logs_startup)
    _startup_step('ensure bootstrap admin user', lambda: ensure_bootstrap_admin(app, db))
    _startup_step('sync right definitions', lambda: sync_right_definitions(db))
    _startup_step('ensure superadmin group', lambda: ensure_superadmin_group(db))

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
    """Serve the screen/kiosk page, resolving the active template and container layout.

    Supports an optional ?preview=true&content_id=<id>&container=<name> query string
    so the admin UI can render a single content item for preview without the normal
    playlist logic.
    """
    preview_mode = request.args.get('preview', 'false').lower() == 'true'
    content_id = request.args.get('content_id', type=int)
    preview_container = request.args.get('container', 'maincontent')
    
    from application.utils import get_default_template
    default_template = get_default_template(db)
    
    container_names = ['maincontent']  # Always include maincontent
    if default_template:
        template_html = default_template.html
        template_css = default_template.css or ''
        
        # Get container names from ContentContainer table
        contentcontainers = db.session.execute(
            db.select(ContentContainer).where(ContentContainer.template_id == default_template.id)
        ).scalars().all()
        
        # Only include containers that have assigned contenttypes
        for container in contentcontainers:
            if container.contenttypes:  # This container has assigned contenttypes
                container_names.append(container.name)
        
        # Substitute {{ var_<name> }} placeholders in HTML and CSS.
        try:
            from application.admin.magictags.helper import load_magic_tags, substitute_magic_tags
            _tvars = load_magic_tags(db)
            template_html = substitute_magic_tags(template_html, _tvars)
            template_css = substitute_magic_tags(template_css, _tvars)
        except Exception:
            pass

        # Replace Jinja tags {{ tag_name }} with <div data-container="tag_name"></div>
        # Client-side JS looks up containers by `data-container` attribute, so
        # render placeholders accordingly to ensure the content-display
        # functions can find and populate them.
        template_html = re.sub(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}', r'<div data-container="\1"></div>', template_html)
    else:
        template_html = '<div data-container="maincontent"></div>'
        template_css = ''
    
    try:
        from application.models import SystemSetting as _SS
        _row = db.session.execute(db.select(_SS).where(_SS.key == 'hide_powered_by')).scalar_one_or_none()
        hide_powered_by = (_row.value if _row else '') in ('true', '1', 'yes')
    except Exception:
        hide_powered_by = False

    return render_template('index.html',
                         async_mode=socketio.async_mode,
                         template_html=template_html,
                         template_css=template_css,
                         container_names=container_names,
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


def _restore_from_zip_bytes(raw: bytes) -> dict:
    """Replace the media folder + database from an export-format ZIP's bytes.

    Shared by the manual upload endpoint and the demo-content importer, which
    both need to: pull db.json out of the zip, wipe the media folder and
    restore any files it contains, then run import_database.
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

    return import_database(app, db, db_payload)


@app.route('/admin/export/download')
@require_jwt_auth(app)
@require_http_right(app, 'importexport.export')
def admin_export_download():
    """Build a ZIP archive containing db.json + all media files and stream it."""
    import io
    import zipfile
    from datetime import datetime, timezone
    from application.admin.importexport.helper import export_database

    export_data = export_database(app, db)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('db.json', json.dumps(export_data, indent=2))
        if os.path.isdir(_MEDIA_FOLDER):
            for root, _dirs, files in os.walk(_MEDIA_FOLDER):
                for fname in files:
                    abs_path = os.path.join(root, fname)
                    arcname = os.path.join('media', os.path.relpath(abs_path, _MEDIA_FOLDER))
                    zf.write(abs_path, arcname)

    buf.seek(0)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%S')
    return send_file(
        buf,
        as_attachment=True,
        download_name=f'displayhive-export-{now}.zip',
        mimetype='application/zip',
    )


@app.route('/admin/import/upload', methods=['POST'])
@require_jwt_auth(app)
@require_http_right(app, 'importexport.import')
def admin_import_upload():
    """Accept a ZIP (or legacy JSON) upload and restore the database + media files."""
    import zipfile
    from application.admin.importexport.helper import import_database

    file = request.files.get('file')
    if not file:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    filename = file.filename or ''

    if filename.lower().endswith('.zip'):
        raw = file.read()
        try:
            result = _restore_from_zip_bytes(raw)
        except zipfile.BadZipFile:
            return jsonify({'success': False, 'error': 'Invalid ZIP file'}), 400
        return jsonify(result)

    elif filename.lower().endswith('.json'):
        try:
            db_payload = json.loads(file.read().decode('utf-8'))
        except Exception as exc:
            return jsonify({'success': False, 'error': f'Invalid JSON: {exc}'}), 400

    else:
        return jsonify({'success': False, 'error': 'Unsupported file type — upload a .zip or .json file'}), 400

    result = import_database(app, db, db_payload)
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
