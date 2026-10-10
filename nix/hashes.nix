# Hashes of the package's fixed-output inputs (see nix/package.nix). `scripts/update-nix-hashes.sh`
# recomputes them; a lock file change makes the build fail until it was run.
{
  npm = {
    admin  = "sha256-AODQQMPhvaj/zoe8U8LVkg9O0E247j6Fgu3iWJkJNxY=";
    screen = "sha256-6vyMBCWr22NYWxUz3hRP+h6J5EKoMbs7n1uTWIZogMg=";
  };
  pythonWheels = {
    x86_64-linux  = "sha256-aDYMJObepfHqWIFhMCDv5Ke73jdgrAvjyY2MEqxJNgs=";
    aarch64-linux = "sha256-15d/YU61OJUYQ4uz8nq2+dFmZnmCNqsC8N5sEmnVpBw=";
  };
}
