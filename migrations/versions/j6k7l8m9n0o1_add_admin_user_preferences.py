"""add preferences column to admin_user

Revision ID: j6k7l8m9n0o1
Revises: 6a7b8c9d0e1f
Create Date: 2026-09-19
"""

import sqlalchemy as sa
from alembic import op

revision = 'j6k7l8m9n0o1'
down_revision = '6a7b8c9d0e1f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('admin_user', sa.Column('preferences', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('admin_user', 'preferences')
