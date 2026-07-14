# Contributing

## Getting set up

See the root [README](https://github.com/DisplayHive/DisplayHive#getting-started)
for environment setup — `nix develop` provisions everything (Python, Node,
SQLite) and runs first-time setup automatically. Without Nix, you'll need
Python 3.13, Node.js, and SQLite installed manually.

## Running things

```bash
npm run dev              # backend + admin panel + screen client together
npm run dev:backend      # Flask + Socket.IO only, :5000
npm run dev:admin        # admin panel dev server, :5173
npm run dev:screen       # screen client dev server, :5174
```

## Tests

End-to-end tests use Playwright, in `testing/`:

```bash
npm run test:e2e         # headless
npm run test:e2e:headed  # headed browser windows
npm run test:e2e:ui      # interactive UI mode
```

Run these before opening a PR for anything that touches the admin panel,
screen client, or the Socket.IO/HTTP surface between them.

## Database changes

Schema changes go through Alembic. After changing a model in
`application/models/`, generate a migration and commit it alongside the
model change — see [Architecture → Migrations](architecture.md#migrations)
for the file naming convention already in use.

## Pull requests

- Keep PRs small and topic-focused — one change, one concern.
- If a change affects realtime behavior (a new mutation that should reach
  screens), follow the existing `send_upd_content` pattern described in
  [Real-time content push](realtime-push.md) rather than inventing a new
  push path.
- If a change affects a user-facing workflow, please update the relevant
  [User Guide](../user/index.md) page in the same PR.

## AI-assisted contributions

AI-assisted coding is welcome, but every commit is expected to be reviewed
and understood by the person submitting it — no blind commits. If you use
AI tooling, keep changes small, topic-focused, and easy to review, exactly
as you would for hand-written code. If you spot something that looks
AI-generated and unreviewed, flag it — see the README's AI Usage section.
