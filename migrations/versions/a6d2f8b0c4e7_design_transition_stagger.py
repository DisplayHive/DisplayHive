"""add transition_stagger to design

Revision ID: a6d2f8b0c4e7
Revises: f4b0d6e8a2c5
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = 'a6d2f8b0c4e7'
down_revision = 'f4b0d6e8a2c5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('transition_stagger', sa.String(12), nullable=True))


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_column('transition_stagger')
