"""Add default_field_handler/default_content to contentcontainer.

Lets a container render fallback content (via the same field_handler
transform used by TagConfig) whenever no active scene currently targets it,
instead of always going blank.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-07-29
"""

from alembic import op
import sqlalchemy as sa

revision = 'f7a8b9c0d1e2'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('contentcontainer') as batch_op:
        batch_op.add_column(sa.Column('default_field_handler', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('default_content', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('contentcontainer') as batch_op:
        batch_op.drop_column('default_content')
        batch_op.drop_column('default_field_handler')
