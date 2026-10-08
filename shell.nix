{ pkgs ? import <nixpkgs> {} }:

let
  # Only the interpreter comes from Nix (version from .python-version, see
  # nix/python.nix). Python packages come from the lock file
  # requirements-dev.txt into ./.venv — the exact versions CI tests and the
  # Docker image ships (runtime pins are shared), instead of whatever
  # nixpkgs happens to carry.
  python = import ./nix/python.nix { inherit pkgs; };
  # Native libraries some PyPI wheels expect to find on a regular Linux
  # (e.g. psycopg2-binary needs libz); NixOS has no global /usr/lib.
  wheelLibs = pkgs.lib.makeLibraryPath [ pkgs.zlib pkgs.stdenv.cc.cc.lib ];
in
pkgs.mkShell {
  # Tools available while developing
  buildInputs = [
    python
    pkgs.uv  # npm run deps:lock (scripts/lock-python-deps.sh)
    pkgs.direnv
    pkgs.nix-direnv
    pkgs.vim
    pkgs.git
    pkgs.graphviz
    pkgs.nodejs
    pkgs.yarn
    pkgs.pnpm
    pkgs.typescript
    pkgs.esbuild
    pkgs.vite
    pkgs.eslint
    pkgs.prettier
    pkgs.sqlite
    pkgs.ember-cli
    pkgs.ssl-proxy
    pkgs.chromium
    pkgs.libxi
    pkgs.libxcursor
    pkgs.gdk-pixbuf
    pkgs.libxrender
    pkgs.libxft
    pkgs.fontconfig
    pkgs.playwright-driver.browsers
    # ts-node removed: prefer Node's built-in TS support or use `tsc`/`vite` for dev
  ];

  shellHook = ''
    # Python packages: a venv synced to requirements-dev.txt on every shell
    # entry (instant when nothing changed — uv keeps a cache; the network is
    # only needed when the lock file changed). Recreated when the Nix
    # interpreter changes, e.g. after a nixpkgs update.
    export LD_LIBRARY_PATH="${wheelLibs}''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    export UV_PYTHON_DOWNLOADS=never
    # From the repository root, also when the shell is entered in a subfolder.
    dh_root="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
    venv="$dh_root/.venv"
    if [ "$(cat "$venv/.interpreter" 2>/dev/null)" != "${python}" ]; then
      echo "Creating .venv with ${python.name}..."
      rm -rf "$venv"
      uv venv --quiet --python "${python}/bin/python3" "$venv" && echo "${python}" > "$venv/.interpreter"
    fi
    uv pip sync --quiet --python "$venv/bin/python" "$dh_root/requirements-dev.txt" \
      || echo "uv pip sync failed — Python packages may be out of date (offline?)"
    export VIRTUAL_ENV="$venv"
    export PATH="$venv/bin:$PATH"

    # Install JS dependencies (root + each frontend) if package.json is present
    # and node_modules is either missing or stale relative to package-lock.json.
    # frontends/admin and frontends/screen are separate npm projects (not npm
    # workspaces), so each needs its own install. Staleness is tracked via a
    # hash of package-lock.json stamped into node_modules on each successful
    # install, so `nix develop`/`nix-shell` re-syncs automatically whenever the
    # lockfile changes (e.g. after a git pull) instead of silently keeping
    # outdated packages around.
    for jsdir in "$PWD" "$PWD/frontends/admin" "$PWD/frontends/screen"; do
      if [ -f "$jsdir/package.json" ]; then
        lockfile="$jsdir/package-lock.json"
        stamp="$jsdir/node_modules/.lockfile-hash"
        lockhash=""
        [ -f "$lockfile" ] && lockhash=$(sha256sum "$lockfile" | cut -d' ' -f1)

        if [ ! -d "$jsdir/node_modules" ]; then
          echo "node_modules not found in $jsdir; installing JS dependencies..."
          (
            cd "$jsdir"
            if command -v yarn >/dev/null 2>&1; then
              yarn install --frozen-lockfile || npm install
            elif command -v pnpm >/dev/null 2>&1; then
              pnpm install || npm install
            else
              npm install
            fi
          )
        elif [ -n "$lockhash" ] && [ "$(cat "$stamp" 2>/dev/null)" != "$lockhash" ]; then
          echo "package-lock.json changed in $jsdir; re-syncing node_modules (npm ci)..."
          ( cd "$jsdir" && npm ci )
        fi

        [ -n "$lockhash" ] && [ -d "$jsdir/node_modules" ] && echo "$lockhash" > "$stamp"
      fi
    done

    # DATABASE_URL is required; SQLite is only for development, so the dev shell
    # chooses it explicitly (an existing DATABASE_URL wins). The test suite
    # ignores this and uses its own temporary database. A project.db left in the
    # repository root by an old version keeps being used, so dev data survives.
    if [ -z "$DATABASE_URL" ]; then
      if [ -f "$dh_root/project.db" ] && [ ! -f "$dh_root/data/db/project.db" ]; then
        export DATABASE_URL="sqlite:///$dh_root/project.db"
      else
        export DATABASE_URL="sqlite:///$dh_root/data/db/project.db"
      fi
    fi

    # Run database migrations on shell entry so the schema is always up to date.
    if [ -f "$PWD/alembic.ini" ]; then
      echo "Running alembic upgrade head..."
      alembic upgrade head || echo "alembic upgrade failed; check the migration output above."
    fi

    export PLAYWRIGHT_BROWSERS_PATH=${pkgs.playwright-driver.browsers}
    export PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
    export PLAYWRIGHT_HOST_PLATFORM_OVERRIDE="ubuntu-24.04"

    # Show the available root-level `npm run` scripts on shell entry as a
    # quick reminder (dev servers, e2e tests, etc.).
    if [ -f package.json ]; then
      npm run
    fi
  '';

  # Helpful comment: Enter with `nix-shell` then run `pytest -q` or `nix-shell --run "pytest -q"`.
}
