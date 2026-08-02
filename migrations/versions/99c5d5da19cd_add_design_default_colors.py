"""Add default_colors to Design.

Revision ID: 99c5d5da19cd
Revises: c9d0e1f2a3b4
Create Date: 2026-08-02
"""

from alembic import op
import sqlalchemy as sa

revision = '99c5d5da19cd'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('default_colors', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_column('default_colors')
