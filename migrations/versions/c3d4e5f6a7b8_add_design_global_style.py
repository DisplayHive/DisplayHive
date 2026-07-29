"""Add design_global_style table.

The "global" counterpart to design_container_style — a (design, property)
key/value store for CSS overrides applied to every container via a shared
`.dh-container` class, rather than one specific `.dh-container-<id>`.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-29
"""

from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'design_global_style',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('design_id', sa.Integer(), sa.ForeignKey('design.id'), nullable=False),
        sa.Column('property', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.UniqueConstraint('design_id', 'property', name='uq_design_global_style'),
    )


def downgrade():
    op.drop_table('design_global_style')
