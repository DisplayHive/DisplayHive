"""add uuid to primary/independently-selectable entities

Adds a stable `uuid` column to every primary entity type that can be
individually selected for export/import (Screen, Screengroup, Design,
Gradient, Layout, ContentContainer, Contenttype, ContentElement, Media,
Device, MagicTag, MagicTagValueList) — used by the selective import/export
merge logic to detect "this already exists" across instances/exports.

Each existing row gets a distinct uuid4() generated in Python (a single
server-side default can't produce distinct values per row), so the column
is added nullable first, backfilled row-by-row, then tightened to NOT NULL
with a unique index.

Revision ID: h4i5j6k7l8m9
Revises: fa2c04e853e6
Create Date: 2026-08-11
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = 'h4i5j6k7l8m9'
down_revision = 'fa2c04e853e6'
branch_labels = None
depends_on = None


# (table_name, index_name) — index_name matches the SQLAlchemy model's
# `index=True, unique=True` naming convention (ix_<table>_uuid).
TABLES = [
    'screen',
    'screengroup',
    'design',
    'gradient',
    'layout',
    'contentcontainer',
    'contenttype',
    'content_element',
    'media',
    'device',
    'magic_tag',
    'magic_tag_value_list',
]


def upgrade():
    conn = op.get_bind()

    # 1. Add nullable uuid column to every table.
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column('uuid', sa.String(length=36), nullable=True))

    # 2. Backfill: one distinct uuid4() per existing row.
    for table in TABLES:
        t = sa.table(table, sa.column('id', sa.Integer), sa.column('uuid', sa.String(36)))
        rows = conn.execute(sa.select(t.c.id)).fetchall()
        for (row_id,) in rows:
            conn.execute(
                t.update().where(t.c.id == row_id).values(uuid=str(uuid.uuid4()))
            )

    # 3. Tighten to NOT NULL + unique index.
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column('uuid', existing_type=sa.String(length=36), nullable=False)
            batch_op.create_index(f'ix_{table}_uuid', ['uuid'], unique=True)


def downgrade():
    for table in TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f'ix_{table}_uuid')
            batch_op.drop_column('uuid')
