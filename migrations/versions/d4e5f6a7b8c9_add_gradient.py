"""Add gradient table and design.gradient_id.

A reusable, named CSS gradient (linear or radial) that can be applied as a
Design's body background — rendered ahead of that Design's own hand-written
CSS so a manual edit can still override it.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'gradient',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=20), nullable=False, server_default='linear'),
        sa.Column('angle', sa.Integer(), nullable=False, server_default='180'),
        sa.Column('stops', sa.Text(), nullable=False, server_default='[]'),
    )

    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('gradient_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_design_gradient_id_gradient', 'gradient', ['gradient_id'], ['id'])


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_constraint('fk_design_gradient_id_gradient', type_='foreignkey')
        batch_op.drop_column('gradient_id')

    op.drop_table('gradient')
