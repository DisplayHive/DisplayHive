"""Drop ContentContainer.title — redundant with .name, which now covers both.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa

revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('contentcontainer') as batch_op:
        batch_op.drop_column('title')


def downgrade():
    with op.batch_alter_table('contentcontainer') as batch_op:
        batch_op.add_column(sa.Column('title', sa.String(length=255), nullable=True))
