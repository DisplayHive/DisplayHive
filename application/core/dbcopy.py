"""Copy a whole DisplayHive database into another one (SQLite -> PostgreSQL).

This is the way off SQLite for installations that started on it: every table of
the models is copied 1:1 — users, groups and rights, SSO providers, devices and
their keys, settings, content — in one transaction on the target, which is
emptied first. If anything fails, the target is left exactly as it was.

Both databases must already have the schema (``alembic upgrade head``); the
revision check is the CLI's job (application/cli.py, ``flask dh copy-database``).
Media files are not in the database and are not touched.
"""

from typing import Callable, Optional

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

BATCH = 1000


class CopyError(Exception):
    """The copy cannot be done (or failed); the target is unchanged."""


def _self_reference_columns(table: sa.Table) -> list:
    return [fk.parent for fk in table.foreign_keys if fk.column.table is table]


def _in_insert_order(table: sa.Table, rows: list) -> list:
    """Rows of a table that references itself (group.parent_group_id), parents
    first — a foreign key to a row not inserted yet would be refused."""
    columns = _self_reference_columns(table)
    pk = list(table.primary_key.columns)
    if not columns or len(pk) != 1:
        return rows
    key = pk[0].name
    pending, ordered, inserted = list(rows), [], set()
    while pending:
        ready = [r for r in pending if all(r[c.name] is None or r[c.name] in inserted for c in columns)]
        if not ready:
            raise CopyError(f'{table.name}: rows reference each other in a cycle')
        ordered.extend(ready)
        inserted.update(r[key] for r in ready)
        ready_ids = {id(r) for r in ready}
        pending = [r for r in pending if id(r) not in ready_ids]
    return ordered


def _reset_sequence(conn, table: sa.Table) -> None:
    """PostgreSQL: continue each auto-increment id after the highest copied one,
    or the next INSERT would reuse an id and fail."""
    pk = list(table.primary_key.columns)
    if len(pk) != 1 or not isinstance(pk[0].type, sa.Integer):
        return
    quote = conn.dialect.identifier_preparer.quote
    name, column = quote(table.name), quote(pk[0].name)
    conn.execute(sa.text(
        f"SELECT setval(pg_get_serial_sequence('{name}', '{pk[0].name}'), "
        f"COALESCE(MAX({column}), 1), MAX({column}) IS NOT NULL) FROM {name}"
    ))


def copy_database(source: sa.engine.Engine, target: sa.engine.Engine, metadata: sa.MetaData,
                  echo: Optional[Callable[[str], None]] = None) -> dict:
    """Replace the contents of *target* with those of *source*.

    *metadata* describes the tables (the models'). Returns {table: row count}.
    """
    echo = echo or (lambda _msg: None)
    source_tables = set(sa.inspect(source).get_table_names())
    target_tables = set(sa.inspect(target).get_table_names())
    tables = [t for t in metadata.sorted_tables if t.name in source_tables and t.name in target_tables]
    missing = [t.name for t in metadata.sorted_tables if t.name not in target_tables]
    if missing:
        raise CopyError('The target database lacks tables (' + ', '.join(missing) + ') — run `alembic upgrade head` on it first.')
    unknown = sorted(source_tables - {t.name for t in metadata.sorted_tables} - {'alembic_version'})
    if unknown:
        echo('Not copied (no such table in this version): ' + ', '.join(unknown))

    copied = {}
    try:
        with source.connect() as src, target.begin() as dst:
            for table in reversed(tables):
                dst.execute(table.delete())
            for table in tables:
                rows = _in_insert_order(table, [dict(r) for r in src.execute(sa.select(table)).mappings()])
                for start in range(0, len(rows), BATCH):
                    dst.execute(table.insert(), rows[start:start + BATCH])
                copied[table.name] = len(rows)
                echo(f'  {table.name}: {len(rows)}')
            if dst.dialect.name == 'postgresql':
                for table in tables:
                    _reset_sequence(dst, table)
            for table in tables:
                count = dst.execute(sa.select(sa.func.count()).select_from(table)).scalar()
                if count != copied[table.name]:
                    raise CopyError(f'{table.name}: copied {copied[table.name]} rows but the target holds {count}')
    except IntegrityError as exc:
        raise CopyError(
            'A row could not be inserted — the source has rows that point at rows that do not exist '
            '(SQLite does not always enforce that). Fix or delete them in the source and try again. '
            f'Details: {str(exc.orig).splitlines()[0]}'
        ) from exc
    return copied
