"""add indexes on frequently-joined/filtered foreign-key columns that were
never indexed: content_element.contenttype_id, tagconfig.contenttype_id,
tagconfig.contentcontainer_id, device.screen_id, group.parent_group_id.

Revision ID: 73ac2fc69719
Revises: 92555b233f93
Create Date: 2026-08-02
"""

from alembic import op

revision = '73ac2fc69719'
down_revision = '92555b233f93'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('content_element') as batch_op:
        batch_op.create_index('ix_content_element_contenttype_id', ['contenttype_id'])
    with op.batch_alter_table('tagconfig') as batch_op:
        batch_op.create_index('ix_tagconfig_contenttype_id', ['contenttype_id'])
        batch_op.create_index('ix_tagconfig_contentcontainer_id', ['contentcontainer_id'])
    with op.batch_alter_table('device') as batch_op:
        batch_op.create_index('ix_device_screen_id', ['screen_id'])
    with op.batch_alter_table('group') as batch_op:
        batch_op.create_index('ix_group_parent_group_id', ['parent_group_id'])


def downgrade():
    with op.batch_alter_table('group') as batch_op:
        batch_op.drop_index('ix_group_parent_group_id')
    with op.batch_alter_table('device') as batch_op:
        batch_op.drop_index('ix_device_screen_id')
    with op.batch_alter_table('tagconfig') as batch_op:
        batch_op.drop_index('ix_tagconfig_contentcontainer_id')
        batch_op.drop_index('ix_tagconfig_contenttype_id')
    with op.batch_alter_table('content_element') as batch_op:
        batch_op.drop_index('ix_content_element_contenttype_id')
