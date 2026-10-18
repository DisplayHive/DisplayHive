"""Every admin socket handler that names a right refuses a caller without it.

``admin_action(*rights)`` (application/socketio_handlers/actions.py) records the rights on the handler as
``required_rights``. This walks all registered Socket.IO events, calls each such handler as an admin who holds no
right at all and expects ``Permission denied``. It also pins which handlers do *not* name a right, so a new
handler cannot slip in unchecked: it has to carry rights, or be added to ``CHECKS_ITSELF`` / ``NOT_ADMIN_ACTIONS``
below on purpose.
"""

import pytest

from application.security.auth import create_token

DENIED = {'success': False, 'error': 'Permission denied'}

# `@admin_action()` without rights: only "is an admin"; these check what the caller may do inside the handler.
CHECKS_ITSELF = {
    'displayhive:admin:cts:create_content_element', 'displayhive:admin:cts:get_active_design_colors',
    'displayhive:admin:cts:get_active_plugins', 'displayhive:admin:cts:get_contenttype',
    'displayhive:admin:cts:get_contenttypes', 'displayhive:admin:users:cts:merge_user',
    'displayhive:admin:users:cts:update_user', 'displayhive:devices:cts:find_device',
    'displayhive:devices:cts:update_device', 'displayhive:media:cts:update_media', 'displayhive:plugin:call',
}

# Registered events that are not admin actions at all (screens, connection handling, older decorators).
NOT_ADMIN_ACTIONS = {
    # screens and devices (they authenticate with their device key, not as admins)
    'device_request', 'displayhive:devices:cts:ping', 'displayhive:devices:cts:upd_viewport',
    'displayhive:logger:cts:log_entry', 'displayhive:screen:cts:get_server_time', 'displayhive:screen:cts:refresh_content',
    # reads: answered only with what the caller's rights allow (see test_reads_give_a_rightless_admin_nothing)
    'displayhive:admin:cts:get_admin_screen', 'displayhive:admin:cts:get_admin_settings',
    'displayhive:admin:cts:get_all_content_detailed', 'displayhive:admin:cts:get_all_content_element',
    'displayhive:admin:cts:get_all_help', 'displayhive:admin:cts:get_content_by_screengroup',
    'displayhive:admin:cts:get_content_element_detail', 'displayhive:admin:cts:get_image_tags',
    'displayhive:admin:cts:get_media_for_picker', 'displayhive:admin:cts:get_outbound_policy',
    'displayhive:admin:cts:get_screengroup_content', 'displayhive:admin:cts:get_screengroup_screens',
    'displayhive:admin:cts:get_screengroups', 'displayhive:admin:cts:get_unassigned_content',
    'displayhive:admin:cts:preview_content_element', 'displayhive:admin:rights:cts:get_catalog',
    'displayhive:admin:rights:cts:get_my_rights', 'displayhive:admin:users:cts:get_users',
    'displayhive:devices:cts:get_available_screens', 'displayhive:devices:cts:get_devices',
    'displayhive:media:cts:get_media', 'displayhive:screens:cts:get_screen_screengroups',
}

# Reads that need no right (any signed-in admin sees this) — everything else among the reads above must be empty.
PUBLIC_READS = {
    'displayhive:admin:cts:get_all_help', 'displayhive:admin:rights:cts:get_catalog',
    'displayhive:admin:rights:cts:get_my_rights', 'displayhive:devices:cts:get_available_screens',
    'displayhive:admin:cts:get_image_tags', 'displayhive:admin:cts:get_media_for_picker',
}


@pytest.fixture()
def rightless_admin(flask_app, db_session, make_user):
    client = flask_app.socketio.test_client(flask_app.app, auth={'token': create_token(flask_app.app, make_user())})
    assert client.is_connected()
    client.get_received()
    yield client
    client.disconnect()


def _handlers(flask_app):
    return flask_app.socketio.server.handlers['/']


def _classify(flask_app):
    named, bare, other = {}, set(), set()
    for event, handler in _handlers(flask_app).items():
        rights = getattr(handler, 'required_rights', None)
        if rights:
            named[event] = rights
        elif rights is not None:
            bare.add(event)
        else:
            other.add(event)
    return named, bare, other


def test_every_handler_with_rights_refuses_a_caller_without_them(flask_app, rightless_admin):
    named, _bare, _other = _classify(flask_app)
    assert len(named) > 80
    wrong = {}
    for event in sorted(named):
        answer = rightless_admin.emit(event, {}, callback=True)
        if answer != DENIED:
            wrong[event] = answer
    assert wrong == {}


def test_handlers_without_a_named_right_are_listed_on_purpose(flask_app):
    _named, bare, other = _classify(flask_app)
    assert sorted(bare - CHECKS_ITSELF) == [], 'new @admin_action() handler: name its right or list it in CHECKS_ITSELF'
    assert sorted(other - NOT_ADMIN_ACTIONS - {'connect', 'disconnect'}) == [], \
        'new socket event without admin_action: name its right or list it in NOT_ADMIN_ACTIONS'



def test_reads_give_a_rightless_admin_nothing(flask_app, rightless_admin):
    leaks = {}
    for event in sorted(e for e in NOT_ADMIN_ACTIONS if 'cts:get_' in e and e not in PUBLIC_READS
                        and not e.startswith('displayhive:screen:')):
        answer = rightless_admin.emit(event, {}, callback=True)
        pushed = rightless_admin.get_received()
        if answer or pushed:
            leaks[event] = (answer, [p['name'] for p in pushed])
    assert leaks == {}
