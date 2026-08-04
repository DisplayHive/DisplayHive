"""Add default_value preset use (locked/hidden) columns to TagConfig.

Revision ID: b4f6a1d0e7c2
Revises: 73ac2fc69719
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa

revision = 'b4f6a1d0e7c2'
down_revision = '73ac2fc69719'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tagconfig') as batch_op:
        batch_op.add_column(sa.Column('locked', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('hidden', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table('tagconfig') as batch_op:
        batch_op.drop_column('hidden')
        batch_op.drop_column('locked')
