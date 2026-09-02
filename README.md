# Rilevio

A cloud-based document compliance management platform built for Fincantieri to replace the manual SharePoint + Excel workflow used to track supplier documentation across projects and purchase orders.

## Overview

The platform streamlines the end-to-end supplier onboarding and document compliance process — from document collection and validation to expiry tracking and client forwarding — across multiple concurrent projects and suppliers.

It consists of two client-facing interfaces backed by a single API server:

- **Internal Dashboard** — for project managers to manage projects, suppliers, orders, document compliance status, and administrative document expiries
- **Supplier Portal** — external-facing interface where suppliers upload required documents, track submission status, and receive notifications about missing or expiring files

## Key Features

**For Project Managers**

- See the compliance status of every supplier across all active projects at a glance
- Review and approve uploaded documents, flag issues, and trigger automatic email notifications to suppliers
- Track expiring administrative documents (DURC, Visura camerale, CCIA, White List) before they become blockers
- Manage projects, suppliers, and purchase orders from a single dashboard
- Monitor overall document submission progress per supplier with at-a-glance completion percentages
- Forward approved document packages to the end client with a single action

**For Suppliers**

- Log in to a dedicated portal and see exactly which documents are required for each assigned order
- Upload files directly — no SharePoint access, no email attachments
- Get notified automatically when a document is rejected or approaching expiry
- Track submission progress in real time
- Add comments to document uploads to provide context or flag questions

**Regulatory Context**

Built for compliance with D.Lgs. 81/2008 (workplace safety) and D.Lgs. 36/2023 (public procurement), with document templates aligned to Fincantieri's existing procurement workflows.

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
app/
├── web-app/          # Next.js frontend (dashboard + supplier portal)
├── server/           # FastAPI backend
│   ├── app/          # Application source
│   ├── tests/        # Unit and integration tests
│   ├── Makefile      # Dev commands
│   └── pyproject.toml
├── infra/                    # Infrastructure config
│   ├── prometheus/           # Prometheus config
│   └── grafana/               # Grafana dashboards and datasources
├── docker-compose.dev.yml    # Development stack
└── docker-compose.prod.yml   # Production stack
```

---

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose
- [Node.js](https://nodejs.org/) 20+ and npm (for local frontend dev)
- [uv](https://docs.astral.sh/uv/) (for local backend dev)
- A [Clerk](https://clerk.com/) application (for auth)

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

Required variables include Clerk API keys, database credentials, and OpenAI/Langfuse keys.

### Service Identity (renaming a fork)

The API's title, description and versioned path prefix are **not** environment
variables. They live in `server/pyproject.toml`, and the version alongside them
in `[project]`:

```toml
[project]
version = "1.0.0"

[tool.app.metadata]
title = "Rilevio - Server"
description = "A production-ready FastAPI service with LangGraph and Clerk authentication"
api_v1_str = "/api/v1"
```

Change them there, then regenerate the committed contract and commit the result:

```bash
make gen-contract
```

They are kept out of `.env` on purpose. All four land in the committed
`server/openapi.json` — the first three verbatim in its `info` block,
`api_v1_str` as the prefix on every versioned path — and orval stamps the title
into the header of every generated API client file. Read from a gitignored
`.env.<env>` they would differ per machine, so `make check-contract` would fail
on CI and on every fresh clone the moment anyone set one.

`PROJECT_NAME` in `server/.env.example` is a different thing despite the name:
it only tags the Docker image built by `make -C server docker-build`, and has no
effect on the API's title.

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

# Logs
make docker-migrate     # apply Alembic migrations (one-shot container)
make docker-migrate-status  # show the database's current revision

make docker-logs        # follow logs for all services
make docker-logs-core   # follow logs for core services only

# Stop & clean
make docker-stop        # stop all services
make clean              # stop + remove containers, volumes, and networks

# Rebuild from scratch
make rebuild            # clean + full stack
make rebuild-core       # clean + core stack
```

### Database migrations

Migrations are a discrete release phase, not part of app startup. A one-shot
`migrate` service runs `alembic upgrade head` and `server` will not start until
it exits 0, so a failed migration fails the deploy and leaves the previously
running container serving the old image. This is expressed in the compose files
because the deploy target runs only `docker compose up -d --build` and offers no
release-phase hook.

Two consequences worth knowing:

- `depends_on` applies to `compose up`, not to reboots. After a Docker daemon or
  host restart, `server` returns under its restart policy without a `migrate` run.
- Revisions are authored on the host (`cd server && make migrate-create ENV=…`).
  In dev, `server/alembic/` is bind-mounted so the container sees new revisions
  immediately; `alembic.ini` is not, so changes to it need `make docker-build-api`.

For production, use the production compose file directly:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Services will be available at:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API server | http://localhost:8100 |
| API docs (Swagger) | http://localhost:8100/docs |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3001 |
| cAdvisor | http://localhost:8080 |

### Frontend Development (local)

From `web-app/`:

```bash
# Install all workspace dependencies
pnpm install

# Run the internal dashboard
pnpm dev:internal    # http://localhost:3000

# Run the supplier portal (always on 3002)
pnpm dev:supplier    # http://localhost:3002

# Copy and fill env files before starting
cp apps/internal-portal/.env.example apps/internal-portal/.env.local
cp apps/supplier-portal/.env.example apps/supplier-portal/.env.local
```

