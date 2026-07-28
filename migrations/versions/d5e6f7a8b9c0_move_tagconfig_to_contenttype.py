"""Move TagConfig ownership from ContentHandler to Contenttype.

Fields (TagConfig) are shared across all of a Contenttype's ContentHandlers
rather than duplicated per handler — each field now records which container
it targets directly (contentcontainer_id), instead of being scoped to one
ContentHandler.

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa

revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    with op.batch_alter_table('tagconfig', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contenttype_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('contentcontainer_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_tagconfig_contenttype_id_contenttype', 'contenttype', ['contenttype_id'], ['id'])
        batch_op.create_foreign_key('fk_tagconfig_contentcontainer_id_contentcontainer', 'contentcontainer', ['contentcontainer_id'], ['id'])

    # Backfill from each tagconfig's current content_handler.
    rows = bind.execute(sa.text(
        'SELECT tc.id, ch.contenttype_id, ch.contentcontainer_id '
        'FROM tagconfig tc JOIN content_handler ch ON ch.id = tc.content_handler_id'
    )).fetchall()
    for tc_id, contenttype_id, contentcontainer_id in rows:
        bind.execute(
            sa.text('UPDATE tagconfig SET contenttype_id = :contenttype_id, contentcontainer_id = :contentcontainer_id WHERE id = :id'),
            {'contenttype_id': contenttype_id, 'contentcontainer_id': contentcontainer_id, 'id': tc_id},
        )

    with op.batch_alter_table('tagconfig', schema=None) as batch_op:
        batch_op.drop_column('content_handler_id')


def downgrade():
    bind = op.get_bind()

    with op.batch_alter_table('tagconfig', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content_handler_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_tagconfig_content_handler_id_content_handler', 'content_handler', ['content_handler_id'], ['id'])

    # Best-effort: point each tagconfig at the first ContentHandler matching
    # both its contenttype and target container (falls back to the first
    # handler for that contenttype if no exact container match exists).
    rows = bind.execute(sa.text('SELECT id, contenttype_id, contentcontainer_id FROM tagconfig')).fetchall()
    for tc_id, contenttype_id, contentcontainer_id in rows:
        handler_id = None
        if contenttype_id is not None:
            row = bind.execute(
                sa.text(
                    'SELECT id FROM content_handler WHERE contenttype_id = :contenttype_id '
                    'AND (contentcontainer_id = :contentcontainer_id OR :contentcontainer_id IS NULL) '
                    'ORDER BY id LIMIT 1'
                ),
                {'contenttype_id': contenttype_id, 'contentcontainer_id': contentcontainer_id},
            ).fetchone()
            if not row:
                row = bind.execute(
                    sa.text('SELECT id FROM content_handler WHERE contenttype_id = :contenttype_id ORDER BY id LIMIT 1'),
                    {'contenttype_id': contenttype_id},
                ).fetchone()
            if row:
                handler_id = row[0]
        bind.execute(
            sa.text('UPDATE tagconfig SET content_handler_id = :handler_id WHERE id = :id'),
            {'handler_id': handler_id, 'id': tc_id},
        )

    with op.batch_alter_table('tagconfig', schema=None) as batch_op:
        batch_op.drop_column('contentcontainer_id')
        batch_op.drop_column('contenttype_id')
