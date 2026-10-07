# Users & login

## First login

On first startup, if no admin account exists yet, DisplayHive creates one
automatically:

- Username: `admin` (or the value of `ADMIN_BOOTSTRAP_USERNAME`, if set).
- Password: either a fixed value from `ADMIN_BOOTSTRAP_PASSWORD`, or a
  random password generated and printed once to the server logs.

Check your server logs after the first deploy to find this initial
password, log in at `/admin/`, and set a real password for day-to-day use.

Sessions use a JSON Web Token, valid for 12 hours; you'll be asked to log
in again once it expires. Repeated failed login attempts from the same
IP/username are rate-limited and temporarily locked out.

## Managing accounts

Additional admin accounts can be created, deactivated, reactivated, or
deleted from the **Accounts** tab on the **Users** page (`/users`).

### Forcing a password reset

When creating or editing an account, tick **Force user to reset password on
next login** (needs the `users.set_password` right). This is useful for
handing out an initial password that only the account owner should end up
knowing.

- Turning it on for an existing account logs that account out everywhere.
- On their next login, the user only sees a "Choose a New Password" screen
  and must enter their current password plus a new one (at least 8
  characters, different from the current one) before they can use anything
  else.
- Once they've set it, the flag clears and their other sessions are logged
  out. Until then the Users list shows a **Password reset pending** tag next
  to their name.
- Impersonating such an account is unaffected; the impersonating admin is
  never asked to change the password.

## Rights & groups

Access isn't all-or-nothing: what an account can see and do is controlled by
**rights** — one per checkable action (e.g. `media.upload`, `screens.page`,
`content.edit`) — granted through **groups**, managed on the **Groups** tab
of the same page.

- A **group** holds a set of granted rights and can be nested under a parent
  group (subgroups inherit everything their ancestors grant).
- A user can belong to multiple groups; the rights available to them are the
  union of everything those groups (and their ancestor groups) grant.
- An account can also get a **per-user override** for an individual right —
  either `allow` (grants it regardless of group membership) or `deny` (blocks
  it no matter what any group grants). With no override, the right is simply
  inherited from group membership.
- The built-in **Superadmin** group always grants every right — including
  ones added in future updates — and can't be edited away from that. Use it
  for accounts that should always have full access; put everyone else in
  narrower groups.

An account without `users.page`/`rights` access won't see the Users page at
all, and every other page/action across the admin panel is gated the same
way, down to individual buttons (e.g. a user might be able to view Media but
not delete it).
