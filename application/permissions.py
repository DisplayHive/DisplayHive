"""The user-rights system: right catalog and effective-permission resolution.

Model (see application/models/rights.py):
  - Group: can be nested via parent_group_id (subgroups). Holds only allow
    grants (GroupRight); rights are additive across every group a user
    belongs to, plus every ancestor of those groups.
  - UserGroup: a user's direct group memberships.
  - UserRight: a per-user override, 'allow' or 'deny'. No row = inherit.

Resolution (has_right, below):
  1. An explicit 'deny' on the user always wins — it cannot be overridden by
     any group, including the superadmin group.
  2. An explicit 'allow' on the user always grants the right, regardless of
     group membership.
  3. Otherwise ('inherit', i.e. no row), the right is granted if any group in
     the user's effective group closure grants it — or if any group in that
     closure is the superadmin group, which always grants everything.

This module intentionally does no caching: rights are recomputed from the
DB on every check. The app is already single-worker (see application/auth.py),
group hierarchies here are small, and this avoids the staleness problems a
cache would introduce every time a group/right/membership changes.
"""

import logging

logger = logging.getLogger(__name__)

# --- Right catalog -----------------------------------------------------------
# Single source of truth for every checkable right. Adding a right is just
# adding a line here; sync_right_definitions() below keeps the DB's
# right_definition table (used for FKs and for listing rights in the admin
# UI) in sync with this list on every startup.
#
# Naming convention: "<resource>.<action>". "<resource>.page" gates whether
# the admin section is reachable at all; the rest gate individual mutations
# within it.
RIGHTS = [
    ('media.page', 'media', 'View Media page'),
    ('media.upload', 'media', 'Upload media'),
    ('media.delete', 'media', 'Delete media'),
    ('media.rename', 'media', 'Rename media / folders'),
    ('media.tag', 'media', 'Tag media'),
    ('device.page', 'device', 'View Devices page'),
    ('device.enable', 'device', 'Enable / disable device'),
    ('device.rename', 'device', 'Rename device'),
    ('device.delete', 'device', 'Delete device'),
    ('device.showkey', 'device', 'Reveal device key'),
    ('device.adopt', 'device', 'Adopt a new device'),
    ('device.preview', 'device', 'Preview / play a device'),
    ('device.assign', 'device', 'Assign device to a screen'),
    ('special.impersonate', 'special', 'Impersonate other users'),

    ('content.page', 'content', 'View Content page'),
    ('content.create', 'content', 'Create content element'),
    ('content.edit', 'content', 'Edit content element'),
    ('content.enable', 'content', 'Enable / disable content element'),
    ('content.move', 'content', 'Move content element to another container'),
    ('content.delete', 'content', 'Delete content element'),

    ('contenttypes.page', 'contenttypes', 'View Content Types page'),
    ('contenttypes.create', 'contenttypes', 'Create contenttype'),
    ('contenttypes.edit', 'contenttypes', 'Edit contenttype'),
    ('contenttypes.delete', 'contenttypes', 'Delete contenttype'),

    ('templates.page', 'templates', 'View Templates page'),
    ('templates.create', 'templates', 'Create template'),
    ('templates.edit', 'templates', 'Edit template'),
    ('templates.delete', 'templates', 'Delete template'),

    ('screens.page', 'screens', 'View Screens page'),
    ('screens.create', 'screens', 'Create screen'),
    ('screens.edit', 'screens', 'Rename screen / change template / screengroups'),
    ('screens.delete', 'screens', 'Delete screen'),
    ('screens.monitor', 'screens', 'Toggle screen online monitoring'),
    ('screens.resize', 'screens', 'Reset screen resolution to device max'),
    ('screens.debug', 'screens', 'Toggle screen debug mode'),
    ('screens.reload', 'screens', 'Reload a single screen'),
    ('screens.reload_all', 'screens', 'Reload all screens'),

    ('screengroups.page', 'screengroups', 'View Screen Groups page'),
    ('screengroups.create', 'screengroups', 'Create screen group'),
    ('screengroups.rename', 'screengroups', 'Rename screen group'),
    ('screengroups.delete', 'screengroups', 'Delete screen group'),
    ('screengroups.manage_screens', 'screengroups', 'Assign / remove screens in a screen group'),
    ('screengroups.manage_content', 'screengroups', 'Assign / remove content in a screen group'),

    ('settings.page', 'settings', 'View Settings page'),
    ('settings.edit', 'settings', 'Edit system settings / default template'),

    ('alerting.page', 'alerting', 'View Alerting page'),
    ('alerting.manage', 'alerting', 'Manage alert recipients / subscriptions / test messages'),
    ('alerting.showtoken', 'alerting', 'Reveal / set the Telegram bot token'),

    ('logger.page', 'logger', 'View / subscribe to the live log stream'),

    ('importexport.page', 'importexport', 'View Im-/Export page'),
    ('importexport.export', 'importexport', 'Export the full database'),
    ('importexport.import', 'importexport', 'Import / overwrite the full database'),

    ('pretalx.page', 'pretalx', 'View Pretalx page'),
    ('pretalx.manage', 'pretalx', 'Manage Pretalx settings / API URLs'),

    ('magictags.page', 'magictags', 'View Magic Tags page'),
    ('magictags.create', 'magictags', 'Create magic tag'),
    ('magictags.edit', 'magictags', 'Edit magic tag'),
    ('magictags.delete', 'magictags', 'Delete magic tag'),

    ('magictagvaluelists.page', 'magictagvaluelists', 'View Magic Tag Value Lists page'),
    ('magictagvaluelists.create', 'magictagvaluelists', 'Create magic tag value list'),
    ('magictagvaluelists.edit', 'magictagvaluelists', 'Edit magic tag value list'),
    ('magictagvaluelists.delete', 'magictagvaluelists', 'Delete magic tag value list'),

    ('users.page', 'users', 'View Users page'),
    ('users.create', 'users', 'Create admin user'),
    ('users.edit', 'users', 'Edit admin user (username)'),
    ('users.set_password', 'users', 'Set a new password for an admin user'),
    ('users.delete', 'users', 'Delete admin user'),
    ('users.activate', 'users', 'Activate / deactivate admin user'),

    ('rights.page', 'rights', 'View Groups & Rights page'),
    ('rights.manage', 'rights', 'Manage groups, group rights, memberships and user overrides'),
]

