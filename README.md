# Template App

A production-ready template for **multi-tenant B2B platforms with two portals** — one
for internal staff, one for external partners — backed by a single FastAPI server.

## Overview

The starting point this gives you is the part that is tedious to build and easy to get
wrong: tenant isolation, two separately-deployed frontends sharing one component
library, an API contract that cannot silently drift from its client, and a deploy story.

- **Multi-tenancy via Clerk Organizations** — the org id arrives on the JWT and scopes
  every query; role-gated routing keeps internal and external users in their own portal
- **Two Next.js 16 portals** sharing `packages/core`, `packages/ui`,
  `packages/components`, `packages/auth` and a generated API client, built as genuinely
  distinct images
- **A generated, committed API contract** — `server/openapi.json` and the TanStack Query
  hooks derived from it, with four gates that fail if they drift from the routes
- **GDPR erasure** wired end to end, including LangGraph checkpoints and mem0 memories
- **A LangGraph agent** with Langfuse tracing and Postgres checkpointing
- **Observability and deploy** — Prometheus, Grafana, cAdvisor, and a Traefik/Dokploy
  compose file that serves both staging and production

### The example domain

The template ships with a worked example rather than empty stubs: **supplier document
compliance**. Internal staff manage projects, suppliers and orders; suppliers submit
documents against them. That is why you will find a `Supplier` model, a
`supplier-portal/` app and roles named `project_manager`/`reviewer`/`approver`/`supplier`.

None of it is load-bearing. Rename or replace it to fit your domain — the multi-tenancy,
auth, contract and deploy machinery underneath do not depend on any of it.

---

## Tech Stack

### Frontend (`web-app/`)

