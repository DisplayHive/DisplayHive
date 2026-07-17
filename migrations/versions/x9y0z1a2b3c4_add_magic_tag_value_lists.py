"""add magic tag value lists and type/value_list_id to magic_tag

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa

revision = 'x9y0z1a2b3c4'
down_revision = 'w8x9y0z1a2b3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'magic_tag_value_list',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
    )
    op.create_table(
        'magic_tag_value_list_entry',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('value_list_id', sa.Integer(), sa.ForeignKey('magic_tag_value_list.id'), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
    )
    with op.batch_alter_table('magic_tag') as batch_op:
        batch_op.add_column(sa.Column('type', sa.String(length=20), nullable=False, server_default='text'))
        batch_op.add_column(sa.Column('value_list_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_magic_tag_value_list_id', 'magic_tag_value_list', ['value_list_id'], ['id']
        )


def downgrade():
    with op.batch_alter_table('magic_tag') as batch_op:
        batch_op.drop_constraint('fk_magic_tag_value_list_id', type_='foreignkey')
        batch_op.drop_column('value_list_id')
        batch_op.drop_column('type')
    op.drop_table('magic_tag_value_list_entry')
    op.drop_table('magic_tag_value_list')
