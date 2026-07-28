"""Add Layout/ContentHandler, reshape ContentContainer with position fields,
give Contenttype a layout_id and TagConfig a content_handler_id, and backfill
existing data into the new shape.

Revision ID: a2b3c4d5e6f7
Revises: z1a2b3c4d5e6
Create Date: 2026-07-28
"""

from alembic import op
import sqlalchemy as sa

revision = 'a2b3c4d5e6f7'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # --- New tables -----------------------------------------------------
    op.create_table(
        'layout',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
    )
    op.create_table(
        'layout_container',
        sa.Column('layout_id', sa.Integer(), sa.ForeignKey('layout.id'), primary_key=True),
        sa.Column('contentcontainer_id', sa.Integer(), sa.ForeignKey('contentcontainer.id'), primary_key=True),
    )
    op.create_table(
        'content_handler',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('contenttype_id', sa.Integer(), sa.ForeignKey('contenttype.id'), nullable=False),
        sa.Column('contentcontainer_id', sa.Integer(), sa.ForeignKey('contentcontainer.id'), nullable=True),
        sa.Column('html', sa.Text(), nullable=False),
        sa.Column('css', sa.Text(), nullable=True),
    )

    # --- Capture old template_id links before dropping the column -------
    old_links = bind.execute(sa.text(
        'SELECT id, template_id FROM contentcontainer WHERE template_id IS NOT NULL'
    )).fetchall()

    designs = bind.execute(sa.text('SELECT id, name, "isDefault" FROM design')).fetchall()

    # --- One migrated Layout per Design, carrying its old containers ----
    design_layout_id = {}
    for design_id, name, _is_default in designs:
        result = bind.execute(
            sa.text('INSERT INTO layout (name, description) VALUES (:name, :description) RETURNING id'),
            {'name': f'{name} (migrated)', 'description': None},
        )
        layout_id = result.scalar_one()
        design_layout_id[design_id] = layout_id

    for container_id, template_id in old_links:
        layout_id = design_layout_id.get(template_id)
        if layout_id is not None:
            bind.execute(
                sa.text('INSERT INTO layout_container (layout_id, contentcontainer_id) VALUES (:layout_id, :container_id)'),
                {'layout_id': layout_id, 'container_id': container_id},
            )

    # --- Reshape ContentContainer: drop template_id, add position fields ---
    with op.batch_alter_table('contentcontainer', schema=None) as batch_op:
        batch_op.add_column(sa.Column('top', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('left', sa.Float(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('width', sa.Float(), nullable=False, server_default='100'))
        batch_op.add_column(sa.Column('height', sa.Float(), nullable=False, server_default='100'))
        batch_op.drop_column('template_id')

    # --- Contenttype gains layout_id (nullable for now, tightened in cleanup) ---
    # SQLite's batch mode recreates the table to apply schema changes, which
    # requires any new FK constraint to have an explicit name.
    with op.batch_alter_table('contenttype', schema=None) as batch_op:
        batch_op.add_column(sa.Column('layout_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_contenttype_layout_id_layout', 'layout', ['layout_id'], ['id'])

    # --- TagConfig gains content_handler_id (nullable for now) ----------
    with op.batch_alter_table('tagconfig', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content_handler_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_tagconfig_content_handler_id_content_handler', 'content_handler', ['content_handler_id'], ['id'])

    # --- Best-effort default Layout for existing Contenttypes -----------
    # Resolution mirrors get_default_design(): isDefault==True, else first by id.
    default_design_id = None
    for design_id, _name, is_default in designs:
        if is_default:
            default_design_id = design_id
            break
    if default_design_id is None and designs:
        default_design_id = designs[0][0]
    default_layout_id = design_layout_id.get(default_design_id)

    contenttypes = bind.execute(sa.text('SELECT id, html, css FROM contenttype')).fetchall()

    first_container_by_layout = {}
    if default_layout_id is not None:
        row = bind.execute(
            sa.text(
                'SELECT lc.contentcontainer_id FROM layout_container lc '
                'JOIN contentcontainer cc ON cc.id = lc.contentcontainer_id '
                'WHERE lc.layout_id = :layout_id ORDER BY cc."order", cc.id LIMIT 1'
            ),
            {'layout_id': default_layout_id},
        ).fetchone()
        if row:
            first_container_by_layout[default_layout_id] = row[0]

    contenttype_handler_id = {}
    for ct_id, html, css in contenttypes:
        if default_layout_id is not None:
            bind.execute(
                sa.text('UPDATE contenttype SET layout_id = :layout_id WHERE id = :id'),
                {'layout_id': default_layout_id, 'id': ct_id},
            )
        result = bind.execute(
            sa.text(
                'INSERT INTO content_handler (contenttype_id, contentcontainer_id, html, css) '
                'VALUES (:contenttype_id, :contentcontainer_id, :html, :css) RETURNING id'
            ),
            {
                'contenttype_id': ct_id,
                'contentcontainer_id': first_container_by_layout.get(default_layout_id),
                'html': html or '',
                'css': css,
            },
        )
        contenttype_handler_id[ct_id] = result.scalar_one()

    tagconfigs = bind.execute(sa.text('SELECT id, contenttype_id FROM tagconfig')).fetchall()
    for tc_id, ct_id in tagconfigs:
        handler_id = contenttype_handler_id.get(ct_id)
        if handler_id is not None:
            bind.execute(
                sa.text('UPDATE tagconfig SET content_handler_id = :handler_id WHERE id = :id'),
                {'handler_id': handler_id, 'id': tc_id},
            )


def downgrade():
    with op.batch_alter_table('tagconfig', schema=None) as batch_op:
        batch_op.drop_column('content_handler_id')

    with op.batch_alter_table('contenttype', schema=None) as batch_op:
        batch_op.drop_column('layout_id')

    with op.batch_alter_table('contentcontainer', schema=None) as batch_op:
        batch_op.add_column(sa.Column('template_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_contentcontainer_template_id_design', 'design', ['template_id'], ['id'])
        batch_op.drop_column('height')
        batch_op.drop_column('width')
        batch_op.drop_column('left')
        batch_op.drop_column('top')

    op.drop_table('content_handler')
    op.drop_table('layout_container')
    op.drop_table('layout')