SUPERADMIN_GROUP_NAME = 'Superadmin'


def sync_right_definitions(db):
    """Ensure right_definition contains exactly the rows described by RIGHTS.

    Idempotent — safe to call on every startup. Adds new rights, updates the
    category/label of existing ones, and leaves rows for rights removed from
    RIGHTS in place (so group_right / user_right rows referencing them don't
    dangle); an orphaned right simply stops being checkable/settable.
    """
    from application.models import RightDefinition

    existing = {
        r.key: r for r in db.session.execute(db.select(RightDefinition)).scalars().all()
    }
    changed = False
    for key, category, label in RIGHTS:
        row = existing.get(key)
        if row is None:
            db.session.add(RightDefinition(key=key, category=category, label=label))
            changed = True
        elif row.category != category or row.label != label:
            row.category = category
            row.label = label
            changed = True
    if changed:
        db.session.commit()


def ensure_superadmin_group(db):
    """Create the Superadmin group on first run, and backfill membership.

    If the group has no members yet (fresh seed, or an upgrade from a version
    without this system), every existing AdminUser is added to it — so an
    upgrade never silently locks out accounts that previously had unconditional
    admin access.
    """
    from application.models import Group, AdminUser, UserGroup

    group = db.session.execute(
        db.select(Group).where(Group.is_superadmin == True)  # noqa: E712
    ).scalar_one_or_none()
    if group is None:
        group = Group(name=SUPERADMIN_GROUP_NAME, is_superadmin=True)
        db.session.add(group)
        db.session.commit()

    has_members = db.session.execute(
        db.select(UserGroup).where(UserGroup.group_id == group.id)
    ).first() is not None
    if not has_members:
        user_ids = db.session.execute(db.select(AdminUser.id)).scalars().all()
        for uid in user_ids:
            db.session.add(UserGroup(user_id=uid, group_id=group.id))
        if user_ids:
            db.session.commit()
            logger.info('Added %d existing admin user(s) to the Superadmin group', len(user_ids))


