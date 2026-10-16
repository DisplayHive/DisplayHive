"""One server process per data directory — enforced, not just documented.

DisplayHive keeps its live state in the process: which devices and screens are connected, the admin
sockets' sessions, the login rate limiter, pending SSO sign-ins and passkey challenges, the Socket.IO
sessions (see "Process model, and why there is no Redis" in docs/developer/architecture.md). A second
worker would see only part of it: a push would reach only the screens connected to its own worker, and
every failed-login counter would be split between them. Docker and the NixOS module start exactly one
worker; this guard makes a second one fail loudly instead of misbehaving quietly.

The first server process takes an exclusive lock on ``<DATA_DIR>/.server.lock`` and keeps it until it
exits (the operating system drops it then, also after a crash). A second process on the same data
directory finds the lock taken and refuses to start, naming the process that holds it. Under gunicorn a
worker that cannot boot stops the whole server, so ``-w 2`` fails at once with the message below.

Limits: workers forked *after* the app was loaded (``gunicorn --preload``) inherit the lock and are not
noticed; ``WEB_CONCURRENCY`` above 1 is refused as well to catch the common way of asking for them. A
``kill -HUP`` reload starts the new worker while the old one still runs, so it is refused too — restart
the service instead. ``flask dh …`` commands and tests that build their own app (``startup=False``) do
not take the lock.
"""

import logging
import os

try:
    import fcntl
except ImportError:      # not on Linux/macOS: there is no such lock to take
    fcntl = None

logger = logging.getLogger(__name__)

LOCK_NAME = '.server.lock'
_held: dict[str, int] = {}      # lock path -> file descriptor, held for the life of this process


class SecondWorkerError(RuntimeError):
    """Another server process already runs on this data directory (or more workers were asked for)."""


def _concurrency(environ) -> int:
    try:
        return int((environ.get('WEB_CONCURRENCY') or '1').strip())
    except ValueError:
        return 1


def claim_single_worker(data_dir: str, environ=None) -> None:
    """Take the server lock for *data_dir*, or raise ``SecondWorkerError`` with a message to show."""
    environ = os.environ if environ is None else environ
    if _concurrency(environ) > 1:
        raise SecondWorkerError(
            f'WEB_CONCURRENCY={environ.get("WEB_CONCURRENCY")} asks for more than one worker. DisplayHive keeps '
            'its live state (connected screens, sessions, the login limiter) in the process and runs as exactly '
            'one worker; scale with threads (GUNICORN_THREADS) instead.'
        )
    if fcntl is None:
        return
    path = os.path.join(data_dir, LOCK_NAME)
    if path in _held:                       # this process already holds it (the app was built twice)
        return
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        holder = ''
        try:
            holder = os.pread(fd, 32, 0).decode('ascii', 'ignore').strip()
        except OSError:
            pass
        os.close(fd)
        raise SecondWorkerError(
            f'Another DisplayHive server process{f" (pid {holder})" if holder else ""} already uses the data '
            f'directory {data_dir}. DisplayHive runs as exactly one worker: its live state (connected screens, '
            'sessions, the login limiter) is kept in the process. Start one gunicorn worker (-w 1) with '
            'threads for concurrency, and restart the service instead of reloading it (kill -HUP).'
        ) from None
    os.ftruncate(fd, 0)
    os.pwrite(fd, str(os.getpid()).encode('ascii'), 0)
    _held[path] = fd
    logger.debug('Took the server lock %s (pid %s)', path, os.getpid())


def release(data_dir: str) -> None:
    """Give the lock back (tests; a real server keeps it until it exits)."""
    fd = _held.pop(os.path.join(data_dir, LOCK_NAME), None)
    if fd is not None:
        os.close(fd)
