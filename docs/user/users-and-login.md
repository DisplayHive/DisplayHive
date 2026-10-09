# Users & login

## First login

On first startup, if no admin account exists yet, DisplayHive creates one
automatically:

- Username: `admin` (or the value of `ADMIN_BOOTSTRAP_USERNAME`, if set).
- Password: either a fixed value from `ADMIN_BOOTSTRAP_PASSWORD`, or a
  random password generated and printed once to the server logs.

Check your server logs after the first deploy to find this initial
password (look for "created a bootstrap account") and log in at `/admin/`.
**You are asked to choose a new password right away** — the generated one has
been written to the log, and one from `ADMIN_BOOTSTRAP_PASSWORD` sits in an
environment or compose file, so neither should stay. If you log in with a pinned
password from automation, set `ADMIN_BOOTSTRAP_MUST_CHANGE=off` (it has no
effect on a generated password).
Alternatively, create the first account yourself with
[`flask dh create-admin`](cli.md#create-admin-username). If you lose
access, [`flask dh reset-password`](cli.md#reset-password-username) gets
you back in.

## Sessions

A login lasts 12 hours; you'll be asked to log in again once it has expired.

In the browser the session lives in a **cookie** the page cannot read
(`HttpOnly`), that is only sent on requests started from DisplayHive's own
pages (`SameSite=Strict`) and, over https, only over https (`Secure`, name
`__Host-dh_session`). So a script injected into a page cannot steal the login,
and another website cannot use it. Requests that change something also have to
come from DisplayHive's own page (the server checks the `Origin` and a header the
page adds), and the admin WebSocket accepts the cookie only from DisplayHive's own
origin.

- **Logging out** removes the cookie from the browser. The signed session itself
  stays valid until it expires or is revoked: changing a password, deactivating
  or deleting the account ends all of that account's sessions at once.
- **Impersonation** ("log in as") keeps your own session in a second cookie, so
  "stop impersonating" brings you back without logging in again. You cannot
  impersonate while impersonating.
- **After an update** from a version that kept the login in the browser's local
  storage, everybody logs in once more.
- **Screens** do not use cookies at all (they identify themselves with their
  device key), so kiosk browsers that refuse cookies work as before.
- **Scripts and tools** can use the same API with `Authorization: Bearer <token>`:
  `POST /admin/api/auth/login` (without `"session": "cookie"`) returns the token.
  A Bearer request needs none of the cookie protections, because nothing sends it
  by itself.

Behind a **reverse proxy**, forward the `Host` header unchanged (nginx:
`proxy_set_header Host $host;`) and set `PUBLIC_URL` to the public address;
`TRUSTED_PROXY_COUNT` lets the app see that the visitor used https, which makes
the cookie `Secure`. If the admin panel loads but its WebSocket is refused with
"Admin socket refused: Origin … is not this site", one of these is missing — the
log line says which origin it saw. Accessing the panel at an address other than
the `PUBLIC_URL` (an IP address, say) also needs that address in
`CORS_ALLOWED_ORIGINS`; a `*` there does *not* count, as a cookie must never be
accepted from "any origin".

Failed logins are rate-limited in two ways, both counted over 15 minutes:

- **5 failures for the same username from the same IP** lock that
  combination out.
- **20 failures from the same IP, across any usernames,** lock that whole IP
  out (adjustable via `LOGIN_RATE_LIMIT_PER_IP`). This stops one client from
  trying a common password against many accounts.

A lockout starts at 1 minute and doubles with every further failed attempt,
up to 1 hour. It is forgiven after 15 quiet minutes following the last
lockout. A successful login resets only the username counter, not the IP
counter. Wrong current passwords on the forced password-change screen count
the same way.

## Managing accounts

Additional admin accounts can be created, deactivated, reactivated, or
deleted from the **Accounts** tab on the **Users** page (`/users`).

Admins can also log in through an OpenID Connect provider (single sign-on).
The first SSO login creates an account without groups or a password. See
[Single sign-on](sso.md) for setup and for linking SSO logins to existing
accounts. Each account's **Allow login with username and password** setting
controls whether it can still use a password. At least one active
Superadmin always keeps password login as a fallback.

### Forcing a password reset

When creating or editing an account that has password login, tick
**Force user to reset password on next login** (needs the `users.set_password` right). This is useful for
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
- Logging in via SSO is unaffected too: the flag only concerns the password.

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
