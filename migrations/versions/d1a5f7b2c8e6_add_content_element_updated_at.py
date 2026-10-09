"""content_element.updated_at: when a content element was last written (Dashboard: recently changed)

Existing rows stay NULL until they are edited next.

Revision ID: d1a5f7b2c8e6
Revises: c9f4e6a0b3d5
Create Date: 2026-10-09
"""

import sqlalchemy as sa
from alembic import op

revision = 'd1a5f7b2c8e6'
down_revision = 'c9f4e6a0b3d5'
branch_labels = None
depends_on = None


def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('content_element')}
    if 'updated_at' not in columns:
        op.add_column('content_element', sa.Column('updated_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('content_element') as batch:
        batch.drop_column('updated_at')
