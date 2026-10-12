# Security Policy

## Supported Versions

DisplayHive doesn't maintain long-term-support branches — there's one
moving target, `main`, and that's what gets security fixes. If you're
running an older commit or tag, please update to the latest `main` (or the
latest release, if you're using tagged Docker images) before reporting an
issue, to make sure it's still present.

## Reporting a Vulnerability

**Please don't open a public GitHub issue for a security vulnerability** —
that discloses it to everyone, including anyone who might exploit it,
before a fix is available.

Instead, report it privately using one of these:

1. **GitHub's private vulnerability reporting** — use the *Report a vulnerability* button under the
   [Security tab](https://github.com/DisplayHive/DisplayHive/security).
   This is the preferred channel.
2. **Direct message on Mastodon** — [@DisplayHive](https://chaos.social/@DisplayHive).
3. **Email** — `security@displayhive.org`.

Please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce it (a minimal repro is ideal).
- The commit/version you tested against.

This is a small open-source project maintained on a best-effort basis, so we
can't commit to a fixed response SLA — but we'll acknowledge reports as
promptly as we can, and credit reporters (unless you'd prefer to stay
anonymous) once a fix ships.

## Scope

DisplayHive is self-hosted: the backend (Flask + Socket.IO) is typically the
only network-reachable surface, sitting behind a reverse proxy you control.
Issues in DisplayHive's own code (authentication, rights/permissions,
Socket.IO handlers, the admin panel, the screen client, import/export,
migrations) are in scope. Misconfiguration of your own deployment (e.g.
running with `FLASK_DEBUG` enabled on a public host, a weak `SECRET_KEY`, or
skipping the reverse proxy's TLS termination) is not a DisplayHive
vulnerability, but we're happy to hear about it if the docs should warn
about it more clearly.
