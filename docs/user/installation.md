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
  (`webhook.enable = true`) that redeploys automatically on a Gogs push —
  Python-only changes redeploy in seconds since it skips `npm ci`/`npm run
  build` when the frontend source trees haven't changed.

You'll need a reverse proxy (e.g. nginx) in front of the instance to terminate
TLS and forward WebSocket upgrades for Socket.IO. See the commented example in
[`nix/example.nix`](https://github.com/DisplayHive/DisplayHive/blob/main/nix/example.nix)
for a full walkthrough covering SSH deploy keys for private repos, Gogs
webhook configuration, and an nginx `virtualHosts` block — including the
`client_max_body_size` setting required for media uploads. Once a reverse
proxy is in front of the instance, also set `TRUSTED_PROXY_COUNT` (see
[Configuration](#configuration) below) so rate-limiting sees the real client
IP instead of the proxy's.

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
in `.env` before first start. Uploaded media and generated previews persist in
the `media` and `media_previews` Docker volumes; the database persists in
`pgdata`, so they survive container upgrades.

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
| `TRUSTED_PROXY_COUNT` | Number of reverse proxies in front of the app. Set this whenever you put nginx (or similar) in front of DisplayHive, so rate-limiting uses the real client IP rather than the proxy's. |
| `FLASK_DEBUG` | Enables the Werkzeug debugger. Local development only — never set this on a network-reachable host, since it allows arbitrary code execution from the browser. |
| `LOG_LEVEL` | Python logging level (default `INFO`). |

Copy `.env.example` to `.env` (or export the variables in your shell) to set
any of these.

## Debian

TBD
