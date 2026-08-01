# nix/module.nix — NixOS module for displayhive
#
# Lets you declare any number of independent displayhive instances on a single host.
# Each instance gets:
#   • its own systemd service (displayhive-<name>.service)
#   • its own system user / group (displayhive-<name>)
#   • its own PostgreSQL database and role (displayhive-<name>)
#   • its own TCP port
#   • optionally: a Gogs webhook listener (displayhive-<name>-webhook.service)
#
# Instance names must be valid in Linux usernames and PostgreSQL role names
# (letters, digits, dashes — no spaces or underscores at the start).
#
# Alembic migrations are applied automatically on every (re)start before the
# app process is launched.
#
# ── Webhook-triggered deployment ─────────────────────────────────────────────
#
# Enable per-instance with:
#   services.displayhive.instances.myinstance.webhook.enable = true;
#   services.displayhive.instances.myinstance.webhook.port   = 9001;
#   services.displayhive.instances.myinstance.webhook.secretFile =
#     config.age.secrets."displayhive-myinstance-webhook-secret".path;
#
# On receiving a valid POST from Gogs the listener runs a fast redeploy:
#   1. git fetch + reset --hard (no re-clone)
#   2. npm ci  — only if package-lock.json changed since last deploy
#   3. npm run build — only if the frontend source tree changed
#   4. systemctl restart displayhive-<name>.service
#
# This means a Python-only push deploys in ~5 s; a full JS rebuild takes the
# same time as before but is only triggered when actually needed.
#
# ── Socket.IO / WebSocket forwarding hint (nginx, out of scope) ──────────────
#
#   upstream displayhive_myinstance {
#       server 127.0.0.1:5001;
#   }
#   server {
#       listen 443 ssl;
#       server_name myinstance.example.com;
#
#       # Must match MAX_FILE_SIZE in application/admin/media/sockethandlers.py
#       client_max_body_size 50M;
#
#       location / {
#           proxy_pass         http://displayhive_myinstance;
#           proxy_http_version 1.1;
#           proxy_set_header   Upgrade    $http_upgrade;
#           proxy_set_header   Connection "upgrade";
#           proxy_set_header   Host       $host;
#           proxy_set_header   X-Real-IP  $remote_addr;
#           proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
#           proxy_set_header   X-Forwarded-Proto $scheme;
#           proxy_read_timeout 86400s;
#       }
#   }

{ config, lib, pkgs, ... }:

with lib;