| Layer | Technology |
|---|---|
| Framework | [Next.js 16](https://nextjs.org/) + React 19 |
| Language | TypeScript 5 |
| Styling | Tailwind CSS v4 |
| UI Components | shadcn/ui + Base UI + Lucide React |
| Auth | [Clerk](https://clerk.com/) (`@clerk/nextjs`) |
| Data Fetching | TanStack Query v5 |
| Validation | Zod v4 |
| Notifications | Sonner |

### Backend (`server/`)

| Layer | Technology |
|---|---|
| Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Language | Python 3.13+ |
| Runtime | Uvicorn + uvloop |
| ORM / Models | SQLModel + Pydantic v2 |
| Database | PostgreSQL 16 with pgvector |
| Migrations | Alembic |
| Auth | Clerk (JWT via PyJWT + clerk-backend-api) |
| AI / Agents | LangGraph + LangChain + LangChain-OpenAI |
| Memory | Mem0 |
| Observability | Langfuse, Prometheus, structlog |
| Rate Limiting | SlowAPI |
| Package Manager | [uv](https://docs.astral.sh/uv/) |

### Infrastructure

| Component | Technology |
|---|---|
| Database | pgvector/pgvector:pg16 |
| Monitoring | Prometheus + Grafana + cAdvisor |
| Containerization | Docker + Docker Compose |

---

## Project Structure

```
.
├── server/                        # FastAPI backend (Python 3.13, uv)
│   ├── app/                       # Application source
│   ├── alembic/                   # Migrations
│   ├── tests/                     # Unit and integration tests
│   ├── openapi.json               # Committed API contract — generated
│   └── pyproject.toml             # Deps AND the service's public identity
├── web-app/                       # Next.js monorepo (pnpm workspaces)
│   ├── apps/
│   │   ├── internal-portal/       # Staff dashboard (port 3000)
│   │   └── supplier-portal/       # External partner portal (port 3002)
│   └── packages/
│       ├── api-client/            # @app/api-client — generated from openapi.json
│       ├── auth/                  # @app/auth — Role, useAppAuth(), getUserRole()
│       ├── core/                  # @app/core — cn(), NavItem, copy — no renderer
│       ├── ui/                    # @app/ui — shadcn/Base UI primitives, WEB ONLY
│       └── components/            # @app/components — composed chrome, built on ui
├── docs/                          # Setup, architecture, guides, roadmap, TODO/BUGS, specs
├── infra/                         # Prometheus + Grafana config
├── scripts/                       # gen-contract, check-contract, verify-infra, deploy-check
├── docker-compose.dev.yml         # Development stack
└── docker-compose.prod.yml        # Staging AND production (switched by APP_ENV)
```

---

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose
- [Node.js](https://nodejs.org/) 20+ and [pnpm](https://pnpm.io/) (for local frontend dev) — this is a pnpm workspace; npm and yarn will not resolve the `@app/*` packages
- [uv](https://docs.astral.sh/uv/) (for local backend dev)
- The [Clerk CLI](https://clerk.com/docs/cli) and [jq](https://jqlang.org/), which the Clerk
  setup scripts use: `brew install clerk/stable/clerk jq` (or `npm install -g clerk`)
- An [ngrok](https://ngrok.com/) account with its free static domain, for Clerk webhooks
  only. The Docker path runs ngrok in a container; the native path needs it on the host:
  `brew install ngrok`

### Environment Files

Copy the example env files and fill in your values:

```bash
# Root (required by the Makefile — provides APP_ENV, GRAFANA_ADMIN_PASSWORD, etc.)
cp .env.example .env

# Backend
cp server/.env.example server/.env.development

# Frontend
cp web-app/apps/internal-portal/.env.example web-app/apps/internal-portal/.env.local
cp web-app/apps/supplier-portal/.env.example web-app/apps/supplier-portal/.env.local
```

Required variables include Clerk API keys, database credentials and the Langfuse keys. The
OpenAI key is optional: only an LLM call needs it.

### Clerk

Nothing authenticates until a Clerk instance is configured:

```bash
clerk auth login
make clerk-setup CLERK_APP_NAME="Template App Dev — <name>"
```

This creates a development app, writes its keys to the env files, applies the settings and
roles, and seeds three dev users. Re-running it is safe. Then:

- **`ALLOWED_ORIGINS`** must list every portal origin, or valid tokens are rejected — it
  looks like broken auth, not a config error.
- **Webhooks** have no script: add the endpoint in the Clerk dashboard and copy its secret
  into `server/.env.development`. Sign-in works without them; profile edits, offboarding
  and role changes need them. See [`clerk.md` §6](docs/setup/clerk.md#6-webhooks).

Full procedure: [`docs/setup/clerk.md`](docs/setup/clerk.md).

### Git hooks (once per clone)

```bash
git config core.hooksPath .githooks
```

Without this the pre-commit contract gate does not exist, and a route change committed
without its regenerated client is caught only by CI.

### Renaming a fork

The API's title, description, version and `/api/v1` prefix live in `server/pyproject.toml`,
not in `.env` — they land in the committed contract, so changing them is a contract
change. The procedure and the reason: [`docs/setup/making-it-yours.md`](docs/setup/making-it-yours.md) §1.

---

## Running the Application

### Full Stack with Docker Compose (recommended)

A root `Makefile` provides convenience commands for the full stack:

```bash
# Build all services
make docker-build       # build web-app + server
make docker-build-web   # build web-app only
make docker-build-api   # build server only

# Start services
make docker-run         # full stack: web-app, server, db, prometheus, grafana, cadvisor
make docker-run-core    # core only: web-app, server, db (no monitoring)
make docker-run-db      # database only (ENV=development|staging|production)

# Migrations
make docker-migrate     # apply Alembic migrations (one-shot container)
make docker-migrate-status  # show the database's current revision

# Logs
make docker-logs        # follow logs for all services
make docker-logs-core   # follow logs for core services only

# Stop & clean
make docker-stop        # stop all services
make clean              # stop + remove containers, volumes, and networks

# Rebuild from scratch
make rebuild            # clean + full stack
make rebuild-core       # clean + core stack
```

Migrations run as a release phase: a one-shot `migrate` service applies them before
`server` starts, and a failed migration fails the `up`. Authoring revisions, and the
caveats, are in [`server/CLAUDE.md`](server/CLAUDE.md) under **Database Migrations**.

Services will be available at:

| Service | URL |
|---|---|
| Internal portal | http://localhost:3000 |
| Supplier portal | http://localhost:3002 |
| API server | http://localhost:8100 |
| API docs (Swagger) | http://localhost:8100/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 |
| cAdvisor | http://localhost:8080 |
| PostgreSQL | localhost:5434 |

### Native Development (local)

The API and both portals run on the host with hot reload; only Postgres runs in Docker.
Install dependencies once: `uv sync` in `server/`, `pnpm install` in `web-app/`.

**In VS Code**, press ⇧⌘B (Ctrl+Shift+B), the default build task: **Dev: All** checks the
ports, starts Postgres, applies migrations, then runs the API and both portals in their own
terminals. Two more tasks are under **Terminal → Run Task**:

- **Dev: All + Tunnel** adds the ngrok tunnel, for Clerk webhooks.
- **Dev: Kill All** frees the ports.

**From a terminal**, the same steps, each server in its own terminal:

```bash
make dev-preflight                      # fail early if a port is taken
make docker-run-db ENV=development      # Postgres
make -C server migrate ENV=development  # not applied for you on this path
make -C server dev                      # API, http://localhost:8100
make dev-internal                       # internal portal, http://localhost:3000
make dev-supplier                       # supplier portal, http://localhost:3002
make dev-tunnel                         # optional — ngrok, for Clerk webhooks
```

> **The Docker and native paths are mutually exclusive** — they publish the same host
> ports and claim the same ngrok domain. Stop one before starting the other;
> `make dev-preflight` checks.

### Parallel Work (git worktrees)

Each linked git worktree can run its own stack — database, containers, ports — so two
branches can be built side by side, each in its own Claude session.

```bash
make worktree-new NAME=feed                   # .claude/worktrees/feed on feat/feed
cd .claude/worktrees/feed && claude
make worktree-clean                           # inside it, before `git worktree remove`
```

Ports, what stays in the main checkout, and merging two branches' migrations and
contracts: [`CLAUDE.md`](CLAUDE.md) under **Parallel worktrees**.

---

## Testing

```bash
# Backend — from server/
make test              # all tests (APP_ENV=test)
make test-unit         # unit tests only, no database needed
make test-integration  # requires a live database
make test-coverage     # HTML + XML coverage report

# Frontend — from the repo root, or `pnpm test` / `pnpm test:watch` in web-app/
make test-web          # Vitest: packages and both portals

# Repo-level checks
make check                       # ruff, import-linter, ESLint, Prettier — read-only
make check-contract              # committed API artifacts match the routes
bash scripts/verify-infra.sh     # layout, identifiers, compose validity
```

### Quality gates

The git hooks are the main gate. CI re-runs the contract, the server's lint and the
module boundaries on every pull request; ESLint, Prettier and Vitest run only in the
hook. Install the hooks once per clone
with `git config core.hooksPath .githooks`.

| When | What runs | Skipped by |
|---|---|---|
| On save (VS Code) | ruff and Prettier format; ruff organizes imports | — |
| `git commit` touching `server/app/` | `make check-contract` — regenerates the spec and client, blocks on drift | `--no-verify` |
| `git push` with `server/` changes | `make check-server` — ruff, ruff format, import-linter (module boundaries) | `--no-verify` |
| `git push` with `web-app/` changes | `make check-web` — ESLint, Prettier; then `make test-web` | `--no-verify` |
| Pull request, push to `main` | **API Contract** workflow — `check-contract`, the OpenAPI contract tests, `tsc` across the workspace | — |
| Pull request, push to `main` | **Module Boundaries** workflow — import-linter, ruff, the module-contract, tenant-table and event tests | — |
| Building an image | `make docker-build` / `docker-build-web` run `check-contract` first | — |
| By hand only | the server's full pytest suite (`cd server && make test`), `make deploy-check` | — |

A hook whose tool is missing warns and lets the commit or push through rather than
blocking it. The server suite is the gap: nothing runs it automatically, so run it before
pushing a server change.

---

## Deploying

`docker-compose.prod.yml` serves **both** staging and production — the environment is
`APP_ENV`, not a second file. It publishes no ports: a reverse proxy is the only ingress,
and on a Dokploy host that proxy is Traefik, discovering containers through the file's
labels.

```bash
make deploy-check                      # staging (default)
make deploy-check DEPLOY_ENV=production
```

What `deploy-check` proves and what it cannot is in [`CLAUDE.md`](CLAUDE.md) under
**Deploying**; the Traefik label checklist and a 404 triage are in
[`docs/setup/deploy-dokploy.md`](docs/setup/deploy-dokploy.md).

---

## Documentation

| Where | What |
|---|---|
| [`docs/`](docs/) | Index of everything below |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Where the work stands — the one file that records progress |
| [`docs/BUGS.md`](docs/BUGS.md), [`docs/TODO.md`](docs/TODO.md) | What is wrong today, and what is deferred to the change that should make it |
| [`docs/setup/clerk.md`](docs/setup/clerk.md) | **Start here** — the Clerk setup scripts, roles, `ALLOWED_ORIGINS`, webhooks |
| [`docs/setup/infrastructure.md`](docs/setup/infrastructure.md) | Root `.env`, Prometheus/Grafana/cAdvisor, and what production omits |
| [`docs/setup/making-it-yours.md`](docs/setup/making-it-yours.md) | Renaming this template for your project |
| [`docs/setup/deploy-dokploy.md`](docs/setup/deploy-dokploy.md) | Deploying behind Dokploy's Traefik — what `deploy-check` cannot prove |
| [`docs/architecture/`](docs/architecture/) | How the server, the web app and authorization are built |
| [`docs/guides/`](docs/guides/) | Patterns portable beyond this repo — the API codegen pipeline |
| [`CLAUDE.md`](CLAUDE.md), [`server/CLAUDE.md`](server/CLAUDE.md), [`web-app/CLAUDE.md`](web-app/CLAUDE.md) | Working conventions and the most detailed operational notes in the repo |

