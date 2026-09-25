# Template App — Monorepo Guide

Template for a multi-tenant B2B platform with two portals — one internal, one for
external partners — backed by a single FastAPI server. Multi-tenancy is Clerk
Organizations; the org id arrives on the JWT and scopes queries.

The shipped example domain is **supplier document compliance**. It is illustrative, not
load-bearing: the `Supplier` model, the `supplier-portal/` app, the role names and the
Italian UI labels are all meant to be renamed or replaced for your domain.

**Two user types:**
- **Internal project managers** — manage projects, suppliers, orders, document compliance, and expiry tracking
- **External suppliers** — upload required documents, track submission status, receive notifications

---

## Repo Structure

```
app/
├── server/               # FastAPI backend (Python 3.13, uv)
├── web-app/              # Next.js monorepo (pnpm workspaces)
│   ├── apps/
│   │   ├── internal-portal/   # Dashboard for project managers (port 3000)
│   │   └── supplier-portal/   # External supplier portal (port 3002)
│   └── packages/
│       ├── api-client/        # @app/api-client — generated API client from the OpenAPI spec
│       ├── auth/              # @app/auth — Role enum, useAppAuth(), getUserRole()
│       ├── core/              # @app/core — cn(), NavItem, copy — no renderer
│       ├── ui/                # @app/ui — shadcn/Base UI primitives, WEB ONLY
│       └── components/        # @app/components — composed chrome, built on ui
├── infra/                # Infrastructure config
│   ├── prometheus/            # Prometheus scrape config
│   └── grafana/               # Grafana datasources and dashboards
├── docker-compose.dev.yml     # Development stack
└── docker-compose.prod.yml
```

See `server/CLAUDE.md` and `web-app/CLAUDE.md` for service-specific conventions.

---

## Running the Stack

There are two ways to run this app, and **they are mutually exclusive**:

