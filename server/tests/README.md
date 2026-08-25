# Testing Guide

This directory contains the test suite for the FastAPI server application. The tests are organized into unit and integration tests, following pytest best practices.

## Directory Structure

```
tests/
├── conftest.py                          # Shared fixtures (DB, clients, auth helpers)
├── unit/
│   ├── conftest.py                      # Unit fixtures (no DB, resets user caches)
│   ├── schemas/test_schemas.py          # Pydantic validation
│   ├── utils/
│   │   ├── test_sanitization.py         # XSS prevention, email/password validation
│   │   ├── test_graph.py                # Message processing (dump, process, prepare)
│   │   └── test_auth_utils.py           # JWT verification (ClerkJWTVerifier)
│   ├── services/
│   │   ├── test_clerk_service.py        # Clerk API error mapping
│   │   ├── test_llm_registry.py         # Model registry lookups
│   │   ├── test_llm_service.py          # Fallback chain, retry logic
│   │   └── test_user_cache.py           # UserCache TTLs/eviction/invalidation
│   ├── config/test_settings.py          # Environment resolution, AuthSettings
│   ├── exceptions/test_exceptions.py    # Exception hierarchy, status/error codes
│   └── middleware/test_auth_middleware.py # Permissive JWT extraction
└── integration/
    ├── conftest.py                      # Auth override, mock agent, test_user fixture
    ├── services/
    │   ├── test_user_repository.py      # UserRepository CRUD, constraints
    │   ├── test_supplier_repository.py  # SupplierRepository CRUD, contact linking
    │   ├── test_conversation_service.py # ConversationService CRUD, ordering
    │   └── test_user_service.py         # JIT provisioning (mock Clerk, real DB)
    ├── api/
    │   ├── test_health.py               # /, /health, /ready
    │   ├── test_auth.py                 # /api/v1/auth/me — 401, profile response
    │   ├── test_conversations.py        # Conversation CRUD endpoints, ownership
    │   └── test_chatbot.py              # Chat, stream, history — mock agent
    ├── dependencies/
    │   ├── test_database.py             # Error translation, RLS context set/clear
    │   └── test_conversation_access.py  # 403 vs 404 ownership enforcement
    └── exceptions/
        └── test_handlers.py             # Exception → HTTP mapping, no info leakage
```

## Setup

```bash
# Install dependencies
uv sync --group test

# Integration tests additionally need a running Docker daemon
```

The test database runs in a throwaway container started by
[testcontainers](https://testcontainers.com/) (`postgres_container` in
`tests/conftest.py`) — no `createdb`, no `.env.test` database settings, and no
port to configure. It gets an ephemeral host port, so it never collides with
the dev database on 5434, and it is torn down at the end of the session.

The fixture is lazy: only integration tests reach it (via `test_engine` →
`db_session`), so `make test-unit` starts no container.

## Running Tests

```bash
# All tests
make test

# Unit only (fast, no DB)
make test-unit

# Integration only
make test-integration

# With coverage report
make test-coverage
```

Direct pytest (from `server/`):

```bash
# Run a specific file
python -m pytest tests/unit/utils/test_sanitization.py -v

# Run a specific test
python -m pytest tests/integration/api/test_auth.py::TestGetMe::test_authenticated_returns_200 -v

# Run by marker
python -m pytest -m unit
python -m pytest -m integration

# Stop on first failure
python -m pytest -x

# Re-run last failures
python -m pytest --lf
```

## Key Design Decisions

**Unit tests** — no DB, no network. External calls mocked via `unittest.mock.patch`. Every file has `pytestmark = pytest.mark.unit`.

**Integration tests** — real test DB (savepoint rollback — all writes auto-undone after each test). External services mocked:
- **Auth**: `get_current_user` overridden via `app.dependency_overrides` → returns `test_user` directly, bypassing JWT + JIT provisioning
- **Agent**: `get_chatbot_agent` overridden with `AsyncMock` → no OpenAI calls
- **Clerk**: patched at `app.services.user.service.clerk_service` where needed

## Fixtures

### Shared (`tests/conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `db_session` | function | AsyncSession with savepoint rollback |
| `client` | function | AsyncClient with `get_db_session` overridden |
| `unauthenticated_client` | function | AsyncClient, no auth override |
| `reset_app_state` | function (autouse) | Clears `dependency_overrides` before/after |

### Integration (`tests/integration/conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_user` | function | User created in DB for the current test |
| `authenticated_client` | function | `client` + `get_current_user → test_user` |
| `mock_agent` | function | MagicMock ChatbotAgent with AsyncMock methods |
| `authenticated_client_with_agent` | function | `authenticated_client` + `get_chatbot_agent → mock_agent` |

## Markers

```python
pytestmark = pytest.mark.unit        # every unit test file
pytestmark = pytest.mark.integration # every integration test file

@pytest.mark.slow  # external API calls (skipped in CI fast mode)
```

## Coverage

```bash
python -m pytest tests/unit -m unit --cov=app --cov-report=term-missing
python -m pytest tests/integration -m integration --cov=app --cov-report=html
open htmlcov/index.html
```
