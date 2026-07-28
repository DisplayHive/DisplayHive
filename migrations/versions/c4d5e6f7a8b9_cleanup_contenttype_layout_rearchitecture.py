"""cleanup: drop legacy contenttype.html/.css and tagconfig.contenttype_id,
tighten new FKs to non-null now that ContentHandler owns rendering markup.

contenttype.html was NOT NULL in the original schema; since Contenttype no
longer has an html/css column at all (moved to ContentHandler), this must be
dropped now rather than deferred — leaving it in place would break every
Contenttype creation (INSERT with no value for a NOT NULL column).

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa

revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('contenttype', schema=None) as batch_op:
        batch_op.drop_column('html')
        batch_op.drop_column('css')

    with op.batch_alter_table('tagconfig', schema=None) as batch_op:
        batch_op.drop_column('contenttype_id')


def downgrade():
    with op.batch_alter_table('tagconfig', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contenttype_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_tagconfig_contenttype_id_contenttype', 'contenttype', ['contenttype_id'], ['id'])

    with op.batch_alter_table('contenttype', schema=None) as batch_op:
        batch_op.add_column(sa.Column('html', sa.Text(), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('css', sa.Text(), nullable=True))