- **Docker path** — everything in Compose (`make docker-run`). Includes ngrok.
- **Native path** — app processes on the host, Postgres still in Docker
  (VS Code's `Dev: *` tasks). Needs its own host-side tunnel.

They collide on two resources: host ports **3000, 3002 and 8100** (the main checkout's defaults), which the
compose services publish; and the single static **`NGROK_DOMAIN`**, claimed by
both the `ngrok` compose service and `make dev-tunnel`. Stop one path before
starting the other — `make dev-preflight` checks the ports and fails with a
pointer rather than letting the servers die on a bind error.

### Native dev

```bash
make dev-preflight      # verify this checkout's API and portal ports are free
make dev-tunnel         # ngrok: https://$NGROK_DOMAIN -> localhost:$API_HOST_PORT
```

`NGROK_DOMAIN` and `NGROK_AUTHTOKEN` come from the root `.env` (loaded by the
Makefile via `-include`), not from your shell — so run the target rather than
`ngrok` directly. It passes `--authtoken` explicitly, for the reason in
[`docs/setup/clerk-webhooks.md`](docs/setup/clerk-webhooks.md).

In VS Code, `Dev: All` (⇧⌘B) chains preflight → start db → migrate → API server
and both portals. `Dev: All + Tunnel` adds the tunnel, for Clerk webhook work.
Migrations are **not** applied automatically on this path the way the Docker
`migrate` service does it — `Dev: Migrate` runs `make migrate ENV=development`
on the host.

### Docker

The root `Makefile` manages the full Docker Compose stack.

```bash
# Start
make docker-run         # full stack: portals, server, db, prometheus, grafana, cadvisor, ngrok (dev)
make docker-run-core    # core only: portals, server, db
make docker-run-db      # database only (ENV=development|staging|production)

# Build
make docker-build       # build all services
make docker-build-web   # build web-app (internal-portal + supplier-portal) only
make docker-build-api   # build server only

# Migrations (applied automatically on `docker-run*`; these are for on-demand use)
make docker-migrate         # apply Alembic migrations in a one-shot container
make docker-migrate-status  # print the database's current revision

# Logs
make docker-logs        # follow all services
make docker-logs-core   # follow core services only

# Stop / clean
make docker-stop        # stop all services
make clean              # stop + remove containers, volumes, networks
make rebuild            # clean + full stack
make rebuild-core       # clean + core stack
```

### Service URLs (Docker, main checkout defaults)

| Service           | URL                        |
|-------------------|----------------------------|
| Internal Portal   | http://localhost:3000      |
| Supplier Portal   | http://localhost:3002      |
| API server        | http://localhost:8100      |
| Swagger docs      | http://localhost:8100/docs |
| Prometheus        | http://localhost:9090      |
| Grafana           | http://localhost:3001      |
| cAdvisor          | http://localhost:8080      |
| PostgreSQL        | localhost:5434             |
| ngrok (dev only)  | n/a                        |

`ngrok` (dev only) tunnels `server:8000` for Clerk webhook delivery. Compose
publishes no host port for it, so its inspection dashboard has no fixed URL.

### Parallel worktrees

Each linked git worktree can run its own dev stack — its own database (so its
own migrations), containers and ports — so two branches can be built at once.

```bash
make worktree-new NAME=feed             # .claude/worktrees/feed on feat/feed, initialised
make worktree-new NAME=x BRANCH=fix/x   # another branch; an existing one is checked out
cd .claude/worktrees/feed && claude
make worktree-clean                     # inside it, before `git worktree remove`
```

| Slot | Internal | Supplier | API | Postgres | Compose project |
|---|---|---|---|---|---|
| 0 (main checkout) | base | base | base | base | `COMPOSE_PROJECT_NAME`, else the directory name |
| N (1–9) | base + 10N | base + 10N | base + 10N | base + 10N | `<main's project>-<worktree dir>` |

Bases are the main checkout's `*_HOST_PORT`s in its root `.env`, defaulting to
3000 / 3002 / 8100 / 5434. `make worktree-init` (which `worktree-new` runs)
assigns the slot once, saves it as `WORKTREE_SLOT`, and writes the slot's ports,
`ALLOWED_ORIGINS` and `NEXT_PUBLIC_API_URL` into the worktree's env files. Every
make target and `Dev:` task then follows them.

- **Use `worktree-new`, not `claude --worktree`.** The latter names the branch
  `worktree-<name>`, bases it on `origin/main`, starts before init has run, and
  on exit deletes the folder without `worktree-clean`, stranding the slot's
  volume and images.
- **Monitoring and ngrok stay in main.** `make docker-run` refuses in a
  worktree; use `docker-run-core`. `make dev-tunnel` works from any checkout,
  one at a time.
- **Tear a worktree down with `make worktree-clean`**, not `make clean` or
  `rebuild`: those prune the build cache every checkout shares.
- **`ALLOWED_ORIGINS` is rewritten** by `worktree-init` to the slot's three
  origins; extra origins main lists are not carried over.
- **Several projects from this template on one machine?** Give each its own
  block of 100: set the `*_HOST_PORT`s in its root `.env`, and `ALLOWED_ORIGINS`
  and both `NEXT_PUBLIC_API_URL`s to match. Re-run `make worktree-init` in
  existing worktrees to move them along.

---

## Deploying

`docker-compose.prod.yml` is the deploy file, and it serves **both** staging
and production — the environment is `APP_ENV`, not a second file. It publishes
no ports: a reverse proxy is the only ingress, and on a Dokploy host that proxy
is Traefik, discovering the containers through the labels in the file.

```bash
make deploy-check                     # staging (default)
make deploy-check DEPLOY_ENV=production
```

It runs under its own compose project, so a running dev stack is untouched, and
it tears itself down afterwards. It needs `server/.env.<env>` (gitignored, never
committed) and, once per machine, `docker network create dokploy-network` — the
deploy file declares that network `external` because a Dokploy host provides it.

**What it proves:** the file parses under `APP_ENV`; both portals build as
genuinely distinct images with their own `APP_NAME`; a failed migration fails the
stack instead of starting the server against a stale schema; the server reaches
healthy with no ingress but its own healthcheck; nothing publishes a host port.

**What it does not prove: the Traefik labels.** Nothing routes a request through
a proxy. A wrong container port, a router pointing at a service that isn't
declared, a missing `dokploy-network` — each surfaces on the first real deploy,
not here. Reviewing them is the substitute, and the checklist is in
`docs/superpowers/specs/2026-09-03-ws2-traefik-dokploy-deploy-design.md`.

Also unproven, and worth knowing before a first deploy: `ALLOWED_ORIGINS`
(`server/app/core/config.py:208`) gates **both** CORS and the Clerk `azp`
token-party check (`server/app/utils/auth.py:72`). The browser calls the API
cross-origin — there is no server-side proxy hop — so every portal origin must
be listed for the deploying environment. A missing entry does not look like a
config error; it looks like broken auth.

Also unproven: both portal images are built with the internal portal's
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `NEXT_PUBLIC_API_URL`. Compose resolves
`build.args` from the invoking shell's environment, never from a service's own
`env_file:`, and the Makefile's `-include` exports only
`web-app/apps/internal-portal/.env.local`. Harmless while both portals share
one Clerk instance and one API origin. The day they must differ, both images
ship the internal portal's values with nothing warning — `deploy-check` only
asserts each image baked its own `APP_NAME`, not which portal's other values
it baked.

---

## Environment Setup

Each service has its own env file. Copy examples and fill in values before first run:

```bash
cp .env.example .env   # required by the root Makefile (APP_ENV, GRAFANA_ADMIN_PASSWORD, etc.)
cp server/.env.example server/.env.development
cp web-app/apps/internal-portal/.env.example web-app/apps/internal-portal/.env.local
cp web-app/apps/supplier-portal/.env.example web-app/apps/supplier-portal/.env.local
```

Required secrets: Clerk API keys, database credentials, OpenAI key, Langfuse key.

The `server/.env.<ENV>` file is selected by the `APP_ENV` variable (default when unset: `development`). A value that is set but unrecognised — a typo, a trailing space — fails at startup rather than running as development.

Install the repo's git hooks once per clone:

```bash
git config core.hooksPath .githooks
```

Two hooks live there. `pre-commit` keeps the API contract in sync (see **API
Contract** below). `pre-push` runs `make check-server` and `make check-web`
for whichever side changed since the upstream branch: ruff and Prettier in
check mode, plus ESLint — and, for `web-app/`, `make test-web` (Vitest).
There is no CI for these, so the hook is the gate; `make check` runs both
checks by hand and `git push --no-verify` skips it once.
`.vscode/settings.json` formats on save with the same tools, so the hook
rarely has anything to say.

---

## API Contract

`server/openapi.json` and `web-app/packages/api-client/src/generated/` are
generated from `server/app/` and **committed**. They are a published interface,
not a build artifact: the generated tree is what both portals compile against.

```bash
make gen-contract     # re-export the spec and regenerate the client
make check-contract   # regenerate, then fail if anything moved (what CI runs)
```

### Renaming the service (forks)

The API's title, description and `/api/v1` prefix live in `[tool.app.metadata]`
in `server/pyproject.toml`, its version in that file's `[project]`. Change them
there, run `make gen-contract`, and commit the regenerated artifacts.

They are **not** env variables on purpose: they land in the committed
`openapi.json` and in the header of every generated client file, so reading them
from a gitignored `.env.<env>` would make the artifact differ per machine and
fail `check-contract` for everyone else the moment anyone set one.
`server/.env.example`'s `PROJECT_NAME` is unrelated — it only names Docker
images and containers.

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

---

## Tech Stack Summary

| Layer       | Technology                                   |
|-------------|----------------------------------------------|
| Backend     | FastAPI, SQLModel, PostgreSQL 16 + pgvector  |
| AI / Agents | LangGraph, LangChain, Mem0, Langfuse         |
| Auth        | Clerk (shared across backend and frontend)   |
| Frontend    | Next.js 16 (App Router), React 19, TypeScript |
| Styling     | Tailwind CSS v4, shadcn/ui, Base UI          |
| Data        | TanStack Query v5, Zod v4                    |
| Monitoring  | Prometheus + Grafana + cAdvisor              |
| Containers  | Docker + Docker Compose                      |
