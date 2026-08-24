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
rilevio-app/
├── web-app/          # Next.js frontend (dashboard + supplier portal)
├── server/           # FastAPI backend
│   ├── app/          # Application source
│   ├── tests/        # Unit and integration tests
│   ├── Makefile      # Dev commands
│   └── pyproject.toml
├── prometheus/       # Prometheus config
├── grafana/          # Grafana dashboards and datasources
├── docker-compose.yml          # Development stack
└── docker-compose.prod.yml     # Production stack
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
# Backend
cp server/.env.development.example server/.env.development

# Frontend
cp web-app/.env.local.example web-app/.env.local
```

Required variables include Clerk API keys, database credentials, and OpenAI/Langfuse keys.

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
make docker-logs        # follow logs for all services
make docker-logs-core   # follow logs for core services only

# Stop & clean
make docker-stop        # stop all services
make clean              # stop + remove containers, volumes, and networks

# Rebuild from scratch
make rebuild            # clean + full stack
make rebuild-core       # clean + core stack
```

For production, use the production compose file directly:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Services will be available at:

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API server | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
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
cp apps/internal-portal/.env.local.example apps/internal-portal/.env.local
cp apps/supplier-portal/.env.local.example apps/supplier-portal/.env.local
```

