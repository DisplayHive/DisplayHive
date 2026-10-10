{
  description = "displayhive development environment";

  inputs = {
    # Pinned to the same revision as this machine's `<nixpkgs>` channel so
    # `nix-shell` and `nix develop` always resolve identical package versions
    # (e.g. `playwright-driver`'s bundled browser revisions, which must match
    # the `@playwright/test` version pinned in testing/package-lock.json).
    nixpkgs.url = "github:NixOS/nixpkgs/1c3fe55ad329cbcb28471bb30f05c9827f724c76";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    {
      # The NixOS module (nix/module.nix) with this flake's package as the default.
      nixosModules.default = { lib, pkgs, ... }: {
        imports = [ ./nix/module.nix ];
        services.displayhive.package = lib.mkDefault self.packages.${pkgs.stdenv.hostPlatform.system}.default;
      };
      nixosModules.displayhive = self.nixosModules.default;
    }
    //
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        # The package and the hash tool are for the systems the NixOS module runs on.
        linuxOnly = pkgs.lib.optionalAttrs (builtins.elem system [ "x86_64-linux" "aarch64-linux" ]) {
          packages.default = pkgs.callPackage ./nix/package.nix {
            src = self;
            revision = self.shortRev or self.dirtyShortRev or "unknown";
          };

          # A NixOS VM test of the module (needs KVM): nix build .#checks.x86_64-linux.module
          checks.module = import ./nix/tests/module.nix { inherit pkgs self; };

          # Recomputes nix/hashes.nix after a lock file changed (scripts/update-nix-hashes.sh).
          apps.update-hashes = {
            type = "app";
            program = toString (pkgs.writeShellScript "update-nix-hashes" ''
              cd "$(${pkgs.git}/bin/git rev-parse --show-toplevel)"
              exec ${pkgs.bash}/bin/bash scripts/update-nix-hashes.sh
            '');
            meta.description = "Recompute nix/hashes.nix after a lock file changed";
          };
        };
      in
      linuxOnly // {

        # `shell.nix` remains the single source of truth for the dev
        # environment (packages + shellHook) so `nix-shell` keeps working
        # unchanged; this just exposes the same shell via `nix develop`.
        devShells.default = import ./shell.nix { inherit pkgs; };
      }
    );
}
