"""admin_user_passkey: WebAuthn credentials (passkeys) admins sign in with

Revision ID: f4d9e1a6b3c0
Revises: e2b7c9d4f1a8
Create Date: 2026-10-16
"""

import sqlalchemy as sa
from alembic import op

revision = 'f4d9e1a6b3c0'
down_revision = 'e2b7c9d4f1a8'
branch_labels = None
depends_on = None


def upgrade():
    if 'admin_user_passkey' in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        'admin_user_passkey',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('admin_user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('credential_id', sa.String(length=1024), nullable=False),
        sa.Column('public_key', sa.Text(), nullable=False),
        sa.Column('sign_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('transports', sa.Text(), nullable=True),
        sa.Column('synced', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_admin_user_passkey_user_id', 'admin_user_passkey', ['user_id'])
    op.create_index('ix_admin_user_passkey_credential_id', 'admin_user_passkey', ['credential_id'], unique=True)


def downgrade():
    op.drop_index('ix_admin_user_passkey_credential_id', table_name='admin_user_passkey')
    op.drop_index('ix_admin_user_passkey_user_id', table_name='admin_user_passkey')
    op.drop_table('admin_user_passkey')
