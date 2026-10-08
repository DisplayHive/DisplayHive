# nix/example.nix — Example NixOS configuration using the displayhive module
#
# ────────────────────────────────────────────────────────────────────────────
# SSH deploy key setup
# ────────────────────────────────────────────────────────────────────────────
#
#     ssh-keygen -t ed25519 -C "displayhive-staging@server" \
#       -f /etc/displayhive/staging-deploy-key -N ""
#     chmod 400 /etc/displayhive/staging-deploy-key
#
# Add the public key (.pub) as a read-only deploy key in Gogs:
#   Repo → Settings → Deploy Keys → Add Deploy Key
#
# Recommended: manage the key with agenix or sops-nix:
#
#   age.secrets."displayhive-staging-deploy-key" = {
#     file  = ./secrets/displayhive-staging-deploy-key.age;
#     owner = "root";
#     mode  = "0400";
#   };
#   services.displayhive.instances.staging.gitSshKeyFile =
#     config.age.secrets."displayhive-staging-deploy-key".path;
#
# ────────────────────────────────────────────────────────────────────────────
# Gogs / GitHub webhook setup
# ────────────────────────────────────────────────────────────────────────────
#
# The listener accepts a push webhook from either host — it checks whichever
# signature header the request actually carries (Gogs' X-Gogs-Signature, raw
# hex HMAC-SHA256; GitHub's X-Hub-Signature-256, "sha256=" + hex) against the
# same shared secret, so no extra config is needed to support one vs. the
# other.
#
# 1. Generate a webhook secret on the server:
#      python3 -c "import secrets; print(secrets.token_hex(32))"
#    Store it in a file (e.g. via agenix):
#      /run/secrets/displayhive-staging-webhook-secret   (mode 0400, owner root)
#
# 2. Enable the webhook listener in your NixOS config (see below).
#    After nixos-rebuild switch, the listener is on:
#      http://<server-ip>:<webhook.port>/
#
# 3. If nginx terminates TLS, add a proxy location:
#      location /hooks/displayhive-staging/ {
#          proxy_pass http://127.0.0.1:9001/;
#      }
#    Then the webhook URL becomes https://yourserver.com/hooks/displayhive-staging/
#    and you can set listenAddress = "127.0.0.1" so the port is not exposed.
#
# 4a. In Gogs:    Repo → Settings → Webhooks → Add Webhook → Gogs
#       Payload URL : http(s)://<server>:<port>/   (or via nginx proxy)
#       Content type: application/json
#       Secret      : the value from step 1
#       Trigger     : Push events (or "Send me everything")
#       Active      : ✓
#
# 4b. In GitHub:  Repo → Settings → Webhooks → Add webhook
#       Payload URL : same as above
#       Content type: application/json  — MUST be this, not the form-encoded
#                      option. The listener also accepts
#                      application/x-www-form-urlencoded (GitHub's other
#                      choice, which wraps the JSON payload inside a
#                      `payload=` form field), but there's no reason to use
#                      it here.
#       Secret      : the value from step 1
#       Events      : "Just the push event"
#       Active      : ✓
#     GitHub's "Recent Deliveries" tab on the webhook page shows each
#     delivery's response:
#       - 403 "invalid signature" almost always means the secret configured
#         in GitHub doesn't match webhook.secret/secretFile on the server.
#       - 400 with an "invalid JSON body" server log line almost always
#         means Content type was left on the form-encoded option above.
#

# ────────────────────────────────────────────────────────────────────────────
# Deploy speed
# ────────────────────────────────────────────────────────────────────────────
#
# The webhook-triggered deploy skips npm ci / npm run build when the
# respective frontend source trees haven't changed since the last push:
#
#   • Python-only push  → git pull only           ≈  5 s
#   • Frontend CSS/TS   → git pull + npm run build ≈ 30 s
#   • Dependency change → git pull + npm ci + build ≈ same as before
#
# The boot-time deploy service always does a full npm ci + build to guarantee
# a clean state after a nixos-rebuild switch.

{ config, pkgs, lib, ... }:

{
  imports = [
    ./module.nix   # or the absolute path / flake reference
  ];

  services.displayhive.instances = {

    staging = {
      port            = 5001;
      sourceDirectory = "/opt/displayhive/staging";

      gitRepository   = "https://gogs.example.com/yourorg/displayhive.git";
      gitBranch       = "testing";

      # gitSshKeyFile for private repos (see SSH deploy key setup above).
      # gitSshKeyFile = config.age.secrets."displayhive-staging-deploy-key".path;

      secretKey          = "replace-with-a-real-secret-key";
      publicUrl          = "https://staging.example.com";  # CORS + SSO redirect URI derive from it

      # ── Extra app env vars (all optional — see module.nix for defaults) ──
      # logLevel               = "INFO";
      # trustedProxyCount      = 1;  # set when behind the nginx proxy below
      # adminBootstrapUsername = "admin";
      # adminBootstrapPassword = "replace-with-a-real-password";  # WARNING: ends up in Nix store

      # ── Gogs webhook (see webhook setup above) ─────────────────────────
      webhook.enable     = true;
      webhook.port       = 9001;

      # Recommended: keep the secret out of the Nix store.
      webhook.secretFile = "/run/secrets/displayhive-staging-webhook-secret";
      # For a quick test without secrets management you can use inline secret:
      # webhook.secret = "my-shared-secret";  # WARNING: ends up in Nix store

      # Listen only on loopback when nginx proxies (set webhook.port open
      # in the firewall otherwise).
      # webhook.listenAddress = "127.0.0.1";
    };

    # Second instance example
    production = {
      port            = 5002;
      sourceDirectory = "/opt/displayhive/production";
      gitRepository   = "https://gogs.example.com/yourorg/displayhive.git";
      gitBranch       = "main";
      secretKey       = "replace-with-a-real-secret-key-for-production";
      publicUrl          = "https://example.com";
      # No webhook for production — deploy manually via nixos-rebuild switch.
    };

  };

  # Pin the PostgreSQL major version to prevent unexpected upgrades.
  services.postgresql.package = pkgs.postgresql_16;

  # ── Firewall: open the webhook port if not proxied via nginx ───────────
  # networking.firewall.allowedTCPPorts = [ 9001 ];

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
  #     # Route Gogs webhook to the listener (keeps port 9001 off the internet).
  #     locations."/hooks/displayhive-staging/" = {
  #       proxyPass = "http://127.0.0.1:9001/";
  #     };
  #   };
  # };
}
