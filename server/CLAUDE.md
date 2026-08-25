# Server — FastAPI Backend

Continuation of the root `CLAUDE.md`. Covers `server/` conventions only — no repeated project or stack overview.

---

## Running the Server

All commands below run from `server/`. For the full Docker stack, use root `make` commands (see root `CLAUDE.md`).

```bash
make install          # pip install uv + uv sync
make dev              # dev server on :8000 (hot reload, APP_ENV=development)
make staging          # uvicorn in staging env
make prod             # uvicorn in production env
```

Env file is selected by `APP_ENV`. Copy `.env.development.example` → `.env.development` before first run.

### Server-only Docker

```bash
make docker-run                       # dev stack: app + db (APP_ENV=development)
make docker-run-env ENV=staging       # specific environment
make docker-run-db ENV=development    # database only
make docker-logs ENV=development      # follow app + db logs
make docker-stop ENV=development      # stop containers
```

### Database Migrations (Alembic)

```bash
make migrate ENV=development                          # apply all pending migrations
make migrate-create ENV=development MSG='add orders'  # generate new migration
make migrate-downgrade ENV=development                # rollback one step (REV=-1 default)
make migrate-history ENV=development                  # show migration history
make migrate-current ENV=development                  # show current revision
```

### Linting

```bash
make lint     # ruff check
make format   # ruff format
```

---

## Directory Structure

```
server/
├── app/
│   ├── api/
│   │   ├── v1/              # Route handlers: auth.py, chatbot.py, conversation.py
│   │   ├── dependencies/    # FastAPI deps: db session, current user, conversation ownership
│   │   ├── middlewares/     # Auth (JWT), access logging, correlation ID, rate limiting
│   │   └── system/          # Health + Prometheus metrics endpoints
│   ├── agents/
│   │   ├── base/            # Abstract BaseAgent class
│   │   ├── shared/          # memory/, checkpointing/, observability/
│   │   └── chatbot/         # graph.py, state.py, prompts/, tools/
│   ├── core/                # Settings (config.py), app factory
│   ├── database/            # Async engine, session factory
│   ├── exceptions/          # base.py — exception hierarchy
│   ├── models/              # SQLModel ORM models (user.py, conversation.py)
│   ├── schemas/             # Pydantic request/response schemas
│   ├── services/            # Business logic: user/, conversation/, llm/
│   └── utils/               # Shared utilities
└── tests/
    ├── unit/                # No external deps — middleware, models, schemas, services, utils
    └── integration/         # Requires DB — dependencies, API routes, services
```

---

## Code Conventions

- `async def` everywhere — no blocking I/O
- Type hints on all function signatures
- Pydantic models over raw dicts (RORO pattern)
- File names: `lowercase_with_underscores.py`
- All imports at the top of the file — never inside functions

---

## Logging (structlog)

```python
# ✅ Correct
logger.info("document_uploaded", supplier_id=supplier_id, doc_type=doc_type)
logger.exception("db_query_failed", table="documents")

# ❌ Wrong
logger.info(f"Document {doc_id} uploaded")  # no f-strings in events
logger.error("something failed")            # use .exception() to preserve tracebacks
```

- Event names: `lowercase_with_underscores`
- Variables as kwargs, never interpolated into the event string
- HTTP access logs → `AccessLogMiddleware` (never log manually in routes)
- Bind component context: `logger.bind(component="service")`
- All requests get a `correlation_id` via `asgi-correlation-id` — auto-bound to logs and included in error responses

---

## Exception Handling

Services raise domain exceptions; the centralized handler translates them to HTTP. **Never** raise `HTTPException` from services. **Never** add try/except in route handlers.

```python
# In a service
from app.services.documents.exceptions import DocumentNotFoundError
raise DocumentNotFoundError("Document not found", document_id=doc_id)

# In a route — no try/except needed
@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    return await document_service.get(doc_id)
```

Base exceptions live in `app/exceptions/base.py`:

