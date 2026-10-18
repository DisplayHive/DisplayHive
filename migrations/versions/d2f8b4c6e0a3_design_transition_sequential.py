"""add transition_sequential to design

Revision ID: d2f8b4c6e0a3
Revises: c9e5a7b3d1f2
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = 'd2f8b4c6e0a3'
down_revision = 'c9e5a7b3d1f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('transition_sequential', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_column('transition_sequential')
