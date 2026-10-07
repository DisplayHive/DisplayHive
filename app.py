import sys


def _loaded_for_flask_cli_command() -> bool:
    """True when the `flask` CLI imports this module to run a command other
    than `flask run` — e.g. `flask dh check-config` (application/cli.py).

    Importing this module builds the default app (`app`, `socketio`) — that is
    what `gunicorn app:app`, `flask --app app` and `python app.py` expect.
    Building it as a server runs startup DB writes and background tasks; a
    maintenance command often runs next to a live instance, where those would
    do real damage — resetting every device to offline, say — so they're
    skipped then (`create_app(startup=False)`). Flask's CLI imports the app
    while resolving the command, inside a click context; gunicorn,
    `python app.py` and pytest import it without one. Code that builds its own
    app (tests, scripts) calls `application.factory.create_app` directly and
    needs none of this.
    """
    # Only look at click if it's already loaded (the `flask` command loads
    # it) — no reason to import it for the server.
    click = sys.modules.get('click')
    if click is None or click.get_current_context(silent=True) is None:
        return False
    args, command = sys.argv[1:], None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('--app', '-A', '--env-file', '-e'):
            i += 2
            continue
        if not arg.startswith('-'):
            command = arg
            break
        i += 1
    return command != 'run'


CLI_MODE = _loaded_for_flask_cli_command()

from application.config import configure_logging, env_int as _env_int  # noqa: E402,F401  (_env_int: kept for tests)
from application.factory import create_app, run_dev  # noqa: E402
from application.models import db  # noqa: E402,F401  (re-exported: tests use `app_module.db`)
from application.startup import raise_open_files_limit as _raise_open_files_limit  # noqa: E402,F401

configure_logging(CLI_MODE)

# The default app, as a server — or without the startup work for a `flask dh` command.
app, socketio = create_app(startup=not CLI_MODE)

if __name__ == '__main__':
    run_dev(app, socketio)
