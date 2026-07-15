#!/bin/sh
set -e

# Apply pending Alembic migrations, then launch the app.
# Alembic and the app both read DATABASE_URL from the environment.
echo "[entrypoint] Applying database migrations (alembic upgrade head)..."
alembic upgrade head

echo "[entrypoint] Starting DisplayHive on port 5000..."
# Socket.IO requires the eventlet worker; a single worker is mandatory because
# Socket.IO connection state is held in-process (see nix/module.nix).
exec gunicorn \
    --worker-class eventlet \
    --workers 1 \
    --bind "0.0.0.0:5000" \
    app:app
