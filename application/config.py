"""Configuration read from the environment.

The parsing is in small pure functions (they take the environment as an
argument, so tests can feed any); `apply_config` copies the result onto a Flask
app. Nothing here touches the database or starts anything.
"""

import logging
import os
import warnings
from typing import Mapping, Optional, Union
from urllib.parse import urlsplit

from application import paths as data_paths
from application import backup, logfmt, version
from application.db_url import is_sqlite_url, resolve_database_url

logger = logging.getLogger(__name__)

# Plain OS threads: every Socket.IO event and background task runs in a thread,
# WebSockets via simple-websocket, served by gunicorn's gthread worker (one
# connected screen or admin tab holds one thread — size --threads accordingly).
# No monkey-patching. Shared in-memory state is guarded by locks: the login rate
# limiter (application/auth.py), pending SSO logins (application/oidc.py) and
# the connection registry (application/socketio_handlers/lifecycle.py).
ASYNC_MODE = 'threading'

DEFAULT_SECRET_KEY = 'secret!'
DEV_CORS_ORIGINS = [
    'http://localhost:5173', 'http://127.0.0.1:5173',
    'http://localhost:5174', 'http://127.0.0.1:5174',
    'http://localhost:5000', 'http://127.0.0.1:5000',
]


def configure_logging(cli_mode: bool = False) -> None:
    """Configure logging once for the whole application.

    Individual modules use ``logging.getLogger(__name__)``; INFO-level
    operational messages (startup, content pushes, …) go to stderr, and the
    level can be tuned via LOG_LEVEL. A `flask dh` command defaults to WARNING
    so its own output isn't buried. LOG_FORMAT=json writes one JSON object per
    line instead of the readable text (application/logfmt.py).
    """
    level = getattr(logging, os.environ.get('LOG_LEVEL', 'WARNING' if cli_mode else 'INFO').upper(), logging.INFO)
    logging.basicConfig(level=level, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    root = logging.getLogger()
    # basicConfig does nothing when something configured logging first (gunicorn's
    # --log-config-json, a test runner): the level and the format are still ours.
    root.setLevel(level)
    if logfmt.wanted(os.environ) == 'json':
        for handler in root.handlers:
            handler.setFormatter(logfmt.JsonFormatter())


def env_int(name: str, default: int, environ: Optional[Mapping[str, str]] = None) -> int:
    """A positive integer from the environment; *default* if unset, invalid or ≤ 0."""
    environ = os.environ if environ is None else environ
    try:
        value = int(environ.get(name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def is_truthy(value: Optional[str]) -> bool:
    return (value or '').strip().lower() in ('1', 'true', 'yes', 'on')


class ConfigError(ValueError):
    """An environment variable has a value the app cannot start with."""


def resolve_public_url(environ: Mapping[str, str]) -> Optional[str]:
    """PUBLIC_URL: the address people reach this instance at, e.g.
    ``https://signage.example.com`` (a sub-path is allowed, a trailing slash is
    dropped). ``None`` when unset. The CORS default and the SSO redirect URI
    are derived from it, instead of from whatever Host header a request carries.
    """
    raw = (environ.get('PUBLIC_URL') or '').strip()
    if not raw:
        return None
    parsed = urlsplit(raw)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.query or parsed.fragment:
        raise ConfigError(
            f'PUBLIC_URL must look like https://signage.example.com (scheme and host, '
            f'no query or fragment), got {raw!r}'
        )
    return raw.rstrip('/')


def _origin_of(url: str) -> str:
    """scheme://host[:port] of *url* — CORS compares origins, never paths."""
    parsed = urlsplit(url)
    return f'{parsed.scheme}://{parsed.netloc}' if parsed.scheme and parsed.netloc else url


def resolve_cors_origins(environ: Mapping[str, str]) -> Union[list, str]:
    """The allowed CORS origins, shared by flask_cors (HTTP /api/*) and Socket.IO.

    ``CORS_ALLOWED_ORIGINS`` wins when set: ``*`` → everything, only if the
    operator explicitly accepts that; otherwise a comma-separated list (an
    entry with a path is reduced to its origin; set but empty allows
    nothing). Unset → this instance's PUBLIC_URL when that is set; else local dev
    origins only (plus this instance's own port when FLASK_PORT overrides 5000,
    e.g. parallel Playwright workers: the screen client served by this app
    connects back to its own origin).
    """
    raw = environ.get('CORS_ALLOWED_ORIGINS')
    if raw is None:
        public_url = resolve_public_url(environ)
        if public_url:
            return [_origin_of(public_url)]
        origins = list(DEV_CORS_ORIGINS)
        own_port = environ.get('FLASK_PORT')
        if own_port and own_port != '5000':
            origins += [f'http://localhost:{own_port}', f'http://127.0.0.1:{own_port}']
        return origins
    if raw.strip() == '*':
        return '*'
    return [_origin_of(o.strip()) for o in raw.split(',') if o.strip()]


def trusted_proxy_count(environ: Mapping[str, str]) -> int:
    """Number of reverse proxies in front of the app (TRUSTED_PROXY_COUNT).

    Only when this is set are X-Forwarded-* headers trusted, so
    request.remote_addr (used by the login rate limiter) is the real client
    and clients can't spoof the header.
    """
    try:
        return max(0, int(environ.get('TRUSTED_PROXY_COUNT', '0') or '0'))
    except ValueError:
        return 0


def engine_options(environ: Mapping[str, str]) -> dict:
    """SQLAlchemy connection-pool settings.

    Idle screens hold no connection — a thread only borrows one while it
    handles an event or request — but after a restart every screen reconnects
    at once, and each connect needs the database briefly. SQLAlchemy's default
    (5 + 10 overflow) makes that herd queue for up to pool_timeout; 10 + 20
    stays well inside PostgreSQL's default max_connections of 100.
    pool_pre_ping drops connections the server closed.
    """
    return {
        'pool_size': env_int('DB_POOL_SIZE', 10, environ),
        'max_overflow': env_int('DB_MAX_OVERFLOW', 20, environ),
        'pool_timeout': 30,
        'pool_pre_ping': True,
    }


def apply_config(app, paths: data_paths.DataPaths, environ: Mapping[str, str]) -> Union[list, str]:
    """Copy the environment-derived settings onto *app*; returns the CORS origins."""
    for legacy in paths.legacy:
        logger.warning(
            "Still using the legacy location %s for %s. Move it into DATA_DIR (%s) — "
            "see 'Moving data to DATA_DIR' in docs/user/installation.md.",
            legacy['path'], legacy['kind'], paths.data_dir,
        )
    cfg = app.config
    # Every on-disk location (DATA_DIR: media, previews, renditions, import
    # staging, the SQLite file) comes from application/paths.py.
    cfg['DATA_DIR'] = paths.data_dir
    cfg['MEDIA_FOLDER'] = paths.media
    cfg['PREVIEW_FOLDER'] = paths.media_previews
    cfg['MEDIA_RENDITIONS_FOLDER'] = paths.media_renditions
    cfg['LEGACY_DATA_PATHS'] = paths.legacy
    # Uploaded files (media, imports) are streamed here, not into memory or
    # /tmp — see DataDirRequest in application/admin/media/routes.py.
    cfg['UPLOAD_STAGING_DIR'] = paths.import_staging
    cfg['DEPLOYMENT_KIND'] = data_paths.deployment_kind(environ)

    # DATABASE_URL is required (PostgreSQL; SQLite only explicitly, for development).
    database_url = resolve_database_url(
        environ,
        deployment=cfg['DEPLOYMENT_KIND'],
        existing_sqlite_files=data_paths.existing_sqlite_files(environ),
    )
    cfg['SQLALCHEMY_DATABASE_URI'] = database_url
    cfg['SQLITE_IN_USE'] = is_sqlite_url(database_url)
    cfg['SQLALCHEMY_ENGINE_OPTIONS'] = engine_options(environ)

    # Pick up template changes without a full process restart.
    cfg['TEMPLATES_AUTO_RELOAD'] = True

    secret_key = environ.get('SECRET_KEY', DEFAULT_SECRET_KEY)
    if secret_key == DEFAULT_SECRET_KEY:
        warnings.warn(
            "SECRET_KEY is using the insecure default 'secret!'. "
            "Set the SECRET_KEY environment variable before deploying to production.",
            RuntimeWarning,
            stacklevel=2,
        )
    cfg['SECRET_KEY'] = secret_key
    cfg['SECRET_KEY_IS_DEFAULT'] = secret_key == DEFAULT_SECRET_KEY

    # Overwritten by run_dev() when the Werkzeug debugger is enabled (never
    # under gunicorn/production).
    cfg['DEBUG_ENABLED'] = False
    cfg['LOGGER_ROOM'] = 'logger_room'
    cfg['APP_VERSION'] = version.release()
    cfg['APP_REVISION'] = version.revision()
    cfg['ASSET_VERSION'] = version.asset_version()  # cache-busting for the screen's JS/CSS: new per release/commit

    # Opt-in dev mode: the screen page loads its JS as an ES module straight
    # from the Vite dev server (with HMR) instead of dist/screen/screen.js.
    # Deliberately separate from FLASK_DEBUG — enabling the Werkzeug debugger
    # for backend work shouldn't break the screen page for anyone who isn't
    # also running `npm run dev` in frontends/screen.
    cfg['SCREEN_DEV_SERVER'] = is_truthy(environ.get('SCREEN_DEV_SERVER'))
    cfg['SCREEN_DEV_SERVER_URL'] = environ.get('SCREEN_DEV_SERVER_URL', 'http://localhost:5174')

    cfg['PUBLIC_URL'] = resolve_public_url(environ)
    cfg['BACKUP_DIR'] = paths.backups
    cfg['BACKUP_SETTINGS'] = backup.Settings.from_env(environ)
    cors_origins = resolve_cors_origins(environ)
    cfg['CORS_WILDCARD'] = cors_origins == '*'
    return cors_origins
