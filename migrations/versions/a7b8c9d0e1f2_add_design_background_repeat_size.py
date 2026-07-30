"""Add background_repeat, background_size and background_opacity to Design's Backdrop.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa

revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('background_repeat', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('background_size', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('background_opacity', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_column('background_opacity')
        batch_op.drop_column('background_size')
        batch_op.drop_column('background_repeat')
