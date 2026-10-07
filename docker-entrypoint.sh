#!/bin/sh
set -e

# Apply pending Alembic migrations, then launch the app.
# Alembic and the app both read DATABASE_URL from the environment.
echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Starting DisplayHive on port 5000..."
# One worker is mandatory: Socket.IO connection state lives in-process (see
# nix/module.nix). Threads: every connected screen and open admin tab keeps
# one busy for its WebSocket, so GUNICORN_THREADS must exceed the number of
# simultaneous connections, with headroom for plain HTTP requests.
exec gunicorn \
    --worker-class gthread \
    --workers 1 \
    --threads "${GUNICORN_THREADS:-500}" \
    --bind "0.0.0.0:5000" \
    app:app
