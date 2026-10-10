# nix/module.nix — NixOS module for displayhive
#
# Lets you declare any number of independent displayhive instances on a single host.
# Each instance gets:
#   • its own systemd service (displayhive-<name>.service)
#   • its own system user / group (displayhive-<name>)
#   • its own PostgreSQL database and role (displayhive-<name>)
#   • its own TCP port
#   • a `displayhive-<name>` command for maintenance (`flask dh …`, application/cli.py)
#
# The server runs a Nix PACKAGE (nix/package.nix: the frontends, the locked Python packages and the
# application, all built by Nix) — nothing is cloned, installed or built on the host. Use it through
# the flake:
#
#   inputs.displayhive.url = "github:DisplayHive/DisplayHive";          # or a tag / branch
#   …
#   imports = [ inputs.displayhive.nixosModules.default ];
#   services.displayhive.instances.main = { port = 5000; secretKeyFile = "/run/secrets/…"; … };
#
# Updating is a flake update and `nixos-rebuild switch`: the new package is built (or fetched from
# a binary cache) first, then the service restarts on it, and the previous generation is one
# rollback away. Without flakes, set `services.displayhive.package` to a package you built from
# nix/package.nix.
#
# Instance names must be valid in Linux usernames and PostgreSQL role names
# (letters, digits, dashes — no spaces or underscores at the start).
#
# Database migrations (`flask dh migrate`) run before every start of the app:
# after a database backup, and if one fails the app does not start — see
# application/migration.py. The backups (and scheduled ones) are written to
# <dataDirectory>/backups; see the `backup` options below.
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
#       # At least MAX_FILE_SIZE in application/admin/media/storage.py
#       # (uploads are one file per HTTP request, POST /admin/api/media/upload)
#       client_max_body_size 51M;
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

  removedOption = mkOption {
    type    = types.nullOr types.anything;
    default = null;
    visible = false;
    description = "Removed: the module no longer builds on the host.";
  };
  removedOptionNames = [ "sourceDirectory" "gitRepository" "gitBranch" "gitSshKeyFile" "pythonEnvDirectory" "webhook" ];
  removedBuildOnHost = ''
    The module no longer clones, installs or builds anything on the server: it runs the Nix package
    of nix/package.nix. Use the flake (`inputs.displayhive.nixosModules.default`) or set
    `services.displayhive.package`; updates are a flake update and `nixos-rebuild switch`. Remove
    sourceDirectory, gitRepository, gitBranch, gitSshKeyFile, pythonEnvDirectory and webhook.*
    from the instance. See the header of nix/module.nix.
  '';

  # Native libraries are part of the package wrapper (nix/package.nix); nothing to set up here.
  appOf = icfg: "${icfg.package}/${icfg.package.passthru.appDir}";
  pythonOf = icfg: "${icfg.package}/bin/displayhive-python";

  # ── Per-instance option schema ────────────────────────────────────────────
  instanceOpts = { name, ... }: {
    options = {
      # Options of the build-on-the-host module, kept only to say so when one is still set
      # (mkRemovedOptionModule does not work inside a submodule). See the assertions below.
      sourceDirectory    = removedOption;
      gitRepository      = removedOption;
      gitBranch          = removedOption;
      gitSshKeyFile      = removedOption;
      pythonEnvDirectory = removedOption;
      webhook            = removedOption;

      port = mkOption {
        type        = types.port;
        description = "TCP port this displayhive instance listens on.";
      };

      package = mkOption {
        type        = types.package;
        default     = cfg.package;
        defaultText = literalExpression "config.services.displayhive.package";
        description = ''
          The DisplayHive package this instance runs (see nix/package.nix). Defaults to the
          module-wide {option}`services.displayhive.package`; set it per instance to run, say, a
          staging build next to the production one.
        '';
      };

      dataDirectory = mkOption {
        type        = types.path;
        default     = "/var/lib/displayhive/${name}";
        description = ''
          Where this instance keeps uploaded media, previews, renditions, import staging and
          backups (DATA_DIR, see application/paths.py). Created with mode 0750 for the instance's
          user. Updates never touch it. Back it up (the media; the database has its own
          backups, see {option}`backup`).
        '';
      };

      secretKey = mkOption {
        type        = types.nullOr types.str;
        default     = null;
        description = ''
          Flask secret key used for session signing, as a plain string — which
          puts it in the world-readable Nix store. Fine for a test; in
          production use {option}`secretKeyFile` (or {option}`environmentFile`).
          Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
        '';
      };

      secretKeyFile = mkOption {
        type        = types.nullOr types.str;
        default     = null;
        example     = "/run/secrets/displayhive-main-secret-key";
        description = ''
          Absolute path of a file holding the secret key (agenix, sops-nix, or
          any root-only file). systemd loads it as a credential, so only the
          service sees it and the service user needs no access to the file
          itself; it never enters the Nix store or the environment listing.
          Set exactly one of {option}`secretKey`, {option}`secretKeyFile` or a
          SECRET_KEY line in {option}`environmentFile`.
        '';
      };

      environmentFile = mkOption {
        type        = types.nullOr types.str;
        default     = null;
        example     = "/run/secrets/displayhive-main.env";
        description = ''
          Absolute path of a file with further `NAME=value` lines (one per line,
          no `export`, no spaces around `=`) added to the service's environment:
          for example SECRET_KEY, ADMIN_BOOTSTRAP_PASSWORD or DB credentials that
          should stay out of the Nix store. Read by systemd (EnvironmentFile=);
          the `displayhive-<name>` command reads it too.
        '';
      };

      bindAddress = mkOption {
        type    = types.str;
        default = "127.0.0.1";
        example = "0.0.0.0";
        description = ''
          Address the app listens on. The default, loopback, suits a reverse
          proxy on the same host (which you want in front for TLS anyway). Use
          "0.0.0.0" (or one interface's address) only if the proxy runs on
          another machine — the app then speaks plain HTTP on that interface, so
          restrict it with the firewall. (Before this option existed the app
          always listened on 0.0.0.0.)
        '';
      };

      publicUrl = mkOption {
        type    = types.nullOr types.str;
        default = null;
        example = "https://signage.example.com";
        description = ''
          The address people reach this instance at (scheme and host).
          CORS and the SSO redirect URI are derived from it, instead of from
          the Host header of each request. Set this in production.
        '';
      };

      corsAllowedOrigins = mkOption {
        type    = types.nullOr types.str;
        default = null;
        description = ''
          Comma-separated list of allowed origins for Socket.IO CORS.
          When null: the origin of {option}`publicUrl` if that is set,
          otherwise "*" (any origin — set one of the two in production).
        '';
      };

      logFormat = mkOption {
        type    = types.enum [ "text" "json" ];
        default = "text";
        description = ''
          "json" writes the logs (the app's and gunicorn's) as one JSON object per
          line, for log collectors; the journal keeps them as the message. Same as
          LOG_FORMAT.
        '';
      };

      logLevel = mkOption {
        type    = types.str;
        default = "INFO";
        description = "Python logging level (e.g. DEBUG, INFO, WARNING, ERROR).";
      };

      threads = mkOption {
        type        = types.ints.positive;
        default     = 500;
        description = ''
          gunicorn worker threads (gthread worker, single process). Every
          connected screen and open admin tab keeps one thread busy for its
          WebSocket, so this must exceed the number of simultaneous
          connections, with headroom for plain HTTP requests.
        '';
      };

      backup = {
        intervalHours = mkOption {
          type    = types.ints.unsigned;
          default = 24;
          description = ''
            A database backup every this many hours, kept in
            <dataDirectory>/backups (BACKUP_INTERVAL_HOURS). 0 turns scheduled
            backups off — the backup before each migration stays. That directory
            is on the same disk as the data: copy it elsewhere as well.
          '';
        };
        keep = mkOption {
          type    = types.ints.positive;
          default = 7;
          description = "How many scheduled database backups to keep (BACKUP_KEEP).";
        };
        beforeMigration = mkOption {
          type    = types.bool;
          default = true;
          description = ''
            Back the database up before applying migrations (MIGRATION_BACKUP).
            If that fails, nothing is migrated.
          '';
        };
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
    };
  };

  # ── App service builder ───────────────────────────────────────────────────
  # The service's environment — shared with the CLI wrapper below, so
  # maintenance commands see exactly the database and DATA_DIR the server uses.
  mkServiceEnv = name: icfg: {
      DATABASE_URL             = "postgresql:///displayhive-${name}?host=/run/postgresql";
      FLASK_PORT               = toString icfg.port;
      CORS_ALLOWED_ORIGINS     = if icfg.corsAllowedOrigins != null then icfg.corsAllowedOrigins
                                 else if icfg.publicUrl != null then icfg.publicUrl
                                 else "*";
      LOG_LEVEL                = icfg.logLevel;
      LOG_FORMAT               = icfg.logFormat;
      TRUSTED_PROXY_COUNT      = toString icfg.trustedProxyCount;
      DATA_DIR                 = icfg.dataDirectory;
      DISPLAYHIVE_DEPLOYMENT   = "nixos";
      BACKUP_INTERVAL_HOURS    = toString icfg.backup.intervalHours;
      BACKUP_KEEP              = toString icfg.backup.keep;
      MIGRATION_BACKUP         = if icfg.backup.beforeMigration then "on" else "off";
      ADMIN_BOOTSTRAP_USERNAME = icfg.adminBootstrapUsername;
    } // optionalAttrs (icfg.adminBootstrapPassword != "") {
      ADMIN_BOOTSTRAP_PASSWORD = icfg.adminBootstrapPassword;
    } // optionalAttrs (icfg.secretKey != null) {
      SECRET_KEY = icfg.secretKey;
    } // optionalAttrs (icfg.publicUrl != null) {
      PUBLIC_URL = icfg.publicUrl;
    } // icfg.extraEnv;

  # `displayhive-<name> <command>` = `flask dh <command>` as the instance's
  # user, in the package's application directory, with its environment. Run it as root, e.g.
  #   displayhive-main check-config
  #   displayhive-main reset-password admin --activate
  mkCli = name: icfg: pkgs.writeShellScriptBin "displayhive-${name}" ''
    set -euo pipefail
    if [ "$(${pkgs.coreutils}/bin/id -u)" -ne 0 ]; then
      echo "displayhive-${name}: run as root — it switches to the user displayhive-${name}" >&2
      exit 1
    fi
    cd ${escapeShellArg (appOf icfg)}
    ${optionalString (icfg.environmentFile != null) ''
    # The service's EnvironmentFile (NAME=value lines), for the command as well.
    set -a
    . ${escapeShellArg icfg.environmentFile}
    set +a
    ''}${optionalString (icfg.secretKeyFile != null) ''
    # Read as root and handed over in the environment (not on a command line).
    SECRET_KEY="$(${pkgs.coreutils}/bin/cat ${escapeShellArg icfg.secretKeyFile})"
    export SECRET_KEY
    ''}exec ${pkgs.util-linux}/bin/runuser -u displayhive-${name} -- \
      ${pkgs.coreutils}/bin/env \
      ${concatStringsSep " " (mapAttrsToList (k: v: escapeShellArg "${k}=${v}")
          # LOG_LEVEL: the CLI's own quieter default (WARNING) reads better.
          (removeAttrs (mkServiceEnv name icfg) [ "LOG_LEVEL" "FLASK_PORT" ]))} \
      ${pythonOf icfg} -m flask dh "$@"
  '';

  mkService = name: icfg: {
    description = "DisplayHive instance '${name}'";
    after    = [ "network.target" "postgresql.service" ];
    requires = [ "postgresql.service" ];
    wantedBy = [ "multi-user.target" ];

    environment = mkServiceEnv name icfg;
    # pg_dump / pg_restore / psql of the database server's own version.
    path = [ config.services.postgresql.package ];

    # A failing migration (or backup) is retried a few times, then the unit stays
    # failed: `journalctl -u displayhive-<name>` names the backup to restore.
    unitConfig = {
      StartLimitIntervalSec = 300;
      StartLimitBurst       = 3;
    };

    serviceConfig = {
      Type             = "simple";
      User             = "displayhive-${name}";
      Group            = "displayhive-${name}";
      WorkingDirectory = appOf icfg;
      # The migration backs up first and exits 78 if anything fails; the unit then
      # fails and (StartLimit* below) is not retried for ever.
      ExecStartPre     = [ "${pythonOf icfg} -m flask dh migrate" ];
      ExecStart = "${pythonOf icfg} -m gunicorn"
        + " --worker-class gthread"
        + " -w 1"
        + " --threads ${toString icfg.threads}"
        + " --bind ${icfg.bindAddress}:${toString icfg.port}"
        # gunicorn's control socket (gunicornc) is unused, and it wants to create a file
        # in a directory the sandbox keeps read-only.
        + " --no-control-socket"
        + lib.optionalString (icfg.logFormat == "json") " --log-config-json ${appOf icfg}/gunicorn-logging.json"
        + " app:app";
      Restart    = "on-failure";
      RestartSec = "5s";
      # One open socket per connected screen / admin tab (see `threads`).
      LimitNOFILE     = 65536;
    }
    # Secrets that stay out of the Nix store (see secretKeyFile / environmentFile).
    // optionalAttrs (icfg.secretKeyFile != null) {
      LoadCredential = "secret_key:${icfg.secretKeyFile}";
      Environment    = [ "SECRET_KEY_FILE=%d/secret_key" ];
    }
    // optionalAttrs (icfg.environmentFile != null) {
      EnvironmentFile = icfg.environmentFile;
    }
    # Sandbox: the application is read-only (it is in the Nix store); the service writes only its
    # data directory. It needs no capabilities and talks over unix sockets (PostgreSQL) and IP
    # (clients, Pretalx, SSO) only.
    // {
      NoNewPrivileges        = true;
      PrivateTmp             = true;
      PrivateDevices         = true;
      ProtectSystem          = "strict";
      ReadWritePaths         = [ icfg.dataDirectory ];
      # /home stays out of reach, unless the data directory itself lives there.
      ProtectHome            = if hasPrefix "/home" icfg.dataDirectory || hasPrefix "/root" icfg.dataDirectory
                               then "read-only" else true;
      ProtectKernelTunables  = true;
      ProtectKernelModules   = true;
      ProtectKernelLogs      = true;
      ProtectControlGroups   = true;
      ProtectClock           = true;
      ProtectHostname        = true;
      LockPersonality        = true;
      RestrictRealtime       = true;
      RestrictSUIDSGID       = true;
      RestrictNamespaces     = true;
      RestrictAddressFamilies = [ "AF_UNIX" "AF_INET" "AF_INET6" ];
      CapabilityBoundingSet  = "";
      AmbientCapabilities    = "";
      SystemCallArchitectures = "native";
    };
  };

