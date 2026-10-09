import logging

from flask import request
from application.utils import push_content_to_screen, emit_zuweisungen_matrix_update, emit_screengroups_update

logger = logging.getLogger(__name__)


def register_admin_screengroups_handlers(socketio, app, db):
    """Register admin socket handlers related to Screengroups (admin UI)."""

    from application.socketio_handlers.auth import require_right, fields, admin_handler, current_admin_user
    from application.socketio_handlers.actions import admin_action, get_or_fail, Fail, ok
    from application.permissions import has_right
    from application.models import ContentElement, Screen, Screengroup

    def _apply_membership_change(screengroup_id, item_id, *, collection_attr, item_model, action):
        """Add/remove/clear a screen or content_element on a screengroup and push updates.

        `action` is one of 'add', 'remove' or 'clear'. Returns an ack dict. After
        committing, every screen whose displayed content could have changed is
        re-pushed: for screen mutations that is the single screen involved (or,
        for 'clear', the screens being removed); for content mutations it is every
        screen currently in the group.
        """
        if not screengroup_id:
            raise Fail('missing screengroup_id')
        if action in ('add', 'remove') and not item_id:
            raise Fail('missing item id')

        with app.app_context():
            screengroup = get_or_fail(db, Screengroup, screengroup_id, 'screengroup')
            collection = getattr(screengroup, collection_attr)
            item = None
            if action in ('add', 'remove'):
                item = get_or_fail(db, item_model, item_id, 'item')

            if collection_attr == 'screens':
                affected = [item] if item is not None else list(collection)
            else:
                affected = list(screengroup.screens)

            if action == 'add' and item not in collection:
                collection.append(item)
            elif action == 'remove' and item in collection:
                collection.remove(item)
            elif action == 'clear':
                collection.clear()
            db.session.commit()
            logger.debug('%s %s on screengroup %s', action, collection_attr, screengroup.name)

            emit_screengroups_update(socketio, app, db, room='admins')
            for s in affected:
                push_content_to_screen(socketio, app, db, s)
            return ok()

    @socketio.on('displayhive:admin:cts:get_screengroup_screens')
    @require_right('screengroups.page')
    def get_screengroup_screens(message):
        """Get all screens in a screengroup"""
        from application.models import Device
        (screengroup_id,) = fields(message, 'screengroup_id')
        if not screengroup_id:
            return

        screengroup = db.session.get(Screengroup, screengroup_id)
        if not screengroup:
            return
        screens_data = []
        for s in screengroup.screens:
            resolution = f"{s.resolution_width}x{s.resolution_height}" if s.resolution_width and s.resolution_height else "n/a"
            device = db.session.execute(db.select(Device).where(Device.screen_id == s.id)).scalars().first()
            is_online = bool(device and getattr(device, 'is_online', False))
            screens_data.append({'id': s.id, 'name': s.name, 'resolution': resolution, 'is_online': is_online})

        socketio.emit('displayhive:admin:stc:screengroup_screens_data', {'screengroup_id': screengroup_id, 'screens': screens_data}, room=request.sid)
        logger.debug('Sent %s screens for screengroup %s', len(screens_data), screengroup_id)

    @socketio.on('displayhive:admin:cts:add_screen_to_screengroup')
    @admin_action('screengroups.manage_screens')
    def add_screen_to_screengroup(message):
        """Assign a screen to a screengroup."""
        screengroup_id, screen_id = fields(message, 'screengroup_id', 'screen_id')
        return _apply_membership_change(
            screengroup_id, screen_id,
            collection_attr='screens', item_model=Screen, action='add',
        )

    @socketio.on('displayhive:admin:cts:remove_screen_from_screengroup')
    @admin_action('screengroups.manage_screens')
    def remove_screen_from_screengroup(message):
        """Remove a screen from a screengroup."""
        screengroup_id, screen_id = fields(message, 'screengroup_id', 'screen_id')
        return _apply_membership_change(
            screengroup_id, screen_id,
            collection_attr='screens', item_model=Screen, action='remove',
        )

    @socketio.on('displayhive:admin:cts:remove_all_screens_from_screengroup')
    @admin_action('screengroups.manage_screens')
    def remove_all_screens_from_screengroup(message):
        """Remove all screens from a screengroup."""
        (screengroup_id,) = fields(message, 'screengroup_id')
        return _apply_membership_change(
            screengroup_id, None,
            collection_attr='screens', item_model=Screen, action='clear',
        )

    @socketio.on('displayhive:admin:cts:add_content_to_screengroup')
    @admin_action('screengroups.manage_content')
    def add_content_to_screengroup(message):
        """Add a content_element item to a screengroup."""
        screengroup_id, content_id = fields(message, 'screengroup_id', 'content_id')
        return _apply_membership_change(
            screengroup_id, content_id,
            collection_attr='content_elements', item_model=ContentElement, action='add',
        )

    @socketio.on('displayhive:admin:cts:remove_content_from_screengroup')
    @admin_action('screengroups.manage_content')
    def remove_content_from_screengroup(message):
        """Remove a content_element item from a screengroup."""
        screengroup_id, content_id = fields(message, 'screengroup_id', 'content_id')
        return _apply_membership_change(
            screengroup_id, content_id,
            collection_attr='content_elements', item_model=ContentElement, action='remove',
        )

    @socketio.on('displayhive:admin:cts:remove_all_content_from_screengroup')
    @admin_action('screengroups.manage_content')
    def remove_all_content_from_screengroup(message):
        """Remove all content_element items from a screengroup."""
        (screengroup_id,) = fields(message, 'screengroup_id')
        return _apply_membership_change(
            screengroup_id, None,
            collection_attr='content_elements', item_model=ContentElement, action='clear',
        )

    @socketio.on("displayhive:admin:cts:get_screengroups")
    @admin_handler
    def handle_get_screengroups(message=None):
        """Respond to explicit client requests for the screengroups list.

        Either screengroups.page or content.page — see
        application.admin.screengroups.helper._has_screengroups_access.
        """
        user = current_admin_user()
        if not (has_right(db, user, 'screengroups.page') or has_right(db, user, 'content.page')):
            return
        emit_screengroups_update(socketio, app, db, room=request.sid)

    @socketio.on('displayhive:admin:cts:create_screengroup')
    @admin_action('screengroups.create')
    def create_screengroup(message):
        """Create a new screengroup. Answers {success, screengroup_id, name}."""
        (name,) = fields(message, 'name')
        name = (name or '').strip()
        if not name:
            raise Fail('Name is required')
        if db.session.execute(db.select(Screengroup).where(Screengroup.name == name)).scalar_one_or_none():
            raise Fail('A screen group with this name already exists')

        screengroup = Screengroup(name=name)
        db.session.add(screengroup)
        db.session.commit()

        emit_zuweisungen_matrix_update(socketio, db)
        emit_screengroups_update(socketio, app, db, room='admins')
        logger.info("Screengroup '%s' created with id %s", name, screengroup.id)
        return ok(screengroup_id=screengroup.id, name=screengroup.name)

    @socketio.on('displayhive:admin:cts:rename_screengroup')
    @admin_action('screengroups.rename')
    def rename_screengroup(message):
        """Rename a screengroup."""
        screengroup_id, new_name = fields(message, 'screengroup_id', 'new_name')
        new_name = (new_name or '').strip()
        if not new_name:
            raise Fail('Name is required')
        screengroup = get_or_fail(db, Screengroup, screengroup_id, 'Screen group')
        taken = db.session.execute(
            db.select(Screengroup.id).where(Screengroup.name == new_name, Screengroup.id != screengroup.id)
        ).first()
        if taken:
            raise Fail('A screen group with this name already exists')
        screengroup.name = new_name
        db.session.commit()

        emit_screengroups_update(socketio, app, db, room='admins')
        return ok()

    @socketio.on('displayhive:admin:cts:delete_screengroup')
    @admin_action('screengroups.delete')
    def delete_screengroup(message):
        """Delete a screengroup (only if it has no screens and no content)."""
        (screengroup_id,) = fields(message, 'screengroup_id')
        screengroup = get_or_fail(db, Screengroup, screengroup_id, 'Screen group')

        # Single-screen groups are managed together with their screen.
        if getattr(screengroup, 'is_one_screen', False):
            raise Fail('This group belongs to a screen and cannot be deleted manually')
        if len(screengroup.screens) > 0 or len(screengroup.content_elements) > 0:
            raise Fail('The group still has screens or content and cannot be deleted')

        db.session.delete(screengroup)
        db.session.commit()

        emit_zuweisungen_matrix_update(socketio, db)
        emit_screengroups_update(socketio, app, db, room='admins')
        logger.info('Screengroup %s deleted', screengroup_id)
        return ok(screengroup_id=screengroup_id)

    @socketio.on('displayhive:admin:cts:get_screengroup_content')
    @require_right('screengroups.page')
    def get_screengroup_content(message):
        """Get paginated content for a screengroup"""
        screengroup_id, page, per_page = fields(message, 'screengroup_id', 'page', 'per_page')
        page = page or 1
        per_page = per_page or 10
        if not screengroup_id:
            return

        screengroup = db.session.get(Screengroup, screengroup_id)
        if not screengroup:
            return

        total_content = len(screengroup.content_elements)
        total_pages = (total_content + per_page - 1) // per_page

        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_content = screengroup.content_elements[start_idx:end_idx]

        content_data = [
            {
                'id': mc.id,
                'title': mc.title,
                'type': mc.contenttype.name if mc.contenttype else '',
                'duration': mc.duration,
                'active': mc.active,
            }
            for mc in paginated_content
        ]

        socketio.emit('displayhive:admin:stc:screengroup_content_data', {
            'screengroup_id': screengroup_id,
            'content': content_data,
            'page': page,
            'per_page': per_page,
            'total_content': total_content,
            'total_pages': total_pages,
        }, room=request.sid)
        logger.debug('Sent %s content items for screengroup %s (page %s/%s)', len(content_data), screengroup_id, page, total_pages)
