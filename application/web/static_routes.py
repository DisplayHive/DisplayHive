"""Static files: uploaded media, the screen bundle and its assets, logos, favicons."""

import os

from flask import Blueprint, current_app, request, send_from_directory

from application.web import PROJECT_ROOT

bp = Blueprint('static_files', __name__)

_DIST_ADMIN = PROJECT_ROOT / 'dist' / 'admin'
_DIST_SCREEN = PROJECT_ROOT / 'dist' / 'screen'
_SCREEN_ASSETS = PROJECT_ROOT / 'frontends' / 'screen' / 'assets'
_SCREEN_PUBLIC_ICONS = PROJECT_ROOT / 'frontends' / 'screen' / 'public' / 'icons'


# Media live in DATA_DIR (see application/paths.py), not in the static folder,
# but keep their /static/… URLs — stored content references them. More specific
# than Flask's own /static/<path:filename>, so these win.
@bp.route('/static/media/<path:filename>')
def static_media(filename):
    return send_from_directory(current_app.config['MEDIA_FOLDER'], filename)


@bp.route('/static/media_previews/<path:filename>')
def static_media_previews(filename):
    return send_from_directory(current_app.config['PREVIEW_FOLDER'], filename)


@bp.route('/static/media_renditions/<path:filename>')
def static_media_renditions(filename):
    return send_from_directory(current_app.config['MEDIA_RENDITIONS_FOLDER'], filename)


@bp.route('/dist/screen/<path:filename>')
def screen_dist(filename):
    """Serve the compiled screen TypeScript bundle from dist/screen/.

    Icons are the one part of this path fetched at runtime (see
    icon-libraries.ts) rather than bundled into screen.js, so under
    SCREEN_DEV_SERVER they'd otherwise 404 against a dist/ that was never
    built — fall back to the source copy Vite itself serves in dev mode.
    """
    if current_app.config['SCREEN_DEV_SERVER'] and filename.startswith('icons/'):
        return send_from_directory(_SCREEN_PUBLIC_ICONS, filename[len('icons/'):])
    return send_from_directory(_DIST_SCREEN, filename)


@bp.route('/screen-sw.js')
def screen_service_worker():
    """The screen's service worker (frontends/screen/ts/sw), at the root so its scope is the whole site.

    Never cached by the browser itself: a new release is noticed on the next page load. The page
    asks for it as ``/screen-sw.js?v=<ASSET_VERSION>``; the version is for the worker, not for caching.
    """
    response = send_from_directory(_DIST_SCREEN, 'sw.js', mimetype='text/javascript')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Service-Worker-Allowed'] = '/'
    return response


@bp.route('/screen/assets/<path:filename>')
def screen_assets(filename):
    """Serve static screen assets (CSS etc.) directly from source, not via dist."""
    return send_from_directory(_SCREEN_ASSETS, filename)


@bp.route('/logo_wh.png')
def logo():
    """The application logo, from the admin dist folder (also at the root path)."""
    return send_from_directory(_DIST_ADMIN, 'logo_wh.png')


@bp.route('/logo_bl.png')
def logo_bl():
    """The dark/colour logo, from the admin dist folder."""
    return send_from_directory(_DIST_ADMIN, 'logo_bl.png')


# Browsers request /favicon.ico regardless of the page's path; the other sizes
# are linked from index.html directly.
@bp.route('/favicon.ico')
@bp.route('/favicon-32x32.png')
@bp.route('/favicon-16x16.png')
@bp.route('/apple-touch-icon.png')
def favicon():
    return send_from_directory(_DIST_ADMIN, os.path.basename(request.path))
