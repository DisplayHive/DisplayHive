# Backup & restore

DisplayHive keeps two kinds of data: the **database** (content, screens,
users, rights, devices and their keys, settings, SSO providers) and the
**uploaded media** in the data directory. This page explains what is saved
automatically, how to update without risking either, and how to get back.

!!! warning "Copy the backups off this machine"
    Backups are written to `DATA_DIR/backups` (Docker: the `backups` volume).
    That is the same disk as the data, so it protects against mistakes and bad
    updates, **not** against a failed disk or a lost server. Copy the directory
    to another machine regularly, or mount a directory from another disk there
    (see [Where the backups go](#where-the-backups-go)).

## What is saved automatically

| Backup | When | Kept |
|---|---|---|
| **Database, scheduled** | every `BACKUP_INTERVAL_HOURS` (default 24; the first one runs shortly after the app has started) | the newest `BACKUP_KEEP` (default 7) |
| **Database, before a migration** | before every update that changes the database schema | the backups of the last `MIGRATION_BACKUPS_KEEP` upgrades (default 3) |
| **Database, before a restore** | when you run `restore` | the newest 5 |
| **Media** (optional) | every `BACKUP_MEDIA_INTERVAL_DAYS` days (default 0 = off), or `backup --media` | the newest `BACKUP_MEDIA_KEEP` (default 2) |

Previews and renditions are regenerated (**Sync previews** on the Media page)
and not included. Set `BACKUP_INTERVAL_HOURS=0` to turn scheduled database
backups off. The backup before a migration is separate and stays on
(`MIGRATION_BACKUP=off` skips it — only if you have your own).

Backups contain password hashes and secrets: the directory is readable by the
app's user only (`0700`, files `0400`).

!!! note "Not in a database backup"
    Keep your `.env` / `SECRET_KEY` and the NixOS configuration safe separately.
    Without the `SECRET_KEY` of the instance, existing login sessions are invalid
    (everyone logs in again).

## Updating safely

When the app (or the compose `migrate` service) starts and the database needs
migrating, it does this:

1. **Up to date already:** nothing happens.
2. **A new, empty database:** the schema is created, no backup needed.
3. **Otherwise:** it writes a backup first
   (`premigrate-<time>-from-<old>-to-<new>-original.dump`), and only if that
   worked it migrates. If there is not enough free disk space, nothing is
   migrated.
4. **If the migration fails** the app does **not** start and nothing restarts in
   a loop: the `migrate` service exits with status 78 and prints the backup's
   name; with NixOS the unit stays failed after three tries
   (`journalctl -u displayhive-<name>`). PostgreSQL applies all migrations in one
   transaction, so a failed attempt normally leaves the database as it was.

The first backup for an upgrade is its **original** and is never replaced: a
repeated attempt is saved as `…-retry1`, `…-retry2`, and if the database has
moved on in between (a half-applied migration) as `…-partial`. Old backups are
only deleted after a migration has *succeeded*, and then only those of
upgrades older than the newest three.

### If an update fails

1. Read the log: `docker compose logs migrate` (NixOS:
   `journalctl -u displayhive-<name>`). It names the backup.
2. Usually it is enough to **go back to the previous version** of DisplayHive
   (the old image tag, or the old NixOS configuration) — the database is still
   at the old schema. Report the error.
3. If the database really is damaged, **stop the app** and restore the
   *original* backup (below), then start the previous version.

## Commands

Run them as the user the server runs as, with the same environment (see
[Command line](cli.md)).

```bash
flask dh backup            # a database backup now (add --media for the uploads)
flask dh backups           # list the backups, newest first
flask dh restore FILE      # put one back (a name from the list, or a path)
```

With Docker, prefix `docker compose exec displayhive` (for `restore`, stop the
app first and use `docker compose run --rm --no-deps --entrypoint flask migrate dh restore FILE`).
With NixOS use the `displayhive-<name>` command.

### Restoring

1. **Stop DisplayHive.** It must not write while the database is replaced.
2. `flask dh restore premigrate-…-original.dump` (asks for confirmation;
   `--yes` skips it). The whole database is replaced **in one transaction**: if
   anything goes wrong, the database stays exactly as it was. Before it starts,
   the current state is saved as `prerestore-…`, so a restore can itself be undone.
3. **Start DisplayHive.** It migrates the restored database to the current
   version.

Restoring only replaces the database. **Media** come back from a media archive:
stop the app, then `tar -xf media-….tar -C DATA_DIR` (the archive contains a
`media/` folder).

A backup can be restored on the same PostgreSQL **major version** it was made
from. The tools therefore have to match the server: the Docker image contains
the PostgreSQL 16 and 17 client tools and picks the server's; the NixOS module
uses the server's own package. If you use another version, `flask dh check-config`
and the backup itself say so, instead of writing a backup that cannot be restored.

### Try it before you need it

Once, on a copy: restore a recent backup into a scratch instance and check that
it starts and that the content is there. A backup nobody has restored is a hope.

## Where the backups go

- **Docker:** the named volume `backups`. To keep them on another disk, replace
  that volume in `compose.yml` by a bind mount, e.g. `- /mnt/otherdisk/displayhive-backups:/data/backups`
  (the directory must be writable for user id `10001`, the app's user).
- **NixOS:** `<dataDirectory>/backups`. Use a bind mount, a symlink or a backup
  tool that reads this directory.
- **Offsite:** any tool that copies a directory works, e.g. `restic` or
  `rclone sync` on a timer. The files are complete and never modified once
  written, so they can be copied while DisplayHive runs.

## Without DisplayHive's backups

A plain `pg_dump` works too (use the client tools of the **server's** major
version):

```bash
pg_dump --format=custom --no-owner --file displayhive.dump "$DATABASE_URL"
```

and the volumes `media`, `media_previews`, `media_renditions` (or `DATA_DIR`)
can be copied with your usual file backup. Do not copy a running SQLite
database file (development only); use `flask dh backup`.

## Settings

| Variable | Default | |
|---|---|---|
| `BACKUP_INTERVAL_HOURS` | `24` | Hours between scheduled database backups, `0` = off |
| `BACKUP_KEEP` | `7` | Scheduled database backups to keep |
| `BACKUP_MEDIA_INTERVAL_DAYS` | `0` | Days between media archives, `0` = off |
| `BACKUP_MEDIA_KEEP` | `2` | Media archives to keep |
| `MIGRATION_BACKUP` | `on` | `off`: migrate without a backup first |
| `MIGRATION_BACKUPS_KEEP` | `3` | Upgrades whose backups are kept |

NixOS: `backup.intervalHours`, `backup.keep`, `backup.beforeMigration`.
`flask dh check-config` shows whether the tools are there and how old the newest
backup is.
