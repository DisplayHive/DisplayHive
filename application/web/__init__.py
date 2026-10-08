"""The app's own HTTP surface outside the Socket.IO handlers and the admin API:
static files, the screen page, the admin SPA, import/export and the
health probes.

Each module is a Blueprint (or, for import/export, a `register_*` function that
needs the app for its auth decorators); `register_web_routes` wires them up.
"""

from pathlib import Path

from flask import Flask

# Repository root: where dist/, frontends/ and examplecontent/ live.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def register_web_routes(app: Flask, db, socketio) -> None:
    from application.web.admin_spa import bp as admin_spa_bp
    from application.web.health import bp as health_bp
    from application.web.importexport_routes import register_importexport_routes
    from application.web.screen_page import bp as screen_page_bp
    from application.web.static_routes import bp as static_routes_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(static_routes_bp)
    app.register_blueprint(screen_page_bp)
    app.register_blueprint(admin_spa_bp)
    register_importexport_routes(app, db, socketio)
