"""What the running host offers its plugins (``api.db``, ``api.require`` …), set up once the app exists.

Plugins are loaded while the app is being built, before Socket.IO is attached, so they reach the host
through this module at the time they *use* it, not when they register.
"""

_state: dict = {}


def init(app, db, socketio) -> None:
    _state.update(app=app, db=db, socketio=socketio)


def app():
    return _state.get('app')


def db():
    return _state.get('db')


def socketio():
    return _state.get('socketio')


def emit_admins(event: str, payload=None) -> None:
    """Push *event* to every connected admin."""
    sio, application = socketio(), app()
    if sio is None:
        return
    with application.app_context():
        sio.emit(event, payload, room='admins')


def require(right: str) -> None:
    """In an event handler: stop with "Permission denied" unless the calling admin has *right*."""
    from application.security.permissions import has_right
    from application.socketio_handlers.actions import PERMISSION_DENIED, Fail
    from application.socketio_handlers.auth import current_admin_user
    user = current_admin_user()
    if user is None or not has_right(db(), user, right):
        raise Fail(PERMISSION_DENIED)
