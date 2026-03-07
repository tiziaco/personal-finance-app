# Testing Patterns

**Analysis Date:** 2026-02-26

## Test Framework

**Runner:**
- **Backend (Python)**: `pytest` 8.3.5+
  - Config: `pytest.ini` (primary) and `pyproject.toml` (backup)
  - Async support: `pytest-asyncio` 0.25.2+

- **Frontend (TypeScript)**: Not detected - no test framework configured

**Assertion Library:**
- Python: Standard `assert` statements with pytest

**Run Commands:**
```bash
# Backend - all tests
pytest

# Backend - watch mode (not configured)
# Not directly supported; use pytest-watch or IDE integration

# Backend - coverage
pytest --cov=app --cov-report=html --cov-report=xml --cov-report=term-missing

# Coverage report
# HTML: htmlcov/index.html
# XML: coverage.xml
# Terminal: inline in pytest output
```

## Test File Organization

**Location (Python):**
- Separate `tests/` directory at project root
- Mirror source structure: `tests/unit/`, `tests/integration/`
- Test data: `tests/data/` contains CSV fixtures (e.g., `test_transactions_10.csv`)

**Naming (Python):**
- Test modules: `test_*.py` or `*_test.py`
- Test classes: `Test*` (e.g., `class TestGetEnvironment`, `class TestAuthSettings`)
- Test functions: `test_*` (e.g., `def test_environment_resolution()`)

**Structure:**
```
tests/
├── conftest.py                    # Shared fixtures (DB, HTTP client, auth)
├── data/                          # CSV test data
│   ├── test_transactions_10.csv
│   ├── test_transactions_2_months.csv
│   ├── test_transactions_400.csv
├── unit/
│   ├── conftest.py               # Unit test fixtures (cache, mocks)
│   ├── config/
│   │   └── test_settings.py
│   ├── middleware/
│   │   └── test_auth_middleware.py
│   ├── tools/
│   │   └── test_financial_tools.py
│   └── utils/
│       └── test_sanitization.py
└── integration/
    ├── conftest.py               # Integration fixtures (DB, agents, auth overrides)
    └── dependencies/
        ├── test_database.py
        └── test_conversation_access.py
```

## Test Structure

**Suite Organization (Python):**

```python
"""Module docstring describing what's being tested."""

import pytest

pytestmark = pytest.mark.unit  # or integration

class TestFunctionName:
    """Test class for a specific function or feature."""

    @pytest.mark.parametrize(
        "input_value,expected",
        [
            ("case1", expected1),
            ("case2", expected2),
        ],
        ids=["description1", "description2"]
    )
    def test_behavior_with_various_inputs(self, input_value, expected):
        """Test specific behavior."""
        assert result == expected

    def test_error_case(self):
        """Test error handling."""
        with pytest.raises(ValueError):
            function_that_raises()
```

**Patterns:**
- Class-based test organization (not functions at module level)
- `@pytest.mark.parametrize` for data-driven tests with custom `ids` for readability
- Docstrings on test functions describing what's being tested
- `pytestmark` at module level to apply markers to all tests in file

## Mocking

**Framework:**
- `unittest.mock` - `MagicMock`, `AsyncMock`, `patch`
- `pytest-mock` - `mocker` fixture

**Patterns:**

```python
# From tests/integration/conftest.py - AsyncMock pattern
@pytest.fixture
def mock_agent():
    """Mock ChatbotAgent with pre-configured async method stubs."""
    agent = MagicMock()
    agent.get_response = AsyncMock(return_value=[...])
    agent.get_chat_history = AsyncMock(return_value=[...])
    agent.clear_chat_history = AsyncMock(return_value=None)
    agent.llm_service.get_llm.return_value.get_name.return_value = "gpt-5-mini"
    agent.is_ready.return_value = True
    return agent
```

**Dependency Injection via Overrides:**
```python
# Inject mock into FastAPI dependency system
app.dependency_overrides[get_current_user] = lambda: test_user
app.dependency_overrides[get_chatbot_agent] = lambda: mock_agent

# Cleanup after test
app.dependency_overrides.clear()
```

**What to Mock:**
- External services (OpenAI API, Clerk auth) - use mock fixtures
- Database-dependent code in unit tests
- LLM agents in isolation tests

**What NOT to Mock:**
- Core application logic that defines behavior
- Database in integration tests (use real test DB)
- Authentication in integration tests (override dependency instead)

## Fixtures and Factories

**Test Data (Python):**

```python
# Static fixture from tests/conftest.py
@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response for LLM testing."""
    return {
        "id": "chatcmpl-test123",
        "choices": [{"message": {"content": "..."},}],
        "usage": {"total_tokens": 30},
    }

# Database fixture
@pytest_asyncio.fixture(scope="function")
async def transactions_10(db_session, test_user):
    """10 transactions from test_transactions_10.csv."""
    for t in _load_transactions_from_csv("tests/data/test_transactions_10.csv", test_user, db_session):
        db_session.add(t)
    await db_session.flush()
```

**Location:**
- `tests/conftest.py` - Shared across unit and integration (DB, HTTP client, auth)
- `tests/unit/conftest.py` - Unit-only (cache clearing)
- `tests/integration/conftest.py` - Integration-only (real DB, agents, transaction fixtures)

**Factory Pattern:**
```python
def _load_transactions_from_csv(path: str, test_user, db_session):
    """Helper: read CSV, override user_id, return Transaction list."""
    df = pl.read_csv(path)
    transactions = []
    for row in df.iter_rows(named=True):
        t = Transaction(
            user_id=test_user.id,
            date=parsed_date,
            amount=Decimal(str(row["amount"])),
            ...
        )
        transactions.append(t)
    return transactions
```

