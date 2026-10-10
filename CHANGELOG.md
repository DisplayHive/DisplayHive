# Changelog

All notable changes to DisplayHive are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/)
(the current version is in [`VERSION`](VERSION)). Until 1.0, minor versions may still contain breaking changes;
they are called out under **Breaking changes**.

## [Unreleased]

### Breaking changes

- **NixOS module: nothing is built on the server any more.** The module runs a Nix package
  (`nix/package.nix`: both frontends, the locked Python packages and the application) instead of cloning the
  repository and running `npm ci`/`npm run build` at start. Use the flake (`inputs.displayhive.nixosModules.default`)
  or set `services.displayhive.package`. Updating is `nix flake update displayhive && nixos-rebuild switch`; the
  previous generation stays one rollback away.
  - Removed instance options: `sourceDirectory`, `gitRepository`, `gitBranch`, `gitSshKeyFile`,
    `pythonEnvDirectory` and `webhook.*` (the Gogs/GitHub push auto-deploy). Setting one stops the build with a message.
    Let a CI job or a timer run the flake update if you want to deploy on every push.
  - Added: `services.displayhive.package` and a per-instance `package`.
  - Your data is untouched (`dataDirectory`, the database). **Instances that still keep their media in the old
    `<sourceDirectory>/static/media*` must move them to `dataDirectory` first** (steps in the installation guide),
    because the application now lives in the read-only Nix store.
  - The old source directory (for example `/opt/displayhive/<name>`) and the Python cache
    (`/var/cache/displayhive/<name>`) are no longer used and can be deleted.

### Added

- **Dashboard:** what is on air right now, what ends or starts in the next seven days, what was changed last,
  and quick actions (new content, upload media, add a screen). Content elements record when they were last
  written (database migration `d1a5f7b2c8e6`; existing rows are filled in when they are next saved).
- **Search (Ctrl+K / ⌘K):** a search field in the middle of the header (a magnifier on narrow screens) finds pages,
  actions, content, screens, screen groups and media by name.
- **Media usage:** every file shows whether anything uses it; filter by *Unused*; the edit dialog lists where a
  file is used (content, content type presets, container defaults, designs, settings) with links; deleting a
  file that is still in use asks first and names the places.
- **Screen log:** screens report to a log that is stored on the server. The Logger page shows live and earlier
  lines, with filters (screen, severity, text) and *Load older lines*. Screens always report warnings and errors,
  everything else while someone watches the Logger page. Retention is set in Settings → Screens (72 hours and
  250,000 lines by default).
- **Status dot on screens:** a small dot appears in the corner only when something is wrong. Red `con` is a lost
  connection; yellow `mim` is missing content or a picture that did not load, `js` a script error. The codes are
  also written to the screen log, and the dot can be switched off in Settings.
- **Screens work offline:** a service worker keeps the screen page, its files and recently used media; the last
  content is saved in the browser. A screen restarted while the server is unreachable starts again and shows its last
  content (needs https or `localhost`).
- **Reconnecting with backoff:** screens retry quickly at first and then at most every 30 seconds, with random
  spread, so a restarting server is not hit by all screens at once.
- **Daily reload** of screens at a time set in Settings → Screens, a reload after a new release was installed, a
  pointer that hides itself when idle, and a wake lock that keeps the display awake.
- **Binary cache (optional):** CI pushes the built Nix package to a Cachix cache signed with the project's own
  key, so a server can download it instead of building (see the installation guide for the trust it implies).
- **Nix package and tooling:** `nix build .#default`, a NixOS VM test of the module
  (`nix build .#checks.x86_64-linux.module`), `nix run .#update-hashes` for the pinned hashes, and a CI job that
  builds the package. `nix/example.nix` documents every module option.
- **Documentation:** serving media and the screen bundle straight from nginx; which setting lives where
  (admin settings or environment variables); the process model and why there is no Redis; a README that is an
  overview with structured links.

### Changed

- The WYSIWYG editor uses **Quill 2** (the last moderate `npm audit` finding is gone).
- The Docker image is smaller: the application is copied with its owner set (`COPY --chown`) instead of being
  stored twice by a `chown -R` (a layer of about 370 MB shrank to a few kilobytes), and generated icon folders no
  longer reach the build context.
- Two concurrent changes to the same rows (two admins deleting a layout and its container at the same moment)
  answer with "changed or deleted by someone else, reload and try again" instead of "Internal error".
- Admin socket handlers answer in one format (`{success, …}`) and the admin's large views are split into
  smaller parts with tests (no change in behaviour; the end-to-end suite and screenshots were compared).
- The screen package is named `displayhive-screen` and uses the official Socket.IO client 4 types.

### Fixed

- The screen page showed the design-CSS script as text on screen and did not apply the design CSS (a closing
  script tag inside a comment ended the script early).
- The Logger page did not show lines of screens that connected while it was already open.
- The Layout editor's settings card did not follow a drag, a resize or *Reset to Default Position*; typing a
  number there put the old size back.
- Superfluous reloads of lists after saving (layouts, content types, media previews) that could briefly show an
  older list.

## [0.1.0] — 2026-07-10

First public release.
