"""add OIDC login: auth_provider, admin_user_identity, password_login_allowed

Revision ID: b8e3d5f9a2c4
Revises: a7d2c4e8f1b3
Create Date: 2026-10-07
"""

import sqlalchemy as sa
from alembic import op

revision = 'b8e3d5f9a2c4'
down_revision = 'a7d2c4e8f1b3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'auth_provider',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(64), nullable=False, unique=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('issuer', sa.String(512), nullable=False),
        sa.Column('client_id', sa.String(512), nullable=False),
        sa.Column('client_secret', sa.Text(), nullable=True),
        sa.Column('scopes', sa.String(512), nullable=False, server_default='openid profile email'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_table(
        'admin_user_identity',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('admin_user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('issuer', sa.String(512), nullable=False),
        sa.Column('subject', sa.String(255), nullable=False),
        sa.Column('provider_id', sa.Integer(), sa.ForeignKey('auth_provider.id', ondelete='SET NULL'), nullable=True),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('issuer', 'subject', name='uq_admin_user_identity_issuer_subject'),
    )
    op.create_index('ix_admin_user_identity_user_id', 'admin_user_identity', ['user_id'])
    # Every existing account is a local one with a password, so it keeps
    # password login — nobody is locked out by this migration.
    with op.batch_alter_table('admin_user') as batch_op:
        batch_op.add_column(sa.Column('password_login_allowed', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade():
    with op.batch_alter_table('admin_user') as batch_op:
        batch_op.drop_column('password_login_allowed')
    op.drop_index('ix_admin_user_identity_user_id', table_name='admin_user_identity')
    op.drop_table('admin_user_identity')
    op.drop_table('auth_provider')
