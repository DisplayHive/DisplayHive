"""delete orphaned rows in tables whose ondelete='CASCADE' FK was never
enforced on SQLite (the app now enables PRAGMA foreign_keys=ON for every
SQLite connection, see app.py) — one-time cleanup so those constraints don't
immediately fail on rows that predate enforcement.

Revision ID: 92555b233f93
Revises: 99c5d5da19cd
Create Date: 2026-08-02
"""

from alembic import op
import sqlalchemy as sa

revision = '92555b233f93'
down_revision = '99c5d5da19cd'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(sa.text(
        'DELETE FROM group_right WHERE group_id NOT IN (SELECT id FROM "group") '
        'OR right_id NOT IN (SELECT id FROM right_definition)'
    ))
    conn.execute(sa.text(
        'DELETE FROM user_group WHERE user_id NOT IN (SELECT id FROM admin_user) '
        'OR group_id NOT IN (SELECT id FROM "group")'
    ))
    conn.execute(sa.text(
        'DELETE FROM user_right WHERE user_id NOT IN (SELECT id FROM admin_user) '
        'OR right_id NOT IN (SELECT id FROM right_definition)'
    ))
    conn.execute(sa.text(
        'DELETE FROM screen_log WHERE screen_id NOT IN (SELECT id FROM screen)'
    ))
    conn.execute(sa.text(
        'DELETE FROM alert_subscription WHERE user_id NOT IN (SELECT id FROM telegram_users)'
    ))


def downgrade():
    # Deleted rows were already-orphaned garbage with no valid parent to
    # restore a relationship to — nothing meaningful to reverse.
    pass
