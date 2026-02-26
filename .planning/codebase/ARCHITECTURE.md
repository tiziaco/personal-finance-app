# Architecture

**Analysis Date:** 2026-02-26

## Pattern Overview

**Overall:** Fullstack application with clear separation of concerns using FastAPI backend (Python) and Next.js frontend (TypeScript). Backend follows a service-oriented pattern with distinct layers for API, business logic, and persistence. Frontend uses Next.js App Router with server/client component architecture.

**Key Characteristics:**
- Async-first design (FastAPI + SQLAlchemy async ORM, Next.js async components)
- Middleware-based cross-cutting concerns (auth, logging, rate limiting, CORS)
- LangGraph-powered AI agents with persistent state checkpointing
- Type-safe API contracts (Pydantic models on backend, Zod schemas on frontend)
- User authentication via Clerk with JWT tokens
- PostgreSQL with SQLModel ORM for type-safe database operations

## Layers

**API Layer:**
- Purpose: HTTP endpoint definitions and request/response handling
- Location: `server/app/api/`
- Contains: Route handlers organized by feature (`auth.py`, `transactions.py`, `chatbot.py`, `insights.py`, `analytics.py`, `conversation.py`), dependencies for DI, middleware, system endpoints
- Depends on: Service layer, database dependencies, authentication
- Used by: Web-app frontend, external integrations

**Service Layer:**
- Purpose: Business logic and orchestration (stateless operations)
- Location: `server/app/services/`
- Contains: Transaction operations (`transaction/service.py`), user management (`user/`), conversation handling, analytics, insights, LLM interactions, CSV processing, Clerk sync
- Depends on: Database models, repositories, external services (Clerk API, LLM providers)
- Used by: API endpoints, agents

**Database/Persistence Layer:**
- Purpose: Data access and ORM abstractions
- Location: `server/app/database/`, `server/app/models/`
- Contains: Engine initialization (`database/engine.py`), session management, SQLModel model definitions (`models/`), transaction fingerprinting for deduplication
- Depends on: PostgreSQL async driver (asyncpg), SQLModel
- Used by: Services, agents

**Agent Layer:**
- Purpose: LangGraph-based AI workflows for multi-turn conversations and transaction labeling
- Location: `server/app/agents/`
- Contains: Base agent abstraction (`base/agent.py`), chatbot agent (`chatbot/graph.py`), transaction labeler agent, insights agent, factory pattern for agent initialization (`factory.py`), checkpointing and memory management (`shared/`)
- Depends on: LangGraph, LangChain, LLM providers, memory backends (Mem0, PostgreSQL checkpointer)
- Used by: Chatbot and conversation endpoints

**Configuration & Infrastructure:**
- Purpose: Application setup, settings, logging, metrics, observability
- Location: `server/app/core/`
- Contains: Environment configuration (`config.py`), structured logging (`logging.py`), rate limiting (`limiter.py`), metrics collection (`metrics.py`)
- Depends on: Python environment, Langfuse, Prometheus
- Used by: All layers during startup and throughout request lifecycle

**Frontend Application Layer:**
- Purpose: User interface and client-side routing
- Location: `web-app/src/app/`
- Contains: Root layout with authentication and providers, route groups for authenticated pages `(app)/` and auth pages `(auth)/`
- Depends on: Next.js, Clerk, React Query
- Used by: End users

**Frontend Component/Library Layer:**
- Purpose: UI components, hooks, API clients, utilities
- Location: `web-app/src/components/`, `web-app/src/hooks/`, `web-app/src/lib/`, `web-app/src/providers/`
- Contains: Reusable UI components (`components/ui/`), layout components, settings components, custom React hooks, API health checks, environment helpers, React Query provider
- Depends on: React, TailwindCSS, shadcn/ui, BaseUI
- Used by: Pages and other components

## Data Flow

**User Authentication Flow:**

