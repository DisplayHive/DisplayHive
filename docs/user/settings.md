# Settings

The **Settings** page (`/settings`) covers instance-wide options that don't belong to a more specific
page. Each card saves on its own.

## Admin settings (Settings page)

These are stored in the database, belong to the instance, and are part of an [export](import-export.md).

**Dashboard**

- **Welcome headline / welcome text** — shown on the Dashboard's welcome card.
- **Hide community links**, **Hide helping hand**, **Hide powered-by branding** — hide those sections
  (the powered-by badge on screens included).
- **Hide demo mode** — hides the Demo Mode page and the hint on the Dashboard.
- **Hide user tours / Hide admin tours** — hide a category of the guided tours (the **Tour** entry in the header).

**Content editor**

- **Preview size** on the content edit page and in the content list's expanded rows.

**Time**

- **Timezone** — used for schedules (start/end of content) and the daily reload of screens.

**Screens**

- **Status dot** on screens: show or hide it (see [Screens](screens-devices-groups.md#what-a-screen-does-on-its-own)).
- **Reload screens once a day** at a given time.
- **Screen log**: how long lines are kept (hours, 1 to 8760) and the most lines kept (1,000 to 5 million);
  whichever limit is reached first deletes the oldest lines.

**Icon libraries**

DisplayHive ships no icons; the icon field offers the libraries you install here (needs the right
*Install and remove icon libraries*).

- **Known libraries** — Lucide, Heroicons, Phosphor, Tabler, Feather, Material Symbols, Bootstrap Icons,
  Iconoir and Remix Icon. **Install** downloads one from the npm registry (a few megabytes; Material Symbols
  and Tabler are the largest) and checks it against the checksum DisplayHive expects; **Install all** does
  the whole list; **Reinstall** replaces a library, **Remove** deletes it.
- **Your own library** — a ZIP (or `.tar.gz`) file of SVG icons, uploaded or downloaded from a link, with an
  id, a name and a license. The id becomes part of the icon value (`my-icons/home`). Only plain drawings are
  kept; scripts, event handlers and references to other files are removed. A download link into a private
  network needs the setting under *Security*.
- **No internet on the server?** Upload a ZIP instead; the download buttons need access to
  `registry.npmjs.org`.
- Icons are stored in the data directory (`DATA_DIR/icons`), not in the database: they are not part of an
  [export](import-export.md) or of the backups. Content stores only `<library>/<icon>`, so after a restore or
  on a new instance, install the libraries again and the icons are back. Content that uses an icon of a
  library that is not installed shows no icon.

**Security and sign-in** (cards further down)

- **Login providers** — single sign-on, see [Single sign-on](sso.md).
- **Outgoing requests to private networks** — blocked by default; only a Superadmin can allow them. An
  environment variable can force it on (below).

The **default design** is chosen on the Designs page, not here. Telegram and Pretalx settings live on their
own pages — see [Alerting](alerting.md) and [Pretalx](pretalx.md).

## Environment variables (server configuration)

Everything that has to be known before the database can be reached, or that must not be changed from a
browser, is an environment variable (Docker: `.env`/`compose.yml`; NixOS: the instance's options). The
full list, with defaults, is in [Installation → Configuration](installation.md#configuration). The
important ones:

| What | Variable | Why it is not a setting |
|---|---|---|
| The database, the secret key, where data lives | `DATABASE_URL`, `SECRET_KEY`(`_FILE`), `DATA_DIR` | Needed before anything can be read from the database; secrets must not be editable (or exported) from the panel. |
| First administrator | `ADMIN_BOOTSTRAP_USERNAME`/`_PASSWORD`/`_MUST_CHANGE` | Used once, on the first start. |
| Public address, proxies, CORS | `PUBLIC_URL`, `TRUSTED_PROXY_COUNT`, `CORS_ALLOWED_ORIGINS` | They decide who may reach the server and how it sees clients; the panel cannot fix a wrong value. |
| Security policy | `ADMIN_CSP`, `SCREEN_CSP`, `OUTBOUND_ALLOW_PRIVATE` | Deployment decisions, deliberately not changeable by a panel user. |
| Process and logging | `GUNICORN_THREADS`, `DB_POOL_SIZE`, `LOG_LEVEL`, `LOG_FORMAT` | Fixed at start. |
| Backups | `BACKUP_INTERVAL_HOURS`, `BACKUP_KEEP`, `MIGRATION_BACKUP` | Run by the server on a schedule, see [Backup & restore](backup.md). |

**Rule of thumb:** what an administrator may want to change while the system runs, and what is only a
preference of this instance, is a setting on the Settings page. What the deployment needs, and what could
lock everyone out or open a hole if set wrongly from the browser, is an environment variable.
