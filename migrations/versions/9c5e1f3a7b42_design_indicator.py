"""add progress indicator settings to design

Revision ID: 9c5e1f3a7b42
Revises: 8b4d0e2f6a31
Create Date: 2026-10-06
"""

import sqlalchemy as sa
from alembic import op

revision = '9c5e1f3a7b42'
down_revision = '8b4d0e2f6a31'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('indicator_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('indicator_color', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('indicator_height', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('indicator_direction', sa.String(8), nullable=True))


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_column('indicator_direction')
        batch_op.drop_column('indicator_height')
        batch_op.drop_column('indicator_color')
        batch_op.drop_column('indicator_enabled')
