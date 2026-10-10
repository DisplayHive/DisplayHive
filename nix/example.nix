# nix/example.nix — Example NixOS configuration using the displayhive module
#
# ────────────────────────────────────────────────────────────────────────────
# How the server gets DisplayHive
# ────────────────────────────────────────────────────────────────────────────
#
# The module runs a Nix package (nix/package.nix): the admin and screen frontends, the locked Python
# packages and the application, all built by Nix — nothing is cloned, installed or built on the
# server. With flakes (flake.nix of your system):
#
#   inputs.displayhive.url = "github:DisplayHive/DisplayHive";   # add /v1.0.0 or ?ref=… to pin
#   outputs = { nixpkgs, displayhive, ... }: {
#     nixosConfigurations.myhost = nixpkgs.lib.nixosSystem {
#       modules = [ displayhive.nixosModules.default ./configuration.nix ];
#     };
#   };
#
# Update:    nix flake update displayhive && sudo nixos-rebuild switch
# Roll back: sudo nixos-rebuild switch --rollback        (the previous package is still there)
#
# The first build compiles the frontends on the machine that runs `nixos-rebuild` (a minute or two);
# build the configuration on a build machine or in CI with a binary cache (cachix, attic, …) and the
# server only downloads the result.
#
# Without flakes, build the package yourself and hand it over:
#   services.displayhive.package = pkgs.callPackage /path/to/DisplayHive/nix/package.nix {
#     src = /path/to/DisplayHive;       # a checkout, or fetchFromGitHub { … }
#     revision = "abc1234";
#   };
#
# After changing a lock file in a checkout of DisplayHive, `nix run .#update-hashes` recomputes
# nix/hashes.nix.

{ config, pkgs, lib, ... }:

