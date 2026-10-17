"""plugin: which plugins are switched on (state of the plugin system)

Revision ID: a7c3e5f1b9d2
Revises: f4d9e1a6b3c0
Create Date: 2026-10-17
"""

import sqlalchemy as sa
from alembic import op

revision = 'a7c3e5f1b9d2'
down_revision = 'f4d9e1a6b3c0'
branch_labels = None
depends_on = None


def upgrade():
    if 'plugin' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'plugin',
        sa.Column('id', sa.String(length=100), primary_key=True),
        sa.Column('version', sa.String(length=40), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('schema_version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('installed_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('plugin')
