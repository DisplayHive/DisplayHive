"""add rotation column to screen

Revision ID: 8b4d0e2f6a31
Revises: 7a3c9d1e5f20
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = '8b4d0e2f6a31'
down_revision = '7a3c9d1e5f20'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('screen') as batch_op:
        batch_op.add_column(sa.Column('rotation', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('screen') as batch_op:
        batch_op.drop_column('rotation')