{
  # imports = [ inputs.displayhive.nixosModules.default ];   # flakes: see above

  # The package every instance runs. With the flake's nixosModules.default this is already set to the
  # flake's own package; set it only to run something else (a pinned release, a fork).
  # services.displayhive.package = inputs.displayhive.packages.${pkgs.stdenv.hostPlatform.system}.default;

  services.displayhive.instances = {

    staging = {
      # ── Required ────────────────────────────────────────────────────────
      port = 5001;     # TCP port the app listens on

      # One secret key is required (signs sessions). Exactly one of the three ways:
      secretKeyFile = "/run/secrets/displayhive-staging-secret-key";   # recommended: root-only file (agenix / sops-nix),
                                                                       # handed to the service as a systemd credential
      # secretKey   = "change-me";                                     # a plain string: ends up in the world-readable Nix store
      # environmentFile = "/run/secrets/displayhive-staging.env";      # or a SECRET_KEY=… line in this file (see below)

      # ── Where it is reachable ───────────────────────────────────────────
      publicUrl = "https://staging.example.com";   # CORS and the SSO redirect URI derive from it. Set in production.
      # bindAddress        = "127.0.0.1";          # default: loopback, for a reverse proxy on this host.
      #                                            # "0.0.0.0" (or an interface address) only if the proxy is elsewhere:
      #                                            # then restrict the port with the firewall.
      # corsAllowedOrigins = "https://a.example.com,https://b.example.com";  # default: publicUrl, else "*" (any origin)
      # trustedProxyCount  = 1;                    # reverse proxy hops in front (default 0): the real client IP is used
      #                                            # for the login rate limit — set it behind the nginx below

      # ── What it runs ────────────────────────────────────────────────────
      # package = inputs.displayhive-stable.packages.${pkgs.stdenv.hostPlatform.system}.default;
      #                                            # a different build for this instance (default: services.displayhive.package)
      # threads = 500;                             # gunicorn threads; every screen and open admin tab keeps one busy,
      #                                            # so keep it above the number of simultaneous connections

      # ── Data ────────────────────────────────────────────────────────────
      # dataDirectory = "/var/lib/displayhive/staging";   # media, previews, renditions, import staging, backups (DATA_DIR)

      # ── Backups (database; the media are yours to copy from dataDirectory) ──
      # backup.intervalHours   = 24;     # a backup every N hours into <dataDirectory>/backups; 0 = scheduled backups off
      # backup.keep            = 7;      # how many scheduled backups to keep
      # backup.beforeMigration = true;   # back up before applying migrations (if that fails, nothing is migrated)

      # ── First start ─────────────────────────────────────────────────────
      # adminBootstrapUsername = "admin";
      # adminBootstrapPassword = "replace-with-a-real-password";   # WARNING: ends up in the Nix store. Empty (default): a
      #                                                            # random password is generated and printed to the service log.
      #                                                            # Better: ADMIN_BOOTSTRAP_PASSWORD in environmentFile.

      # ── Logging ─────────────────────────────────────────────────────────
      # logLevel  = "INFO";    # DEBUG, INFO, WARNING, ERROR
      # logFormat = "text";    # "json": one JSON object per line (app and gunicorn), for log collectors

      # ── Anything else ───────────────────────────────────────────────────
      # environmentFile = "/run/secrets/displayhive-staging.env";   # NAME=value lines (no `export`), read by systemd and by the
      #                                                             # displayhive-staging command: SECRET_KEY, passwords, DB credentials …
      # extraEnv = {                                                # more environment variables for the process; names and defaults in
      #   OUTBOUND_ALLOW_PRIVATE = "0";                             # docs/user/installation.md → Configuration
      #   LOGIN_RATE_LIMIT_PER_IP = "20";
      #   SCREEN_CSP = "report";
      # };
    };

    # Second instance example
    production = {
      port          = 5002;
      secretKeyFile = "/run/secrets/displayhive-production-secret-key";
      publicUrl     = "https://example.com";
      # A different package for this instance, e.g. a pinned release next to a newer staging:
      # package = inputs.displayhive-stable.packages.${pkgs.stdenv.hostPlatform.system}.default;
    };

  };

  # Pin the PostgreSQL major version to prevent unexpected upgrades.
  services.postgresql.package = pkgs.postgresql_16;

  # ── Nginx reverse proxy (optional) ─────────────────────────────────────
  # services.nginx = {
  #   enable = true;
  #   recommendedProxySettings = true;
  #   recommendedTlsSettings   = true;
  #
  #   virtualHosts."staging.example.com" = {
  #     forceSSL   = true;
  #     enableACME = true;
  #
  #     locations."/" = {
  #       proxyPass       = "http://127.0.0.1:5001";
  #       proxyWebsockets = true;
  #       extraConfig = ''
  #         proxy_read_timeout 86400s;
  #       '';
  #     };
  #
  #     # Static files straight from disk (see "Serving media and the screen bundle from
  #     # nginx" in docs/user/installation.md). A missing file falls through to the app.
  #     # Needs: users.users.nginx.extraGroups = [ "displayhive-staging" ];
  #     locations."/static/media/" = {
  #       alias       = "/var/lib/displayhive/staging/media/";
  #       tryFiles    = "$uri @displayhive";
  #       extraConfig = ''
  #         add_header Cache-Control "public, max-age=2592000, immutable";
  #       '';
  #     };
  #     locations."/static/media_previews/" = {
  #       alias       = "/var/lib/displayhive/staging/media_previews/";
  #       tryFiles    = "$uri @displayhive";
  #       extraConfig = ''
  #         add_header Cache-Control "public, max-age=2592000, immutable";
  #       '';
  #     };
  #     locations."/static/media_renditions/" = {
  #       alias       = "/var/lib/displayhive/staging/media_renditions/";
  #       tryFiles    = "$uri @displayhive";
  #       extraConfig = ''
  #         add_header Cache-Control "public, max-age=2592000, immutable";
  #       '';
  #     };
  #     locations."/dist/screen/" = {
  #       alias       = "${config.services.displayhive.instances.staging.package}/share/displayhive/dist/screen/";
  #       tryFiles    = "$uri @displayhive";
  #       extraConfig = ''
  #         add_header Cache-Control "public, max-age=2592000, immutable";
  #       '';
  #     };
  #     locations."/screen/assets/" = {
  #       alias       = "${config.services.displayhive.instances.staging.package}/share/displayhive/frontends/screen/assets/";
  #       tryFiles    = "$uri @displayhive";
  #       extraConfig = ''
  #         add_header Cache-Control "public, max-age=2592000, immutable";
  #       '';
  #     };
  #     locations."@displayhive" = {
  #       proxyPass       = "http://127.0.0.1:5001";
  #       proxyWebsockets = true;
  #     };
  #
  #   };
  # };
}
