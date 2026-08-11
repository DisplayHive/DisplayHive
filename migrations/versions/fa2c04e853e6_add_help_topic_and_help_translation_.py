"""add help_topic and help_translation tables

Revision ID: fa2c04e853e6
Revises: c7e2b5a3f108
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa

revision = 'fa2c04e853e6'
down_revision = 'c7e2b5a3f108'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'help_topic',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('context', sa.String(length=100), nullable=False),
        sa.Column('docs_url', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_table(
        'help_translation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.Column('locale', sa.String(length=10), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['topic_id'], ['help_topic.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('topic_id', 'locale', name='uq_help_translation_topic_locale'),
    )
    with op.batch_alter_table('help_translation') as batch_op:
        batch_op.create_index('ix_help_translation_topic_id', ['topic_id'])


def downgrade():
    with op.batch_alter_table('help_translation') as batch_op:
        batch_op.drop_index('ix_help_translation_topic_id')
    op.drop_table('help_translation')
    op.drop_table('help_topic')
