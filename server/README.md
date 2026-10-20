# Finsight — API Server

FastAPI backend serving the web app. Handles authentication via Clerk; every row is scoped
to its user. Also user provisioning and GDPR erasure, the LangGraph agent, and the OpenAPI
contract the frontend client is generated from.

## Tech Stack

- **FastAPI** + uvicorn + uvloop
- **PostgreSQL 18** with pgvector (via SQLModel + Alembic)
- **LangGraph** + LangChain + OpenAI for AI agent workflows
- **Clerk** for JWT authentication and user provisioning
- **Langfuse** for LLM observability
- **Prometheus** + structlog for metrics and structured logging
- **uv** for dependency management

## Setup

```bash
# Install dependencies
make install

# Copy and fill in environment variables
cp .env.example .env.development
```

`.env.example` lists every variable with a comment. The ones that must be real: the
Postgres credentials, `CLERK_SECRET_KEY` (and the rest of the Clerk block —
[`docs/setup/clerk.md`](../docs/setup/clerk.md)) and the Langfuse keys. `OPENROUTER_API_KEY`
is optional; only an LLM call needs it.

## Development Commands

```bash
# Start the server (hot reload)
make dev

# Run database migrations (host / non-Docker path)
make migrate ENV=development

# Create a new migration
make migrate-create ENV=development MSG="add transaction table"

# Rollback last migration
make migrate-downgrade ENV=development
```

The `make migrate*` targets run on the host via `uv` — the path for **authoring**
revisions. The Docker stack applies them itself, as a release phase; see
[`CLAUDE.md`](CLAUDE.md) under **Database Migrations**.

## Testing

```bash
make test               # all tests
make test-unit          # unit tests only
make test-integration   # integration tests only
make test-coverage      # tests + HTML/XML coverage report
make test-fast          # skip slow tests
```

## Code Quality

```bash
make lint       # ruff check
make format     # ruff format
```

## API

Swagger UI: `http://localhost:8100/docs`

`openapi.json` is a committed artifact, not a build output: it generates the
frontend's typed client. After changing any route, run `make gen-contract` from
the repo root and commit both outputs in the same commit — `make check-contract`
is what CI runs, and the pre-commit hook blocks a commit that touches `app/`
without them.

The schema's title, description and `/api/v1` prefix come from
`[tool.app.metadata]` in `pyproject.toml`, and its version from `[project]`,
loaded by `app/core/metadata.py`. They are not environment variables, and changing one is
a contract change — see **Identity** in the root [`README.md`](../README.md).
