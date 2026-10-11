# Hashes of the package's fixed-output inputs (see nix/package.nix). `scripts/update-nix-hashes.sh`
# recomputes them; a lock file change makes the build fail until it was run.
{
  npm = {
    admin  = "sha256-vlamJtXzZgSJDf0yDzrIAx6nJFTkR9cnxdcWdX6TK94=";
    screen = "sha256-61daTaUr0FvxTUPyRUkipUolUneOn7cwTOqnifyB3xo=";
  };
  pythonWheels = {
    x86_64-linux  = "sha256-Q8dLathBWCuMnTpzGGb8FMhHGt4s8bSJGTSpATIPOBM=";
    aarch64-linux = "sha256-Ueo6W0WzV4m9GYdosNr5e9qzyR+wlECDu06ZZQvD2Qc=";
  };
}
