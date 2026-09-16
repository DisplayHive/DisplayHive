"""Tests for application/permissions.py: the rights resolution algorithm.

Every function under test takes the Flask-SQLAlchemy extension object (it
calls `db.session`/`db.select` internally) — passed here as `flask_app.db`
— not a bare Session. The test-local helpers below (`_grant`/`_set_override`)
use the raw `db_session` Session directly for setup, same as everywhere else
in this suite.

Real RightDefinition rows already exist for every key in
application.permissions.RIGHTS — app.py's module-level startup runs
sync_right_definitions() on import — so these tests exercise real right keys
rather than inventing fake ones (has_right() silently returns False for a
right_key with no RightDefinition row, which would mask what these tests are
actually trying to exercise).
"""

from application.permissions import (
    effective_group_closure,
    has_right,
    is_superadmin,
    sync_right_definitions,
    would_create_cycle,
)

RIGHT_KEY = 'media.page'
OTHER_RIGHT_KEY = 'media.upload'


def _grant(db_session, group, right_key):
    from sqlalchemy import select
    from application.models import GroupRight, RightDefinition

    right = db_session.execute(select(RightDefinition).where(RightDefinition.key == right_key)).scalar_one()
    db_session.add(GroupRight(group_id=group.id, right_id=right.id))
    db_session.commit()


def _set_override(db_session, user, right_key, value):
    from sqlalchemy import select
    from application.models import RightDefinition, UserRight

    right = db_session.execute(select(RightDefinition).where(RightDefinition.key == right_key)).scalar_one()
    db_session.add(UserRight(user_id=user.id, right_id=right.id, value=value))
    db_session.commit()


# --- has_right -----------------------------------------------------------------


def test_has_right_false_with_no_group_and_no_override(flask_app, db_session, make_user):
    user = make_user()
    assert has_right(flask_app.db, user, RIGHT_KEY) is False


def test_has_right_true_when_group_grants_it(flask_app, db_session, make_user, make_group):
    from application.models import UserGroup

    user = make_user()
    group = make_group()
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.commit()
    _grant(db_session, group, RIGHT_KEY)

    assert has_right(flask_app.db, user, RIGHT_KEY) is True
    # A right the group was never granted stays denied.
    assert has_right(flask_app.db, user, OTHER_RIGHT_KEY) is False


def test_has_right_user_allow_override_wins_with_no_group_grant(flask_app, db_session, make_user):
    user = make_user()
    _set_override(db_session, user, RIGHT_KEY, 'allow')
    assert has_right(flask_app.db, user, RIGHT_KEY) is True


def test_has_right_user_deny_override_beats_superadmin_group(flask_app, db_session, make_user, make_group):
    """The single highest-value case in this file: an explicit per-user
    'deny' must win even when the user is in the superadmin group, which
    would otherwise grant every right unconditionally."""
    from application.models import UserGroup

    user = make_user()
    superadmin_group = make_group(is_superadmin=True)
    db_session.add(UserGroup(user_id=user.id, group_id=superadmin_group.id))
    db_session.commit()

    # Sanity check: superadmin membership alone grants the right.
    assert has_right(flask_app.db, user, RIGHT_KEY) is True

    _set_override(db_session, user, RIGHT_KEY, 'deny')
    assert has_right(flask_app.db, user, RIGHT_KEY) is False


def test_has_right_unknown_right_key_is_false(flask_app, db_session, make_user):
    user = make_user()
    assert has_right(flask_app.db, user, 'not.a.real.right') is False


def test_has_right_none_user_is_false(flask_app, db_session):
    assert has_right(flask_app.db, None, RIGHT_KEY) is False


# --- effective_group_closure ---------------------------------------------------


def test_effective_group_closure_direct_group_only(flask_app, db_session, make_user, make_group):
    from application.models import UserGroup

    user = make_user()
    group = make_group()
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.commit()

    closure = effective_group_closure(flask_app.db, user)
    assert closure == {group}


def test_effective_group_closure_inherits_through_ancestors(flask_app, db_session, make_user, make_group):
    from application.models import UserGroup

    grandparent = make_group()
    parent = make_group(parent=grandparent)
    child = make_group(parent=parent)
    user = make_user()
    db_session.add(UserGroup(user_id=user.id, group_id=child.id))
    db_session.commit()

    closure = effective_group_closure(flask_app.db, user)
    assert closure == {grandparent, parent, child}


def test_effective_group_closure_empty_for_user_with_no_groups(flask_app, db_session, make_user):
    user = make_user()
    assert effective_group_closure(flask_app.db, user) == set()


# --- would_create_cycle ---------------------------------------------------------


def test_would_create_cycle_none_parent_is_false(flask_app, db_session, make_group):
    group = make_group()
    assert would_create_cycle(flask_app.db, group.id, None) is False


def test_would_create_cycle_self_parent_is_true(flask_app, db_session, make_group):
    group = make_group()
    assert would_create_cycle(flask_app.db, group.id, group.id) is True


def test_would_create_cycle_detects_indirect_cycle(flask_app, db_session, make_group):
    root = make_group()
    mid = make_group(parent=root)
    leaf = make_group(parent=mid)
    # Attempting to make `root`'s parent `leaf` would close a cycle
    # root -> leaf -> mid -> root.
    assert would_create_cycle(flask_app.db, root.id, leaf.id) is True


def test_would_create_cycle_unrelated_group_is_false(flask_app, db_session, make_group):
    a = make_group()
    b = make_group()
    assert would_create_cycle(flask_app.db, a.id, b.id) is False


# --- is_superadmin ---------------------------------------------------------------


def test_is_superadmin_direct_membership(flask_app, db_session, make_user, make_group):
    from application.models import UserGroup

    user = make_user()
    group = make_group(is_superadmin=True)
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.commit()
    assert is_superadmin(flask_app.db, user) is True


def test_is_superadmin_inherited_via_subgroup(flask_app, db_session, make_user, make_group):
    from application.models import UserGroup

    top = make_group(is_superadmin=True)
    sub = make_group(parent=top)
    user = make_user()
    db_session.add(UserGroup(user_id=user.id, group_id=sub.id))
    db_session.commit()
    assert is_superadmin(flask_app.db, user) is True


def test_is_superadmin_false_for_regular_group(flask_app, db_session, make_user, make_group):
    from application.models import UserGroup

    user = make_user()
    group = make_group(is_superadmin=False)
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.commit()
    assert is_superadmin(flask_app.db, user) is False


# --- sync_right_definitions ------------------------------------------------------


def test_sync_right_definitions_is_idempotent(flask_app, db_session):
    from sqlalchemy import select
    from application.models import RightDefinition

    sync_right_definitions(flask_app.db)
    before = db_session.execute(select(RightDefinition)).scalars().all()

    sync_right_definitions(flask_app.db)
    after = db_session.execute(select(RightDefinition)).scalars().all()

    assert len(before) == len(after)
