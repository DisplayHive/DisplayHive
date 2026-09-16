{ pkgs ? import <nixpkgs> {} }:

let
  python = pkgs.python313.withPackages (ps: with ps; [
    flask
    flask-socketio
    flask-bootstrap
    flask-sqlalchemy
    flask-cors
    alembic
    pillow
    gunicorn
    mkdocs
    mkdocstrings
    mkdocs-material
    pip
    setuptools
    pytest
    playwright
    eventlet
    requests
    pyjwt
   
    
    
   
    
  ]);
in
pkgs.mkShell {
  # Tools available while developing
  buildInputs = [
    python
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

  # Ensure pyan3 is available inside the nix-shell for Python callgraph generation.
  # If pyan3 is not present we install it via pip on shell entry. This keeps
  # the nix derivation simple while providing a reproducible developer flow.
  shellHook = ''
    # Ensure pyan3 is importable. If not available system-wide, install it into
    # a project-local directory (.venv_lib) and prepend that to PYTHONPATH. This
    # avoids modifying system site-packages and works without elevated privileges.
    python -c "import importlib.util, sys; sys.exit(0) if importlib.util.find_spec('pyan') else sys.exit(1)" 2>/dev/null || {
      if [ ! -d "$PWD/.venv_lib" ]; then
        echo "pyan not found; installing into $PWD/.venv_lib via pip..."
        python -m pip install --upgrade --target "$PWD/.venv_lib" pyan3 || echo "pip install failed; please install pyan3 manually inside the nix-shell (pip install --upgrade pyan3)"
      fi
      export PYTHONPATH="$PWD/.venv_lib:${PYTHONPATH:-}"
    }

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
