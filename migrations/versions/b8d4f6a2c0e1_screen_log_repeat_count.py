"""screen_log.repeat_count: identical consecutive lines of a screen are counted, not stored again

Revision ID: b8d4f6a2c0e1
Revises: a7c3e5f1b9d2
Create Date: 2026-10-18
"""

from alembic import op
import sqlalchemy as sa

revision = 'b8d4f6a2c0e1'
down_revision = 'a7c3e5f1b9d2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('screen_log') as batch:
        batch.add_column(sa.Column('repeat_count', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    with op.batch_alter_table('screen_log') as batch:
        batch.drop_column('repeat_count')
