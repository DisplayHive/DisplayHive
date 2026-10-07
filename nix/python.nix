# The Python interpreter for DisplayHive, picked from the repository's
# .python-version (e.g. "3.13" → pkgs.python313) — the one place that sets
# the Python version for the dev shell, the NixOS module, CI
# (actions/setup-python's python-version-file) and the Docker image
# (PYTHON_VERSION build arg). tests/test_python_version.py keeps them in sync.
{ pkgs }:
let
  raw = builtins.readFile ../.python-version;
  m = builtins.match "[[:space:]]*([0-9]+)\\.([0-9]+)[[:space:]]*" raw;
in
  if m == null
  then throw ".python-version must contain a version like 3.13, got: ${raw}"
  else pkgs."python${builtins.elemAt m 0}${builtins.elemAt m 1}"
