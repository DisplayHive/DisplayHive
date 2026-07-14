# Developer Guide

This guide covers DisplayHive's internals: how the backend and both
frontends fit together, how content reaches a screen in real time, and how
to contribute a change.

For environment setup and day-to-day commands (`nix develop`, `npm run dev`,
tests), see the root [README](https://github.com/DisplayHive/DisplayHive#getting-started)
and [`startup.md`](https://github.com/DisplayHive/DisplayHive/blob/main/startup.md) —
this guide assumes a working dev environment and focuses on how the code is
organized.

- **[Architecture](architecture.md)** — components, models, blueprints, and
  frontend structure.
- **[Real-time content push](realtime-push.md)** — how an edit in the admin
  panel ends up rendered on a screen.
- **[Contributing](contributing.md)** — conventions and expectations for
  changes, including AI-assisted ones.
