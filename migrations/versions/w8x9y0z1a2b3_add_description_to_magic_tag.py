"""add description to magic_tag

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa

revision = 'w8x9y0z1a2b3'
down_revision = 'v7w8x9y0z1a2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('magic_tag') as batch_op:
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('magic_tag') as batch_op:
        batch_op.drop_column('description')
