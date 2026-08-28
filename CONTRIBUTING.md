# Contributing to DisplayHive

Thanks for wanting to contribute — this file covers the short version; the
full guide (environment setup, running the dev servers, tests, database
migrations, PR conventions) lives at
[docs/developer/contributing.md](docs/developer/contributing.md) and on
[docs.displayhive.org](https://docs.displayhive.org/developer/contributing/).

## Quick start

```bash
git clone https://github.com/DisplayHive/DisplayHive.git
cd DisplayHive
nix develop   # or: nix-shell — provisions Python, Node, SQLite and runs first-time setup
npm run dev   # backend + admin panel + screen client together
```

Without Nix, you'll need Python 3.13, Node.js, and SQLite installed manually.
See the [README](README.md#getting-started) for details.

## Before opening a PR

- Keep PRs small and topic-focused — one change, one concern.
- Run the Playwright end-to-end tests (`npm run test:e2e`) for anything that
  touches the admin panel, screen client, or the Socket.IO/HTTP surface
  between them.
- If a change affects a model in `application/models/`, include the Alembic
  migration in the same PR.
- If a change affects a user-facing workflow, update the relevant
  [User Guide](docs/user/index.md) page in the same PR.

## AI-assisted contributions

At the beginning of development, DisplayHive started without any AI usage.
As the code evolved, more and more AI-generated code was introduced to the
codebase. AI-assisted coding is welcome, but every commit is expected to be
reviewed and understood by the person submitting it — no blind commits. Keep
AI-assisted changes small, topic-focused, and easy to review, exactly as you
would for hand-written code. In cases where things were AI-generated, there
may be things that slipped through review — if you spot something that
looks AI-generated and unreviewed, flag it.

## Reporting bugs / requesting features

Open an issue on [GitHub](https://github.com/DisplayHive/DisplayHive/issues).
For questions or discussion, see [Contact](docs/contact.md) — Mastodon,
Telegram, and more.

## Reporting security vulnerabilities

Please don't open a public issue — see [SECURITY.md](SECURITY.md) instead.

