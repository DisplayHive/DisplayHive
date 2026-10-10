# nix/package.nix — DisplayHive built as a Nix package: the admin and screen frontends, the Python
# packages from the lock file, and the application, ready to run. The NixOS module (nix/module.nix)
# runs this package, so a server never builds anything itself.
#
#   nix build .#default            → result/bin/displayhive-python, result/share/displayhive
#
# Three pieces, each reproducible and each pinned by a hash:
#   • the frontends: buildNpmPackage from the package-lock.json files (npmDepsHash);
#   • the Python packages: the wheels named in requirements.txt (the one lock file Docker, CI and
#     the dev shell use too — it pins every version with hashes), downloaded by pip into a
#     fixed-output derivation (pythonWheelsHash) and unpacked;
#   • the application: the source files the server needs, next to dist/.
#
# When a lock file changes, the hashes change: `nix run .#update-hashes` (scripts/update-nix-hashes.sh)
# recomputes them, and CI fails with a clear message until they are committed.
{ pkgs
, src                       # the repository
, revision ? "unknown"      # the commit, shown in the admin footer (REVISION file)
, lockHashes ? import ./hashes.nix
}:

let
  inherit (pkgs) lib;
  system = pkgs.stdenv.hostPlatform.system;
  python = import ./python.nix { inherit pkgs; };
  pyVersion = python.pythonVersion;                        # "3.13"
  pyTag = "cp${builtins.replaceStrings [ "." ] [ "" ] pyVersion}";

  # Only what a build needs — editing docs, tests or notes does not rebuild anything.
  keep = rel: type:
    let
      top = builtins.head (lib.splitString "/" rel);
      base = baseNameOf rel;
    in
      !(builtins.elem base [ "node_modules" "__pycache__" ".venv" "dist" ".git" ])
      && (builtins.elem top [
        "app.py" "application" "migrations" "alembic.ini" "VERSION" "gunicorn-logging.json"
        "examplecontent" "static" "requirements.txt" ".python-version" "frontends"
      ])
      && !(lib.hasPrefix "static/media" rel);
  source = lib.cleanSourceWith {
    src = lib.cleanSource src;
    filter = path: type: keep (lib.removePrefix (toString src + "/") (toString path)) type;
    name = "displayhive-source";
  };

  # ── Frontends ──────────────────────────────────────────────────────────────
  # Each frontend's vite.config.ts writes to ../../dist/<name> (relative to frontends/<name>).
  mkFrontend = { name, script }: pkgs.buildNpmPackage {
    pname = "displayhive-${name}-dist";
    version = "0";
    inherit source;
    src = source;
    sourceRoot = "displayhive-source/frontends/${name}";
    npmDepsHash = lockHashes.npm.${name};
    npmDepsFetcherVersion = 2;
    nodejs = pkgs.nodejs;
    # The build writes to ../../dist: the unpacked source (read-only, as in the store) must allow it.
    postPatch = ''
      chmod -R u+w ../..
    '';
    DISPLAYHIVE_REVISION = revision;
    npmBuildScript = script;
    dontNpmInstall = true;
    installPhase = ''
      runHook preInstall
      mkdir -p $out
      cp -r ../../dist/${name}/. $out/
      runHook postInstall
    '';
  };
  adminDist = mkFrontend { name = "admin"; script = "build-only"; };
  screenDist = mkFrontend { name = "screen"; script = "build"; };

  # ── Python packages ────────────────────────────────────────────────────────
  # `pip download` verifies every file against the hashes in requirements.txt. Naming the platform
  # makes the choice of wheels independent of the machine that evaluates this.
  archOf = { x86_64-linux = "x86_64"; aarch64-linux = "aarch64"; }.${system}
    or (throw "displayhive: no Python wheels are locked for ${system}");
  platforms = [ "linux_${archOf}" "manylinux2014_${archOf}" "manylinux2010_${archOf}" "manylinux1_${archOf}" ]
    ++ map (minor: "manylinux_2_${toString minor}_${archOf}") (lib.range 5 42)
    ++ [ "musllinux_1_1_${archOf}" ];
  wheels = pkgs.stdenvNoCC.mkDerivation {
    name = "displayhive-python-wheels";
    nativeBuildInputs = [ python.pkgs.pip pkgs.cacert ];
    src = ../requirements.txt;
    dontUnpack = true;
    outputHashMode = "recursive";
    outputHashAlgo = "sha256";
    outputHash = lockHashes.pythonWheels.${system};
    SSL_CERT_FILE = "${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt";
    buildCommand = ''
      export HOME=$TMPDIR
      python -m pip download --disable-pip-version-check --no-deps --only-binary=:all: \
        --python-version ${pyVersion} --implementation cp --abi ${pyTag} --abi abi3 --abi none \
        ${lib.concatMapStringsSep " " (p: "--platform ${p}") platforms} \
        -r $src --dest $out
    '';
  };
  # Wheels are zip files: unpacked next to each other they are the site-packages directory.
  sitePackages = pkgs.stdenvNoCC.mkDerivation {
    name = "displayhive-python-packages";
    nativeBuildInputs = [ pkgs.unzip python ];
    dontUnpack = true;
    buildCommand = ''
      dir=$out/lib/python${pyVersion}/site-packages
      mkdir -p $dir
      for wheel in ${wheels}/*.whl; do unzip -q -o "$wheel" -d $dir; done
      # console scripts / data of wheels are not needed: the app runs through `python -m`.
      rm -rf $dir/*.data
      python -m compileall -q $dir
    '';
  };

  # Native libraries some wheels expect to find (psycopg2-binary needs libz); NixOS has no /usr/lib.
  wheelLibs = lib.makeLibraryPath [ pkgs.zlib pkgs.stdenv.cc.cc.lib ];

in
pkgs.stdenvNoCC.mkDerivation {
  pname = "displayhive";
  version = lib.removeSuffix "\n" (builtins.readFile ../VERSION);
  dontUnpack = true;
  nativeBuildInputs = [ pkgs.makeWrapper ];

  installPhase = ''
    app=$out/share/displayhive
    mkdir -p $app $out/bin
    cp -r ${source}/. $app/
    chmod -R u+w $app
    rm -rf $app/frontends/admin $app/frontends/screen/ts $app/frontends/screen/scripts
    # the screen page's template and static assets stay: the app serves them.
    mkdir -p $app/dist
    cp -r ${adminDist} $app/dist/admin
    cp -r ${screenDist} $app/dist/screen
    echo ${lib.escapeShellArg revision} > $app/REVISION

    # `displayhive-python` is Python with the locked packages and the application on its path:
    #   displayhive-python -m gunicorn … app:app      displayhive-python -m flask dh migrate
    # (run from $out/share/displayhive: the app finds dist/, migrations/ … next to application/).
    makeWrapper ${python}/bin/python3 $out/bin/displayhive-python \
      --prefix PYTHONPATH : ${sitePackages}/lib/python${pyVersion}/site-packages:$app \
      --prefix LD_LIBRARY_PATH : ${wheelLibs} \
      --set PYTHONDONTWRITEBYTECODE 1 \
      --set-default FLASK_APP app \
      --chdir $app
  '';

  passthru = { inherit adminDist screenDist wheels sitePackages python; appDir = "share/displayhive"; };

  meta = {
    description = "DisplayHive — self-hosted digital signage";
    mainProgram = "displayhive-python";
    platforms = [ "x86_64-linux" "aarch64-linux" ];
  };
}
