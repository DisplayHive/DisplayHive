"""align the migrated schema with the models (what `alembic check` reported)

- admin_user.username, device.devicekey, device.registration_token,
  group.name, right_definition.key: the models want ONE unique index
  (`ix_<table>_<column>`, like every uuid column). The initial migrations
  created a unique constraint (plus, for device/group/right_definition, a
  second non-unique index) instead. Replace them with the unique index.
  The unique index is created before the constraint is dropped, so the column
  is never without a uniqueness guarantee. On SQLite only *named* constraints
  can be dropped; unnamed ones stay as a harmless duplicate.
- content_element.contentcontainer: leftover column from the maincontent
  rename; no model maps it any more.

Revision ID: c9f4e6a0b3d5
Revises: b8e3d5f9a2c4
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op

revision = 'c9f4e6a0b3d5'
down_revision = 'b8e3d5f9a2c4'
branch_labels = None
depends_on = None

UNIQUE_COLUMNS = [
    ('admin_user', 'username'),
    ('device', 'devicekey'),
    ('device', 'registration_token'),
    ('group', 'name'),
    ('right_definition', 'key'),
]


def upgrade():
    insp = sa.inspect(op.get_bind())

    for table, column in UNIQUE_COLUMNS:
        ix = f'ix_{table}_{column}'
        indexes = {i['name']: i for i in insp.get_indexes(table)}
        if ix in indexes and not indexes[ix]['unique']:
            op.drop_index(ix, table_name=table)
            indexes.pop(ix)
        if ix not in indexes:
            op.create_index(ix, table, [column], unique=True)
        for uc in insp.get_unique_constraints(table):
            if uc.get('name') and uc['column_names'] == [column]:
                with op.batch_alter_table(table) as batch_op:
                    batch_op.drop_constraint(uc['name'], type_='unique')

    if 'contentcontainer' in {c['name'] for c in insp.get_columns('content_element')}:
        with op.batch_alter_table('content_element') as batch_op:
            batch_op.drop_column('contentcontainer')


def downgrade():
    # The old shape was redundant (constraint + non-unique index) and the
    # column unused; there is nothing worth restoring.
    pass
