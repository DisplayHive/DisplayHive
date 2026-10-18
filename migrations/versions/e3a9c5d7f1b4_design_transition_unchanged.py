"""add transition_unchanged to design

Revision ID: e3a9c5d7f1b4
Revises: d2f8b4c6e0a3
Create Date: 2026-10-18
"""

import sqlalchemy as sa
from alembic import op

revision = 'e3a9c5d7f1b4'
down_revision = 'd2f8b4c6e0a3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('transition_unchanged', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_column('transition_unchanged')
