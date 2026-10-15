# Hashes of the package's fixed-output inputs (see nix/package.nix). `scripts/update-nix-hashes.sh`
# recomputes them; a lock file change makes the build fail until it was run.
{
  npm = {
    admin  = "sha256-vlamJtXzZgSJDf0yDzrIAx6nJFTkR9cnxdcWdX6TK94=";
    screen = "sha256-6I+xDz5NBVTekMTNsZyKYMlSiuscI/YzdVj+cgUHUiI=";
  };
  pythonWheels = {
    x86_64-linux  = "sha256-7hbz9pLqonaUs85FL3Mn8sOiYXoxxV60JCQfAMEk0OY=";
    aarch64-linux = "sha256-6yKuTWc7a+IpHoOSA4oU1EB8Vce86FtaqqstEfYp0QM=";
  };
}
