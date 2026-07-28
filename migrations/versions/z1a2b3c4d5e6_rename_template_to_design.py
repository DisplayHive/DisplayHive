"""rename template table to design

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
Create Date: 2026-07-28
"""

from alembic import op

revision = 'z1a2b3c4d5e6'
down_revision = 'y0z1a2b3c4d5'
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table('template', 'design')


def downgrade():
    op.rename_table('design', 'template')