in {
  imports = [
    (mkRemovedOptionModule [ "services" "displayhive" "pythonEnv" ] ''
      Python packages come from the lock file requirements.txt, built into the Nix package
      (nix/package.nix), so the server runs exactly the versions CI tests and the Docker image
      ships. Add a dependency to requirements.in, run `npm run deps:lock`, then
      `nix run .#update-hashes`.
    '')
  ];

  # ── Module options ─────────────────────────────────────────────────────────
  options.services.displayhive = {

    package = mkOption {
      type        = types.package;
      description = ''
        The DisplayHive package (nix/package.nix) the instances run. The flake's
        {file}`nixosModules.default` sets it to the flake's own package; without flakes, build one with
        `pkgs.callPackage ./nix/package.nix { src = ./.; }`.
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
            port          = 5001;
            secretKeyFile = "/run/secrets/displayhive-staging-secret-key";
            publicUrl     = "https://staging.example.com";
          };
        }
      '';
    };
  };

  # ── Module implementation ─────────────────────────────────────────────────
  config = mkIf (cfg.instances != {}) {

    assertions = concatLists (mapAttrsToList (name: icfg: [
      {
        assertion = all (o: icfg.${o} == null) removedOptionNames;
        message   = "services.displayhive.instances.${name}: ${removedBuildOnHost}";
      }
      {
        assertion = icfg.secretKey != null || icfg.secretKeyFile != null || icfg.environmentFile != null;
        message   = "services.displayhive.instances.${name}: set secretKeyFile (recommended), secretKey, "
                    + "or a SECRET_KEY line in environmentFile — without one the app runs with an insecure default key.";
      }
      {
        assertion = !(icfg.secretKey != null && icfg.secretKeyFile != null);
        message   = "services.displayhive.instances.${name}: set secretKey or secretKeyFile, not both.";
      }
      {
        assertion = all (f: f == null || hasPrefix "/" f) [ icfg.secretKeyFile icfg.environmentFile ];
        message   = "services.displayhive.instances.${name}: secretKeyFile and environmentFile must be absolute paths.";
      }
    ]) cfg.instances);

    services.postgresql.enable = mkDefault true;

    environment.systemPackages = mapAttrsToList mkCli cfg.instances;

    services.postgresql.ensureDatabases =
      mapAttrsToList (name: _: "displayhive-${name}") cfg.instances;

    services.postgresql.ensureUsers =
      mapAttrsToList (name: _: {
        name              = "displayhive-${name}";
        ensureDBOwnership = true;
      }) cfg.instances;

    systemd.services =
      mapAttrs' (name: icfg:
        nameValuePair "displayhive-${name}" (mkService name icfg)
      ) cfg.instances;

    users.users =
      mapAttrs' (name: icfg: nameValuePair "displayhive-${name}" {
        isSystemUser = true;
        group        = "displayhive-${name}";
        home         = icfg.dataDirectory;
        createHome   = false;
        description  = "System user for displayhive instance '${name}'";
      }) cfg.instances;

    # DATA_DIR per instance, owned by its service user (see dataDirectory).
    systemd.tmpfiles.rules =
      mapAttrsToList (name: icfg:
        "d ${icfg.dataDirectory} 0750 displayhive-${name} displayhive-${name} -"
      ) cfg.instances;

    users.groups =
      mapAttrs' (name: _: nameValuePair "displayhive-${name}" {})
      cfg.instances;
  };
}
