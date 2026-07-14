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
deleted from the **Users** page (`/users`).

!!! warning "No roles or permission tiers"
    Every admin account has identical, full access to the instance — there
    is currently no way to grant a more limited role. Only create accounts
    for people you trust with the whole system.
