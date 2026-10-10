#!/usr/bin/env bash
# Recomputes nix/hashes.nix — the hashes of the Nix package's fixed-output inputs (nix/package.nix):
#   • npm.admin / npm.screen   from frontends/*/package-lock.json
#   • pythonWheels.<system>    from requirements.txt (the wheels pip downloads for that platform)
# Run it after changing a lock file:   nix run .#update-hashes     (or: sh scripts/update-nix-hashes.sh)
# It needs network access, and nothing else installed: every tool comes from Nix.
set -euo pipefail
cd "$(dirname "$0")/.."

root=$PWD
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

FAKE="sha256-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

write_hashes() {   # admin screen x86_64 aarch64
  cat > nix/hashes.nix <<EOF
# Hashes of the package's fixed-output inputs (see nix/package.nix). \`scripts/update-nix-hashes.sh\`
# recomputes them; a lock file change makes the build fail until it was run.
{
  npm = {
    admin  = "$1";
    screen = "$2";
  };
  pythonWheels = {
    x86_64-linux  = "$3";
    aarch64-linux = "$4";
  };
}
EOF
}

# The npm dependencies: build the fetch with a placeholder hash; Nix reports the real one.
npm_hash() {
  local out
  out=$(nix build --no-link ".#default.$1Dist.npmDeps" 2>&1 || true)
  echo "$out" | sed -n 's/^ *got: *//p' | head -n1
}

# The same pip command as the derivation in nix/package.nix (keep them in step: it names the
# Python version and the platforms), so the hash is the same on every machine.
wheels_hash() {
  local arch=$1 out="$tmp/wheels-$1"
  local py platforms=()
  py=$(sed -E 's/^[[:space:]]*([0-9]+)\.([0-9]+).*/\1.\2/' .python-version)
  for p in "linux_$arch" "manylinux2014_$arch" "manylinux2010_$arch" "manylinux1_$arch" \
           $(for m in $(seq 5 42); do echo "manylinux_2_${m}_$arch"; done) "musllinux_1_1_$arch"; do
    platforms+=(--platform "$p")
  done
  nix shell --quiet nixpkgs#python3Packages.pip --command pip download \
    --disable-pip-version-check --no-deps --only-binary=:all: \
    --python-version "$py" --implementation cp --abi "cp${py/./}" --abi abi3 --abi none \
    "${platforms[@]}" -r requirements.txt --dest "$out" >/dev/null
  nix hash path "$out"
}

echo "python wheels (x86_64)…" >&2;  x86=$(wheels_hash x86_64)
echo "python wheels (aarch64)…" >&2; arm=$(wheels_hash aarch64)

# The flake only sees tracked files: make sure nix/hashes.nix is one.
git add -N nix/hashes.nix 2>/dev/null || true
write_hashes "$FAKE" "$FAKE" "$x86" "$arm"
echo "npm (admin)…" >&2;  admin=$(npm_hash admin)
echo "npm (screen)…" >&2; screen=$(npm_hash screen)
[ -n "$admin" ] && [ -n "$screen" ] || { echo "could not compute the npm hashes" >&2; exit 1; }
write_hashes "$admin" "$screen" "$x86" "$arm"
echo "nix/hashes.nix updated." >&2