1. User navigates to app → Next.js root layout checks Clerk auth
2. Unauthenticated users redirected to `/sign-in`
3. Authenticated request includes Clerk JWT token
4. FastAPI `AuthMiddleware` (executed via ASGI stack) extracts and verifies JWT
5. Sets `request.state.clerk_id` from token
6. Endpoint dependency `get_current_user` looks up user by `clerk_id` (cache → DB → Clerk API)
7. JIT user provisioning creates user record on first access
8. `request.state.user_id` (internal UUID) stored for logging and database context

**Transaction Crud Flow:**

1. Frontend sends request to `/api/v1/transactions/{id}` with auth header
2. API endpoint gets `DbSession` (dependency creates session, sets RLS context)
3. Endpoint calls `TransactionService.get()` with user_id (from auth context)
4. Service queries database with user_id condition (prevents cross-user access)
5. Transaction returned with fingerprint (SHA-256 hash for deduplication)
6. Response serialized via Pydantic schema and sent to frontend

**Conversation/Agent Flow:**

1. Frontend sends message to `/api/v1/chatbot/message` or `/api/v1/conversation/message`
2. API retrieves agent from `app.state.agents` (pre-compiled graph)
3. Agent's `get_response()` or `get_stream_response()` called
4. Memory retrieval: queries Mem0 for relevant past context based on current message
5. LangGraph executes compiled workflow with state (messages, long_term_memory)
6. State persisted via `AsyncPostgresSaver` (PostgreSQL checkpointer)
7. Response streamed back to client via SSE or returned as complete message

**State Management:**

- **Request State:** Authentication context, user_id, correlation IDs (set via middleware, available to endpoints)
- **Application State:** Session factory, database engine, pre-compiled agents, rate limiter (initialized at startup in lifespan context manager)
- **Database State:** Transactions stored in PostgreSQL with timestamps, soft-delete support, fingerprinting for duplicate detection
- **Agent State:** Conversation history persisted in PostgreSQL via LangGraph checkpointer, memory in Mem0 service, thread_id used as conversation identifier

## Key Abstractions

**BaseAgent:**
- Purpose: Abstract base class for all LangGraph agents (chatbot, transaction labeler, insights)
- Examples: `server/app/agents/chatbot/graph.py`, `server/app/agents/transactions_labeler/agent.py`, `server/app/agents/insights/agent.py`
- Pattern: Template Method + Strategy. Each subclass implements `create_graph()` to define workflow. `get_response()` and `get_stream_response()` provide common streaming/non-streaming interface. Pre-compiled at startup, not per-request.

**Service Pattern:**
- Purpose: Stateless business logic encapsulation with static methods
- Examples: `server/app/services/transaction/service.py`, `server/app/services/user/service.py`, `server/app/services/insights/service.py`
- Pattern: Services expose static async methods (no instance state). Dependencies injected via function parameters. Logging integrated throughout.

**Repository Pattern:**
- Purpose: Data access abstraction (currently used for User, could extend to other models)
- Examples: `server/app/services/user/service.py` (contains UserRepository inline)
- Pattern: Static methods for CRUD operations. Scoped to single user (JIT provisioning, ownership checks).

**Dependency Injection via FastAPI Depends:**
- Purpose: Provide request-scoped dependencies (database sessions, auth, agents)
- Examples: `server/app/api/dependencies/database.py` (DbSession), `server/app/api/dependencies/auth.py` (get_current_user)
- Pattern: Async generator functions that setup/teardown resources. Type-annotated for clarity. Exceptions converted to domain exceptions.

**Middleware Stack (Execution Order):**
1. SecurityHeadersMiddleware (outermost, applies to all responses)
2. CorrelationIdMiddleware (generates request IDs)
3. setup_cors middleware (CORS handling)
4. AccessLogMiddleware (HTTP request/response logging)
5. AuthMiddleware (JWT verification, sets request.state.clerk_id)
6. LoggingContextMiddleware (binds clerk_id to logging context)
7. MetricsMiddleware (Prometheus metrics collection)

