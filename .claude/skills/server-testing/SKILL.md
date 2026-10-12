---
name: server-testing
description: >
  Writing, running and debugging tests for the FastAPI server (pytest, pytest-asyncio, a testcontainers
  Postgres). Use when adding or changing a test under server/tests/, choosing unit or integration, picking a
  client fixture, testing an ownership 404, an event subscriber or a webhook, mocking Clerk or
  the agent, touching a conftest.py, or debugging a test that fails for no obvious reason or silently never
  runs. Trigger on "write a test for X", "add tests", "this test fails", "make test-unit doesn't run my test",
  "500 instead of 429", "Docker is not running", a failing test_module_contracts,
  test_owned_tables or test_openapi_contract, or any work on server/tests/.
---

# Server Testing

pytest configured by `server/pytest.ini`: `asyncio_mode = auto` (no `@pytest.mark.asyncio`), one
session-scoped event loop for every fixture and test. A throwaway Postgres is started by testcontainers. Two files already cover the basics, and this skill does not restate them:

- `server/tests/README.md`: the fixtures (tables for all three conftests), how the layers isolate,
  running a subset. **Read it before picking a fixture.**
- `server/CLAUDE.md` § Testing: the layout (`tests/` mirrors `app/`, one file per slot, route tests under
  `tests/integration/modules/<name>/router/`) and the `make` targets.

```bash
make test-unit            # from server/; -m unit, starts no container
make test-integration     # -m integration; needs a running Docker daemon
uv run pytest tests/unit/modules/account/test_cache.py   # one file; conftest sets APP_ENV=test
```

A `DockerException` at fixture setup means the daemon is down. Only integration tests reach the
container, so unit tests still run.

## Does it earn a test?

A branch, a query, a mapping, a guard, an ordering that is contractual (`erase_user`'s cascade).
Not a pass-through. **A test written after its subject proves nothing until it has failed once:**
break the line it pins, watch it go red, then `git checkout -- <file>`. A test for a route not written
yet goes red as a 404 first.

| It touches | Layer | Session |
|---|---|---|
| Only Python: a service's branching, a handler, a mapper | unit | `AsyncMock()` with `s.add = MagicMock()` (`add` is sync) |
| SQL, a route, a dependency chain | integration | `db_session`, rolled back after every test |

## Traps

### 1. A file without `pytestmark` never runs under `make`

`make test-unit` selects `-m unit`, `make test-integration` selects `-m integration`. A test file without
`pytestmark = pytest.mark.unit` (or `.integration`) passes when run by path and is **deselected** by
the target, with only `N deselected` in the summary. A `pytestmark` in a `conftest.py` marks
nothing: pytest reads it from test modules only. Check with
`uv run pytest tests/unit -m "not unit" --collect-only -q`, which must collect nothing, and the same
for `integration`. `--strict-markers` is on, so a new marker goes in `pytest.ini` first. A new test
directory gets an empty `__init__.py` like its siblings, because file names repeat across modules
(`test_repository.py`, `test_dependencies.py`).

### 2. No token is 401

`CurrentUser` is the only identity dependency and nothing else gates a route, so a request with no token
answers 401. Use `client` for the no-user request: `unauthenticated_client` leaves `get_db_session`
un-overridden, so a route that opens a session raises `RuntimeError: Database session factory not
initialized`.

`tests/integration/modules/conversation/test_dependencies.py` mounts the ownership dependency through a real
route; for a dependency no route uses yet, mount a sentinel router in a module-scoped fixture.

### 3. The error body's key is `error`

`{"error": "CONVERSATION_NOT_FOUND", "message": …, "correlation_id": …}`. Assert
`response.json()["error"]`, not `error_code`.

### 4. No lifespan runs under test

The clients call the app through `ASGITransport`. `client` sets `app.state.engine` itself, and
nothing sets the rest:

- **Rate limits:** a tripped limit answers 500, and counts leak between tests. See the
  [`BUGS.md`](../../../docs/BUGS.md) entry, which gives the fixture that fixes it.
- **Agent:** use `authenticated_client_with_agent`.
- **Checkpoints:** a route that clears a conversation blocks until `PoolTimeout` without
  `stub_checkpoint_deletion`.

### 5. Deferred event subscribers never run in a route test

`client` replaces `get_db_session`, and with it the `events.flush()` that runs deferred handlers after
the commit. Inline subscribers (every one today) run. For a deferred one, unit-test the handler by
calling it, and assert the publish separately.

### 6. Writes roll back, commits don't commit

`db_session` joins an outer transaction with savepoints, so a route's commit releases a savepoint and
everything is undone at teardown. Fixtures `add` → `flush` → `refresh`. Services never commit (the
request's `DbSession` does). A unit test pins that with `session.commit.assert_not_awaited()`.

## Mocking

- **Patch where it is looked up:** `app.modules.account.service.clerk_client.get_user`, not the
  integration package. Same for `…service.events.publish`.
- **Clerk webhooks** go in signed with svix: `tests/integration/modules/account/router/test_webhooks.py`
  has the `signed()` helper and the test secret.

## Ownership

The user is the tenant. A query or route scoped by `user_id` needs a second `User` that owns a row the caller must
not see: absent from a list, and 404 by id with the module's not-found code (`CONVERSATION_NOT_FOUND`), the same
answer as a missing id. `tests/integration/modules/conversation/test_dependencies.py` does this for conversations:
`test_other_users_conversation_returns_404` and its indistinguishable-from-missing sibling.

## Gate tests

These fail on purpose when wiring is missing. Fix the wiring, never the test.

| Fails | Because | Fix |
|---|---|---|
| `tests/unit/test_module_contracts.py` | a module lacks import contracts, its alembic line or its `app/main.py` import | `server-patterns` → `references/new-module.md` |
| `tests/unit/models/test_owned_tables.py` | a table has no `user_id` | `UserOwnedMixin`, or an `ALLOWLIST` row with the reason |
| `tests/unit/api/test_openapi_contract.py` | a route lacks an explicit tag, a camelCase `operation_id`, or a `response_model` / `status_code=204` | `server-patterns` → `references/api-routes.md` |

## Assertions

- **Order:** a list route with an `ordering` parameter pins each allowed value. One without an
  `ordering` parameter makes no promise about order, so compare by id.
- **A whole-object assertion pins a field mapping only if every field holds a distinguishable value.**
  Give each field of a fixture row its own value.
- **A test that pins known-wrong behaviour names its `BUGS.md` entry** in a comment. Invert it when the
  bug is fixed, don't delete it. Before "fixing" a test that looks wrong, check `BUGS.md`.
