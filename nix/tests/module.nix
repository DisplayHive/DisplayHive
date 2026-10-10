# NixOS VM test of nix/module.nix: an instance starts from the package alone, with nothing built or
# downloaded on the machine, migrates its database and serves the admin, the screen page and the
# service worker.   nix build .#checks.x86_64-linux.module   (needs KVM)
{ pkgs, self }:

pkgs.testers.runNixOSTest {
  name = "displayhive-module";

  nodes.machine = { ... }: {
    imports = [ self.nixosModules.default ];
    services.displayhive.instances.main = {
      port = 5000;
      secretKey = "test-secret-key-not-for-production";
      adminBootstrapPassword = "test-admin-password";
      publicUrl = "http://localhost:5000";
    };
    # Nothing may need the internet: the machine has no network but loopback.
    networking.useDHCP = false;
    virtualisation.memorySize = 2048;
  };

  testScript = ''
    machine.wait_for_unit("displayhive-main.service")
    machine.wait_for_open_port(5000)

    with subtest("health and readiness"):
        machine.succeed("curl -fsS http://localhost:5000/healthz")
        machine.succeed("curl -fsS http://localhost:5000/readyz")

    with subtest("the admin, the screen page and the service worker are served"):
        machine.succeed("curl -fsS http://localhost:5000/admin/ | grep -qi '<div id=\"app\"'")
        machine.succeed("curl -fsS http://localhost:5000/ | grep -q 'asset-version'")
        machine.succeed("curl -fsS http://localhost:5000/screen-sw.js | grep -q 'dh-screen'")
        machine.succeed("curl -fsS -o /dev/null http://localhost:5000/dist/screen/screen.js")

    with subtest("the maintenance command works"):
        machine.succeed("displayhive-main check-config")

    with subtest("the service writes only to its data directory"):
        machine.succeed("test -d /var/lib/displayhive/main/media")
        machine.succeed("stat -c %U /var/lib/displayhive/main | grep -qx displayhive-main")

    with subtest("a restart comes back (migrations run again, nothing to do)"):
        machine.succeed("systemctl restart displayhive-main.service")
        machine.wait_for_open_port(5000)
        machine.succeed("curl -fsS http://localhost:5000/readyz")
  '';
}
