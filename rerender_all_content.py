"""One-off maintenance script: re-render every ContentElement's stored HTML.

Existing ContentElement rows created before the Design/Layout/ContentHandler
rearchitecture store ``html`` as a single rendered string. The current
rendering pipeline expects a JSON map of ``{contentcontainer_id: rendered_html}``
(one entry per ContentHandler on the element's Contenttype). The screen
renderer already tolerates the old format at read time (see
``application.utils.design.parse_content_html``), but re-rendering once
here brings the stored data itself up to date — which also refreshes any
magic-tag substitutions, pretalx tables, or random-image picks that were
frozen at original creation time.

Usage:
    python rerender_all_content.py

Superseded by ``flask dh rerender-content`` (application/cli.py), which does
the same; this script stays for existing habits and docs.

Uses the same DATABASE_URL / SQLite resolution as the Flask app (application/paths.py).
"""

import os
import sys

from flask import Flask

sys.path.insert(0, os.path.dirname(__file__))

from application import paths as data_paths
from application.models import db
from application.cli import rerender_all


def build_app() -> Flask:
    app = Flask(__name__)
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{data_paths.resolve().db_path}'
    db.init_app(app)
    return app


def main() -> None:
    print('Note: this is now `flask dh rerender-content`.')
    app = build_app()
    with app.app_context():
        rerender_all(db, echo=print)


if __name__ == '__main__':
    main()
