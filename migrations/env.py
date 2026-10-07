"""Alembic migration environment.

Database URL resolution order:
1. DATABASE_URL environment variable (PostgreSQL in production).
2. Otherwise the same SQLite file the app uses — TEST_DB_PATH in tests,
   else DATA_DIR/db/project.db (or a legacy project.db in the app root),
   decided by application/paths.py.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Make the project root importable so models can be imported below.
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from application.db_url import normalize_database_url  # noqa: E402
from application import paths as data_paths  # noqa: E402

# Alembic Config object, giving access to values in alembic.ini.
config = context.config

# Override sqlalchemy.url with the environment-supplied DATABASE_URL when
# present, so that the same alembic.ini works for both SQLite (dev) and
# PostgreSQL (production) without editing the file.
_db_url = os.environ.get('DATABASE_URL')
if _db_url:
    config.set_main_option('sqlalchemy.url', normalize_database_url(_db_url))
else:
    # Never alembic.ini's relative default: that depends on the working
    # directory and could migrate a different file than the app opens.
    _paths = data_paths.resolve()
    data_paths.ensure_dirs(_paths)
    config.set_main_option('sqlalchemy.url', f'sqlite:///{_paths.db_path}')

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

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
