"""The application factory.

`create_app()` builds a complete, independent app: configuration, database,
CORS, security headers, Socket.IO, every handler and route. Importing this
module has no side effects, so tests, scripts and `flask dh` commands can build
exactly what they need.

`startup=True` (the default, for a real server) additionally runs the one-time
startup work from application/startup.py: raise the open-files limit, run the
startup steps, start background tasks, and create the data directories.
"""

import json
import logging
import os
import sqlite3
from typing import Optional

from flask import Flask
from flask_socketio import SocketIO

from application import paths as data_paths
from application.config import ASYNC_MODE, apply_config, trusted_proxy_count
from application.models import db
from application.security_headers import register_security_headers
from application.web import PROJECT_ROOT, register_web_routes

logger = logging.getLogger(__name__)

_sqlite_foreign_keys_registered = False


def _enable_sqlite_foreign_keys() -> None:
    """SQLite doesn't enforce foreign keys per connection unless this pragma is
    set — without it every ForeignKey(..., ondelete=...) on the models is inert
    on SQLite (only enforced on PostgreSQL). Enabling it makes FK-constrained
    deletes fail loudly (IntegrityError) instead of silently leaving orphaned
    rows, matching PostgreSQL. The hook is global to SQLAlchemy and checks the
    connection type, so registering it once covers every app in the process.
    """
    global _sqlite_foreign_keys_registered
    if _sqlite_foreign_keys_registered:
        return
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, 'connect')
    def _on_connect(dbapi_connection, connection_record):
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()

    _sqlite_foreign_keys_registered = True


def _from_json(value):
    """Jinja filter: parse a JSON string to a Python object. {} on error or empty input."""
    try:
        return json.loads(value) if value else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def create_app(overrides: Optional[dict] = None, *, startup: bool = True):
    """Build the app. Returns ``(app, socketio)``.

    *overrides* are applied to ``app.config`` after the environment-derived
    settings and before the database/Socket.IO are set up — e.g. a test passing
    its own ``SQLALCHEMY_DATABASE_URI``.
    """
    app = Flask(
        'app',
        root_path=str(PROJECT_ROOT),
        static_folder='static',
        static_url_path='/static',
        template_folder=str(PROJECT_ROOT / 'frontends' / 'screen' / 'templates'),
    )
    paths = data_paths.resolve()
    if startup:
        # Not for the CLI: it may run as another user (root), and directories it
        # created would then be unwritable for the server. check-config reports
        # missing ones instead.
        data_paths.ensure_dirs(paths)
    cors_origins = apply_config(app, paths, os.environ)
    if overrides:
        app.config.update(overrides)
    app.jinja_env.auto_reload = True
    app.jinja_env.filters['from_json'] = _from_json

    # Behind a reverse proxy: trust X-Forwarded-* only for the configured number of hops.
    proxies = trusted_proxy_count(os.environ)
    if proxies > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies)
        logger.info('ProxyFix enabled for %s trusted proxy hop(s)', proxies)

    db.init_app(app)
    if app.config['SQLITE_IN_USE']:
        _enable_sqlite_foreign_keys()

    # CORS for the API paths, if flask_cors is available (the admin SPA may be
    # served from another origin in development).
    try:
        from flask_cors import CORS
        CORS(app, resources={r'/api/*': {'origins': cors_origins}})
        logger.info('CORS enabled for /api/*')
    except Exception:
        logger.warning('flask_cors not installed; API CORS not enabled')

    # Security headers + Content-Security-Policy (see application/security_headers.py)
    register_security_headers(app)

    socketio = SocketIO(
        app,
        async_mode=ASYNC_MODE,
        logger=False,
        engineio_logger=False,
        ping_interval=25,
        ping_timeout=60,
        cors_allowed_origins=cors_origins,
        # Largest single Socket.IO message, accepted from any connection before
        # it has authenticated. Media uploads go over HTTP (application/admin/
        # media/routes.py); this only needs room for big content payloads, e.g.
        # images embedded as data: URLs.
        max_http_buffer_size=10 * 1024 * 1024,
    )

    from application import startup as startup_tasks
    if startup:
        startup_tasks.raise_open_files_limit()
        startup_tasks.run_startup_steps(app, db)

    from application.admin.auth.routes import register_auth_routes
    from application.admin.media.routes import DataDirRequest, register_media_routes
    from application.cli import register_cli
    from application.socketio_handlers import register_all_handlers

    register_all_handlers(socketio, app, db)
    register_auth_routes(app, db)             # /admin/api/auth/*
    app.request_class = DataDirRequest        # media upload streams to disk
    register_media_routes(app, db)            # /admin/api/media/upload
    register_cli(app)                         # `flask dh …` maintenance commands
    register_web_routes(app, db, socketio)    # static files, screen page, admin SPA, import/export

    if startup:
        startup_tasks.start_background_tasks(app, db, socketio, paths)
    return app, socketio


def run_dev(app: Flask, socketio: SocketIO) -> None:
    """`python app.py`: the development server (also what the e2e tests start)."""
    # Listen on all interfaces so the app is reachable from the network.
    # FLASK_PORT overrides the port (parallel test workers).
    port = int(os.environ.get('FLASK_PORT', 5000))

    # The Werkzeug debugger allows arbitrary code execution if ever exposed to
    # the network, so it is OFF by default. Opt in with FLASK_DEBUG=1 for local
    # development only (never on a network-reachable host).
    flask_debug = os.environ.get('FLASK_DEBUG')
    debug_mode = str(flask_debug).lower() in ('1', 'true', 'yes', 'on') if flask_debug is not None else False
    app.config['DEBUG_ENABLED'] = debug_mode

    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        use_reloader=False,  # reloader forks the process, incompatible with worker-per-port isolation
        # `python app.py` is for development and the e2e tests; production runs
        # gunicorn (docker-entrypoint.sh, nix/module.nix) and never gets here.
        allow_unsafe_werkzeug=True,
    )
