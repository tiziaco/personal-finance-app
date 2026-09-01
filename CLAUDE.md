# Rilevio — Monorepo Guide

Document compliance management platform built for Fincantieri to replace a manual SharePoint + Excel workflow for tracking supplier documentation across projects and purchase orders.

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
│       ├── auth/              # @app/auth — Role enum, useAppAuth(), getUserRole()
│       ├── types/             # @app/types — shared TypeScript types
│       └── ui/                # @app/ui — shared component library (shadcn/ui)
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

They collide on two resources: host ports **3000, 3002 and 8100**, which the
compose services publish; and the single static **`NGROK_DOMAIN`**, claimed by
both the `ngrok` compose service and `make dev-tunnel`. Stop one path before
starting the other — `make dev-preflight` checks the ports and fails with a
pointer rather than letting the servers die on a bind error.

### Native dev

```bash
make dev-preflight      # verify ports 8100/3000/3002 are free
make dev-tunnel         # ngrok: https://$NGROK_DOMAIN -> localhost:8100
```

`NGROK_DOMAIN` and `NGROK_AUTHTOKEN` come from the root `.env` (loaded by the
Makefile via `-include`), not from your shell — so run the target, not `ngrok`
directly. It passes `--authtoken` explicitly because
`~/Library/Application Support/ngrok/ngrok.yml` takes precedence over the env
var, and a stale token there fails the reserved domain with `ERR_NGROK_320`
while `.env` looks correct.

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

### Service URLs (Docker)

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

The `server/.env.<ENV>` file is selected by the `APP_ENV` variable (default: `development`).

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
