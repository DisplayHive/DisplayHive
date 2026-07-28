"""drop contenttype_container association table

Content types are no longer restricted to specific content containers.

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa

revision = 'y0z1a2b3c4d5'
down_revision = 'x9y0z1a2b3c4'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('contenttype_container')


def downgrade():
    op.create_table(
        'contenttype_container',
        sa.Column('contenttype_id', sa.Integer(), sa.ForeignKey('contenttype.id'), primary_key=True),
        sa.Column('contentcontainer_id', sa.Integer(), sa.ForeignKey('contentcontainer.id'), primary_key=True),
    )