## Entry Points

**Backend:**
- Location: `server/app/main.py`
- Triggers: Server startup (uvicorn)
- Responsibilities:
  - FastAPI app initialization
  - Middleware setup and ordering
  - Exception handler registration
  - Lifespan context manager (database, agent, checkpointer initialization)
  - Router inclusion (system endpoints, versioned v1 API)

**Frontend Root:**
- Location: `web-app/src/app/layout.tsx`
- Triggers: Browser page load
- Responsibilities:
  - ClerkProvider wraps entire app
  - QueryProvider initializes React Query client
  - ThemeProvider for dark/light mode
  - Root HTML structure with fonts and global styles
  - Toaster for notifications

**Frontend App Layout:**
- Location: `web-app/src/app/(app)/layout.tsx`
- Triggers: All authenticated page loads
- Responsibilities:
  - SidebarProvider + navigation sidebar
  - Outlet for nested route pages
  - Frame structure (sidebar + main content area)

**Home Page:**
- Location: `web-app/src/app/page.tsx`
- Triggers: `/` route access
- Responsibilities:
  - Checks authentication (middleware)
  - Redirects authenticated users to `/home`
  - Only accessible to authenticated users

## Error Handling

**Strategy:** Hierarchical exception handling with domain exceptions converted to HTTP responses.

**Patterns:**

1. **Domain Exceptions (app/exceptions/base.py):**
   - ServiceError (base for all domain errors)
   - AuthenticationError (auth failures)
   - TransactionNotFoundError (resource not found)
   - DatabaseConflictError (constraint violations)
   - DatabaseConnectionError (connection issues)

2. **Exception Handlers (app/exceptions/ + main.py):**
   - RequestValidationError → 422 Unprocessable Entity (Pydantic validation)
   - ServiceError → 400/403/404 (domain-specific status)
   - RateLimitExceeded → 429 Too Many Requests
   - Exception (catch-all) → 500 Internal Server Error with correlation ID for tracing

3. **Database Session Handling:**
   - IntegrityError (unique constraints) → DatabaseConflictError
   - OperationalError (connection issues) → DatabaseConnectionError
   - DBAPIError (generic DB errors) → DatabaseError
   - All caught and rolled back in dependency

4. **Async Agent Errors:**
   - Caught in `BaseAgent.get_response()` and `get_stream_response()`
   - Logged with conversation_id for debugging
   - Re-raised or wrapped appropriately

## Cross-Cutting Concerns

**Logging:** Structured logging via structlog (`server/app/core/logging.py`). All log entries are JSON with context fields (user_id, correlation_id, transaction_id, etc.). LoggingContextMiddleware binds clerk_id to context, persisted throughout request lifecycle.

**Validation:** Pydantic models for all API request/response bodies (`server/app/schemas/`). SQLModel for database models. Zod for frontend forms. Backend validates before service methods, frontend validates before API calls.

**Authentication:** Clerk JWT tokens + internal UUID user records. AuthMiddleware extracts token, verifies signature. get_current_user dependency does JIT user creation. RLS context set at session level to prevent cross-user data access at DB layer.

**Rate Limiting:** slowapi library with configurable limits per endpoint. Limiter instance initialized at startup, attached to app.state. RateLimitExceeded exceptions converted to 429 responses.

**Observability:**
  - Langfuse integration for agent/LLM tracing (configured in main.py)
  - Prometheus metrics via starlette-prometheus middleware
  - Correlation IDs on all requests (asgi-correlation-id)
  - Structured logging with JSON output

**Data Privacy/GDPR:**
  - User model implements AnonymizableMixin with anonymize_user() method
  - Soft deletes (deleted_at timestamp) for non-destructive data removal
  - Transaction fingerprinting prevents duplicate imports (deduplication efficiency)
  - RLS context prevents accidental cross-user queries

---

*Architecture analysis: 2026-02-26*
