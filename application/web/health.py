"""Liveness and readiness probes for Docker, reverse proxies and monitoring.

  GET /healthz   the process is up and answering. No database access, so a
                 database outage does not make orchestrators restart the app.
  GET /readyz    the app can serve: the database answers and its schema is at
                 the migration head of this code (alembic upgrade head ran).
                 200 when ready, 503 otherwise.

Both are unauthenticated, so the bodies say only ok / not ok per check — no
revisions, hostnames or exception text.
"""

import logging
from functools import lru_cache

from flask import Blueprint, current_app, jsonify

from application.web import PROJECT_ROOT

logger = logging.getLogger(__name__)

bp = Blueprint('health', __name__)


@lru_cache(maxsize=1)
def _migration_heads() -> frozenset:
    """The head revision(s) of migrations/ — fixed for the life of the process."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config()
    config.set_main_option('script_location', str(PROJECT_ROOT / 'migrations'))
    return frozenset(ScriptDirectory.from_config(config).get_heads())


def migration_state(connection, heads) -> str:
    """'head' when the database is at the code's migration head, 'behind' when
    it is not, 'untracked' for a SQLite file built by create_all() (the
    development convenience, no alembic_version table)."""
    from sqlalchemy import inspect, text

    if not inspect(connection).has_table('alembic_version'):
        return 'untracked' if connection.dialect.name == 'sqlite' else 'behind'
    current = {row[0] for row in connection.execute(text('SELECT version_num FROM alembic_version'))}
    return 'head' if current == set(heads) else 'behind'


def readiness(db) -> tuple:
    """(ready, checks) — never raises."""
    checks = {'database': 'error', 'migrations': 'error'}
    try:
        with db.engine.connect() as connection:
            checks['database'] = 'ok'
            checks['migrations'] = migration_state(connection, _migration_heads())
    except Exception:
        logger.warning('readiness check failed', exc_info=True)
    return checks['database'] == 'ok' and checks['migrations'] in ('head', 'untracked'), checks


def _no_store(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.route('/healthz')
def healthz():
    return _no_store(jsonify(status='ok'))


@bp.route('/readyz')
def readyz():
    db = current_app.extensions['sqlalchemy']
    ready, checks = readiness(db)
    response = jsonify(status='ok' if ready else 'unavailable', checks=checks)
    response.status_code = 200 if ready else 503
    return _no_store(response)
