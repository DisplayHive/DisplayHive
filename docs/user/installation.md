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
`client_max_body_size` setting required for media uploads.

## Debian

TBD

## Docker

TBD
