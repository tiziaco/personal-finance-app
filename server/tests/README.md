# Testing Guide

The server's test suite, split into unit and integration tests. The layout rule, the
`make` targets and the testing lessons are in [`../CLAUDE.md`](../CLAUDE.md) under
**Testing**; this file covers the fixtures and how the two layers isolate.

## Layout

`tests/` mirrors `app/`: a test for `app/modules/account/cache.py` is
`tests/unit/modules/account/test_cache.py`, or under `tests/integration/modules/account/`
if it needs the database. Route tests sit under `tests/integration/modules/<name>/router/`.
Files are not listed here — the tree is the list, and a copy of it goes stale on the next
commit.

## Setup

```bash
uv sync --group test   # integration tests also need a running Docker daemon
```

The test database runs in a throwaway container started by
[testcontainers](https://testcontainers.com/) (`postgres_container` in
`tests/conftest.py`) — no `createdb`, no `.env.test` database settings, and no port to
configure. It gets an ephemeral host port, so it never collides with the dev database,
and it is torn down at the end of the session.

The fixture is lazy: only integration tests reach it (via `test_engine` → `db_session`),
so `make test-unit` starts no container.

## Running a subset

`conftest.py` sets `APP_ENV=test` itself; the `make` targets set it too. From `server/`:

```bash
uv run pytest tests/unit/modules/account/test_cache.py -v   # one file
uv run pytest -k "test_name"                                # by name
uv run pytest -m unit                                       # by marker
uv run pytest -x --lf                                       # stop on first failure, re-run last failures
```

## How the layers isolate

**Unit tests** — no database, no network. External calls are mocked with
`unittest.mock.patch`. Every file sets `pytestmark = pytest.mark.unit`.

**Integration tests** — a real database, with savepoint rollback: every write is undone
after each test. External services are mocked:

- **Auth**: `get_current_user` overridden via `app.dependency_overrides` → returns
  `test_user` directly, bypassing JWT verification and JIT provisioning
- **Agent**: `get_chatbot_agent` overridden with a mock → no LLM calls
- **Clerk**: patched where the service uses it, e.g.
  `app.modules.account.service.clerk_client.get_user`
- **Checkpoints**: `stub_checkpoint_deletion`, because the checkpoint tables sit behind a
  connection pool no integration test opens

## Fixtures

### Shared (`tests/conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `db_session` | function | `AsyncSession` with savepoint rollback |
| `client` | function | `AsyncClient` with `get_db_session` overridden to `db_session` |
| `unauthenticated_client` | function | `AsyncClient`, no overrides |
| `reset_app_state` | function (autouse) | Clears `dependency_overrides` before and after |

### Unit (`tests/unit/conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `clear_user_cache` | function (autouse) | Resets the user cache |

### Integration (`tests/integration/conftest.py`)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `clear_user_cache` | function (autouse) | Resets the user cache |
| `test_user` | function | A user created in the database for the current test |
| `authenticated_client` | function | `client` + `get_current_user → test_user` |
| `mock_agent` | function | Mock `ChatbotAgent` with async method stubs |
| `authenticated_client_with_agent` | function | `authenticated_client` + `get_chatbot_agent → mock_agent` |
| `stub_checkpoint_deletion` | function | Stubs LangGraph checkpoint deletion; yields the erasure path's stub |

## Markers

```python
pytestmark = pytest.mark.unit        # every unit test file
pytestmark = pytest.mark.integration # every integration test file

@pytest.mark.slow  # external API calls; `make test-fast` skips them
```