let
  cfg = config.services.displayhive;

  # ── Boot-time deploy script (initial clone + full build) ─────────────────
  # Runs once at boot via a one-shot systemd service. Always does a full
  # npm ci + npm run build to guarantee a clean initial state.
  deployScript = pkgs.writeShellApplication {
    name           = "displayhive-deploy";
    runtimeInputs  = with pkgs; [ git nodejs openssh ];
    text = ''
      instance="$1"
      source_dir="$2"
      git_url="$3"
      git_branch="$4"
      ssh_key_file="$5"   # empty string → HTTPS or public repo
      service_user="displayhive-$instance"

      export HOME=/root
      export npm_config_cache=/root/.npm

      # Always run non-interactively over SSH (accept new host keys, never
      # prompt) so anonymous/keyless ssh:// checkouts don't hang waiting for
      # a TTY that a systemd service doesn't have. Only add -i when a key
      # was actually configured. Harmless (unused) for HTTPS repos.
      ssh_opts="-o StrictHostKeyChecking=accept-new -o BatchMode=yes"
      if [ -n "$ssh_key_file" ]; then
        if [ ! -r "$ssh_key_file" ]; then
          echo "[displayhive-deploy/$instance] ERROR: SSH key '$ssh_key_file' not readable" >&2
          exit 1
        fi
        ssh_opts="-i $ssh_key_file $ssh_opts"
      fi
      export GIT_SSH_COMMAND="ssh $ssh_opts"

      export GIT_CONFIG_COUNT=1
      export GIT_CONFIG_KEY_0="safe.directory"
      export GIT_CONFIG_VALUE_0="$source_dir"

      if [ -d "$source_dir/.git" ]; then
        echo "[displayhive-deploy/$instance] Pulling $git_branch from origin"
        # gitRepository may have changed since the initial clone (repo moved,
        # renamed, migrated hosts) — keep origin pointed at the configured URL.
        git -C "$source_dir" remote set-url origin "$git_url"
        # The initial clone below is single-branch, so origin's fetch refspec
        # only tracks the branch it was cloned with. If gitBranch was since
        # changed, that branch isn't fetchable yet — add it explicitly so a
        # branch switch on redeploy doesn't fail with a pathspec error.
        git -C "$source_dir" remote set-branches --add origin "$git_branch"
        git -C "$source_dir" fetch --prune --depth 1 origin "$git_branch"
        git -C "$source_dir" checkout "$git_branch"
        git -C "$source_dir" reset --hard "origin/$git_branch"
      else
        echo "[displayhive-deploy/$instance] Cloning $git_url ($git_branch)"
        mkdir -p "$(dirname "$source_dir")"
        git clone --branch "$git_branch" --depth 1 "$git_url" "$source_dir"
      fi

      # Extend PATH so npm postinstall scripts can find sh, python3, etc.
      export PATH="$PATH:/run/current-system/sw/bin"

      cd "$source_dir/frontends/screen"
      npm ci --prefer-offline
      npm run build

      cd "$source_dir/frontends/admin"
      npm ci --prefer-offline
      npm run build

      chown -R "$service_user:$service_user" "$source_dir"
      echo "[displayhive-deploy/$instance] Done."
    '';
  };

  # ── Webhook-triggered fast redeploy script ────────────────────────────────
  # Called by the webhook listener on each Gogs push. Uses git tree-object
  # hashes to skip npm ci/build steps when the frontend sources haven't
  # changed — a Python-only push typically completes in ~5 s.
  webhookDeployScript = pkgs.writeShellApplication {
    name          = "displayhive-webhook-deploy";
    runtimeInputs = with pkgs; [ git nodejs openssh systemd ];
    text = ''
      instance="$1"
      source_dir="$2"
      git_url="$3"
      git_branch="$4"
      ssh_key_file="$5"
      service_user="displayhive-$instance"

      export HOME=/root
      export npm_config_cache=/root/.npm

      # See the boot-time deploy script for why this is unconditional: it
      # keeps anonymous/keyless ssh:// checkouts from hanging on a host-key
      # prompt with no TTY to answer it.
      ssh_opts="-o StrictHostKeyChecking=accept-new -o BatchMode=yes"
      if [ -n "$ssh_key_file" ]; then
        ssh_opts="-i $ssh_key_file $ssh_opts"
      fi
      export GIT_SSH_COMMAND="ssh $ssh_opts"

      export GIT_CONFIG_COUNT=1
      export GIT_CONFIG_KEY_0="safe.directory"
      export GIT_CONFIG_VALUE_0="$source_dir"

      if [ ! -d "$source_dir/.git" ]; then
        echo "[displayhive-webhook/$instance] ERROR: $source_dir is not a git repo — run the boot deploy first" >&2
        exit 1
      fi

      # gitRepository may have changed since the initial clone — keep origin
      # pointed at the configured URL.
      git -C "$source_dir" remote set-url origin "$git_url"

      # Snapshot frontend tree hashes before pulling so we can skip
      # expensive npm steps when nothing relevant changed.
      prev_screen_lock=$(git -C "$source_dir" rev-parse "HEAD:frontends/screen/package-lock.json" 2>/dev/null || echo "none")
      prev_admin_lock=$(git -C "$source_dir"  rev-parse "HEAD:frontends/admin/package-lock.json" 2>/dev/null || echo "none")
      prev_screen_tree=$(git -C "$source_dir" rev-parse "HEAD:frontends/screen" 2>/dev/null || echo "none")
      prev_admin_tree=$(git -C "$source_dir"  rev-parse "HEAD:frontends/admin" 2>/dev/null || echo "none")

      echo "[displayhive-webhook/$instance] Fetching $git_branch"
      # See the boot-time deploy script for why this is needed: the initial
      # clone is single-branch, so a branch not present at clone time won't
      # be fetchable until explicitly added here.
      git -C "$source_dir" remote set-branches --add origin "$git_branch"
      git -C "$source_dir" fetch --prune --depth 1 origin "$git_branch"
      git -C "$source_dir" checkout "$git_branch"
      git -C "$source_dir" reset --hard "origin/$git_branch"

      new_screen_lock=$(git -C "$source_dir" rev-parse "HEAD:frontends/screen/package-lock.json" 2>/dev/null || echo "none")
      new_admin_lock=$(git -C "$source_dir"  rev-parse "HEAD:frontends/admin/package-lock.json" 2>/dev/null || echo "none")
      new_screen_tree=$(git -C "$source_dir" rev-parse "HEAD:frontends/screen" 2>/dev/null || echo "none")
      new_admin_tree=$(git -C "$source_dir"  rev-parse "HEAD:frontends/admin" 2>/dev/null || echo "none")

      export PATH="$PATH:/run/current-system/sw/bin"

      # ── screen-client ──────────────────────────────────────────────────────
      if [ "$prev_screen_lock" != "$new_screen_lock" ]; then
        echo "[displayhive-webhook/$instance] screen deps changed — npm ci"
        cd "$source_dir/frontends/screen" && npm ci --prefer-offline
      fi
      if [ "$prev_screen_tree" != "$new_screen_tree" ]; then
        echo "[displayhive-webhook/$instance] screen source changed — npm run build"
        cd "$source_dir/frontends/screen" && npm run build
      else
        echo "[displayhive-webhook/$instance] screen: no changes, skipping build"
      fi

      # ── admin ──────────────────────────────────────────────────────────
      if [ "$prev_admin_lock" != "$new_admin_lock" ]; then
        echo "[displayhive-webhook/$instance] admin deps changed — npm ci"
        cd "$source_dir/frontends/admin" && npm ci --prefer-offline
      fi
      if [ "$prev_admin_tree" != "$new_admin_tree" ]; then
        echo "[displayhive-webhook/$instance] admin source changed — npm run build"
        cd "$source_dir/frontends/admin" && npm run build
      else
        echo "[displayhive-webhook/$instance] admin: no changes, skipping build"
      fi

      chown -R "$service_user:$service_user" "$source_dir"

      echo "[displayhive-webhook/$instance] Restarting app service"
      systemctl restart "displayhive-$instance.service"
      echo "[displayhive-webhook/$instance] Deploy complete."
    '';
  };

  # ── Webhook HTTP listener (Python stdlib — no extra dependencies) ─────────
  # Validates the Gogs HMAC-SHA256 signature, checks the pushed branch, then
  # spawns webhookDeployScript in a background thread.  A deploy-lock prevents
  # concurrent deploys when pushes arrive faster than the build completes.
  #
  # Secret resolution order (evaluated at runtime, not at Nix evaluation time):
  #   1. DISPLAYHIVE_WEBHOOK_SECRET_FILE env var — path to a plain-text file
  #      containing just the secret (recommended; use with agenix / sops-nix).
  #   2. DISPLAYHIVE_WEBHOOK_SECRET env var — inline secret (stored in the
  #      Nix store; acceptable for staging, not recommended for production).
  #   3. Neither set — requests are accepted without signature validation
  #      (only appropriate for purely internal/firewalled staging networks).
  webhookServerPy = pkgs.writeText "displayhive-webhook-server.py" ''
    #!/usr/bin/env python3
    import hashlib, hmac, http.server, json, os, subprocess, sys, threading

    INSTANCE    = sys.argv[1]
    PORT        = int(sys.argv[2])
    LISTEN      = sys.argv[3]          # e.g. "0.0.0.0" or "127.0.0.1"
    BRANCH      = sys.argv[4]          # branch to watch; "" = any branch
    DEPLOY_BIN  = sys.argv[5]
    SOURCE_DIR  = sys.argv[6]
    GIT_URL     = sys.argv[7]
    GIT_BRANCH  = sys.argv[8]
    SSH_KEY     = sys.argv[9] if len(sys.argv) > 9 else ""

    # Resolve webhook secret at runtime so secretFile works with agenix/sops-nix.
    _secret_file = os.environ.get("DISPLAYHIVE_WEBHOOK_SECRET_FILE", "")
    if _secret_file:
        with open(_secret_file) as _f:
            SECRET = _f.read().strip().encode()
    else:
        SECRET = os.environ.get("DISPLAYHIVE_WEBHOOK_SECRET", "").encode()

    if not SECRET:
        print(f"[webhook/{INSTANCE}] WARNING: no secret configured — requests accepted without validation", flush=True)

    _lock = threading.Lock()

    def _run_deploy():
        if not _lock.acquire(blocking=False):
            print(f"[webhook/{INSTANCE}] deploy already in progress, skipping", flush=True)
            return
        try:
            subprocess.run(
                [DEPLOY_BIN, INSTANCE, SOURCE_DIR, GIT_URL, GIT_BRANCH, SSH_KEY],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            print(f"[webhook/{INSTANCE}] deploy failed: {exc}", flush=True)
        finally:
            _lock.release()

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            print(f"[webhook/{INSTANCE}] " + fmt % args, flush=True)

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"displayhive webhook ready\n")

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length)

            if SECRET:
                sig    = self.headers.get("X-Gogs-Signature", "")
                expect = hmac.new(SECRET, body, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(sig, expect):
                    self.send_response(403)
                    self.end_headers()
                    self.wfile.write(b"invalid signature\n")
                    print(f"[webhook/{INSTANCE}] rejected: bad signature", flush=True)
                    return

            try:
                payload = json.loads(body)
            except (ValueError, UnicodeDecodeError):
                self.send_response(400)
                self.end_headers()
                return

            ref = payload.get("ref", "")
            watch = BRANCH or GIT_BRANCH
            print(f"[webhook/{INSTANCE}] ref={ref!r} watch={watch!r}", flush=True)
            if ref != f"refs/heads/{watch}":
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"ignored: wrong branch\n")
                return

            self.send_response(202)
            self.end_headers()
            self.wfile.write(b"deploy triggered\n")
            threading.Thread(target=_run_deploy, daemon=True).start()

    http.server.HTTPServer((LISTEN, PORT), _Handler).serve_forever()
  '';

  # ── Deploy service builder (boot-time, one-shot) ──────────────────────────
  mkDeployService = name: icfg: {
    description = "Checkout and build displayhive source for instance '${name}'";
    after       = [ "network-online.target" ];
    wants       = [ "network-online.target" ];
    environment = {
      HOME             = "/root";
      npm_config_cache = "/root/.npm";
    };
    serviceConfig = {
      Type            = "oneshot";
      RemainAfterExit = true;
      ExecStart =
        "${deployScript}/bin/displayhive-deploy"
        + " ${name}"
        + " ${icfg.sourceDirectory}"
        + " ${icfg.gitRepository}"
        + " ${icfg.gitBranch}"
        + (if icfg.gitSshKeyFile == "" then " \"\"" else " ${icfg.gitSshKeyFile}");
    };
  };

  # ── Webhook service builder ───────────────────────────────────────────────
  mkWebhookService = name: icfg:
    let wcfg = icfg.webhook; in {
      description = "Gogs webhook listener for displayhive instance '${name}'";
      after    = [ "network-online.target" "displayhive-${name}.service" ];
      wants    = [ "network-online.target" ];
      wantedBy = [ "multi-user.target" ];

      # Secret injected via environment — either inline (Nix store) or from a
      # runtime file (agenix / sops-nix).  The Python server reads both.
      environment = optionalAttrs (wcfg.secret != "") {
        DISPLAYHIVE_WEBHOOK_SECRET = wcfg.secret;
      } // optionalAttrs (wcfg.secretFile != "") {
        DISPLAYHIVE_WEBHOOK_SECRET_FILE = wcfg.secretFile;
      };

      serviceConfig = {
        Type      = "simple";
        # Runs as root: needs to read the SSH deploy key and call systemctl.
        ExecStart = "${cfg.pythonEnv}/bin/python3 ${webhookServerPy}"
          + " ${name}"
          + " ${toString wcfg.port}"
          + " ${wcfg.listenAddress}"
          + (if wcfg.branch == "" then " \"\"" else " ${wcfg.branch}")
          + " ${webhookDeployScript}/bin/displayhive-webhook-deploy"
          + " ${icfg.sourceDirectory}"
          + (if icfg.gitRepository == "" then " \"\"" else " ${icfg.gitRepository}")
          + " ${icfg.gitBranch}"
          + (if icfg.gitSshKeyFile == "" then " \"\"" else " ${icfg.gitSshKeyFile}");
        Restart    = "on-failure";
        RestartSec = "5s";
        NoNewPrivileges = false;  # root needs to call systemctl
      };
    };

  # ── Default Python environment ────────────────────────────────────────────
  defaultPythonEnv = pkgs.python3.withPackages (ps: with ps; [
    flask
    flask-socketio
    flask-sqlalchemy
    flask-cors
    alembic
    pillow
    gunicorn
    eventlet
    psycopg2
    requests
    pyjwt
  ]);

  # ── Per-instance option schema ────────────────────────────────────────────
  instanceOpts = { name, ... }: {
    options = {
      port = mkOption {
        type        = types.port;
        description = "TCP port this displayhive instance listens on.";
      };

      sourceDirectory = mkOption {
        type        = types.path;
        description = ''
          Absolute path to the displayhive source tree on the target host.
        '';
      };

      gitRepository = mkOption {
        type    = types.str;
        default = "";
        description = ''
          Git repository URL to clone/pull on boot.  Leave empty to manage
          the source tree yourself (e.g. via rsync).
        '';
      };

      gitBranch = mkOption {
        type    = types.str;
        default = "main";
        description = "Branch to check out.  Only used when gitRepository is set.";
      };

      gitSshKeyFile = mkOption {
        type    = types.str;
        default = "";
        description = ''
          Absolute path to an SSH private key for private repositories.
          Leave empty for public HTTPS repositories, or for an ssh:// repository
          the server exposes for anonymous/keyless read access — the deploy
          scripts always pass BatchMode + accept-new host-key options, so a
          keyless ssh:// checkout won't hang waiting for a host-key prompt.
          Manage with agenix or sops-nix (owner: root, mode: 0400).
        '';
      };

      secretKey = mkOption {
        type        = types.str;
        description = ''
          Flask secret key used for session signing.
          Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
          Use agenix / sops-nix to keep this out of the Nix store in production.
        '';
      };

      corsAllowedOrigins = mkOption {
        type    = types.str;
        default = "*";
        description = ''
          Comma-separated list of allowed origins for Socket.IO CORS.
          Set to the public URL of your reverse proxy in production.
        '';
      };

      logLevel = mkOption {
        type    = types.str;
        default = "INFO";
        description = "Python logging level (e.g. DEBUG, INFO, WARNING, ERROR).";
      };

      trustedProxyCount = mkOption {
        type    = types.ints.unsigned;
        default = 0;
        description = ''
          Number of reverse proxy hops in front of this instance. When > 0,
          enables ProxyFix so request.remote_addr reflects the real client IP
          (used by the login rate limiter) instead of the proxy's address.
        '';
      };

      adminBootstrapUsername = mkOption {
        type    = types.str;
        default = "admin";
        description = "Username for the auto-created bootstrap admin account (first run only).";
      };

      adminBootstrapPassword = mkOption {
        type    = types.str;
        default = "";
        description = ''
          Password for the auto-created bootstrap admin account (first run
          only). Leave empty to have a random password generated and printed
          to the service log on first start.
          WARNING: this value ends up in the Nix store (world-readable).
        '';
      };

      extraEnv = mkOption {
        type    = types.attrsOf types.str;
        default = {};
        description = "Additional environment variables passed to the displayhive process.";
      };

      # ── Webhook sub-options ──────────────────────────────────────────────
      webhook = {
        enable = mkOption {
          type    = types.bool;
          default = false;
          description = ''
            Enable a Gogs webhook listener for this instance.
            Creates systemd service displayhive-<name>-webhook.service.
          '';
        };

        port = mkOption {
          type    = types.port;
          default = 9000;
          description = "TCP port the webhook listener binds to.";
        };

        listenAddress = mkOption {
          type    = types.str;
          default = "0.0.0.0";
          description = ''
            Address the webhook listener binds to.
            Use "127.0.0.1" if nginx terminates TLS and proxies locally.
          '';
        };

        branch = mkOption {
          type    = types.str;
          default = "";
          description = ''
            Only trigger deploys for pushes to this branch.
            Defaults to the instance's gitBranch when left empty.
          '';
        };

        secret = mkOption {
          type    = types.str;
          default = "";
          description = ''
            HMAC-SHA256 secret shared with Gogs (Gogs → repo → Settings →
            Webhooks → Secret).
            WARNING: this value ends up in the Nix store (world-readable).
            Use secretFile for production deployments.
          '';
        };

        secretFile = mkOption {
          type    = types.str;
          default = "";
          description = ''
            Path to a plain-text file containing just the HMAC secret.
            Takes precedence over the inline secret option.
            Recommended approach: manage with agenix or sops-nix.

              age.secrets."displayhive-staging-webhook-secret" = {
                file  = ./secrets/displayhive-staging-webhook-secret.age;
                owner = "root";
                mode  = "0400";
              };
              services.displayhive.instances.staging.webhook.secretFile =
                config.age.secrets."displayhive-staging-webhook-secret".path;
          '';
        };
      };
    };
  };

  # ── App service builder ───────────────────────────────────────────────────
  mkService = name: icfg:
    let hasGit = icfg.gitRepository != ""; in {
    description = "DisplayHive instance '${name}'";
    after    = [ "network.target" "postgresql.service" ]
               ++ optional hasGit "displayhive-${name}-deploy.service";
    requires = [ "postgresql.service" ]
               ++ optional hasGit "displayhive-${name}-deploy.service";
    wantedBy = [ "multi-user.target" ];

    environment = {
      DATABASE_URL             = "postgresql:///displayhive-${name}?host=/run/postgresql";
      FLASK_PORT               = toString icfg.port;
      SECRET_KEY               = icfg.secretKey;
      CORS_ALLOWED_ORIGINS     = icfg.corsAllowedOrigins;
      LOG_LEVEL                = icfg.logLevel;
      TRUSTED_PROXY_COUNT      = toString icfg.trustedProxyCount;
      ADMIN_BOOTSTRAP_USERNAME = icfg.adminBootstrapUsername;
    } // optionalAttrs (icfg.adminBootstrapPassword != "") {
      ADMIN_BOOTSTRAP_PASSWORD = icfg.adminBootstrapPassword;
    } // icfg.extraEnv;

    serviceConfig = {
      Type             = "simple";
      User             = "displayhive-${name}";
      Group            = "displayhive-${name}";
      WorkingDirectory = icfg.sourceDirectory;
      ExecStartPre     = "${cfg.pythonEnv}/bin/alembic upgrade head";
      ExecStart = "${cfg.pythonEnv}/bin/gunicorn"
        + " --worker-class eventlet"
        + " -w 1"
        + " --bind 0.0.0.0:${toString icfg.port}"
        + " app:app";
      Restart    = "on-failure";
      RestartSec = "5s";
      NoNewPrivileges = true;
      PrivateTmp      = true;
    };
  };

