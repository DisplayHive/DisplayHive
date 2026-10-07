# =====================================================================
# Stage 1 — build both Vite frontends (admin + screen)
# Outputs land in /build/dist/{admin,screen} because each vite.config.ts
# has outDir "../../dist/<name>" relative to its frontends/<name> folder.
# =====================================================================
# Python version: from .python-version — CI passes it in (docker-image.yml);
# this default is for plain `docker build` / `docker compose build` and is
# kept equal to .python-version by tests/test_python_version.py.
ARG PYTHON_VERSION=3.13

FROM node:22-bookworm-slim AS frontend
WORKDIR /build

# Admin SPA (Vue 3 + PrimeVue) — install deps first for better layer caching.
# scripts/ is also copied here (not just package.json/-lock.json): `npm ci`
# runs the "postinstall" script (scripts/copy-icons.mjs, populates the icon
# field handler's assets from the icon-library packages), which needs to
# exist before install runs, not just once the rest of the source lands.
COPY frontends/admin/package.json frontends/admin/package-lock.json frontends/admin/
COPY frontends/admin/scripts/ frontends/admin/scripts/
RUN npm --prefix frontends/admin ci
COPY frontends/admin/ frontends/admin/
# build-only skips vue-tsc type-checking (a CI concern, not a runtime one),
# keeping image builds from failing on non-fatal type errors.
RUN npm --prefix frontends/admin run build-only

# Screen client (TypeScript, no framework). Same scripts/-before-ci reasoning
# as the admin frontend above.
COPY frontends/screen/package.json frontends/screen/package-lock.json frontends/screen/
COPY frontends/screen/scripts/ frontends/screen/scripts/
RUN npm --prefix frontends/screen ci
COPY frontends/screen/ frontends/screen/
RUN npm --prefix frontends/screen run build

# =====================================================================
# Stage 2 — Python runtime (Flask + Socket.IO via gunicorn's gthread worker)
# =====================================================================
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# psycopg2-binary and pillow ship manylinux wheels that bundle their native
# libs, so no system build/runtime packages are required here.
COPY requirements.txt ./
# requirements.txt is the runtime lock (every package pinned, with hashes —
# pip checks them); test/docs tools live in requirements-dev.txt only.
RUN pip install --no-cache-dir -r requirements.txt

# Application source.
COPY . .

# Built frontends from stage 1 (app.py serves dist/admin and dist/screen).
COPY --from=frontend /build/dist ./dist

# Everything the app writes goes to DATA_DIR (see application/paths.py);
# DISPLAYHIVE_DEPLOYMENT tells the admin UI to show Docker-specific steps
# when data still sits in the old /app/static/media* locations.
ENV DATA_DIR=/data \
    DISPLAYHIVE_DEPLOYMENT=docker \
    FLASK_APP=app
# FLASK_APP: maintenance commands work as
#   docker compose exec displayhive flask dh check-config   (see application/cli.py)

# Run as an unprivileged user; give it ownership of the writable data dirs.
# The old /app/static/media* dirs are still created so a pre-DATA_DIR
# compose.yml that mounts fresh volumes there keeps working (with the
# migration notice) instead of failing on root-owned mount points.
RUN useradd --system --create-home --uid 10001 displayhive \
    && mkdir -p /data/media /data/media_previews /data/media_renditions /data/import-staging /data/db \
    && mkdir -p /app/static/media /app/static/media_previews /app/static/media_renditions \
    && chmod 750 /data /data/media /data/media_previews /data/media_renditions \
    && chmod 700 /data/import-staging /data/db \
    && chown -R displayhive:displayhive /app /data
USER displayhive

ENTRYPOINT ["/app/docker-entrypoint.sh"]
