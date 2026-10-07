"""Socket handlers for the user-rights system: querying effective rights, and
managing groups, group rights, memberships and per-user overrides.

Viewing (get_groups/get_users_rights) requires rights.page; every mutation
requires rights.manage. Superadmins hold both implicitly (has_right() grants
every right to the superadmin group), so this is a strict generalization of
the earlier "superadmin only" gate, not a narrowing of it.
"""

import logging

logger = logging.getLogger(__name__)


def register_admin_rights_handlers(socketio, app, db):
    """Register socket handlers for the rights system."""
    from application.socketio_handlers.auth import admin_handler, current_admin_user
    from application.models import Group, RightDefinition, GroupRight, UserGroup, UserRight, AdminUser
    from application.permissions import (
        RIGHTS,
        get_effective_rights,
        has_right,
        is_superadmin,
        would_create_cycle,
        password_superadmin_exists,
        PASSWORD_SUPERADMIN_ERROR,
    )

    def _gated_handler(right_key):
        """Like admin_handler, but also requires *right_key*; returns an explicit
        error dict (rather than admin_handler's silent None) so the admin UI can
        surface why an action was refused."""
        from functools import wraps

        def decorator(fn):
            @admin_handler
            @wraps(fn)
            def wrapper(*args, **kwargs):
                if not has_right(db, current_admin_user(), right_key):
                    return {'success': False, 'error': 'Permission denied'}
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    _view_handler = _gated_handler('rights.page')
    _manage_handler = _gated_handler('rights.manage')

    def _right_row(right_key):
        return db.session.execute(
            db.select(RightDefinition).where(RightDefinition.key == right_key)
        ).scalar_one_or_none()

    def _group_to_dict(group, right_keys_by_group):
        return {
            **group.to_dict(),
            'rights': sorted(right_keys_by_group.get(group.id, [])),
        }

    def _build_groups_payload():
        groups = db.session.execute(db.select(Group)).scalars().all()
        rights_by_id = {r.id: r.key for r in db.session.execute(db.select(RightDefinition)).scalars().all()}
        group_rights = db.session.execute(db.select(GroupRight)).scalars().all()
        right_keys_by_group: dict[int, list[str]] = {}
        for gr in group_rights:
            right_keys_by_group.setdefault(gr.group_id, []).append(rights_by_id.get(gr.right_id, ''))
        return [_group_to_dict(g, right_keys_by_group) for g in groups]

    def _build_users_rights_payload():
        users = db.session.execute(db.select(AdminUser).order_by(AdminUser.username)).scalars().all()
        rights_by_id = {r.id: r.key for r in db.session.execute(db.select(RightDefinition)).scalars().all()}
        memberships = db.session.execute(db.select(UserGroup)).scalars().all()
        groups_by_user: dict[int, list[int]] = {}
        for m in memberships:
            groups_by_user.setdefault(m.user_id, []).append(m.group_id)
        overrides = db.session.execute(db.select(UserRight)).scalars().all()
        overrides_by_user: dict[int, dict[str, str]] = {}
        for o in overrides:
            overrides_by_user.setdefault(o.user_id, {})[rights_by_id.get(o.right_id, '')] = o.value

        result = []
        for u in users:
            result.append({
                'id': u.id,
                'username': u.username,
                'group_ids': groups_by_user.get(u.id, []),
                'overrides': overrides_by_user.get(u.id, {}),
                'effective_rights': get_effective_rights(db, u),
            })
        return result

    @socketio.on('displayhive:admin:rights:cts:get_my_rights')
    @admin_handler
    def handle_get_my_rights(data=None):
        """Return the caller's own effective right map — used by the frontend to gate the UI."""
        user = current_admin_user()
        return {
            'rights': get_effective_rights(db, user),
            'is_superadmin': is_superadmin(db, user),
        }

    @socketio.on('displayhive:admin:rights:cts:get_catalog')
    @admin_handler
    def handle_get_catalog(data=None):
        """Return the static right catalog, grouped by category."""
        return {
            'rights': [{'key': k, 'category': c, 'label': label} for k, c, label in RIGHTS],
        }

    @socketio.on('displayhive:admin:rights:cts:get_groups')
    @_view_handler
    def handle_get_groups(data=None):
        return {'success': True, 'groups': _build_groups_payload()}

    @socketio.on('displayhive:admin:rights:cts:get_users_rights')
    @_view_handler
    def handle_get_users_rights(data=None):
        return {'success': True, 'users': _build_users_rights_payload()}

    @socketio.on('displayhive:admin:rights:cts:create_group')
    @_manage_handler
    def handle_create_group(data):
        data = data or {}
        name = str(data.get('name', '')).strip()
        parent_group_id = data.get('parent_group_id')
        if not name:
            return {'success': False, 'error': 'Group name is required'}
        existing = db.session.execute(db.select(Group).where(Group.name == name)).scalar_one_or_none()
        if existing:
            return {'success': False, 'error': 'A group with that name already exists'}
        if parent_group_id is not None and not db.session.get(Group, parent_group_id):
            return {'success': False, 'error': 'Parent group not found'}
        group = Group(name=name, parent_group_id=parent_group_id)
        db.session.add(group)
        db.session.commit()
        return {'success': True, 'id': group.id}

    @socketio.on('displayhive:admin:rights:cts:update_group')
    @_manage_handler
    def handle_update_group(data):
        """Rename a group and/or move it under a new parent. data: {id, name?, parent_group_id?}."""
        data = data or {}
        group_id = data.get('id')
        group = db.session.get(Group, group_id) if group_id else None
        if not group:
            return {'success': False, 'error': 'Group not found'}

        if 'name' in data:
            new_name = str(data.get('name', '')).strip()
            if not new_name:
                return {'success': False, 'error': 'Group name is required'}
            if new_name != group.name:
                existing = db.session.execute(db.select(Group).where(Group.name == new_name)).scalar_one_or_none()
                if existing:
                    return {'success': False, 'error': 'A group with that name already exists'}
                group.name = new_name

        if 'parent_group_id' in data:
            new_parent_id = data.get('parent_group_id')
            if new_parent_id is not None and not db.session.get(Group, new_parent_id):
                return {'success': False, 'error': 'Parent group not found'}
            if would_create_cycle(db, group.id, new_parent_id):
                return {'success': False, 'error': 'That would create a group cycle'}
            # Moving a group out from under Superadmin can strip its members
            # of Superadmin, so this needs the break-glass check too.
            had_break_glass = password_superadmin_exists(db)
            group.parent_group_id = new_parent_id
            if had_break_glass and not password_superadmin_exists(db):
                db.session.rollback()
                return {'success': False, 'error': PASSWORD_SUPERADMIN_ERROR}

        db.session.commit()
        return {'success': True}

    @socketio.on('displayhive:admin:rights:cts:delete_group')
    @_manage_handler
    def handle_delete_group(data):
        data = data or {}
        group = db.session.get(Group, data.get('id'))
        if not group:
            return {'success': False, 'error': 'Group not found'}
        if group.is_superadmin:
            return {'success': False, 'error': 'Cannot delete the Superadmin group'}
        has_children = db.session.execute(
            db.select(Group).where(Group.parent_group_id == group.id)
        ).first() is not None
        if has_children:
            return {'success': False, 'error': 'Reassign or delete subgroups first'}
        had_break_glass = password_superadmin_exists(db)
        db.session.delete(group)
        if had_break_glass and not password_superadmin_exists(db):
            db.session.rollback()
            return {'success': False, 'error': PASSWORD_SUPERADMIN_ERROR}
        db.session.commit()
        return {'success': True}

    @socketio.on('displayhive:admin:rights:cts:set_group_right')
    @_manage_handler
    def handle_set_group_right(data):
        """Grant/revoke a right on a group. data: {group_id, right_key, allow}."""
        data = data or {}
        group = db.session.get(Group, data.get('group_id'))
        if not group:
            return {'success': False, 'error': 'Group not found'}
        if group.is_superadmin:
            return {'success': False, 'error': 'The Superadmin group implicitly has every right'}
        right = _right_row(data.get('right_key'))
        if not right:
            return {'success': False, 'error': 'Unknown right'}

        existing = db.session.execute(
            db.select(GroupRight).where(GroupRight.group_id == group.id, GroupRight.right_id == right.id)
        ).scalar_one_or_none()
        allow = bool(data.get('allow'))
        if allow and not existing:
            db.session.add(GroupRight(group_id=group.id, right_id=right.id))
        elif not allow and existing:
            db.session.delete(existing)
        db.session.commit()
        return {'success': True}

    @socketio.on('displayhive:admin:rights:cts:set_group_rights_bulk')
    @_manage_handler
    def handle_set_group_rights_bulk(data):
        """Grant/revoke a batch of rights on a group in a single transaction.

        data: {group_id, right_keys: [...], allow}. Used by the "All"/"None"
        buttons in the admin UI — deliberately NOT implemented as N parallel
        calls to set_group_right from the client: N concurrent Socket.IO
        handler invocations (each in its own thread) can interleave their
        check-then-insert on the same group (one handler's rollback wiping
        out another's uncommitted add), silently dropping some of the N rights.
        One handler call, one commit, no interleaving.
        """
        data = data or {}
        group = db.session.get(Group, data.get('group_id'))
        if not group:
            return {'success': False, 'error': 'Group not found'}
        if group.is_superadmin:
            return {'success': False, 'error': 'The Superadmin group implicitly has every right'}
        right_keys = data.get('right_keys') or []
        allow = bool(data.get('allow'))

        rights = db.session.execute(
            db.select(RightDefinition).where(RightDefinition.key.in_(right_keys))
        ).scalars().all()
        right_ids = [r.id for r in rights]

        existing = db.session.execute(
            db.select(GroupRight).where(GroupRight.group_id == group.id, GroupRight.right_id.in_(right_ids))
        ).scalars().all()

        if allow:
            existing_ids = {gr.right_id for gr in existing}
            for right in rights:
                if right.id not in existing_ids:
                    db.session.add(GroupRight(group_id=group.id, right_id=right.id))
        else:
            for gr in existing:
                db.session.delete(gr)

        db.session.commit()
        return {'success': True}

    @socketio.on('displayhive:admin:rights:cts:set_user_rights_bulk')
    @_manage_handler
    def handle_set_user_rights_bulk(data):
        """Set a batch of per-user right overrides in a single transaction.

        data: {user_id, right_keys: [...], value: 'allow'|'deny'|'inherit'}.
        Same rationale as set_group_rights_bulk above — one handler call, one
        commit, instead of N parallel single-right calls that can interleave.
        """
        data = data or {}
        user = db.session.get(AdminUser, data.get('user_id'))
        if not user:
            return {'success': False, 'error': 'User not found'}
        right_keys = data.get('right_keys') or []
        value = data.get('value')
        if value not in ('allow', 'deny', 'inherit'):
            return {'success': False, 'error': 'value must be allow, deny, or inherit'}

        rights = db.session.execute(
            db.select(RightDefinition).where(RightDefinition.key.in_(right_keys))
        ).scalars().all()
        right_ids = [r.id for r in rights]

        existing = db.session.execute(
            db.select(UserRight).where(UserRight.user_id == user.id, UserRight.right_id.in_(right_ids))
        ).scalars().all()
        existing_by_right_id = {ur.right_id: ur for ur in existing}

        if value == 'inherit':
            for ur in existing:
                db.session.delete(ur)
        else:
            for right in rights:
                row = existing_by_right_id.get(right.id)
                if row:
                    row.value = value
                else:
                    db.session.add(UserRight(user_id=user.id, right_id=right.id, value=value))

        db.session.commit()
        return {'success': True}

    @socketio.on('displayhive:admin:rights:cts:set_user_groups')
    @_manage_handler
    def handle_set_user_groups(data):
        """Replace a user's group memberships wholesale. data: {user_id, group_ids: [...]}."""
        data = data or {}
        user = db.session.get(AdminUser, data.get('user_id'))
        if not user:
            return {'success': False, 'error': 'User not found'}
        group_ids = set(data.get('group_ids') or [])
        valid_ids = set(db.session.execute(db.select(Group.id).where(Group.id.in_(group_ids))).scalars().all())

        current = db.session.execute(
            db.select(UserGroup).where(UserGroup.user_id == user.id)
        ).scalars().all()
        current_ids = {ug.group_id for ug in current}

        superadmin_group = db.session.execute(
            db.select(Group).where(Group.is_superadmin == True)  # noqa: E712
        ).scalar_one_or_none()
        if (superadmin_group and superadmin_group.id in current_ids
                and superadmin_group.id not in valid_ids):
            remaining = db.session.execute(
                db.select(db.func.count()).select_from(UserGroup).where(UserGroup.group_id == superadmin_group.id)
            ).scalar()
            if remaining <= 1:
                return {'success': False, 'error': 'Cannot remove the last member of the Superadmin group'}

        had_break_glass = password_superadmin_exists(db)
        for ug in current:
            if ug.group_id not in valid_ids:
                db.session.delete(ug)
        for gid in valid_ids - current_ids:
            db.session.add(UserGroup(user_id=user.id, group_id=gid))
        if had_break_glass and not password_superadmin_exists(db):
            db.session.rollback()
            return {'success': False, 'error': PASSWORD_SUPERADMIN_ERROR}
        db.session.commit()
        return {'success': True}

    @socketio.on('displayhive:admin:rights:cts:set_user_right')
    @_manage_handler
    def handle_set_user_right(data):
        """Set a per-user right override. data: {user_id, right_key, value: 'allow'|'deny'|'inherit'}."""
        data = data or {}
        user = db.session.get(AdminUser, data.get('user_id'))
        if not user:
            return {'success': False, 'error': 'User not found'}
        right = _right_row(data.get('right_key'))
        if not right:
            return {'success': False, 'error': 'Unknown right'}
        value = data.get('value')
        if value not in ('allow', 'deny', 'inherit'):
            return {'success': False, 'error': 'value must be allow, deny, or inherit'}

        existing = db.session.execute(
            db.select(UserRight).where(UserRight.user_id == user.id, UserRight.right_id == right.id)
        ).scalar_one_or_none()
        if value == 'inherit':
            if existing:
                db.session.delete(existing)
        elif existing:
            existing.value = value
        else:
            db.session.add(UserRight(user_id=user.id, right_id=right.id, value=value))
        db.session.commit()
        return {'success': True}
