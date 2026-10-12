"""`flask dh …` — maintenance commands for a DisplayHive instance.

    flask --app app dh create-admin USERNAME
    flask --app app dh reset-password USERNAME
    flask --app app dh check-config [--online]
    flask --app app dh rerender [--missing-only]
    flask --app app dh rerender-content [--contenttype ID]
    flask --app app dh migrate [--no-backup]
    flask --app app dh backup [--media]
    flask --app app dh backups
    flask --app app dh restore FILE [--yes]
    flask --app app dh copy-database --from SQLITE_URL [--upgrade-source] [--yes]

(The Docker image sets FLASK_APP, so `flask dh …` is enough there; the
NixOS module installs a `displayhive-<instance>` wrapper.)

Run them as the user the server runs as, with the same environment
(DATABASE_URL, DATA_DIR, SECRET_KEY …) — they open the same database. Safe
next to a running server: app.py skips its startup side effects (resetting
devices to offline, background jobs, creating directories) when loaded for
one of these commands, see _loaded_for_flask_cli_command there.
"""

from .group import dh
# Importing the modules registers their commands on `dh`.
from . import check, database, media, users  # noqa: F401
from .database import _revision_of, _upgrade_to_head  # noqa: F401  (used by tests)
from .media import rerender_all, rerender_media  # noqa: F401


def register_cli(app):
    app.cli.add_command(dh)
