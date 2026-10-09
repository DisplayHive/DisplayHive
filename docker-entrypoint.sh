#!/bin/sh
set -e

# The entrypoint's own messages, in the app's log format (LOG_FORMAT=json: one
# JSON object per line). Messages must not contain quotes or backslashes.
log() {
    if [ "${LOG_FORMAT:-text}" = "json" ]; then
        printf '{"time":"%s","level":"%s","logger":"entrypoint","message":"%s"}\n' \
            "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2"
    else
        echo "[entrypoint] $2"
    fi
}

# `docker-entrypoint.sh migrate`: only migrate the database, then exit. The
# compose file runs this as a separate one-shot service ("migrate") that the app
# service waits for.
if [ "$1" = "migrate" ]; then
    exec flask dh migrate
fi

# Bring the database schema up to date before the app starts: a backup first,
# then the migration (flask dh migrate, see application/migration.py). If that
# fails (exit 78) the app is NOT started on a half-migrated database; the
# message names the backup. Set MIGRATE_ON_START=0 when a separate migrate
# service does this.
if [ "${MIGRATE_ON_START:-1}" != "0" ]; then
    log INFO "Migrating the database (flask dh migrate)..."
    status=0
    flask dh migrate || status=$?
    if [ "$status" -ne 0 ]; then
        log ERROR "Not starting: the database migration failed (exit $status)." >&2
        exit "$status"
    fi
fi

# LOG_FORMAT=json: gunicorn's own lines in the same JSON format as the app's.
log_args=""
if [ "${LOG_FORMAT:-text}" = "json" ]; then
    log_args="--log-config-json /app/gunicorn-logging.json"
fi

log INFO "Starting DisplayHive on port 5000..."
# One worker is mandatory: Socket.IO connection state lives in-process (see
# nix/module.nix). Threads: every connected screen and open admin tab keeps
# one busy for its WebSocket, so GUNICORN_THREADS must exceed the number of
# simultaneous connections, with headroom for plain HTTP requests.
exec gunicorn \
    --worker-class gthread \
    --workers 1 \
    --threads "${GUNICORN_THREADS:-500}" \
    --bind "0.0.0.0:5000" \
    $log_args \
    app:app