| Class | HTTP |
|---|---|
| `NotFoundError` | 404 |
| `AuthenticationError` | 401 |
| `AuthorizationError` | 403 |
| `ConflictError` | 409 |
| `ValidationError` | 422 |
| `DatabaseError` | 500/503 |

Each service package defines its own exceptions extending these. New service exceptions go in `app/services/<name>/exceptions.py`.

---

## Authentication

- Clerk JWTs verified by `AuthMiddleware` (RS256); `clerk_id` set on `request.state`
- Use `CurrentUser` dependency for protected endpoints:
  ```python
  async def endpoint(user: Annotated[User, Depends(get_current_user)]):
  ```
- Users are JIT-provisioned in the local DB on first request via `UserService`
- Conversation ownership enforced by the `UserConversation` dependency

---

## Settings Access

Pydantic nested models in `app/core/config.py`. Domains: `database`, `llm`, `langfuse`, `memory`, `auth`, `logging`, `rate_limits`, `cors`, `evaluation`.

```python
# ✅ Correct — unpack SecretStr
api_key = settings.llm.OPENAI_API_KEY.get_secret_value()

# ❌ Wrong — returns SecretStr object, not the string
api_key = settings.llm.OPENAI_API_KEY
```

---

## Agent Architecture

All agents extend `BaseAgent` (`app/agents/base/`) and must implement `create_graph()`.

**Shared components:**
- `app/agents/shared/memory/` — `get_relevant_memory()`, `update_memory()`, `delete_user_memory()`
- `app/agents/shared/checkpointing/` — `AsyncPostgresSaver` for LangGraph persistence
- `app/agents/shared/observability/` — `create_graph_config()` wires Langfuse callbacks

`BaseAgent` provides `get_response()`, `get_stream_response()`, `get_chat_history()`, `clear_chat_history()` with memory and tracing built in. All LLM calls must have Langfuse tracing. All retries must use `tenacity` with exponential backoff.

---

## Testing

Tests live in `server/tests/` split into two layers:

```
tests/
├── unit/          # Pure logic, no external deps — mock everything external
│   ├── api/       # Dependency logic (auth, etc.)
│   ├── config/    # Settings loading
│   ├── exceptions/
│   ├── middleware/
│   ├── models/
│   ├── schemas/
│   ├── services/  # Service logic with mocked DB/Clerk/LLM
│   └── utils/
└── integration/   # Requires a live DB connection
    ├── api/       # Full route tests via TestClient
    ├── dependencies/
    └── services/
```

Run from `server/`:

```bash
make test              # all tests (APP_ENV=test)
make test-unit         # unit tests only
make test-integration  # integration tests only
make test-coverage     # all tests + HTML/XML coverage report
make test-fast         # all tests, skipping slow ones

# Target a specific file or test name
APP_ENV=test uv run pytest tests/unit/services/test_user_cache.py
APP_ENV=test uv run pytest -k "test_name"
```

Coverage is reported automatically (`--cov=app`). HTML report written to `htmlcov/`.

New tests mirror the `app/` structure: a test for `app/services/user/cache.py` goes in `tests/unit/services/test_user_cache.py`. Unit tests mock external deps (DB, Clerk, LLM); integration tests use a real DB.

---

## GDPR — Right to Erasure

When a user is deleted (`DELETE /api/v1/auth/me`), in order:

1. Clerk deletion (JWTs immediately invalidated)
2. LangGraph checkpoints hard-deleted (`clear_chat_history`)
3. mem0 memories deleted (`delete_user_memory`)
4. User PII anonymized via `AnonymizableMixin.anonymize_user()`
5. Conversation records soft-deleted

Rules:
- Never use `SoftDeleteMixin` on `User` — it leaves PII in the DB
- New models with PII must implement `AnonymizableMixin` and an `anonymize_*()` method
- Always call `agent.clear_chat_history()` before soft-deleting a conversation
