"""Support multiple gradients per Design and the full gradient feature set.

- Gradient gains: repeating, shape, size, position_x, position_y (conic type
  was already free-form text, no migration needed for that).
- New design_gradient association table (ordered many-to-many) replaces the
  single design.gradient_id FK — a Design can now stack several gradients as
  layered `background-image` values. Existing single assignments are
  backfilled into the new table before the old column is dropped.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('gradient') as batch_op:
        batch_op.add_column(sa.Column('repeating', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('shape', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('size', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('position_x', sa.Float(), nullable=False, server_default='50'))
        batch_op.add_column(sa.Column('position_y', sa.Float(), nullable=False, server_default='50'))

    op.create_table(
        'design_gradient',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('design_id', sa.Integer(), sa.ForeignKey('design.id'), nullable=False),
        sa.Column('gradient_id', sa.Integer(), sa.ForeignKey('gradient.id'), nullable=False),
        sa.Column('order', sa.Integer(), nullable=False, server_default='0'),
        sa.UniqueConstraint('design_id', 'gradient_id', name='uq_design_gradient'),
    )

    # Backfill: one row per Design that already had a single gradient_id set.
    bind = op.get_bind()
    rows = bind.execute(sa.text('SELECT id, gradient_id FROM design WHERE gradient_id IS NOT NULL')).fetchall()
    for design_id, gradient_id in rows:
        bind.execute(
            sa.text('INSERT INTO design_gradient (design_id, gradient_id, "order") VALUES (:d, :g, 0)'),
            {'d': design_id, 'g': gradient_id},
        )

    with op.batch_alter_table('design') as batch_op:
        batch_op.drop_constraint('fk_design_gradient_id_gradient', type_='foreignkey')
        batch_op.drop_column('gradient_id')


def downgrade():
    with op.batch_alter_table('design') as batch_op:
        batch_op.add_column(sa.Column('gradient_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_design_gradient_id_gradient', 'gradient', ['gradient_id'], ['id'])

    bind = op.get_bind()
    rows = bind.execute(sa.text(
        'SELECT design_id, gradient_id FROM design_gradient GROUP BY design_id HAVING MIN("order")'
    )).fetchall()
    for design_id, gradient_id in rows:
        bind.execute(
            sa.text('UPDATE design SET gradient_id = :g WHERE id = :d'),
            {'d': design_id, 'g': gradient_id},
        )

    op.drop_table('design_gradient')

    with op.batch_alter_table('gradient') as batch_op:
        batch_op.drop_column('position_y')
        batch_op.drop_column('position_x')
        batch_op.drop_column('size')
        batch_op.drop_column('shape')
        batch_op.drop_column('repeating')
