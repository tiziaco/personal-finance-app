# Codebase Structure

**Analysis Date:** 2026-02-26

## Directory Layout

```
personal-finance-app/
├── .planning/              # GSD planning and documentation
├── server/                 # Backend (FastAPI + Python)
│   ├── app/
│   │   ├── main.py                  # FastAPI app entry point
│   │   ├── api/                     # HTTP endpoints
│   │   │   ├── v1/                  # Versioned API routes
│   │   │   ├── dependencies/        # FastAPI dependency injection
│   │   │   ├── middlewares/         # Request/response middleware
│   │   │   └── system/              # Health checks, readiness
│   │   ├── agents/                  # LangGraph AI agents
│   │   │   ├── base/                # Abstract BaseAgent class
│   │   │   ├── chatbot/             # Chatbot agent
│   │   │   ├── transactions_labeler/# Transaction categorizer agent
│   │   │   ├── insights/            # Insights generation agent
│   │   │   ├── shared/              # Checkpointing, memory, observability
│   │   │   └── factory.py           # Agent initialization & registry
│   │   ├── services/                # Business logic (stateless)
│   │   │   ├── user/                # User CRUD, JIT provisioning
│   │   │   ├── transaction/         # Transaction CRUD, fingerprinting
│   │   │   ├── conversation/        # Conversation management
│   │   │   ├── insights/            # Insight generation
│   │   │   ├── analytics/           # Analytics calculations
│   │   │   ├── csv_mapping/         # CSV format detection
│   │   │   ├── llm/                 # LLM interactions
│   │   │   └── clerk/               # Clerk API sync
│   │   ├── models/                  # SQLModel ORM definitions
│   │   │   ├── user.py
│   │   │   ├── transaction.py
│   │   │   ├── conversation.py
│   │   │   ├── insight.py
│   │   │   ├── csv_mapping_profile.py
│   │   │   ├── csv_upload_session.py
│   │   │   ├── base.py              # BaseModel, mixins
│   │   │   └── __init__.py
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   ├── database/                # Database setup and management
│   │   │   ├── engine.py            # AsyncEngine, session factory
│   │   │   └── context.py           # RLS context setup
│   │   ├── exceptions/              # Domain exceptions
│   │   ├── core/                    # Infrastructure config
│   │   │   ├── config.py            # Settings, environment vars
│   │   │   ├── logging.py           # Structlog setup
│   │   │   ├── limiter.py           # Rate limiter
│   │   │   └── metrics.py           # Prometheus metrics
│   │   ├── analytics/               # Analytics module (separate)
│   │   ├── tools/                   # Tools for agents
│   │   └── utils/                   # Utility functions
│   ├── alembic/                     # Database migrations
│   │   └── versions/
│   ├── tests/                       # Test suite
│   │   ├── unit/
│   │   └── integration/
│   ├── scripts/                     # Utility scripts
│   ├── docs/                        # Documentation
│   ├── evals/                       # Evaluation metrics
│   ├── pyproject.toml               # Project metadata, dependencies
│   └── .env.example                 # Environment template
├── web-app/                         # Frontend (Next.js + TypeScript)
│   ├── src/
│   │   ├── app/                     # Next.js app router
│   │   │   ├── layout.tsx           # Root layout (Clerk, Query, Theme providers)
│   │   │   ├── page.tsx             # Home redirect
│   │   │   ├── (app)/               # Authenticated routes group
│   │   │   │   ├── layout.tsx       # App layout (sidebar, main)
│   │   │   │   └── [pages]/
│   │   │   └── (auth)/              # Auth routes group
│   │   ├── components/              # Reusable React components
│   │   │   ├── ui/                  # Base UI components (shadcn-style)
│   │   │   │   ├── button.tsx
│   │   │   │   ├── card.tsx
│   │   │   │   ├── sidebar.tsx
│   │   │   │   ├── dialog.tsx
│   │   │   │   ├── input.tsx
│   │   │   │   ├── theme-provider.tsx
│   │   │   │   └── [more UI components]/
│   │   │   ├── layout/              # Layout components
│   │   │   │   ├── app-sidebar.tsx
│   │   │   │   ├── nav-sidebar.tsx
│   │   │   │   ├── user-panel.tsx
│   │   │   │   └── company-logo.tsx
│   │   │   └── settings/            # Settings feature components
│   │   │       ├── settings-dialog.tsx
│   │   │       └── server-status.tsx
│   │   ├── hooks/                   # Custom React hooks
│   │   │   ├── use-mobile.ts
│   │   │   └── use-server-status.ts
│   │   ├── lib/                     # Utilities and helpers
│   │   │   ├── api/                 # API client functions
│   │   │   │   └── health.ts        # Health check endpoint
│   │   │   ├── env-helpers.ts       # Environment detection
│   │   │   ├── utils.ts             # General utilities
│   │   │   ├── hub-nav.ts           # Navigation config
│   │   │   └── [other helpers]/
│   │   ├── providers/               # React context providers
│   │   │   └── query-provider.tsx   # React Query setup
│   │   ├── types/                   # TypeScript type definitions
│   │   │   ├── nav.ts
│   │   │   ├── health.ts
│   │   │   └── [other types]/
│   │   ├── styles/                  # Global styles
│   │   │   └── globals.css          # TailwindCSS imports
│   │   ├── proxy.ts                 # Middleware/proxy config
│   │   └── middleware.ts            # Next.js middleware (auth)
│   ├── public/                      # Static assets
│   │   ├── icons/
│   │   └── images/
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   └── tailwind.config.js
├── docker-compose.yml               # Local development services
├── docker-compose.prod.yml          # Production services
├── Makefile                         # Build and run commands
├── README.md                        # Project documentation
└── personal-finance-app.code-workspace  # VS Code workspace
```

