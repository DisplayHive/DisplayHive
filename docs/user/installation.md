# Installation

DisplayHive is a self-hosted app: a Flask + Socket.IO backend, a PostgreSQL
(or SQLite, for local testing) database, and two built frontends (the admin
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
frontends, and runs `alembic upgrade head` to bring the (SQLite, by default)
database schema up to date. With [direnv](https://direnv.net/) hooked into
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

    secretKey          = "replace-with-a-real-secret-key";
    corsAllowedOrigins = "https://example.com";
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

- A `displayhive-<name>.service` running the app under `gunicorn` (eventlet
  worker), with `alembic upgrade head` run on every (re)start before the app
  launches.
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

On startup the container applies Alembic migrations (`alembic upgrade head`),
then launches gunicorn with the eventlet worker. Once it's up, everything is
served from a single port:

| Surface | URL |
|---|---|
| Screen / kiosk client | http://localhost:5000/ |
| Admin panel | http://localhost:5000/admin/ |
| REST API + Socket.IO | http://localhost:5000/ |

Set at least `SECRET_KEY`, `POSTGRES_PASSWORD`, and `ADMIN_BOOTSTRAP_PASSWORD`
in `.env` before first start. Uploaded media, previews and renditions persist
in the `media`, `media_previews` and `media_renditions` volumes (mounted under
`/data`, the image's data directory); the database persists in `pgdata`, so
they survive container upgrades.

Useful commands:

```bash
docker compose logs -f displayhive   # follow app logs
docker compose up -d                  # pull the latest image and restart
docker compose down                   # stop (add -v to also delete volumes/data)
```

By default `compose.yml` pulls the pre-built
`ghcr.io/displayhive/displayhive:latest` image, published automatically on
every push to `main` and on version tags. To build locally from source
instead, comment out the `image:` line and uncomment `build: .`, then run
`docker compose up -d --build`.

As with the NixOS deployment, put a reverse proxy in front of the container
for TLS, and set `TRUSTED_PROXY_COUNT` (see [Configuration](#configuration)
below) so rate-limiting sees the real client IP instead of the proxy's.

## Configuration

Beyond `SECRET_KEY`, `POSTGRES_PASSWORD`, and `ADMIN_BOOTSTRAP_*` (covered
above) and `DATABASE_URL`/`CORS_ALLOWED_ORIGINS` (see
[Architecture](../developer/architecture.md)), a few more environment
variables are worth knowing about:

| Variable | Purpose |
|---|---|
| `TRUSTED_PROXY_COUNT` | Number of reverse proxies in front of the app. Set this whenever you put nginx (or similar) in front of DisplayHive, so rate-limiting uses the real client IP rather than the proxy's, and SSO redirect URIs use the public address. **Without it, every client looks like the proxy's IP, and the per-IP login limit (below) locks out everyone at once after a handful of failed logins.** |
| `LOGIN_RATE_LIMIT_PER_IP` | Failed logins allowed from one IP address, across all usernames, within 15 minutes before that IP is locked out (default `20`). Separate from the stricter 5-failure limit per IP + username. |
| `FLASK_DEBUG` | Enables the Werkzeug debugger. Local development only — never set this on a network-reachable host, since it allows arbitrary code execution from the browser. |
| `LOG_LEVEL` | Python logging level (default `INFO`). |
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
| `db/project.db` | The SQLite database, only without `DATABASE_URL` | `0700` (directory) |

DisplayHive creates missing directories with these permissions on start and
leaves existing ones alone. The SQLite database holds password hashes and
secrets; if the file is readable by other users, the log says so.

Backups: copy `media/` (previews and renditions are regenerated by
**Sync previews** on the Media page). Don't copy a running SQLite database
file; use `sqlite3 DATA_DIR/db/project.db ".backup backup.db"` instead.

Media URLs stay `/static/media/…`, and the app serves them from `DATA_DIR`.
If your reverse proxy serves `/static/media` straight from disk, point it at
`DATA_DIR/media`.

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

## Debian

TBD