## Coverage

**Requirements:** No hard limit enforced (`--cov-fail-under=0` in pyproject.toml)

**View Coverage:**
```bash
# Run with coverage
pytest --cov=app --cov-report=html

# Open HTML report
open htmlcov/index.html

# Terminal output shows missing lines
pytest --cov=app --cov-report=term-missing
```

**Configuration (`pytest.ini`):**
```
[coverage:run]
source = app
omit =
    */tests/*
    */migrations/*
    */__pycache__/*

[coverage:report]
precision = 2
show_missing = True
skip_covered = False
```

## Test Types

**Unit Tests (Python):**
- **Scope**: Single function or class, no database, no external services
- **Location**: `tests/unit/`
- **Marker**: `@pytest.mark.unit`
- **Approach**:
  - Test configuration parsing (`test_settings.py`)
  - Test utility functions in isolation
  - Use mocks/monkeypatch for environment vars
  - Fast execution (<1ms per test typically)

Example:
```python
class TestGetEnvironment:
    """Tests for get_environment() function."""

    @pytest.mark.parametrize(
        "env_value,expected",
        [("production", Environment.PRODUCTION), ("dev", Environment.DEVELOPMENT)],
        ids=["production", "dev"],
    )
    def test_environment_resolution(self, monkeypatch, env_value, expected):
        monkeypatch.setenv("APP_ENV", env_value)
        assert get_environment() == expected
```

**Integration Tests (Python):**
- **Scope**: Full API endpoints, real database (test instance), mocked external services
- **Location**: `tests/integration/`
- **Marker**: `@pytest.mark.integration`
- **Approach**:
  - Test database fixtures (create DB, create/drop tables per session)
  - HTTP client with authenticated requests
  - Real transaction data from CSV files
  - Dependency overrides for mocks (agents, auth)
  - Database auto-rollback after each test

Example:
```python
@pytest_asyncio.fixture
async def authenticated_client(client, test_user):
    """HTTP client with get_current_user overridden to return test_user."""
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)

@pytest.mark.integration
async def test_create_transaction(authenticated_client):
    response = await authenticated_client.post("/api/v1/transactions", json={...})
    assert response.status_code == 201
```

**E2E Tests:**
- Not implemented in current codebase

## Async Testing (Python)

**Pattern:**
```python
@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test."""
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        yield session
        await session.close()
        await trans.rollback()

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result == expected
```

**Configuration (`pytest.ini`):**
```
asyncio_mode = auto
asyncio_default_fixture_loop_scope = session
asyncio_default_test_loop_scope = session
```

All async tests automatically run with pytest-asyncio without explicit marker.

## Error Testing (Python)

**Pattern:**
```python
# From test_settings.py
def test_jwks_url_derived_from_issuer(self):
    """Test derived property computation."""
    auth = AuthSettings(ISSUER="https://clerk.example.com")
    assert auth.jwks_url == "https://clerk.example.com/.well-known/jwks.json"

def test_enum_is_string(self):
    """Test enum type."""
    assert isinstance(Environment.PRODUCTION, str)
    assert Environment.PRODUCTION == "production"

@pytest.mark.asyncio
async def test_database_connection_failure(test_engine):
    """Test error handling on connection failure."""
    # Simulate failure
    with pytest.raises(Exception):
        await test_database_connection(bad_engine)
```

## Common Test Fixtures

**Database Fixtures (session-scoped):**
- `test_database_url()` - PostgreSQL test DB URL
- `ensure_test_database()` - Creates test DB if missing
- `test_engine()` - SQLAlchemy async engine with table creation/cleanup
- `db_session()` - Per-test session with automatic rollback

**HTTP Client Fixtures (function-scoped):**
- `client()` - Authenticated async HTTP client with DB override
- `unauthenticated_client()` - Public HTTP client (no auth, no DB session)
- `authenticated_client()` (integration only) - Client with test user auto-injected

**Auth Fixtures:**
- `mock_clerk_user_id()` - Returns test user ID string
- `mock_jwt_token()` - Returns mock JWT token
- `auth_headers()` - Returns `{"Authorization": "Bearer {token}"}`

**Mock Service Fixtures:**
- `mock_openai_response()` - Mocked GPT API response
- `mock_agent()` - Mocked `ChatbotAgent` with async method stubs
- `test_user()` (integration) - Real user in test DB

**Data Fixtures (integration):**
- `transactions_single()` - 1 transaction (edge cases)
- `transactions_10()` - 10 transactions (same month)
- `transactions_2_months()` - ~90 transactions (2 months)
- `transactions_400()` - ~400 transactions (3 years)
- `transactions_income_only()` - Single income transaction

## Markers

**Defined Markers (`pytest.ini`):**
- `@pytest.mark.unit` - Fast unit tests (no DB, no network)
- `@pytest.mark.integration` - Integration tests (uses DB, mocked services)
- `@pytest.mark.slow` - Slow tests (external API calls)
- `@pytest.mark.asyncio` - Async tests (auto-applied by pytest-asyncio)

**Usage:**
```bash
# Run only unit tests
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# Run integration tests with strict marker checking
pytest -m integration --strict-markers
```

## Test Output Configuration

**Options (`pytest.ini`):**
```
addopts =
    -ra                          # Show extra test summary for all except passed
    --strict-markers             # Enforce defined markers only
    --strict-config              # Enforce valid config
    --showlocals                 # Show local variables on failure
    --tb=short                   # Shorter traceback format
```

---

*Testing analysis: 2026-02-26*