in {
  # ── Module options ─────────────────────────────────────────────────────────
  options.services.displayhive = {

    pythonEnv = mkOption {
      type        = types.package;
      default     = defaultPythonEnv;
      defaultText = literalExpression
        "pkgs.python3.withPackages (ps: [ flask flask-socketio ... ])";
      description = ''
        Python environment used by every instance.
        Override to pin versions or add extra packages.
      '';
    };

    instances = mkOption {
      type        = types.attrsOf (types.submodule instanceOpts);
      default     = {};
      description = ''
        Set of displayhive instances to run.  Each attribute key becomes the
        instance name and determines the system user, PostgreSQL role/database,
        and systemd service names.
      '';
      example = literalExpression ''
        {
          staging = {
            port            = 5001;
            sourceDirectory = "/opt/displayhive/staging";
            gitRepository   = "https://gogs.example.com/yourorg/displayhive.git";
            gitBranch       = "testing";
            secretKey       = "change-me";
            corsAllowedOrigins = "https://staging.example.com";
            webhook.enable     = true;
            webhook.port       = 9001;
            webhook.secretFile = "/run/secrets/displayhive-staging-webhook-secret";
          };
        }
      '';
    };
  };

  # ── Module implementation ─────────────────────────────────────────────────
  config = mkIf (cfg.instances != {}) {

    services.postgresql.enable = mkDefault true;

    services.postgresql.ensureDatabases =
      mapAttrsToList (name: _: "displayhive-${name}") cfg.instances;

    services.postgresql.ensureUsers =
      mapAttrsToList (name: _: {
        name              = "displayhive-${name}";
        ensureDBOwnership = true;
      }) cfg.instances;

    systemd.services =
      # App services
      mapAttrs' (name: icfg:
        nameValuePair "displayhive-${name}" (mkService name icfg)
      ) cfg.instances
      //
      # Boot-time deploy services (only when gitRepository is set)
      mapAttrs' (name: icfg:
        nameValuePair "displayhive-${name}-deploy" (mkDeployService name icfg)
      ) (filterAttrs (_: icfg: icfg.gitRepository != "") cfg.instances)
      //
      # Webhook listener services (only when webhook.enable is true)
      mapAttrs' (name: icfg:
        nameValuePair "displayhive-${name}-webhook" (mkWebhookService name icfg)
      ) (filterAttrs (_: icfg: icfg.webhook.enable) cfg.instances);

    users.users =
      mapAttrs' (name: icfg: nameValuePair "displayhive-${name}" {
        isSystemUser = true;
        group        = "displayhive-${name}";
        home         = icfg.sourceDirectory;
        createHome   = false;
        description  = "System user for displayhive instance '${name}'";
      }) cfg.instances;

    users.groups =
      mapAttrs' (name: _: nameValuePair "displayhive-${name}" {})
      cfg.instances;
  };
}
