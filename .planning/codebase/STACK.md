# Technology Stack

**Analysis Date:** 2026-02-26

## Languages

**Primary:**
- Python 3.13 - Backend API and agent-based services (`/Users/tizianoiacovelli/projects/personal-finance-app/server`)
- TypeScript 5 - Frontend web application (`/Users/tizianoiacovelli/projects/personal-finance-app/web-app`)
- JavaScript (React 19) - Frontend UI components and state management

**Secondary:**
- YAML - Docker Compose and Prometheus configuration
- JSON - Package manifests and configuration

## Runtime

**Environment:**
- Python 3.13 (specified in `/Users/tizianoiacovelli/projects/personal-finance-app/server/.python-version`)
- Node.js 18+ (required for web-app frontend builds)
- Docker & Docker Compose (containerized deployment)

**Package Manager:**
- Python: `uv` (ultra-fast Python package installer)
- Node: `npm` (npm lockfile present at `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/package-lock.json`)

## Frameworks

**Backend:**
- FastAPI 0.121.0+ - Async REST API framework (`/Users/tizianoiacovelli/projects/personal-finance-app/server/app/main.py`)
- LangChain 1.0.5+ - LLM application framework (`/Users/tizianoiacovelli/projects/personal-finance-app/server/app/services/llm/`)
- LangGraph 1.0.2+ - Graph-based agent orchestration (`/Users/tizianoiacovelli/projects/personal-finance-app/server/app/agents/`)
- SQLModel 0.0.24 - SQL ORM with Pydantic integration
- Alembic 1.18.3 - Database migration management (`/Users/tizianoiacovelli/projects/personal-finance-app/server/alembic.ini`)

**Frontend:**
- Next.js 16.1.6 - React framework with SSR (`/Users/tizianoiacovelli/projects/personal-finance-app/web-app/next.config.ts`)
- React 19.2.4 - UI library and component framework
- Tailwind CSS 4 - Utility-first CSS framework (`/Users/tizianoiacovelli/projects/personal-finance-app/web-app/tailwind.config.*`)
- TypeScript 5 - Static type checking

**Build & Development:**
- uvicorn 0.34.0 - ASGI server for FastAPI
- uvloop 0.22.1 - Ultra-fast asyncio event loop replacement
- pytest 8.3.5+ - Python testing framework (configured in `pyproject.toml`)
- ESLint 9.39.3 - JavaScript/TypeScript linting (`/Users/tizianoiacovelli/projects/personal-finance-app/web-app/eslint.config.mjs`)

## Key Dependencies

**Critical (Backend):**
- langchain-openai 1.0.2+ - OpenAI integration with LangChain
- langchain-core 1.0.4+ - Core abstractions for LLM applications
- langchain-community 0.4.1+ - Community integrations including DuckDuckGo search
- langgraph-checkpoint-postgres 3.0.1 - Persistent checkpointing for agent state
- pydantic 2.11.1+ - Data validation and settings management
- psycopg 3.3.2+ - PostgreSQL database adapter for Python
- asyncpg 0.30.0 - Async PostgreSQL driver (high performance)

**Infrastructure (Backend):**
- prometheus-client 0.19.0 - Prometheus metrics export
- starlette-prometheus 0.7.0 - Prometheus middleware for FastAPI
- slowapi 0.1.9 - Rate limiting middleware
- structlog 25.2.0 - Structured logging framework
- asgi-correlation-id 4.3.4 - Request correlation tracking
- python-dotenv 1.1.0 - Environment variable loading

**AI/ML (Backend):**
- mem0ai 1.0.0 - Long-term memory for agents
- langfuse 3.9.1 - LLM observability and tracing (`/Users/tizianoiacovelli/projects/personal-finance-app/server/app/core/config.py` LangfuseSettings)
- tenacity 9.1.2 - Retry and resilience library
- duckduckgo-search 3.9.0 & ddgs 9.10.0 - Web search integration

**Data Processing (Backend):**
- polars 1.38.1 - Fast DataFrame library for transaction processing
- statsmodels 0.14.6 - Statistical analysis tools
- email-validator 2.2.0 - Email validation utility

**Authentication (Backend):**
- clerk-backend-api 1.0.0 - Clerk authentication provider SDK
- pyjwt 2.9.0 with crypto - JWT token handling

**Frontend:**
- @clerk/nextjs 6.38.1 - Clerk authentication for Next.js (`/Users/tizianoiacovelli/projects/personal-finance-app/web-app/package.json`)
- @tanstack/react-query 5.90.21 - Data fetching and caching
- zod 4.3.6 - TypeScript-first schema validation
- lucide-react 0.575.0 - Icon library
- sonner 2.0.7 - Toast notifications
- class-variance-authority 0.7.1 - Component variant management
- tailwind-merge 3.5.0 - Tailwind CSS class merging

**Testing (Backend):**
- httpx 0.28.1 - Async HTTP client for API testing
- pytest-asyncio 0.25.2 - Async test support
- pytest-cov 6.0.0 - Coverage reporting
- pytest-mock 3.14.0 - Mocking utilities

## Configuration

**Environment:**
- Multiple environment files: `.env.development`, `.env.test`, `.env.example`
- Pydantic Settings pattern for configuration management (`/Users/tizianoiacovelli/projects/personal-finance-app/server/app/core/config.py`)
- Environment-aware configuration with `APP_ENV` variable (development/staging/production/test)

**Build:**
- Next.js config: `next.config.ts` with security headers and standalone output
- Dockerfile multi-stage builds for optimized production images (`/Users/tizianoiacovelli/projects/personal-finance-app/server/Dockerfile`, `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/Dockerfile`)
- Docker Compose orchestration: `docker-compose.yml` (development), `docker-compose.prod.yml` (production)
- Makefile-based commands for common tasks

## Platform Requirements

**Development:**
- PostgreSQL 14+ with pgvector extension (for semantic search)
- Python 3.13
- Node.js 18+
- Docker & Docker Compose (recommended)

**Production:**
- Container runtime (Docker)
- PostgreSQL 14+ with pgvector (db service uses `pgvector/pgvector:pg16`)
- Prometheus (metrics collection)
- Grafana (optional, for metrics visualization)

## Additional Tools

**Database:**
- alembic - Schema migrations
- SQLModel - ORM and data modeling

**Observability:**
- Prometheus - Metrics collection and time-series database
- Grafana - Metrics visualization (referenced in docker-compose.yml)
- Langfuse - LLM tracing and observability

**Rate Limiting:**
- slowapi - Endpoint-specific rate limiting via decorators

**Logging:**
- structlog - Structured logging (JSON or console format configurable)
- asgi-correlation-id - Request tracking across distributed components

---

*Stack analysis: 2026-02-26*
