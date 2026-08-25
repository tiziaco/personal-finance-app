# Rilevio — API Server

FastAPI backend for the Rilevio document compliance platform. Handles authentication, document workflows, supplier management, and AI-assisted compliance checks.

## Tech Stack

- **FastAPI** + uvicorn + uvloop
- **PostgreSQL 16** with pgvector (via SQLModel + Alembic)
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

Key variables in `.env.development`:

```bash
APP_ENV=development
POSTGRES_HOST=localhost
POSTGRES_PORT=5434
POSTGRES_DB=rilevio
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
OPENAI_API_KEY=...
CLERK_SECRET_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
```

## Development Commands

```bash
# Start the server (hot reload)
make dev

# Run database migrations
make migrate ENV=development

# Create a new migration
make migrate-create ENV=development MSG="add document table"

# Rollback last migration
make migrate-downgrade ENV=development
```

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

Swagger UI: `http://localhost:8000/docs`
