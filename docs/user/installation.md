# Installation

DisplayHive is a self-hosted app: a Flask + Socket.IO backend, a PostgreSQL
database (SQLite only for local development, see below), and two built frontends (the admin
panel and the screen client) served by the same process. There's no external
service dependency and no cloud component — everything runs on infrastructure
you control.

This page covers getting an instance running. Pick the section for your
platform below.

## NixOS

NixOS is the primary, best-supported way to run DisplayHive — the project
ships its own [NixOS module](https://github.com/DisplayHive/DisplayHive/blob/main/nix/module.nix)
that sets up the systemd service, database, and (optionally) auto-deploy for
you.

### Trying it out / developing locally

If you just want to run DisplayHive locally — to try it out or to work on it
— use the bundled dev shell instead of the module:

```bash
git clone https://github.com/DisplayHive/DisplayHive.git
cd DisplayHive
nix develop   # or: nix-shell
```

Entering the shell installs the JS dependencies for the root project and both
frontends, and runs `alembic upgrade head` to bring the development database (a SQLite
file in `data/db/`, chosen by the shell through `DATABASE_URL`) up to date. With [direnv](https://direnv.net/) hooked into
your shell, this happens automatically on `cd` into the repo (`direnv allow`).

Then start everything with:

```bash
npm run dev
```

| Service | URL |
|---|---|
| Backend (Flask + Socket.IO) | http://localhost:5000 |
| Admin panel | http://localhost:5173 |
| Screen client | http://localhost:5174 |

### Production deployment: the DisplayHive NixOS module

For a real deployment, import the module into your NixOS configuration and
declare one or more instances. Each instance gets its own systemd service, its
own system user/group, and its own PostgreSQL database and role — so a single
host can run multiple independent DisplayHive instances (e.g. `staging` and
`production`) side by side.

```nix
{ config, pkgs, ... }:
{
  imports = [
    /path/to/DisplayHive/nix/module.nix
  ];

  services.displayhive.instances.production = {
    port            = 5002;
    sourceDirectory = "/opt/displayhive/production";

    # Optional: let the module clone/pull and build the source tree for you.
    # Omit gitRepository if you manage the source tree yourself (e.g. rsync).
    gitRepository = "https://gogs.example.com/yourorg/displayhive.git";
    gitBranch     = "main";

    # The secret key stays out of the (world-readable) Nix store: a root-only file,
    # e.g. from agenix or sops-nix. (`secretKey = "…"` works for a quick test.)
    secretKeyFile = "/run/secrets/displayhive-production-secret-key";
    publicUrl     = "https://example.com";   # CORS and the SSO redirect URI derive from it
    trustedProxyCount = 1;                   # one reverse proxy in front (see below)
  };

  # Pin the PostgreSQL major version to avoid unexpected upgrades.
  services.postgresql.package = pkgs.postgresql_16;
}
```

Then apply it:

```bash
sudo nixos-rebuild switch
```

What the module handles automatically for each declared instance:

- A `displayhive-<name>.service` running the app under `gunicorn` (one
  `gthread` worker process with `threads` threads, default 500, and an open
  files limit of 65536), with
  `flask dh migrate` run on every (re)start before the app launches: after a
  database backup, and if it fails the app does not start (see
  [Backup & restore](backup.md)). `backup.intervalHours`, `backup.keep` and
  `backup.beforeMigration` configure the backups.
- The Python packages: Nix provides the interpreter (the version in
  `.python-version`), the packages come from the lock file `requirements.txt`
  into a venv in `pythonEnvDirectory` (default
  `/var/cache/displayhive/<name>`), synced before every start — the same
  versions the Docker image ships. **The first start, and the first one
  after `requirements.txt` changed, needs internet access** to download
  them; other restarts don't. (The former `pythonEnv` option is gone.)
- **Secrets outside the Nix store:** `secretKeyFile` (a root-only file, handed
  to the service as a systemd credential, so the service user needs no access
  to it) and `environmentFile` (further `NAME=value` lines, e.g. a bootstrap
  password). `secretKey = "…"` as a plain string still works, but is readable by
  every user on the host. The `displayhive-<name>` command reads both files too.
  The build refuses an instance with no secret key at all.
- **Listening on loopback only:** `bindAddress` defaults to `127.0.0.1`, which
  is what a reverse proxy on the same host needs. Set it to `"0.0.0.0"` (or an
  interface address) only if the proxy is on another machine — and then
  restrict the port with the firewall. *(Earlier versions always listened on
  `0.0.0.0`; if your proxy is not on the host, set `bindAddress` when you
  update.)*
- **A sandboxed service:** the unit gets a read-only file system except the
  instance's `dataDirectory` and `pythonEnvDirectory`, no access to `/home`
  (read-only if the instance lives there), no capabilities, only
  `AF_UNIX`/`AF_INET`/`AF_INET6` sockets, a private `/tmp` and `/dev`, and
  the kernel, control groups, clock and hostname are protected. `systemd-analyze
  security displayhive-<name>` rates it 3.0 "OK" (an unsandboxed unit: 9.0
  "UNSAFE"). The deploy and webhook units are not sandboxed — they have to run
  git and npm and write the source tree.
- A dedicated system user/group and a PostgreSQL database + role, both named
  `displayhive-<name>`.
- Optionally, a `displayhive-<name>-deploy` one-shot service that clones/pulls
  the git repository and builds both frontends on boot, when `gitRepository`
  is set.
- Optionally, a `displayhive-<name>-webhook` listener
  (`webhook.enable = true`) that redeploys automatically on a push from
  either Gogs or GitHub — Python-only changes redeploy in seconds since it
  skips `npm ci`/`npm run build` when the frontend source trees haven't
  changed.

You'll need a reverse proxy (e.g. nginx) in front of the instance to terminate
TLS and forward WebSocket upgrades for Socket.IO. See the commented example in
[`nix/example.nix`](https://github.com/DisplayHive/DisplayHive/blob/main/nix/example.nix)
for a full walkthrough covering SSH deploy keys for private repos, Gogs/GitHub
webhook configuration, and an nginx `virtualHosts` block — including the
`client_max_body_size` setting required for media uploads. Once a reverse
proxy is in front of the instance, also set `TRUSTED_PROXY_COUNT` (see
[Configuration](#configuration) below) so rate-limiting sees the real client
IP instead of the proxy's.

Uploaded media live in the instance's `dataDirectory` (default
`/var/lib/displayhive/<name>`), outside the source tree, so redeploys never
touch them. See [Data directory](#data-directory-data_dir).

## Docker

A [`Dockerfile`](https://github.com/DisplayHive/DisplayHive/blob/main/Dockerfile)
builds a single image bundling the Flask/Socket.IO backend and both pre-built
frontends. A [`compose.yml`](https://github.com/DisplayHive/DisplayHive/blob/main/compose.yml)
is included that runs this container alongside a PostgreSQL service.

**Requirements:** Docker with the Compose plugin.

```bash
cp .env.example .env      # then edit .env and set the secrets
# Generate a strong SECRET_KEY:  openssl rand -hex 32

docker compose up -d
```

The one-shot `migrate` service brings the database schema up to date first —
after a database backup; if that fails, the app is not started (see
[Backup & restore](backup.md)) — then the app launches gunicorn (one `gthread` worker with `GUNICORN_THREADS` threads,
default 500). Once it's up, everything is
served from a single port:

| Surface | URL |
|---|---|
| Screen / kiosk client | http://localhost:5000/ |
| Admin panel | http://localhost:5000/admin/ |
| REST API + Socket.IO | http://localhost:5000/ |

Set at least `SECRET_KEY`, `POSTGRES_PASSWORD`, and `ADMIN_BOOTSTRAP_PASSWORD`
in `.env` before first start. Uploaded media, previews and renditions persist
in the `media`, `media_previews` and `media_renditions` volumes (mounted under
`/data`, the image's data directory); the database persists in `pgdata`, and
the database backups in `backups`, so they survive container upgrades.

Useful commands:

```bash
docker compose logs -f displayhive   # follow app logs
docker compose up -d                  # pull the latest image and restart
docker compose down                   # stop (add -v to also delete volumes/data)
```

By default `compose.yml` pulls the pre-built
`ghcr.io/displayhive/displayhive:latest` image, published automatically on
every push to `main` and on version tags, for `linux/amd64` and `linux/arm64`
(a Raspberry Pi 4/5 with a 64-bit OS, an ARM server): Docker picks the right one. To build locally from source
instead, comment out the `image:` line and uncomment `build: .`, then run
`docker compose up -d --build`.

As with the NixOS deployment, put a reverse proxy in front of the container
for TLS, and set `TRUSTED_PROXY_COUNT` (see [Configuration](#configuration)
below) so rate-limiting sees the real client IP instead of the proxy's.

## Configuration

Beyond `SECRET_KEY`, `POSTGRES_PASSWORD`, and `ADMIN_BOOTSTRAP_*` (covered
above) and `DATABASE_URL` (see
[Architecture](../developer/architecture.md)), a few more environment
variables are worth knowing about:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | **Required.** The database: `postgresql://user:password@host:5432/dbname`. A `sqlite:///…` URL is accepted for development only (not in the Docker image or the NixOS module); see [Database](#database-postgresql-and-sqlite-for-development-only). |
| `BACKUP_INTERVAL_HOURS` / `BACKUP_KEEP` | A database backup every this many hours (default `24`, `0` = off) and how many of them to keep (default `7`). See [Backup & restore](backup.md). |
| `MIGRATION_BACKUP` / `MIGRATION_BACKUPS_KEEP` | A backup before every migration (default `on`; `off` migrates without one) and for how many upgrades to keep those (default `3`). |
| `MIGRATE_ON_START` | Docker image only: `0` skips the migration at container start. The compose file sets it because its `migrate` service does that. |
| `DISPLAYHIVE_REVISION` | The commit the instance was built from, shown in the admin footer and by `flask dh check-config`. The Docker image sets it at build time; with git checkouts (NixOS, development) it is read from git, so you normally never set it. |
| `SECRET_KEY_FILE` | Path of a file holding the secret key, instead of `SECRET_KEY` itself (which wins if both are set): Docker secrets (`/run/secrets/…`), systemd credentials, agenix/sops-nix. The key then stays out of environment variables, compose files and the Nix store. NixOS: `secretKeyFile`. |
| `ADMIN_BOOTSTRAP_MUST_CHANGE` | `on` (default): the first admin account, created from `ADMIN_BOOTSTRAP_USERNAME`/`_PASSWORD` or with a generated password, must choose a new password at its first login. `off` lets a *pinned* password stay (for automated setups); a generated one is always changed. |
| `OUTBOUND_ALLOW_PRIVATE` | `1` lets DisplayHive fetch Pretalx and SSO addresses that point into private networks (10.x, 192.168.x, 172.16–31.x, loopback …). Off by default; a Superadmin can also switch it in Settings → Security. The cloud metadata address and other special addresses stay blocked either way. See [Outgoing requests](pretalx.md#where-pretalx-may-be). |
| `PUBLIC_URL` | The address people reach DisplayHive at, e.g. `https://signage.example.com` (scheme and host; a trailing slash is dropped). Set it in production. The **SSO redirect URI** is built from it (instead of from each request's `Host` header), and it is the default for **CORS**. An invalid value stops the app at start-up. NixOS: `publicUrl`. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins for the API and Socket.IO; an entry with a path is reduced to its origin. Wins over `PUBLIC_URL` when set. Unset: `PUBLIC_URL`'s origin; without that, local development origins only (the Docker compose file and the NixOS module fall back to `*`, i.e. any origin, which `flask dh check-config` and the admin panel flag as a warning). |
| `TRUSTED_PROXY_COUNT` | Number of reverse proxies in front of the app. Set this whenever you put nginx (or similar) in front of DisplayHive, so rate-limiting uses the real client IP rather than the proxy's, and SSO redirect URIs use the public address. **Without it, every client looks like the proxy's IP, and the per-IP login limit (below) locks out everyone at once after a handful of failed logins.** |
| `LOGIN_RATE_LIMIT_PER_IP` | Failed logins allowed from one IP address, across all usernames, within 15 minutes before that IP is locked out (default `20`). Separate from the stricter 5-failure limit per IP + username. |
| `FLASK_DEBUG` | Enables the Werkzeug debugger. Local development only — never set this on a network-reachable host, since it allows arbitrary code execution from the browser. |
| `LOG_LEVEL` | Python logging level (default `INFO`). |
| `LOG_FORMAT` | `text` (default) or `json`: with `json` every log line is one JSON object on stderr — `time` (UTC), `level`, `logger`, `message`, plus `exception` for errors — from the app, gunicorn and the Docker entrypoint, for log collectors like Loki or Elasticsearch. NixOS: `logFormat`. See [Where the logs go](#where-the-logs-go). |
| `ADMIN_CSP` | Content-Security-Policy for the admin panel: `enforce` (default — only the bundled scripts may run), `report` (log violations only) or `off`. Violations are logged as `CSP violation …` warnings. Previews always run in a separate, sandboxed page with their own policy. |
| `SCREEN_CSP` | Content-Security-Policy for the screen page: `report` (default — log only, since designs and raw-HTML content may contain anything), `enforce` or `off`. |
| `GUNICORN_THREADS` | Docker only (NixOS: the instance's `threads` option): gunicorn worker threads, default `500`. Every connected screen and open admin tab keeps one busy, so set it above the number of simultaneous connections, with headroom for normal requests. Idle threads cost almost nothing: they're only created when needed. |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | Database connections kept open / allowed on top under load (default `10` / `20`). Only threads that are handling an event use one, but after a restart every screen reconnects at once. Keep the sum below PostgreSQL's `max_connections` (default 100). |
| `DATA_DIR` | Where DisplayHive writes its data (see [below](#data-directory-data_dir)). Default: `data/` inside the app directory; `/data` in the Docker image; the module's `dataDirectory` on NixOS. |

Copy `.env.example` to `.env` (or export the variables in your shell) to set
any of these.

## Data directory (`DATA_DIR`)

Everything DisplayHive writes lives in one directory, so the app directory
itself can stay read-only and a single path covers backups:

| Path | Contents | Mode |
|---|---|---|
| `DATA_DIR/` | | `0750` |
| `media/` | Uploaded files, served at `/static/media/…` | `0750` |
| `media_previews/` | Thumbnails | `0750` |
| `media_renditions/` | Scaled copies for screens (can be regenerated) | `0750` |
| `import-staging/` | Uploaded import files between preview and confirm | `0700` |
| `db/project.db` | A SQLite *development* database, only if `DATABASE_URL` points into it. Never used implicitly. | `0700` (directory) |

DisplayHive creates missing directories with these permissions on start and
leaves existing ones alone. The SQLite database holds password hashes and
secrets; if the file is readable by other users, the log says so.

Backups: copy `media/` (previews and renditions are regenerated by
**Sync previews** on the Media page). Don't copy a running SQLite database
file; use `sqlite3 DATA_DIR/db/project.db ".backup backup.db"` instead.

Media URLs stay `/static/media/…`, and the app serves them from `DATA_DIR`.
If your reverse proxy serves `/static/media` straight from disk, point it at
`DATA_DIR/media`.

### Serving media and the screen bundle from nginx

Behind a reverse proxy, the app answers every request for a picture, a video or the screen's
JavaScript itself. With many screens (they all load the same files after a restart or a release)
that is work nginx does better, from disk and without Python. Static files can be served directly;
everything else, including Socket.IO, still goes to the app.

| URL | Directory | Caching |
|---|---|---|
| `/static/media/`, `/static/media_previews/`, `/static/media_renditions/` | `DATA_DIR/media`, `DATA_DIR/media_previews`, `DATA_DIR/media_renditions` | a file's URL never changes its content: cache for a long time |
| `/dist/screen/` | `<app>/dist/screen/` (the built screen bundle, hashed file names) | long; `screen.js` is asked for with `?v=<release>` |
| `/screen/assets/` | `<app>/frontends/screen/assets/` (`screen.css`, fonts) | long; asked for with `?v=<release>` |

Keep **`/screen-sw.js`** and **`/`** on the app: the service worker script must never be cached by
the browser (a new release is noticed through it), and the screen page is generated per request.

```nginx
server {
    # … listen, server_name, TLS …

    client_max_body_size 200m;                  # media uploads

    # Uploaded media — straight from disk; if a file is missing, the app decides.
    location /static/media/ {
        alias /var/lib/displayhive/main/media/;     # DATA_DIR/media
        try_files $uri @displayhive;
        add_header Cache-Control "public, max-age=2592000, immutable";
        autoindex off;
    }
    location /static/media_previews/ {
        alias /var/lib/displayhive/main/media_previews/;
        try_files $uri @displayhive;
        add_header Cache-Control "public, max-age=2592000, immutable";
    }
    location /static/media_renditions/ {
        alias /var/lib/displayhive/main/media_renditions/;
        try_files $uri @displayhive;
        add_header Cache-Control "public, max-age=2592000, immutable";
    }

    # The screen bundle and its assets (file names carry a hash or `?v=<release>`).
    location /dist/screen/ {
        alias /opt/displayhive/main/dist/screen/;
        try_files $uri @displayhive;
        add_header Cache-Control "public, max-age=2592000, immutable";
    }
    location /screen/assets/ {
        alias /opt/displayhive/main/frontends/screen/assets/;
        try_files $uri @displayhive;
        add_header Cache-Control "public, max-age=2592000, immutable";
    }

    location @displayhive {
        proxy_pass http://127.0.0.1:5000;
        include proxy_params;                       # or the proxy_set_header lines you already use
    }

    location / {                                    # the app: pages, API, Socket.IO
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
    }
}
```

Things to watch:

- **Permissions.** nginx's user needs read access to those directories. `DATA_DIR` is `0750` for the
  app's user, so add nginx to that group (NixOS: `users.users.nginx.extraGroups = [ "displayhive-<name>" ];`,
  see [`nix/example.nix`](https://github.com/DisplayHive/DisplayHive/blob/main/nix/example.nix)).
- **Docker.** The media volumes can be mounted into an nginx container (`media:/data/media:ro`, …).
  The screen bundle lives inside the image (`/app/dist/screen`); leave `/dist/screen/` and
  `/screen/assets/` to the app unless you copy them out (`docker cp`) on every upgrade.
- **Deleted or replaced files.** Media keep their file names for good, so long caching is safe; a
  deleted file stays in browsers' caches until they drop it.
- **The screens' service worker** keeps the page and the bundle per release and recently used media in
  the browser, so a restarted screen asks nginx for little in any case.

### Moving data to `DATA_DIR`

Older versions kept media in `static/media*` and the SQLite database in
`project.db` inside the app directory. Nothing is moved automatically. As
long as one of those old locations still holds data while its new location
is empty, DisplayHive keeps using it, logs a warning and shows admins with
access to Settings an amber notice with these steps:

**Docker.** Change the volume mount points in `compose.yml` from
`/app/static/media*` to `/data/media*`. They're the same volumes, so nothing
needs copying:

```yaml
    volumes:
      - media:/data/media
      - media_previews:/data/media_previews
      - media_renditions:/data/media_renditions
```

Then run `docker compose up -d`.

**NixOS.** The module now sets `dataDirectory` (default
`/var/lib/displayhive/<name>`). Stop the service, move the files, fix the
owner, then rebuild:

```bash
systemctl stop displayhive-<name>
mv <sourceDirectory>/static/media <sourceDirectory>/static/media_previews \
   <sourceDirectory>/static/media_renditions /var/lib/displayhive/<name>/
chown -R displayhive-<name>: /var/lib/displayhive/<name>
nixos-rebuild switch
```

**Manual install.** Stop DisplayHive, move the files, set `DATA_DIR`, start
it again:

```bash
mkdir -p /var/lib/displayhive
mv static/media static/media_previews static/media_renditions /var/lib/displayhive/
# only if you run without DATABASE_URL:
mkdir -p /var/lib/displayhive/db && chmod 700 /var/lib/displayhive/db
mv project.db /var/lib/displayhive/db/project.db
export DATA_DIR=/var/lib/displayhive   # e.g. in your systemd unit or .env
```

The notice disappears as soon as nothing is left in the old locations.
[`flask dh check-config`](cli.md#check-config) lists the same and checks the
rest of the setup.

## Database: PostgreSQL, and SQLite for development only

`DATABASE_URL` is required. DisplayHive runs on PostgreSQL
(`postgresql://user:password@host:5432/displayhive`). SQLite works for local
development and tests, but only when you ask for it explicitly with a
`sqlite:///…` URL, and the Docker image and the NixOS module refuse it.

Earlier versions silently created a SQLite file when `DATABASE_URL` was unset
(in a container, outside every volume, so it was lost whenever the container
was recreated). That fallback is gone: without `DATABASE_URL` the app and
`alembic` stop with an error. If an old SQLite file exists at one of its former
places, the message names it. Nothing is moved or deleted.

### Moving from SQLite to PostgreSQL

1. **Secure the file.** On a normal install it is `DATA_DIR/db/project.db`
   (or `project.db` in the app directory of a very old install). In a
   **Docker container** it sits inside the container, so copy it out *before*
   the container is removed or recreated:

   ```bash
   docker cp displayhive:/data/db/project.db ./project.db
   ```

2. **Prepare PostgreSQL.** Create an empty database and point `DATABASE_URL`
   at it. With Docker, use the current `compose.yml` (it includes PostgreSQL)
   and start it: the container creates the schema itself. Without Docker, run
   `alembic upgrade head` against the new database. The freshly started
   instance creates a bootstrap admin account; the copy in the next step
   replaces it.

3. **Copy.** The old file is brought up to the current schema version on the
   way (`--upgrade-source`, in place, so work on a copy of the file):

   ```bash
   flask dh copy-database --from sqlite:////absolute/path/project.db --upgrade-source
   ```

   With Docker, put the file into the running container first and run the
   command there:

   ```bash
   docker compose cp ./project.db displayhive:/tmp/project.db
   docker compose exec -u root displayhive chown displayhive /tmp/project.db
   docker compose exec displayhive flask dh copy-database --from sqlite:////tmp/project.db --upgrade-source
   ```

   The command shows source and target, asks for confirmation (`--yes` skips
   it) and then **replaces everything** in the target in one go: users,
   groups and rights, SSO providers, devices and their keys, settings and
   content. If anything fails, the target stays as it was. Rows that point at
   rows that don't exist (SQLite doesn't always enforce that) are reported;
   fix or delete them in the source copy and run it again.

4. **Start DisplayHive** against PostgreSQL. Devices keep their keys and
   reconnect by themselves. Media files are not in the database; keep the same
   `DATA_DIR` or volumes.

Keep the SQLite file until you have checked the result.

## Version

The admin panel's footer shows the running version and commit (for example
`Version 0.1.0 · Commit: 2be5109`), the same values as
`flask dh check-config` and the `version` / `revision` fields of
`GET /admin/api/auth/me` (signed-in admins only; the health endpoints below
don't reveal them). The screen client's JS and CSS are requested with the
version and commit in the URL (`?v=0.1.0-2be5109`), so browsers load the new
files after every update.

## Where the logs go

DisplayHive writes its logs to **stderr** and keeps no log files of its own; rotation and
retention are up to whatever collects them:

| Setup | Read them with |
|---|---|
| Docker Compose | `docker compose logs -f displayhive` (the app), `docker compose logs migrate` (the backup and migration before each start) |
| NixOS | `journalctl -u displayhive-<name>` (the migration runs as part of the same unit) |
| Local | the terminal |

`LOG_LEVEL` sets the level (default `INFO`). With `LOG_FORMAT=json` each line is
one JSON object, from the app, gunicorn and the Docker entrypoint alike:

```json
{"time": "2026-10-09T08:15:02.123Z", "level": "WARNING", "logger": "application.backup", "message": "Scheduled backup failed: …"}
```

`exception` holds the traceback of an error. The log of the **screens** (the
logger view in the admin panel) is separate and not written to this stream: it is kept in the
database for 72 hours / 250,000 lines by default (Settings → Screen Log).

On first start without admin users, the generated password of the bootstrap
account is logged once at `WARNING` level (look for "created a bootstrap
account"). Set `ADMIN_BOOTSTRAP_PASSWORD` to choose it yourself.

## Health checks

DisplayHive has two unauthenticated endpoints for monitoring and proxies:

| Endpoint | Answers | Use it for |
|---|---|---|
| `GET /healthz` | `200` as long as the process responds. Does not touch the database. | "Is the process alive?" |
| `GET /readyz` | `200` when the database answers **and** its schema is at the newest migration (`alembic upgrade head` has run). `503` otherwise. | "Can the instance serve requests?" |

```json
{"status": "ok", "checks": {"database": "ok", "migrations": "head"}}
```

`migrations` is `head`, `behind` (the database is not at the newest migration,
or was never migrated) or `untracked` (a SQLite file created without Alembic,
as in local development; counts as ready). The answers contain no versions,
addresses or error messages.

Nothing acts on these endpoints by itself:

- The **Docker image** has a `HEALTHCHECK` on `/healthz`, so `docker ps` shows
  `healthy` or `unhealthy`. Docker does not restart the container because of
  it. It checks the process only, so a database outage does not mark the
  container itself as broken.
- Point an **external monitor** at `/readyz`, for example
  [Uptime Kuma](https://github.com/louislam/uptime-kuma) with an HTTP check
  that expects status `200`, and let it notify you.
- A reverse proxy or orchestrator that needs a readiness probe can use
  `/readyz` as well. Restarting the app automatically on a failed probe drops
  every connected screen, so do that only if you accept it.

## Debian

TBD
