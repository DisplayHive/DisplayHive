# =====================================================================
# Stage 1 — build both Vite frontends (admin + screen)
# Outputs land in /build/dist/{admin,screen} because each vite.config.ts
# has outDir "../../dist/<name>" relative to its frontends/<name> folder.
# =====================================================================
FROM node:22-bookworm-slim AS frontend
WORKDIR /build

# Admin SPA (Vue 3 + PrimeVue) — install deps first for better layer caching.
COPY frontends/admin/package.json frontends/admin/package-lock.json frontends/admin/
RUN npm --prefix frontends/admin ci
COPY frontends/admin/ frontends/admin/
# build-only skips vue-tsc type-checking (a CI concern, not a runtime one),
# keeping image builds from failing on non-fatal type errors.
RUN npm --prefix frontends/admin run build-only

# Screen client (TypeScript, no framework).
COPY frontends/screen/package.json frontends/screen/package-lock.json frontends/screen/
RUN npm --prefix frontends/screen ci
COPY frontends/screen/ frontends/screen/
RUN npm --prefix frontends/screen run build

# =====================================================================
# Stage 2 — Python runtime (Flask + Socket.IO via gunicorn/eventlet)
# Pinned to 3.12: eventlet's monkey-patching/worker fails to import on
# Python 3.13, which makes gunicorn report "worker eventlet not found".
# =====================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# psycopg2-binary and pillow ship manylinux wheels that bundle their native
# libs, so no system build/runtime packages are required here.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Application source.
COPY . .

# Built frontends from stage 1 (app.py serves dist/admin and dist/screen).
COPY --from=frontend /build/dist ./dist

# Run as an unprivileged user; give it ownership of the writable data dirs.
RUN useradd --system --create-home --uid 10001 displayhive \
    && mkdir -p /app/static/media /app/static/media_previews \
    && chown -R displayhive:displayhive /app
USER displayhive

ENTRYPOINT ["/app/docker-entrypoint.sh"]
