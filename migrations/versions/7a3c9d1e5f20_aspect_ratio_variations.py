"""aspect ratio variations: design ratios, screen ratio, layout variations, container positions

Revision ID: 7a3c9d1e5f20
Revises: 6e2f1a9c4b7d
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = '7a3c9d1e5f20'
down_revision = '6e2f1a9c4b7d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('aspect_ratios', sa.Text(), nullable=True))
    with op.batch_alter_table('screen') as batch_op:
        batch_op.add_column(sa.Column('aspect_ratio', sa.String(16), nullable=False, server_default='16:9'))

    op.create_table(
        'layout_variation',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('layout_id', sa.Integer(), sa.ForeignKey('layout.id', ondelete='CASCADE'), nullable=False),
        sa.Column('aspect_ratio', sa.String(16), nullable=False),
        sa.UniqueConstraint('layout_id', 'aspect_ratio', name='uq_layout_variation'),
    )
    op.create_index('ix_layout_variation_layout_id', 'layout_variation', ['layout_id'])
    op.create_table(
        'layout_variation_container',
        sa.Column('variation_id', sa.Integer(), sa.ForeignKey('layout_variation.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('contentcontainer_id', sa.Integer(), sa.ForeignKey('contentcontainer.id', ondelete='CASCADE'), primary_key=True),
    )
    op.create_table(
        'container_position',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('contentcontainer_id', sa.Integer(), sa.ForeignKey('contentcontainer.id', ondelete='CASCADE'), nullable=False),
        sa.Column('aspect_ratio', sa.String(16), nullable=False),
        sa.Column('top', sa.Float(), nullable=False),
        sa.Column('left', sa.Float(), nullable=False),
        sa.Column('width', sa.Float(), nullable=False),
        sa.Column('height', sa.Float(), nullable=False),
        sa.UniqueConstraint('contentcontainer_id', 'aspect_ratio', name='uq_container_position'),
    )
    op.create_index('ix_container_position_contentcontainer_id', 'container_position', ['contentcontainer_id'])


def downgrade():
    op.drop_index('ix_container_position_contentcontainer_id', table_name='container_position')
    op.drop_table('container_position')
    op.drop_table('layout_variation_container')
    op.drop_index('ix_layout_variation_layout_id', table_name='layout_variation')
    op.drop_table('layout_variation')
    with op.batch_alter_table('screen') as batch_op:
        batch_op.drop_column('aspect_ratio')
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_column('aspect_ratios')
