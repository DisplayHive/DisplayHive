# Upgrading a Docker install to 1.0 (release candidate)

This page takes a Docker Compose installation that runs the current
`:latest` image (0.x) to the 1.0 release candidate, from the first backup to
the settings you may want to add afterwards. The release candidate is its own
image tag, `ghcr.io/displayhive/displayhive:1.0.0-rc1`; `:latest` stays
on the old version until 1.0 is released, so nothing changes by itself.

!!! warning "Take the backup first, and by hand"
    The old image has no `flask dh` commands and makes no backups. The
    commands of [Backup & restore](backup.md) only exist **after** the
    upgrade. The new image takes a database backup before it migrates, but
    the migrations change the schema: the way back is a restore, not a
    downgrade.

NixOS installs are different (the module no longer builds on the server);
see the *Breaking changes* of the [changelog](https://github.com/DisplayHive/DisplayHive/blob/release/1.0/CHANGELOG.md).

## 1. Back up by hand

Run everything in the directory that holds your `compose.yml`.

**1. Note which volumes you have.** Their names start with the Compose project
name (by default the directory name):

```bash
docker compose ps
docker volume ls | grep -E 'media|pgdata'
```

You should see `…_media`, `…_media_previews`, `…_media_renditions` and
`…_pgdata`. Only the database and `…_media` (the uploaded originals) cannot be
recreated; previews and renditions are rebuilt from the originals.

**2. Dump the database.** `-Fc` writes the compact format `pg_restore`
reads; `-T` is needed because the output goes into a file:

```bash
docker compose exec -T db pg_dump -U displayhive -Fc displayhive > displayhive-before-1.0.dump
```

**3. Archive the media volume** (replace `myproject_media` with your volume
name; repeat for `…_media_previews` and `…_media_renditions` if you want them
too):

```bash
docker run --rm -v myproject_media:/src:ro -v "$PWD":/out alpine \
    tar czf /out/media-before-1.0.tgz -C /src .
```

**4. Keep your configuration.** Copy `.env` and `compose.yml` next to the
backups.

**5. Check that the files are readable**, then copy all of it to another
machine. A backup on the same disk does not survive a lost disk.

```bash
docker compose exec -T db pg_restore --list < displayhive-before-1.0.dump | head
tar tzf media-before-1.0.tgz | head
```

**6. Pin the old image**, so that you can come back to exactly this version
even after `latest` has moved:

```bash
docker image inspect --format '{{index .RepoDigests 0}}' ghcr.io/displayhive/displayhive:latest
```

Write the printed `ghcr.io/displayhive/displayhive@sha256:…` down.

## 2. Migrate to the release candidate

**1. Get the new `compose.yml` and `.env.example`** of the release candidate
and merge your own changes (ports, bind mounts, reverse proxy) into them:

```bash
curl -fLO https://raw.githubusercontent.com/DisplayHive/DisplayHive/v1.0.0-rc1/compose.yml
curl -fLO https://raw.githubusercontent.com/DisplayHive/DisplayHive/v1.0.0-rc1/.env.example
```

Do not overwrite your own copies before you have compared them. The new file
differs in these ways:

- a one-shot `migrate` service runs first and the app waits for it,
- the media volumes are mounted at `/data/media*` (not `/app/static/media*`)
  and there is a `backups` volume,
- more settings are passed through from `.env` (see part 3).

The volumes keep their names, so the data is found without copying.

**2. Use the release candidate image.** The file says `:latest`, which is
still the old version. Change the `image:` line of **both** the `migrate` and
the `displayhive` service:

```yaml
    image: ghcr.io/displayhive/displayhive:1.0.0-rc1
```

**3. Start it:**

```bash
docker compose pull
docker compose up -d
```

What happens: the database container keeps running, the `migrate` service
takes a database backup into the `backups` volume
(`premigrate-…-original.dump`), brings the schema up to date (five new
migrations) and exits. If that fails, the app is **not** started and nothing
restarts in a loop.

**4. Check:**

```bash
docker compose logs migrate              # ends without an error
docker compose logs -f displayhive       # the app is up
docker compose exec displayhive flask dh check-config
```

Open `/admin/`, log in with your existing account (passwords stay as they
are) and reload the browser tab once so that it loads the new admin. Screens
reload the new screen page by themselves a few seconds after the update.

!!! note "You may keep your old volume mounts for now"
    If you keep a `compose.yml` that mounts the media at `/app/static/media*`,
    the new image still finds the files and keeps working, but admins see a
    notice in Settings. The only change is the mount path
    (`media:/data/media`, `media_previews:/data/media_previews`,
    `media_renditions:/data/media_renditions`); see
    [Installation](installation.md#moving-data-to-data_dir).

### Going back

If something is wrong and you want the old version again:

```bash
docker compose stop displayhive
docker compose exec -T db pg_restore -U displayhive -d displayhive --clean --if-exists \
    < displayhive-before-1.0.dump
```

Then put your old `compose.yml` (and the pinned
`ghcr.io/displayhive/displayhive@sha256:…` as the image) back and run
`docker compose up -d`. Never use `docker compose down -v`: `-v` deletes the
volumes, including the database.

## 3. Add what is missing afterwards

The migration changes the database, but a few things are not set for you.
`flask dh check-config` lists what is left; this is the checklist.

**Install icon libraries.** The image no longer contains any icons. Under
**Settings → Icon libraries**, install the libraries your content uses (or all
of them). Until you do, icon fields show no icon. The stored icon values do
not change, so no content has to be edited.

**Give your groups the two new rights.** Two rights are new:
`icons.manage` (install and remove icon libraries) and `authproviders.manage`
(single sign-on providers). Existing groups do not get them; Superadmins
have every right anyway. Grant them on the **Users & Rights** page to the
groups that need them.

**Add settings to `.env`** (all optional, with defaults):

| Setting | When you need it |
|---|---|
| `PUBLIC_URL` | Set it to the address people use (`https://signage.example.com`). CORS and the single sign-on redirect address are derived from it. Without it and without `CORS_ALLOWED_ORIGINS`, Compose allows any origin (`*`), and `check-config` warns about that. |
| `TRUSTED_PROXY_COUNT` | `1` when a reverse proxy such as nginx is in front, so the login rate limiter sees the real client address. Leave `0` if the app is reached directly. |
| `ADMIN_BOOTSTRAP_*` | Only used on an empty database; nothing to do for an existing install. |
| `BACKUP_INTERVAL_HOURS`, `BACKUP_KEEP`, `MIGRATION_BACKUP` | Defaults: a database backup every 24 hours, the newest 7 kept, and one before every migration. Copy the `backups` volume to another machine, or mount a directory from another disk there (see [Backup & restore](backup.md)). |
| `LOG_FORMAT` | `json` for log collectors. |

**Review the new options in Settings.** Defaults are in place; look at them
once:

- **Settings → Screens:** the status dot is on, the daily reload is off, and
  the screen log keeps 72 hours / 250,000 lines.
- **Settings → Time:** check the time zone; it also applies to the daily
  reload.
- **Settings → Content Editor:** preview sizes of the content page and list.
- **Settings → Dashboard:** hide switches for the community links, tours and
  Demo Mode.

**Optional extras.** [Single sign-on](sso.md) with an OpenID Connect provider,
[Telegram alerting](alerting.md) (unchanged), and offline start for screens:
that needs the screen page to be opened over `https` or on `localhost`.
