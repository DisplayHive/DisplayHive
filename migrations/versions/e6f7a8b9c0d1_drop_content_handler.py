"""Drop content_handler table.

Each ContentContainer a Contenttype uses is now itself a field (TagConfig)
with an assigned field_handler — there is no separate per-container render
template, so ContentHandler is no longer needed.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa

revision = 'e6f7a8b9c0d1'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('content_handler')


def downgrade():
    bind = op.get_bind()

    op.create_table(
        'content_handler',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('contenttype_id', sa.Integer(), sa.ForeignKey('contenttype.id'), nullable=False),
        sa.Column('contentcontainer_id', sa.Integer(), sa.ForeignKey('contentcontainer.id'), nullable=True),
        sa.Column('html', sa.Text(), nullable=False),
        sa.Column('css', sa.Text(), nullable=True),
    )

    # Best-effort: synthesize one empty-html ContentHandler per distinct
    # (contenttype_id, contentcontainer_id) pair currently in use by
    # tagconfig, so the prior migration's downgrade (which looks up a
    # handler id per tagconfig) has something to find. The original
    # per-container render templates are not recoverable at this point.
    rows = bind.execute(sa.text(
        'SELECT DISTINCT contenttype_id, contentcontainer_id FROM tagconfig '
        'WHERE contenttype_id IS NOT NULL'
    )).fetchall()
    for contenttype_id, contentcontainer_id in rows:
        bind.execute(
            sa.text(
                'INSERT INTO content_handler (contenttype_id, contentcontainer_id, html, css) '
                'VALUES (:contenttype_id, :contentcontainer_id, :html, :css)'
            ),
            {'contenttype_id': contenttype_id, 'contentcontainer_id': contentcontainer_id, 'html': '', 'css': None},
        )
