# Hashes of the package's fixed-output inputs (see nix/package.nix). `scripts/update-nix-hashes.sh`
# recomputes them; a lock file change makes the build fail until it was run.
{
  npm = {
    admin  = "sha256-vlamJtXzZgSJDf0yDzrIAx6nJFTkR9cnxdcWdX6TK94=";
    screen = "sha256-6I+xDz5NBVTekMTNsZyKYMlSiuscI/YzdVj+cgUHUiI=";
  };
  pythonWheels = {
    x86_64-linux  = "sha256-q5V2w/3rhcJG07rHi6fJmRGSR9u5MlgRFXfSCx2damY=";
    aarch64-linux = "sha256-cJoAP8ZGvwX0Gm/5bzgF7Rq+0Odd80BtkpFnbNp8CKk=";
  };
}
