# Hashes of the package's fixed-output inputs (see nix/package.nix). `scripts/update-nix-hashes.sh`
# recomputes them; a lock file change makes the build fail until it was run.
{
  npm = {
    admin  = "sha256-Os13EhuR3pP1fculVX2ETQHcAjXwUZaHC76kcH4H8sk=";
    screen = "sha256-ltiuXk5+QqCpSSMUrv8GqKELwEyg/FtE8eaktW/DR4w=";
  };
  pythonWheels = {
    x86_64-linux  = "sha256-aDYMJObepfHqWIFhMCDv5Ke73jdgrAvjyY2MEqxJNgs=";
    aarch64-linux = "sha256-15d/YU61OJUYQ4uz8nq2+dFmZnmCNqsC8N5sEmnVpBw=";
  };
}
