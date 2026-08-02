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

Uses the same DATABASE_URL / project.db resolution as the Flask app.
"""

import os
import sys

from flask import Flask

sys.path.insert(0, os.path.dirname(__file__))

from application.models import db, Contenttype
from application.admin.content.helper import rerender_content_element_for_contenttype


def build_app() -> Flask:
    app = Flask(__name__)
    database_url = os.environ.get('DATABASE_URL')
    if database_url:
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    else:
        db_path = os.path.join(os.path.dirname(__file__), 'project.db')
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    db.init_app(app)
    return app


def main() -> None:
    app = build_app()
    with app.app_context():
        contenttype_ids = db.session.execute(db.select(Contenttype.id)).scalars().all()
        total_updated = 0
        for ct_id in contenttype_ids:
            updated_ids = rerender_content_element_for_contenttype(db, ct_id)
            total_updated += len(updated_ids)
            print(f'Contenttype {ct_id}: re-rendered {len(updated_ids)} content element(s)')
        print(f'Done. Re-rendered {total_updated} content element(s) across {len(contenttype_ids)} contenttype(s).')


if __name__ == '__main__':
    main()
