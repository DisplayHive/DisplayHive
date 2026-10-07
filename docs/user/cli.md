# Command line (`flask dh`)

DisplayHive ships maintenance commands for the server. They're safe to run
next to a running instance: loading the app for a command skips the server's
own startup steps (for example resetting all devices to offline).

## Running the commands

Run them as the user DisplayHive runs as, with the same environment
(`DATABASE_URL`, `DATA_DIR`, `SECRET_KEY` …), so they open the same database
and data directory.

| Deployment | How |
|---|---|
| Docker | `docker compose exec displayhive flask dh <command>` |
| NixOS | `displayhive-<instance> <command>` (as root, e.g. `displayhive-main check-config`) |
| Manual | `flask --app app dh <command>` in the app directory, as the service user |

`flask dh --help` lists all commands; add `--help` after a command for its options.

## Commands

### `create-admin USERNAME`

Creates an admin account. It becomes a Superadmin unless you pass
`--no-superadmin`. The command prompts for the password twice. To pipe it in
from a script instead, use `--password-stdin`, which reads one line from
standard input. Never pass the password as an argument, because it would
end up in the shell history.

- `--force-change`: the user must choose a new password on first login.

```bash
flask dh create-admin alice
```

### `reset-password USERNAME`

Sets a new password, turns password login on for the account and logs it out
everywhere. This is the way back in when you're locked out, e.g. every SSO
provider is down, or the only Superadmin forgot their password.

- `--activate`: also reactivate a deactivated account.
- `--force-change`: the user must choose another password on next login.
- `--password-stdin`: read the password from standard input.

```bash
flask dh reset-password admin --activate
```

### `check-config`

Checks the setup and prints `OK` / `INFO` / `WARN` / `FAIL` lines. It covers:

- **Settings:** `SECRET_KEY`, CORS, the debugger and `TRUSTED_PROXY_COUNT`.
- **Data directory:** whether every part exists, can be written to and has
  the right permissions, and whether any data is still in an old location.
- **Database:** whether it can be reached and its schema is up to date, plus
  the permissions of the SQLite file.
- **Accounts:** whether there is an active admin, and a Superadmin who can
  still log in with a password.
- **Admin frontend:** whether it has been built.

It exits with status 1 if anything is `FAIL`, so it fits health checks and
deploy scripts. `--online` also contacts each enabled SSO provider.

### `rerender`

Re-renders the preview and the FHD/4K/8K renditions of every media file from
the original upload. Originals are never changed.

- `--missing-only`: only create what's missing. This is what **Sync previews**
  on the Media page does.

### `rerender-content`

Re-renders the stored HTML of all content, for example after an update that
changed how a field type renders. Limit it with `--contenttype ID`
(repeatable). Running screens pick up the new HTML with their next content
update, because the command can't reach them itself.