def effective_group_closure(db, user):
    """Return the set of Group objects effective for *user*: their direct
    groups, plus every ancestor of those groups (a subgroup's members also
    hold everything granted to the parent group(s))."""
    from application.models import Group, UserGroup

    direct_ids = db.session.execute(
        db.select(UserGroup.group_id).where(UserGroup.user_id == user.id)
    ).scalars().all()
    if not direct_ids:
        return set()

    all_groups = {g.id: g for g in db.session.execute(db.select(Group)).scalars().all()}
    closure = {}
    frontier = [gid for gid in direct_ids if gid in all_groups]
    while frontier:
        gid = frontier.pop()
        if gid in closure:
            continue
        g = all_groups.get(gid)
        if g is None:
            continue
        closure[gid] = g
        if g.parent_group_id is not None and g.parent_group_id not in closure:
            frontier.append(g.parent_group_id)
    return set(closure.values())


def _group_grants(db, user, right_key):
    """True if any group in the user's effective closure grants *right_key*
    (or is the superadmin group, which grants everything)."""
    from application.models import GroupRight, RightDefinition

    closure = effective_group_closure(db, user)
    if not closure:
        return False
    if any(g.is_superadmin for g in closure):
        return True

    right = db.session.execute(
        db.select(RightDefinition).where(RightDefinition.key == right_key)
    ).scalar_one_or_none()
    if right is None:
        return False

    group_ids = [g.id for g in closure]
    row = db.session.execute(
        db.select(GroupRight).where(
            GroupRight.right_id == right.id,
            GroupRight.group_id.in_(group_ids),
        )
    ).first()
    return row is not None


def has_right(db, user, right_key):
    """Resolve the effective value of *right_key* for *user*. See module docstring."""
    if user is None:
        return False

    from application.models import UserRight, RightDefinition

    right = db.session.execute(
        db.select(RightDefinition).where(RightDefinition.key == right_key)
    ).scalar_one_or_none()
    if right is not None:
        override = db.session.execute(
            db.select(UserRight).where(UserRight.user_id == user.id, UserRight.right_id == right.id)
        ).scalar_one_or_none()
        if override is not None:
            if override.value == 'deny':
                return False
            if override.value == 'allow':
                return True

    return _group_grants(db, user, right_key)


def is_superadmin(db, user):
    """True if *user* belongs to the superadmin group (directly or via a subgroup)."""
    if user is None:
        return False
    return any(g.is_superadmin for g in effective_group_closure(db, user))


def would_create_cycle(db, group_id, new_parent_id):
    """True if setting *group_id*'s parent to *new_parent_id* would create a cycle
    (i.e. new_parent_id is group_id itself, or a descendant of group_id)."""
    from application.models import Group

    if new_parent_id is None:
        return False
    if new_parent_id == group_id:
        return True

    all_groups = {g.id: g for g in db.session.execute(db.select(Group)).scalars().all()}
    cursor = all_groups.get(new_parent_id)
    seen = set()
    while cursor is not None and cursor.id not in seen:
        if cursor.id == group_id:
            return True
        seen.add(cursor.id)
        cursor = all_groups.get(cursor.parent_group_id) if cursor.parent_group_id else None
    return False


def get_effective_rights(db, user):
    """Return {right_key: bool} for every known right, resolved for *user*.

    Used to hand the frontend a single map it can gate the UI with, and by
    the admin UI to show the *resolved* value next to a user's inherit/
    allow/deny override.
    """
    return {key: has_right(db, user, key) for key, _category, _label in RIGHTS}
