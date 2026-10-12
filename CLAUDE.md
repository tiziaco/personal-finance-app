# Personal Finance — Monorepo Guide

Personal Finance is a B2C app for tracking and understanding one person's money: a Next.js
app (`web-app/apps/web`) backed by a FastAPI server. The user is the tenant — data is keyed
by `user_id`; there are no organisations and no roles.

What the product does is in [`docs/product/`](docs/product/), what it stores in
[`docs/data-model/`](docs/data-model/). **Before brainstorming a
feature, read its feature doc and its data-model doc** — a spec is written against both.

---

See `server/CLAUDE.md` and `web-app/CLAUDE.md` for service-specific conventions, and
[`docs/README.md`](docs/README.md) for the index of everything else — setup, architecture,
guides, and [`docs/ROADMAP.md`](docs/ROADMAP.md), the one file that records progress.

## Specs and plans

Superpowers saves specs to `.superpowers/specs/` and plans to `.superpowers/plans/`,
not `docs/superpowers/`. Both are committed while their change is in flight. In the PR
that completes it, the spec's lasting facts move into `docs/` — architecture, a
data-model decision, a `TODO.md` entry — and both files are deleted; git history keeps
them.

---

## Running the Stack

There are two ways to run this app, and **they are mutually exclusive**:

- **Docker path** — everything in Compose (`make docker-run`). Includes ngrok.
- **Native path** — app processes on the host, Postgres still in Docker
  (VS Code's `Dev: *` tasks). Needs its own host-side tunnel.

They collide on two resources: host ports **3000 and 8100** (the main checkout's defaults), which the
compose services publish; and the single static **`NGROK_DOMAIN`**, claimed by
both the `ngrok` compose service and `make dev-tunnel`. Stop one path before
starting the other — `make dev-preflight` checks the ports and fails with a
pointer rather than letting the servers die on a bind error.

That exclusion is per checkout. A linked git worktree runs a second,
independent stack on its own ports — see **Parallel worktrees** below.

The commands for each path — first-run env files, the VS Code `Dev: *` tasks, the
ngrok tunnel, and where migrations run — are in the `/run-stack` skill. `make help`
lists every root target.

### Parallel worktrees

Each linked git worktree can run its own dev stack on its own ports. Slots,
setup and teardown are in the `/worktrees` skill; these hold regardless:

- **Create with `make worktree-new`, never `claude --worktree`**, and **tear down
  with `make worktree-clean`, never `make clean` or `rebuild`** — those prune the
  build cache every checkout shares.
- **Never hand-merge `server/openapi.json` or the generated client** — take either
  side, run `make gen-contract`, and commit what it produces.

---

## Deploying

`docker-compose.prod.yml` serves both staging and production (`APP_ENV` picks).
Before changing it or deploying, use the `/deploy-check` skill: `make deploy-check`
proves less than it looks like it does.

---

## Environment Setup

Each service has its own env file; `/run-stack` has the copy commands for a fresh clone.

Required secrets: Clerk API keys, database credentials, Langfuse key. The OpenAI key is
optional — the server starts without it; only an LLM call needs it.

The `server/.env.<ENV>` file is selected by the `APP_ENV` variable (default when unset: `development`). A value that is set but unrecognised — a typo, a trailing space — fails at startup rather than running as development.

Install the repo's git hooks once per clone:

```bash
git config core.hooksPath .githooks
```

Two hooks live there. `pre-commit` keeps the API contract in sync (see **API
Contract** below). `pre-push` runs `make check-server` and `make check-web`
for whichever side changed since the upstream branch: ruff and Prettier in
check mode, plus ESLint — and, for `web-app/`, `make test-web` (Vitest).
CI repeats the server half (`.github/workflows/module-boundaries.yml`: import
contracts, ruff, the module and ownership tests); nothing in CI runs the web checks,
so for `web-app/` the hook is the only gate. `make check` runs both by hand and
`git push --no-verify` skips the hook once.
`.vscode/settings.json` formats on save with the same tools, so the hook
rarely has anything to say.

---

## API Contract

`server/openapi.json` and `web-app/packages/api-client/src/generated/` are
generated from `server/app/` and **committed**. They are a published interface,
not a build artifact: the generated tree is what the app compiles against.

```bash
make gen-contract     # re-export the spec and regenerate the client
make check-contract   # regenerate, then fail if anything moved (what CI runs)
```

Four checkpoints, each catching what the last one lets through:

| When | What | On drift |
|---|---|---|
| You change a route | `make gen-contract`, or the **Contract: Generate** VS Code task | regenerates |
| You commit | `.githooks/pre-commit`, if the commit touches `server/app/` | regenerates, then blocks |
| You build an image | `make docker-build` / `docker-build-web` gate on `check-contract` | fails the build |
| You push | `.github/workflows/api-contract.yml` | fails CI |

Nothing runs on save, and nothing is wired into the `Dev:` task chain.
Exporting the spec imports `app.main`, so a half-finished refactor would stop
the dev servers from starting — and drift is the normal state while a route is
being written. The gates sit where an inconsistent artifact would actually
escape: a commit, an image, a push.

`git commit --no-verify` bypasses the hook for a single commit; CI still holds.
