#!/bin/sh
# Regenerate the Python lock files from their inputs:
#   requirements.in      → requirements.txt      (runtime; the Docker image)
#   requirements-dev.in  → requirements-dev.txt  (runtime + test/docs; CI)
#
# Pins every package (transitive ones too) with hashes, for the Python version
# in .python-version, resolved for every platform (--universal), so the same
# files work in the Linux image and on a developer's Mac. The dev lock is
# constrained by the runtime lock: shared packages get identical versions.
#
#   npm run deps:lock                 refresh within the constraints in the .in files
#   npm run deps:lock -- --upgrade    also move every pin to the newest allowed version
#
# CI (ci.yml, job python-locks) fails if the committed locks don't match the inputs.
set -eu
cd "$(dirname "$0")/.."
PY="$(tr -d '[:space:]' < .python-version)"
COMMON="--python-version $PY --universal --generate-hashes --quiet"

uv pip compile $COMMON "$@" \
    --custom-compile-command "npm run deps:lock" \
    requirements.in -o requirements.txt
uv pip compile $COMMON "$@" \
    --custom-compile-command "npm run deps:lock" \
    --constraint requirements.txt \
    requirements-dev.in -o requirements-dev.txt
