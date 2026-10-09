# =====================================================================
# Stage 1 — build both Vite frontends (admin + screen)
# Outputs land in /build/dist/{admin,screen} because each vite.config.ts
# has outDir "../../dist/<name>" relative to its frontends/<name> folder.
# =====================================================================
# Python version: from .python-version — CI passes it in (docker-image.yml);
# this default is for plain `docker build` / `docker compose build` and is
# kept equal to .python-version by tests/test_python_version.py.
ARG PYTHON_VERSION=3.13

# --platform=$BUILDPLATFORM: the frontends' output is the same JavaScript for every
# CPU, so they are built once, natively, however many architectures the image is
# built for (docker-image.yml builds amd64 and arm64; only the runtime stage below
# is built once per architecture, under emulation for the foreign one).
FROM --platform=$BUILDPLATFORM node:22-bookworm-slim AS frontend
WORKDIR /build

# Both frontends: install dependencies first for better layer caching. scripts/
# is also copied (not just package.json/-lock.json): `npm ci` runs the
# "postinstall" script (scripts/copy-icons.mjs, populates the icon field
# handler's assets from the icon-library packages), which needs to exist before
# install runs, not just once the rest of the source lands.
# Admin SPA: Vue 3 + PrimeVue.
COPY frontends/admin/package.json frontends/admin/package-lock.json frontends/admin/
COPY frontends/admin/scripts/ frontends/admin/scripts/
RUN npm --prefix frontends/admin ci
# Screen client: TypeScript, no framework.
COPY frontends/screen/package.json frontends/screen/package-lock.json frontends/screen/
COPY frontends/screen/scripts/ frontends/screen/scripts/
RUN npm --prefix frontends/screen ci
COPY frontends/admin/ frontends/admin/
COPY frontends/screen/ frontends/screen/

# The build context has no .git, so the commit comes in as a build argument (CI
# passes github.sha; locally: --build-arg GIT_COMMIT=$(git rev-parse HEAD)). It is
# declared only here, after the installs, so a new commit doesn't redo them.
ARG GIT_COMMIT=
# build-only skips vue-tsc type-checking (a CI concern, not a runtime one),
# keeping image builds from failing on non-fatal type errors.
RUN DISPLAYHIVE_REVISION="${GIT_COMMIT}" npm --prefix frontends/admin run build-only
RUN DISPLAYHIVE_REVISION="${GIT_COMMIT}" npm --prefix frontends/screen run build

# =====================================================================
# Stage 2 — Python runtime (Flask + Socket.IO via gunicorn's gthread worker)
# =====================================================================
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# The PostgreSQL client tools: `flask dh backup` (pg_dump) and `restore`
# (pg_restore, psql), and the backup before each migration, need them — in the
# major version of the SERVER: a dump from pg_dump 17 does not restore on a
# version 16 server. Debian ships only 17, so the PostgreSQL project's own
# repository (PGDG) supplies 16 (what compose.yml runs) next to it; the tools of
# the right version are picked at run time (application/backup.py).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/keyrings/pgdg.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 postgresql-client-17 \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*

# psycopg2-binary and pillow ship manylinux wheels that bundle their native
# libs, so no system build/runtime packages are required here.
COPY requirements.txt ./
# requirements.txt is the runtime lock (every package pinned, with hashes —
# pip checks them); test/docs tools live in requirements-dev.txt only.
RUN pip install --no-cache-dir -r requirements.txt \
    # The app never needs pip at run time; its vendored libraries (msgpack,
    # urllib3, ...) lag behind and are what image scanners flag.
    && pip uninstall -y pip

# Shown in the admin footer and the admin API, and part of the asset cache-busting
# version (application/version.py). After the dependency install, so a new commit
# doesn't redo it.
ARG GIT_COMMIT=
ENV DISPLAYHIVE_REVISION=${GIT_COMMIT}

# Run as an unprivileged user. Created before the source is copied, so that COPY --chown can give
# the files to it directly: a `chown -R` over /app afterwards would store the whole source tree a
# second time as another image layer.
RUN useradd --system --create-home --uid 10001 displayhive

# Application source.
COPY --chown=displayhive:displayhive . .

# Built frontends from stage 1 (app.py serves dist/admin and dist/screen).
COPY --from=frontend --chown=displayhive:displayhive /build/dist ./dist

# Everything the app writes goes to DATA_DIR (see application/paths.py);
# DISPLAYHIVE_DEPLOYMENT tells the admin UI to show Docker-specific steps
# when data still sits in the old /app/static/media* locations.
ENV DATA_DIR=/data \
    DISPLAYHIVE_DEPLOYMENT=docker \
    FLASK_APP=app
# FLASK_APP: maintenance commands work as
#   docker compose exec displayhive flask dh check-config   (see application/cli.py)

# Give the unprivileged user the writable data dirs. The old /app/static/media* dirs are still
# created so a pre-DATA_DIR compose.yml that mounts fresh volumes there keeps working (with the
# migration notice) instead of failing on root-owned mount points.
RUN mkdir -p /data/media /data/media_previews /data/media_renditions /data/import-staging /data/db /data/backups \
    && mkdir -p /app/static/media /app/static/media_previews /app/static/media_renditions \
    && chmod 750 /data /data/media /data/media_previews /data/media_renditions \
    && chmod 700 /data/import-staging /data/db /data/backups \
    && chown displayhive:displayhive /app \
    && chown -R displayhive:displayhive /data /app/static
USER displayhive

# Liveness only (/healthz: the process answers) — a database outage must not
# make Docker report the app itself as broken; /readyz is for proxies and
# monitoring. python, because the slim image has no curl.
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=4)"]

ENTRYPOINT ["/app/docker-entrypoint.sh"]