## Directory Purposes

**server/app/api/v1/:**
- Purpose: All API route definitions, feature-organized
- Contains: Route modules for each feature (auth, transactions, chatbot, conversation, analytics, insights)
- Key files: `api.py` includes all routers with prefixes

**server/app/agents/:**
- Purpose: LangGraph workflow definitions and orchestration
- Contains: Agent implementations (ChatbotAgent, TransactionLabelerAgent, InsightsAgent), base class, shared utilities for checkpointing and memory
- Pattern: Each agent is a subclass of BaseAgent, pre-compiled at startup

**server/app/services/:**
- Purpose: Business logic, database operations, external service integrations
- Contains: Transaction service with CRUD + fingerprinting, user provisioning, CSV processing, analytics, insights generation, LLM calls
- Pattern: Static async methods, dependency injection via parameters, no instance state

**server/app/models/:**
- Purpose: SQLModel ORM definitions (database schema + Python types)
- Contains: User, Transaction, Conversation, Insight, CsvMappingProfile models
- Mixins: BaseModel (timestamps), SoftDeleteMixin (deleted_at), AnonymizableMixin (GDPR)

**server/app/schemas/:**
- Purpose: Pydantic request/response validation schemas
- Contains: Request DTOs (TransactionCreate, TransactionUpdate, BatchUpdateItem), filter objects (TransactionFilters), response models
- Pattern: Used on all endpoints for validation and serialization

**server/app/core/:**
- Purpose: Application infrastructure and settings
- Contains: Environment config (Settings class from pydantic-settings), structured logging setup, rate limiter config, metrics initialization
- Key pattern: Settings loaded from .env with validation, singletons for logger/limiter

**web-app/src/app/:**
- Purpose: Next.js App Router routes and layouts
- Contains: Root layout with providers, authenticated routes under `(app)/`, auth routes under `(auth)/`
- Pattern: File-based routing, route groups for logical grouping, layouts provide structure

**web-app/src/components/ui/:**
- Purpose: Reusable base UI components (button, card, input, dialog, sidebar, etc.)
- Contains: Styled components using shadcn/ui pattern (Radix + TailwindCSS)
- Pattern: Unstyled/minimal logic, composition-friendly

**web-app/src/lib/api/:**
- Purpose: API client functions and HTTP utilities
- Contains: Health check endpoint, future endpoints for CRUD operations
- Pattern: Async fetch functions with token auth, error handling

**web-app/src/providers/:**
- Purpose: React Context providers for global state
- Contains: QueryProvider (React Query client setup with devtools)
- Pattern: "use client" components, singletons

## Key File Locations

**Entry Points:**

- `server/app/main.py`: Backend FastAPI app, middleware stack, lifespan events
- `web-app/src/app/layout.tsx`: Frontend root layout, provider setup
- `web-app/src/app/page.tsx`: Home page (redirects to /home)

**Configuration:**

- `server/app/core/config.py`: All environment variables (database, auth, LLM, services)
- `web-app/next.config.js`: Next.js build config
- `web-app/tailwind.config.js`: TailwindCSS design tokens

**Core Logic:**

- `server/app/services/transaction/service.py`: Transaction CRUD, fingerprinting, import
- `server/app/services/user/service.py`: User repository and JIT provisioning
- `server/app/agents/base/agent.py`: BaseAgent abstraction for all agents
- `server/app/agents/factory.py`: Agent registry and initialization
- `server/app/database/engine.py`: AsyncEngine setup, session factory

**Authentication:**

- `server/app/api/dependencies/auth.py`: Clerk JWT validation, JIT provisioning
- `server/app/api/middlewares/auth.py`: AuthMiddleware (sets request.state.clerk_id)
- `web-app/src/middleware.ts`: Next.js middleware for auth redirects

**Error Handling:**

- `server/app/exceptions/base.py`: Domain exception definitions
- `server/app/exceptions/__init__.py`: Exception handlers registered in main.py

**Testing:**

