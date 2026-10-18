"""add the slide transition settings to design

Revision ID: c9e5a7b3d1f2
Revises: b8d4f6a2c0e1
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = 'c9e5a7b3d1f2'
down_revision = 'b8d4f6a2c0e1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('transition', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('transition_direction', sa.String(8), nullable=True))
        batch_op.add_column(sa.Column('transition_duration_ms', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_column('transition_duration_ms')
        batch_op.drop_column('transition_direction')
        batch_op.drop_column('transition')
