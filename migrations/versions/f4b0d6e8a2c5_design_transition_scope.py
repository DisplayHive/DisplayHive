"""add transition_scope to design

Revision ID: f4b0d6e8a2c5
Revises: e3a9c5d7f1b4
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = 'f4b0d6e8a2c5'
down_revision = 'e3a9c5d7f1b4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('transition_scope', sa.String(10), nullable=True))


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_column('transition_scope')
