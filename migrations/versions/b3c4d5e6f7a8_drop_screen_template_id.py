"""drop screen.template_id

Design is now a single instance-wide setting with no per-screen override.

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa

revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('screen', schema=None) as batch_op:
        batch_op.drop_column('template_id')


def downgrade():
    with op.batch_alter_table('screen', schema=None) as batch_op:
        batch_op.add_column(sa.Column('template_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_screen_template_id_design', 'design', ['template_id'], ['id'])
