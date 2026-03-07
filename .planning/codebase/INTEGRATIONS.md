# External Integrations

**Analysis Date:** 2026-02-26

## APIs & External Services

**Large Language Models:**
- OpenAI API - Primary LLM provider (ChatGPT models)
  - SDK/Client: `langchain-openai` 1.0.2+
  - Auth: Environment variable `OPENAI_API_KEY`
  - Configuration: `DEFAULT_LLM_MODEL` (default: gpt-4o-mini), `DEFAULT_LLM_TEMPERATURE` (default: 0.2)
  - Location: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/services/llm/service.py`

**Web Search:**
- DuckDuckGo Search - Web search integration for chatbot agent
  - SDK/Client: `langchain-community.tools.DuckDuckGoSearchResults`, `duckduckgo-search`, `ddgs`
  - Auth: None required (public API)
  - Location: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/agents/chatbot/tools/duckduckgo_search.py`

**LLM Observability:**
- Langfuse - LLM tracing, debugging, and monitoring
  - SDK/Client: `langfuse` 3.9.1
  - Auth: Environment variables `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`
  - Endpoint: `LANGFUSE_HOST` (default: https://cloud.langfuse.com)
  - Configuration: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/core/config.py` (LangfuseSettings)
  - Initialized in: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/main.py`

**Agent Memory:**
- Mem0 AI - Long-term memory for agents
  - SDK/Client: `mem0ai` 1.0.0
  - Configuration: `LONG_TERM_MEMORY_MODEL`, `LONG_TERM_MEMORY_EMBEDDER_MODEL`, `LONG_TERM_MEMORY_COLLECTION_NAME`
  - Uses OpenAI embeddings (text-embedding-3-small)

## Data Storage

**Databases:**
- PostgreSQL 16 (with pgvector extension)
  - Provider: pgvector/pgvector:pg16 (Docker image)
  - Connection: Environment variables `POSTGRES_HOST`, `POSTGRES_PORT` (5432), `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
  - Client: `psycopg[binary]` 3.3.2+, `asyncpg` 0.30.0
  - ORM: SQLModel 0.0.24 (SQL models with Pydantic validation)
  - Location: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/core/database.py`
  - Migrations: Alembic (`/Users/tizianoiacovelli/projects/personal-finance-app/server/alembic`)

**State Persistence (Agent Checkpointing):**
- PostgreSQL Checkpointing - LangGraph agent state persistence
  - SDK/Client: `langgraph-checkpoint-postgres` 3.0.1
  - Location: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/agents/shared/checkpointing/postgres.py`
  - Checkpoint tables: `checkpoint_blobs`, `checkpoint_writes`, `checkpoints`

**File Storage:**
- Local filesystem only - CSV uploads handled in-memory then stored in database
  - Service: `csv_mapping` service processes uploaded files
  - Location: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/services/csv_mapping/`

**Caching:**
- None at application level - PostgreSQL serves as the primary data store
- AsyncPG provides connection pooling (POSTGRES_POOL_SIZE: 15, POSTGRES_MAX_OVERFLOW: 10)

## Authentication & Identity

**Auth Provider:**
- Clerk - Primary authentication and user management
  - SDK/Client: `clerk-backend-api` 1.0.0 (backend), `@clerk/nextjs` 6.38.1 (frontend)
  - Backend Auth: Environment variables `CLERK_SECRET_KEY`, `CLERK_ISSUER`, `CLERK_OAUTH_CLIENT_ID`, `CLERK_OAUTH_CLIENT_SECRET`
  - Backend Endpoints: `CLERK_AUTHORIZE_URL`, `CLERK_TOKEN_URL`
  - Frontend Auth: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `NEXT_PUBLIC_CLERK_SIGN_IN_URL`, `NEXT_PUBLIC_CLERK_SIGN_UP_URL`, etc.
  - Backend Implementation: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/services/clerk/` (service), `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/utils/auth.py` (JWT verification)
  - Frontend Implementation: Built-in to `@clerk/nextjs` middleware
  - JWKS URL: Derived from `CLERK_ISSUER` as `{issuer}/.well-known/jwks.json`

**JWT Token Handling:**
- Library: `pyjwt[crypto]` 2.9.0
- Location: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/utils/auth.py` (JWT verification logic)

## Monitoring & Observability

**Error Tracking:**
- Not integrated - relying on application logging and Langfuse for LLM-specific errors

**Logs:**
- Structured logging via `structlog` 25.2.0
- Format: JSON or console (configurable via `LOG_FORMAT` env var)
- Location: `LOG_DIR` environment variable (default: `logs/` directory)
- Correlation IDs: Tracked via `asgi-correlation-id` 4.3.4 for request tracing
- Implementation: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/core/logging.py`

**Metrics:**
- Prometheus - Metrics collection and storage
  - Image: `prom/prometheus:latest`
  - Configuration: `/Users/tizianoiacovelli/projects/personal-finance-app/prometheus/prometheus.yml`
  - Retention: 30 days (time) or 10GB (size)
  - Client: `prometheus-client` 0.19.0
  - Middleware: `starlette-prometheus` 0.7.0
  - Metrics implementation: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/core/metrics.py`
  - Middleware setup: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/api/middlewares/prometheus.py`

**Visualization:**
- Grafana - Metrics visualization dashboard
  - Image/Service: Referenced in docker-compose.yml but not fully configured
  - Default URL: http://localhost:3001 (admin/admin)

## CI/CD & Deployment

**Hosting:**
- Docker containers (self-hosted or cloud deployment)
- Web App: Port 3000, standalone Next.js build
- API Server: Port 8000, FastAPI with Uvicorn
- Database: PostgreSQL on port 5432
- Prometheus: Port 9090

**CI Pipeline:**
- None detected - no GitHub Actions, GitLab CI, or Jenkins configuration
- Local development via Makefile commands

**Deployment:**
- Docker Compose for orchestration (development and production variants)
- Multi-stage Docker builds for optimized images
- Network: `monitoring` Docker network for service communication
- Health checks: FastAPI `/health` endpoint for container health verification

## Environment Configuration

**Required env vars (Backend):**
- `APP_ENV` - Application environment (development/staging/production/test)
- `OPENAI_API_KEY` - OpenAI API key for LLM access
- `CLERK_SECRET_KEY` - Clerk authentication secret
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` - Database connection
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` - Langfuse observability

**Required env vars (Frontend):**
- `NEXT_PUBLIC_API_URL` - Backend API URL
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` - Clerk public key
- `CLERK_SECRET_KEY` - Clerk backend secret
- `CLERK_JWT_ISSUER_DOMAIN` - Clerk issuer domain

**Secrets location:**
- Environment files: `.env`, `.env.development`, `.env.test` (not committed)
- Example files: `.env.example` (committed as template)
- Production secrets: Managed outside of repository (env vars in deployment platform)

## Webhooks & Callbacks

**Incoming:**
- None detected - application is driven by client requests and LLM agent processing

**Outgoing:**
- Clerk Webhooks - Potentially configured in Clerk dashboard but not implemented in codebase
- Langfuse Callbacks - Automatic via LangChain integration for LLM tracing

## Rate Limiting

**Implementation:**
- Library: `slowapi` 0.1.9
- Global default: 200 requests per day, 50 per hour
- Endpoint-specific limits configurable via environment variables:
  - `RATE_LIMIT_CHAT`: 30 per minute (default)
  - `RATE_LIMIT_CHAT_STREAM`: 20 per minute (default)
  - `RATE_LIMIT_MESSAGES`: 50 per minute (default)
  - `RATE_LIMIT_REGISTER`: 10 per hour (default)
  - `RATE_LIMIT_LOGIN`: 20 per minute (default)
- Location: `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/core/limiter.py` (limiter configuration)
- Middleware: Applied in main FastAPI app setup

---

*Integration audit: 2026-02-26*