- `server/tests/unit/`: Unit tests (models, schemas, utilities, services)
- `server/tests/integration/`: Integration tests (API endpoints, database, services)
- `server/tests/data/`: Test fixtures and sample data

**Database:**

- `server/alembic/`: Alembic migration scripts
- `server/alembic/env.py`: Migration configuration
- `server/app/models/`: SQLModel ORM definitions
- `server/app/database/engine.py`: AsyncEngine and session factory

## Naming Conventions

**Files:**

- Python: `snake_case.py` (e.g., `transaction_service.py`, `get_user.py`)
- TypeScript/JavaScript: `camelCase.ts` or `kebab-case.tsx` for components (e.g., `useServerStatus.ts`, `app-sidebar.tsx`)
- Models: PascalCase (e.g., `Transaction`, `User`)
- Schemas: PascalCase with descriptive suffix (e.g., `TransactionCreate`, `TransactionUpdate`, `TransactionFilters`)

**Directories:**

- Feature modules: `snake_case/` (e.g., `transaction/`, `csv_mapping/`)
- Component directories: `kebab-case/` (e.g., `app-sidebar/`, `user-panel/`)
- Utility directories: `plural_snake_case/` (e.g., `services/`, `models/`, `schemas/`)

**Functions:**

- Python: `snake_case()` (e.g., `get_user()`, `create_transaction()`, `compute_fingerprint()`)
- TypeScript: `camelCase()` hooks (`useServerStatus()`), `PascalCase()` components (`AppSidebar`)

**Variables:**

- Constants: `UPPER_SNAKE_CASE` (e.g., `AGENT_REGISTRY`, `DATABASE_URL`)
- Regular variables: `snake_case` (Python), `camelCase` (TypeScript)

**Types:**

- Python: `PascalCase` for classes, type aliases in PascalCase (e.g., `User`, `TransactionCreate`, `AsyncSession`)
- TypeScript: `PascalCase` for types and interfaces (e.g., `HealthResponse`, `Message`)

## Where to Add New Code

**New Feature (backend):**

1. Create folder in `server/app/services/{feature}/` with `service.py`, `exceptions.py`, `__init__.py`
2. Add SQLModel in `server/app/models/{feature}.py` if persistent data
3. Add Pydantic schemas in `server/app/schemas/{feature}.py`
4. Create endpoint file `server/app/api/v1/{feature}.py`
5. Include router in `server/app/api/v1/api.py` with prefix
6. Add tests in `server/tests/unit/services/test_{feature}.py` and `server/tests/integration/api/test_{feature}.py`

**New Feature (frontend):**

1. Create route folder: `web-app/src/app/(app)/{feature}/`
2. Create page component: `web-app/src/app/(app)/{feature}/page.tsx`
3. Create layout if needed: `web-app/src/app/(app)/{feature}/layout.tsx`
4. Extract components into `web-app/src/components/{feature}/` if reusable
5. Add API client function in `web-app/src/lib/api/{feature}.ts` if backend integration
6. Create hook if complex state: `web-app/src/hooks/use{Feature}.ts`

**New Component/Module:**

- Reusable components: `web-app/src/components/{category}/{component-name}.tsx`
- Custom hooks: `web-app/src/hooks/use{HookName}.ts`
- Shared utilities: `web-app/src/lib/utils.ts` or dedicated file if large
- Server services: `server/app/services/{module}/service.py`

**Utilities:**

- Shared Python helpers: `server/app/utils/{utility_name}.py`
- Shared TypeScript helpers: `web-app/src/lib/utils.ts` or feature-specific
- Constants/config: `server/app/core/config.py` (backend), `web-app/src/lib/env-helpers.ts` (frontend)

## Special Directories

**server/alembic/:**
- Purpose: Database schema migrations
- Generated: No (manually created)
- Committed: Yes (migrations are version-controlled)
- Usage: `alembic revision --autogenerate -m "migration_name"`, `alembic upgrade head`

**server/.venv/:**
- Purpose: Python virtual environment
- Generated: Yes (created by pip install)
- Committed: No (.gitignore)
- Usage: Source this for development

**web-app/node_modules/:**
- Purpose: JavaScript/TypeScript dependencies
- Generated: Yes (created by npm install)
- Committed: No (.gitignore)
- Usage: Auto-installed, never edited

**server/.pytest_cache/, server/htmlcov/:**
- Purpose: Test caching and coverage reports
- Generated: Yes (created by pytest)
- Committed: No (.gitignore)
- Usage: Artifacts from `pytest --cov`

**web-app/.next/:**
- Purpose: Next.js build cache and output
- Generated: Yes (created by next build)
- Committed: No (.gitignore)
- Usage: Deleted/recreated on each build

**server/logs/:**
- Purpose: Application runtime logs
- Generated: Yes (created by application)
- Committed: No (.gitignore)
- Usage: Local development only, structured JSON logs

---

*Structure analysis: 2026-02-26*
