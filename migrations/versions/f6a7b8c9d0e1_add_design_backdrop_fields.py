"""Add Backdrop fields to Design: background_color and background_image_url.

Rendered as the body's background-color and a bottommost background-image
layer, beneath any Gradients — see render_backdrop_css().

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa

revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('background_color', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('background_image_url', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_column('background_image_url')
        batch_op.drop_column('background_color')
