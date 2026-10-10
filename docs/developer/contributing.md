# Contributing

## Version

The release version is the one line in the `VERSION` file in the repository
root; bump it when you release. The build revision comes from git, or from the
`DISPLAYHIVE_REVISION` variable / `GIT_COMMIT` build argument where there is no
`.git` (the Docker image). See `application/version.py`.

## Getting set up

See the root [README](https://github.com/DisplayHive/DisplayHive#getting-started)
for environment setup — `nix develop` provisions everything (Python, Node,
SQLite) and runs first-time setup automatically: JS dependencies, the
Python venv (`.venv`, see below) and `alembic upgrade head`. `nix-shell`
works too — `flake.nix` just wraps `shell.nix`. Without Nix, you'll need
the Python version from `.python-version` (currently 3.13), Node.js, and
SQLite installed manually, and set `DATABASE_URL` yourself, e.g.
`export DATABASE_URL=sqlite:///$PWD/data/db/project.db` — SQLite is for
development only and is never picked up implicitly. The test suite ignores
that variable and uses its own temporary database (`TEST_DATABASE_URL` selects
another one, e.g. PostgreSQL).

With [direnv](https://direnv.net/) hooked into your shell
(`eval "$(direnv hook bash)"`), run `direnv allow` once and the dev shell
loads automatically whenever you `cd` into the repository.

The dev backend is plain HTTP — no certificates needed. `frontends/admin`
and `frontends/screen` pin their own dev ports in `vite.config.ts`
(5173 / 5174), so all three servers run side by side.

### Python version

`.python-version` is the one place that sets it, for the dev shell and the
NixOS module (`nix/python.nix`), CI (`actions/setup-python`'s
`python-version-file`) and the Docker image (`PYTHON_VERSION` build arg). To
move to a new version:

1. Change `.python-version`.
2. Change the `ARG PYTHON_VERSION=` default in the `Dockerfile` to match.
   `tests/test_python_version.py` fails until both agree, and also when a
   workflow or Nix file picks a version of its own.
3. If `nix develop` can't find `pythonXY`, update the flake's nixpkgs
   (`nix flake update`).

### Python dependencies

| File | What | Used by |
|---|---|---|
| `requirements.in` | Runtime dependencies (what the server imports) — edit this | |
| `requirements.txt` | Lock: every runtime package pinned, with hashes — generated | Docker image |
| `requirements-dev.in` | Test and docs tools on top — edit this | |
| `requirements-dev.txt` | Lock: runtime + dev, runtime pins identical to `requirements.txt` — generated | CI, e2e, docs |

After changing an `.in` file, regenerate both locks with `npm run deps:lock`
(uv, included in `nix develop`); `npm run deps:lock -- --upgrade` moves every
pin to the newest allowed version. Commit the `.in` and `.txt` files
together — CI's `python-locks` job fails otherwise.

Every environment installs from the locks, so there's nothing else to keep
in sync: `nix develop` takes only the interpreter from Nix and syncs
`./.venv` from `requirements-dev.txt` on every shell entry (instant when
nothing changed; recreated when the Nix interpreter changes), and the Nix
package (`nix/package.nix`, which the NixOS module runs) builds its Python
environment from the hash-checked wheels named in `requirements.txt`.
Native libraries some wheels need (e.g. `libz` for psycopg2) come from Nix
via `LD_LIBRARY_PATH`. `tests/test_dependency_sync.py` fails if a Nix file
starts listing Python packages of its own again.

### The Nix package and its hashes

`nix build .#default` builds the whole application (both frontends, the Python packages, the app).
Its fixed-output inputs are pinned in `nix/hashes.nix`: the npm dependencies of each frontend and the
Python wheels (per CPU architecture). **After changing a `package-lock.json` or `requirements.txt`,
run `nix run .#update-hashes`** (`scripts/update-nix-hashes.sh`) and commit `nix/hashes.nix`; CI's
`nix-package` job fails with the same hint otherwise. Every `package-lock.json` entry must carry
`resolved` and `integrity` (Nix fetches the packages itself); if npm leaves them out,
`scripts/fill-npm-lock-integrity.py` adds them. `nix build .#checks.x86_64-linux.module` runs the NixOS
module in a VM (needs KVM).

## Running things

```bash
npm run dev              # backend + admin panel + screen client together
npm run dev:backend      # Flask + Socket.IO only, :5000
npm run dev:admin        # admin panel dev server, :5173
npm run dev:screen       # screen client dev server, :5174
```

## Tests

The backend tests (pytest, `tests/`):

```bash
pytest -n auto         # in parallel, one process per CPU core: the whole suite in ~13 s
pytest                 # one process — better with -x, -k or a debugger (pdb)
pytest --cov           # with the coverage report
```

Parallel runs work because every worker process gets its own temporary SQLite
database and data directory (`tests/conftest.py`). Against PostgreSQL
(`TEST_DATABASE_URL`, as in CI) run sequentially: the workers would share one
database.

End-to-end tests use Playwright, in `testing/`:

```bash
npm run test:e2e         # headless
npm run test:e2e:headed  # headed browser windows
npm run test:e2e:ui      # interactive UI mode
```

Run these before opening a PR for anything that touches the admin panel,
screen client, or the Socket.IO/HTTP surface between them.

## Database changes

Schema changes go through Alembic. After changing a model in
`application/models/`, generate a migration and commit it alongside the
model change — see [Architecture → Migrations](architecture.md#migrations)
for the file naming convention already in use.

## Pull requests

- Keep PRs small and topic-focused — one change, one concern.
- If a change affects realtime behavior (a new mutation that should reach
  screens), follow the existing `send_upd_content` pattern described in
  [Real-time content push](realtime-push.md) rather than inventing a new
  push path.
- If a change affects a user-facing workflow, please update the relevant
  [User Guide](../user/index.md) page in the same PR.

## AI-assisted contributions

AI-assisted coding is welcome, but every commit is expected to be reviewed
and understood by the person submitting it — no blind commits. If you use
AI tooling, keep changes small, topic-focused, and easy to review, exactly
as you would for hand-written code. If you spot something that looks
AI-generated and unreviewed, flag it — see
[CONTRIBUTING.md](https://github.com/DisplayHive/DisplayHive/blob/main/CONTRIBUTING.md#ai-assisted-contributions)
for more.
