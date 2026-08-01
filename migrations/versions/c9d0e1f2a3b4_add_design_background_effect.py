"""Add background_effect and background_effect_settings to Design.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-01
"""

from alembic import op
import sqlalchemy as sa

revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('background_effect', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('background_effect_settings', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_column('background_effect_settings')
        batch_op.drop_column('background_effect')
