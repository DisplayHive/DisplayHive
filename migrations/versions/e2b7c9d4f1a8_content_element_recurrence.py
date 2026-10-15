"""content_element.recurrence: weekly time windows (JSON text, NULL = always)

Revision ID: e2b7c9d4f1a8
Revises: d1a5f7b2c8e6
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

revision = 'e2b7c9d4f1a8'
down_revision = 'd1a5f7b2c8e6'
branch_labels = None
depends_on = None


def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('content_element')}
    if 'recurrence' not in columns:
        op.add_column('content_element', sa.Column('recurrence', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('content_element') as batch:
        batch.drop_column('recurrence')
