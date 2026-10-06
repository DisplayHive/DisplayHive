"""add locked column to contentcontainer

Revision ID: 5d4a0acfbdd4
Revises: j6k7l8m9n0o1
Create Date: 2026-09-23
"""

import sqlalchemy as sa
from alembic import op

revision = '5d4a0acfbdd4'
down_revision = 'j6k7l8m9n0o1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('contentcontainer') as batch_op:
        batch_op.add_column(sa.Column('locked', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('contentcontainer') as batch_op:
        batch_op.drop_column('locked')
