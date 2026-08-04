"""Replace TagConfig's whole-field locked/hidden with per-option option_flags.

Revision ID: c7e2b5a3f108
Revises: b4f6a1d0e7c2
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa

revision = 'c7e2b5a3f108'
down_revision = 'b4f6a1d0e7c2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tagconfig') as batch_op:
        batch_op.add_column(sa.Column('option_flags', sa.Text(), nullable=True))
        batch_op.drop_column('hidden')
        batch_op.drop_column('locked')


def downgrade():
    with op.batch_alter_table('tagconfig') as batch_op:
        batch_op.add_column(sa.Column('locked', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('hidden', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.drop_column('option_flags')
