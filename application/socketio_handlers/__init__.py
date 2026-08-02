"""Socket.IO event handlers package.

Handler organization:
- socketio_handlers/ - Core device/screen handlers and lifecycle
- application/admin/ - Admin Vue app handlers
"""

# Core device and screen handlers
from .screens import register_screen_handlers
from .content import register_content_handlers
from .logger import register_logger_handlers
from .lifecycle import register_lifecycle_handlers
from .refresh_content import register_refresh_content_handlers

# Admin Vue app handlers
from application.admin.devices.sockethandlers import register_admin_device_handlers
from application.admin.screens.sockethandlers import register_admin_screens_handlers
from application.admin.screengroups.sockethandlers import register_admin_screengroups_handlers
from application.admin.content.sockethandlers import register_admin_content_handlers
from application.admin.designs.sockethandlers import register_admin_designs_handlers
from application.admin.layouts.sockethandlers import register_admin_layouts_handlers
from application.admin.contenttypes.sockethandlers import register_admin_contenttypes_handlers
from application.admin.matrix.sockethandlers import register_admin_matrix_handlers
from application.admin.settings.sockethandlers import register_admin_settings_handlers
from application.admin.media.sockethandlers import register_admin_media_handlers
from application.admin.magictags.sockethandlers import register_admin_magictags_handlers
from application.admin.alerting.sockethandlers import register_admin_alerting_handlers
from application.admin.pretalx.sockethandlers import register_admin_pretalx_handlers
from application.admin.users.sockethandlers import register_admin_user_handlers
from application.admin.rights.sockethandlers import register_admin_rights_handlers


def register_all_handlers(socketio, app, db):
    """Register all Socket.IO event handlers with the given socketio instance.

    Call this once during app startup after the Flask app and db are configured.
    Handlers are organised by feature area and imported from their respective
    sub-modules so each concern stays in a single file.
    """
    # Core device and screen handlers
    register_lifecycle_handlers(socketio, app, db)
    register_screen_handlers(socketio, app, db)
    register_content_handlers(socketio, app, db)
    register_logger_handlers(socketio, app, db)
    register_refresh_content_handlers(socketio, app, db)
    
    # Admin Vue app handlers
    register_admin_device_handlers(socketio, app, db)
    register_admin_screens_handlers(socketio, app, db)
    register_admin_screengroups_handlers(socketio, app, db)
    register_admin_content_handlers(socketio, app, db)
    register_admin_designs_handlers(socketio, app, db)
    register_admin_layouts_handlers(socketio, app, db)
    register_admin_contenttypes_handlers(socketio, app, db)
    register_admin_matrix_handlers(socketio, app, db)
    register_admin_settings_handlers(socketio, app, db)
    register_admin_media_handlers(socketio, app, db)
    register_admin_magictags_handlers(socketio, app, db)
    register_admin_alerting_handlers(socketio, app, db)
    register_admin_pretalx_handlers(socketio, app, db)
    register_admin_user_handlers(socketio, app, db)
    register_admin_rights_handlers(socketio, app, db)
