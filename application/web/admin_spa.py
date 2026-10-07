"""The admin SPA (Vue 3 + PrimeVue), served from dist/admin under /admin/."""

import os

from flask import Blueprint, redirect, send_from_directory

from application.web import PROJECT_ROOT

bp = Blueprint('admin_spa', __name__)

_DIST_ADMIN = str(PROJECT_ROOT / 'dist' / 'admin')


@bp.route('/admin')
def admin_redirect():
    """Redirect /admin (no trailing slash) to the admin SPA."""
    return redirect('/admin/')


@bp.route('/admin/')
@bp.route('/admin/<path:filename>')
def admin_spa(filename='index.html'):
    """Serve files from dist/admin for the Vue 3 + PrimeVue admin SPA."""
    dist_dir = _DIST_ADMIN
    if not os.path.isdir(dist_dir):
        return "Admin dist not built. Run: nix-shell --run 'cd frontends/admin && npm run build'", 404

    if not filename:
        filename = 'index.html'

    try:
        candidate = os.path.join(dist_dir, filename)
        if os.path.isfile(candidate):
            resp = send_from_directory(dist_dir, filename)
            if filename == 'index.html':
                resp.headers['Cache-Control'] = 'no-store'
            return resp

        # For SPA client-side routing, return index.html for non-asset paths
        _, ext = os.path.splitext(filename)
        if ext:
            return "Not Found", 404

        resp = send_from_directory(dist_dir, 'index.html')
        resp.headers['Cache-Control'] = 'no-store'
        return resp
    except Exception:
        return "Not Found", 404
