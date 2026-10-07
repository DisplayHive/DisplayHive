"""add must_change_password to admin_user

Revision ID: a7d2c4e8f1b3
Revises: 9c5e1f3a7b42
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = 'a7d2c4e8f1b3'
down_revision = '9c5e1f3a7b42'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('admin_user') as batch_op:
        batch_op.add_column(sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('admin_user') as batch_op:
        batch_op.drop_column('must_change_password')
