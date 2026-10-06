"""add show_when_empty column to contentcontainer

Revision ID: 6e2f1a9c4b7d
Revises: 49c967c07605
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = '6e2f1a9c4b7d'
down_revision = '49c967c07605'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('contentcontainer') as batch_op:
        batch_op.add_column(sa.Column('show_when_empty', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('contentcontainer') as batch_op:
        batch_op.drop_column('show_when_empty')
