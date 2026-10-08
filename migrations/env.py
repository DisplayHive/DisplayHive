"""Alembic migration environment.

The database is DATABASE_URL, exactly as for the app (PostgreSQL; SQLite only
as an explicit development URL) — application/db_url.py decides, and there is
no fallback file.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make the project root importable so models can be imported below.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from application.db_url import DatabaseConfigError, resolve_database_url  # noqa: E402
from application import paths as data_paths  # noqa: E402

# Alembic Config object, giving access to values in alembic.ini.
config = context.config

# Override sqlalchemy.url with DATABASE_URL, so that the same alembic.ini
# works for SQLite (dev) and PostgreSQL without editing the file. (Never
# alembic.ini's relative default: that depends on the working directory and
# could migrate a different file than the app opens.)
# `flask dh copy-database --upgrade-source` hands in the connection of the
# database to migrate (the old SQLite file), which is not DATABASE_URL.
_given_connection = config.attributes.get('connection')
if _given_connection is None:
    try:
        _db_url = resolve_database_url(
            os.environ,
            deployment=data_paths.deployment_kind(),
            existing_sqlite_files=data_paths.existing_sqlite_files(),
        )
    except DatabaseConfigError as exc:
        sys.exit(f'\nERROR: {exc}\n')
    config.set_main_option('sqlalchemy.url', _db_url)
    _paths = data_paths.resolve()
    if _paths.db_path:
        data_paths.ensure_dirs(_paths)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Import models so that target_metadata is populated.
from application.models import db  # noqa: E402  (must come after sys.path setup)

target_metadata = db.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection required)."""
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (with a live DB connection)."""
    if _given_connection is not None:
        context.configure(connection=_given_connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
