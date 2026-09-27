"""drop magic tags feature (magic_tag, magic_tag_value_list, magic_tag_value_list_entry)

The Magic Tags feature (global {{ var_name }} template substitution) has
been removed from the app entirely — see application/admin/content/helper.py
and application/admin/designs/helper.py, which no longer call
substitute_magic_tags. This migration drops the three tables that backed
it. This is a permanent, destructive migration: any existing magic tag
data is not recoverable, even if this migration is later downgraded (the
downgrade only recreates the empty schema).

Revision ID: 49c967c07605
Revises: 5d4a0acfbdd4
Create Date: 2026-09-27
"""

from alembic import op
import sqlalchemy as sa

revision = '49c967c07605'
down_revision = '5d4a0acfbdd4'
branch_labels = None
depends_on = None


def upgrade():
    # Child-to-parent FK order.
    op.drop_table('magic_tag_value_list_entry')
    op.drop_table('magic_tag')
    op.drop_table('magic_tag_value_list')


def downgrade():
    # Schema-only recreation — matches the tables' final shape before
    # removal. The data itself is gone; this just restores the structure.
    op.create_table(
        'magic_tag_value_list',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('uuid', sa.String(length=36), nullable=False, unique=True),
        sa.Column('name', sa.String(length=255), nullable=False),
    )
    op.create_index('ix_magic_tag_value_list_uuid', 'magic_tag_value_list', ['uuid'], unique=True)

    op.create_table(
        'magic_tag',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('uuid', sa.String(length=36), nullable=False, unique=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('type', sa.String(length=20), nullable=False, server_default='text'),
        sa.Column('value_list_id', sa.Integer(), sa.ForeignKey('magic_tag_value_list.id'), nullable=True),
    )
    op.create_index('ix_magic_tag_uuid', 'magic_tag', ['uuid'], unique=True)

    op.create_table(
        'magic_tag_value_list_entry',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('value_list_id', sa.Integer(), sa.ForeignKey('magic_tag_value_list.id'), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
    )
