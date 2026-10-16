# Changelog

All notable changes to DisplayHive are listed here, newest first. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/)
(the current version is in [`VERSION`](VERSION)). Until 1.0, minor versions may still contain breaking changes;
they are called out under **Breaking changes**.

## [Unreleased]

### Fixed

- **Stores are emptied when a session ends.** After a logout (or an expired session, or a sign-out in
  another tab) the admin kept the data it had fetched — screens, devices, content, media, settings, help —
  in memory, so the next person to sign in at the same tab could see it until their own fetch replaced it,
  and for everything their rights never fetch, not even then. Every such store now has a `reset()`, run
  when the session is cleared.

### Added

- **One server process per data directory is enforced.** DisplayHive keeps its live state (connected screens,
  sessions, the login rate limiter) in the process and has always been meant to run as exactly one gunicorn
  worker. The server now takes a lock on `DATA_DIR/.server.lock`; a second worker (`-w 2`, a second container on
  the same volume, `WEB_CONCURRENCY` above 1, a `kill -HUP` reload) refuses to start with a message instead of
  running with split state. Restart the service rather than reloading it. Docker and the NixOS module already
  start one worker and are unaffected.
- **My account page.** Clicking the name in the top bar opens a page with the account's username, theme
  choice, *change password* (for accounts with a password) and the passkeys below.
- **Passkeys (WebAuthn).** Admins can sign in with a passkey instead of a password — no username needed — from
  *Sign in with a passkey* on the login page. Passkeys are managed on the **My account** page (add,
  rename, remove; accounts created by SSO can have them too); an admin with the right to edit users can remove
  someone else's passkey from the Users page. They need `https` (or `localhost`) and `PUBLIC_URL`; user
  verification (PIN, fingerprint, face) is always required. New dependency `webauthn`, migration
  `f4d9e1a6b3c0` (table `admin_user_passkey`).
- **Weekly time windows for content.** Under *Scheduling* a content element can be limited to recurring times
  (for example Mon–Fri 08:00–18:00; a window may run past midnight). They apply on top of the start and end
  date-time, are read in the instance's time zone, and are evaluated by the screens themselves, so they work
  offline too. The Dashboard's *On air* tile counts only content inside its window. Database migration
  `e2b7c9d4f1a8` adds `content_element.recurrence`; export files get version 11 (older files import as
  "always"). A screen now also takes down content whose window has closed, instead of leaving it on screen
  until the next change.

## [1.0.0-rc1] — 2026-10-15

First release candidate for 1.0.

### Breaking changes

- **Docker: upgrading from 0.x.** `:latest` keeps the old version until 1.0; the release candidate is the image
  `ghcr.io/displayhive/displayhive:1.0.0-rc1`. The old image has no backup commands, so **take a backup by hand
  first**: the migrations change the schema (the way back is a restore). The step-by-step guide is
  [Upgrading a Docker install to 1.0](https://docs.displayhive.org/user/upgrade-to-1.0-rc/). New rights
  `icons.manage` and `authproviders.manage` must be granted to existing groups.

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

- **Icon libraries are no longer shipped; install them in the admin.** The icon field's nine libraries (Lucide,
  Heroicons, Phosphor, Tabler, Feather, Material Symbols, Bootstrap Icons, Iconoir, Remix Icon) were part of the
  build; now **Settings → Icon libraries** installs them (see *Added*). **After updating, install the libraries
  your content uses** (or all of them); until then icon fields show no icon. The icon values stay the same
  (`<library>/<name>`), so nothing in your content needs to change.

- **Raw HTML runs in a sandbox.** A Raw HTML field is now rendered in an isolated frame
  (`<iframe sandbox="allow-scripts" srcdoc=…>` without `allow-same-origin`) instead of straight into the screen
  page, so HTML pasted into a content element can no longer read or control the screen (its server connection,
  device key or page). Scripts and embed codes keep working inside the frame. **Because the frame is a separate
  document, it no longer inherits the design's fonts and colours: look at existing Raw HTML content and set
  font, colour and size in the HTML itself where needed.**

### Added

- **Dashboard:** what is on air right now, what ends or starts in the next seven days, what was changed last.
  Content elements record when they were last
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
- **Status indicator as icons:** Settings → Screens → *Look of the status indicator* switches the dot with
  codes to one pictogram per problem (connection lost, content missing, script error).
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
- **Installable icon libraries:** Settings → Icon libraries installs the known libraries with one click
  (downloaded from the npm registry and checked against a pinned checksum), or your own — a ZIP/TAR file or a
  download link. SVGs are sanitised on installation. The icons live in the data directory, the Docker image and
  the Nix package no longer contain them, and neither frontend needs the icon packages to build.
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
- **Unexpected errors say more than "Internal error".** An admin action that fails for an unforeseen reason now
  answers "Unexpected server error (reference 3f9a2c1b) — the details are in the server log", with the page's own
  wording in front ("Save failed — …"); the same reference is in the log line with the traceback. The same
  goes for uploads, icon library installs and the export/import/demo requests, which used to show "Server error: 500"
  or a parse error; the usual statuses (401, 403, 413, 502–504) have a plain explanation too.
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
