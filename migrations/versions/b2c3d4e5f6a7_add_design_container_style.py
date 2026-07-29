"""Add design_container_style table.

A scoped (design, container) key/value store for per-container CSS property
overrides — starting with a "Font" group (font-family, font-variant,
font-weight, font-stretch, font-size, line-height, font-style). Rendered
into `.dh-container-<id> { ... }` rules and appended to the owning Design's
CSS at push time; an empty value means the property is left unset.

Revision ID: b2c3d4e5f6a7
Revises: f7a8b9c0d1e2
Create Date: 2026-07-29
"""

from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'design_container_style',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('design_id', sa.Integer(), sa.ForeignKey('design.id'), nullable=False),
        sa.Column('contentcontainer_id', sa.Integer(), sa.ForeignKey('contentcontainer.id'), nullable=False),
        sa.Column('property', sa.String(length=100), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.UniqueConstraint('design_id', 'contentcontainer_id', 'property', name='uq_design_container_style'),
    )


def downgrade():
    op.drop_table('design_container_style')
