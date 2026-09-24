# Commit Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Commit the request's transaction after the route returns and **before** the response is sent, so a 200 means the write is durable and a failure at commit time reaches the client as an error.

**Architecture:** One keyword: `DbSession` becomes `Depends(get_db_session, scope="function")`. That covers every route, `CurrentUser` and `UserConversation`. Two things go with it. The RLS session context, which no policy reads, is deleted first, because it sits in the same dependency. `UserService.erase_user` stops committing, so `get_db_session` is the only thing that ends a transaction.

**Tech Stack:** FastAPI 0.141.1 (`Depends(scope=...)` exists from 0.121), SQLAlchemy 2 async, pytest, httpx `ASGITransport`.

**Spec:** No separate spec. Scope agreed in session on 2026-09-23. The reference is flyorbit's commit-boundary change (flyorbit `135b4d5`, spec `docs/superpowers/specs/2026-09-22-commit-boundary-design.md` in that repo), ported to this repo's differences: deferred events, the org-role cache, and no background tasks.

**Measured before planning.** A throwaway app ran the template's real `get_db_session` against a stub session:

| Scope | Order | Commit raises `IntegrityError` |
|---|---|---|
| `request` (today) | handler → body → commit | status **200**, write lost |
| `function` | handler → commit → close → body | status **409** via `service_exception_handler` |

## Global Constraints

- Run commands from `server/`. Tests: `APP_ENV=test uv run pytest <path> -q` (integration tests start their own Postgres testcontainer). Baseline on `main` 7c1692f: full suite **583 passed**.
- Checks from the repo root: `make check-server` (ruff + import-linter, 5 contracts) and `make check-contract` (no drift; no route changes here).
- Never `commit()` in a service or repository after this branch. `get_db_session` is the only committer. `app/core/events.py`'s `flush()` commits its own handler sessions, and that stays: those are separate transactions it owns.
- Log events: structured `logger.<level>("snake_case_event", key=value)`.
- Comments: state the constraint in one or two lines, no narrative.
- Commit messages end with: `Claude-Session: https://claude.ai/code/session_01NFDrERAUYXLeBxBUSshgVA`

## Review Focus

1. **The streaming route after the session closes.** `chat_stream`'s generator reads `conversation.id` and `user.id` after `get_db_session` has committed and closed. That works only because `create_session_factory` sets `expire_on_commit=False`. Pinned in Task 2 (declaration test).
2. **Deferred event handlers now run before the response.** `events.flush()` sits after the commit inside `get_db_session`, so it moves in front of the response with the commit. Its failures are still caught and logged, so they can't turn a 200 into a 500. Every subscriber today is inline, so there's no latency change yet. The docstrings in Task 2 say so. The existing `test_deferred_events_are_flushed_after_commit` must stay green.
3. **An exception from the route still rolls back.** The route's exception is thrown into the dependency's generator in both scopes. `get_db_session`'s `except Exception` branch rolls back and re-raises. The existing `TestErrorTranslation` tests plus the full suite cover it.
4. **Erasure on both paths.** `DELETE /auth/me` and the `user.deleted` webhook both call `erase_user` with the request's `DbSession`, and neither runs anything after it. With the explicit commit gone, the dependency commits the whole cascade. The org-role cache is refilled from Clerk, not from our table, so clearing it before the commit can't cache a pre-erasure value. Pinned in Task 3; the integration erasure tests stay green.
5. **A commit-time conflict reaches the client.** A unique violation surfacing at `commit()` must answer 409, not 200. Pinned in Task 2 (ordering test, failing-commit case).

**Deliberately not ported:** flyorbit's `committing_client` fixture and its read-after-write test on a second connection. Flyorbit needed a `BackgroundTasks` route to make that race deterministic; this repo has none. The stub-session ordering pin asserts the same invariant with no database and no timing.

---

### Task 1: Delete the RLS session context

`get_db_session` sets the Postgres setting `app.current_user_id` on the way in and resets it on the way out. No `POLICY` or `ROW LEVEL SECURITY` exists anywhere in `app/` or `alembic/`. `AuthMiddleware` sets `request.state.user_id = None` on every request (`app/api/middlewares/auth.py:30`), and `get_db_session` resolves before `get_current_user`, so the value written is always empty. The cost is two round trips per request for a setting nothing reads. It goes rather than getting fixed; real RLS, if it ever comes, should be transaction-scoped and designed for tenancy.

**Files:**
- Delete: `server/app/database/context.py`
- Modify: `server/app/database/__init__.py`
- Modify: `server/app/database/dependencies.py:21-24` (import), `:64-66` (set), `:108-110` (clear)
- Modify: `server/app/modules/account/router/webhooks.py:7-16` (module docstring RLS note)
- Modify: `server/app/core/events.py` (`flush()` docstring paragraph naming `set_session_context`)
- Modify: `server/tests/integration/database/test_dependencies.py`
- Modify: `server/tests/README.md:37`

- [x] **Step 1: Delete the module and its exports**

`git rm server/app/database/context.py`. Then in `server/app/database/__init__.py` delete the import block

```python
from app.database.context import (
    clear_session_context,
    get_session_context,
    set_session_context,
)
```

and the three `__all__` entries `"clear_session_context"`, `"get_session_context"`, `"set_session_context"`.

- [x] **Step 2: Remove the calls from `get_db_session`**

In `server/app/database/dependencies.py` delete the import

```python
from app.database.context import (
    clear_session_context,
    set_session_context,
)
```

delete, inside the `try:`,

```python
        # Set RLS context if user is authenticated
        if hasattr(request.state, "user_id"):
            await set_session_context(session, request.state.user_id)

```

and change the `finally:` block from

```python
    finally:
        # Clear RLS context to prevent leaking to pooled connections
        await clear_session_context(session)
        await session.close()
```

to

```python
    finally:
        await session.close()
```

- [x] **Step 3: Update the two docstrings that describe it**

`server/app/modules/account/router/webhooks.py`: replace the whole paragraph starting `RLS note: this route writes to the database outside any authenticated user` (through `not on behalf of a signed-in user.`) with:

```
No user identity reaches this route: there is no bearer token. If row-level
security is ever added, this path writes as Clerk's events dictate, not on
behalf of a signed-in user, and will need a service-role escape hatch.
```

`server/app/core/events.py`, `flush()` docstring: delete this paragraph and the blank line after it:

```
        Each fresh session is built from `session_factory` alone —
        `set_session_context` is never called here, unlike the request path.
        No RLS policy reads that context today, but a fork adding one would
        find its first deferred handler failing with nothing pointing here.
```

- [x] **Step 4: Update the integration tests**

In `server/tests/integration/database/test_dependencies.py`:

- Module docstring: `"""Integration tests for get_db_session dependency — error translation and deferred-event flushing."""`
- Imports: `from unittest.mock import AsyncMock, MagicMock` (drop `patch`, now unused).
- Replace `_make_mock_request` with:

```python
def _make_mock_request():
    """Create a mock FastAPI request with session_factory on app state."""
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()

    mock_request = MagicMock()
    mock_request.app.state.session_factory.return_value = mock_session
    return mock_request, mock_session
```

- In `TestErrorTranslation`, remove both `@patch(...)` decorators from each of the three tests, and the `mock_set, mock_clear` parameters: `async def test_integrity_error_raises_database_conflict(self):` and likewise for the other two. The test bodies are unchanged.
- Delete `class TestRLSContext` entirely (both tests).
- In `test_deferred_events_are_flushed_after_commit`, delete the line `request.state = MagicMock(spec=[])  # no user_id → no RLS context`.

`server/tests/README.md:37`: change the comment `# Error translation, RLS context set/clear` to `# Error translation, deferred-event flush`.

- [x] **Step 5: Verify nothing references it**

Run: `grep -rnE "session_context|current_user_id" app tests alembic`
Expected: no output.

- [x] **Step 6: Run the tests**

Run: `APP_ENV=test uv run pytest tests -q`
Expected: **581 passed** (583 − the 2 `TestRLSContext` tests).

- [x] **Step 7: Commit**

```bash
git add -A app/database app/modules/account/router/webhooks.py app/core/events.py tests/integration/database/test_dependencies.py tests/README.md
git commit -m "refactor(server): delete the RLS session context no policy reads

get_db_session set app.current_user_id on every request, always to an empty
value, and reset it on the way out. No table has a policy that reads it.

Claude-Session: https://claude.ai/code/session_01NFDrERAUYXLeBxBUSshgVA"
```

---

### Task 2: Commit before the response is sent

**Files:**
- Create: `server/tests/unit/database/__init__.py` (empty)
- Create: `server/tests/unit/database/test_dependencies.py`
- Modify: `server/app/database/dependencies.py` (`get_db_session` docstring, `DbSession`)
- Modify: `server/app/core/events.py` (module docstring, the `deferred` bullet)
- Modify: `docs/architecture/server-modules.md:169`
- Modify: `server/CLAUDE.md` (Code Conventions)

**Interfaces:**
- Produces: `DbSession = Annotated[AsyncSession, Depends(get_db_session, scope="function")]`. Task 3 relies on the dependency committing before the response.

- [x] **Step 1: Write the failing tests**

Create `server/tests/unit/database/__init__.py` (empty) and `server/tests/unit/database/test_dependencies.py`:

```python
"""Pins for get_db_session's transaction boundary: commit after the route returns, before the response is sent."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from app.database.dependencies import DbSession
from app.database.engine import create_session_factory
from app.exceptions.base import ServiceError
from app.exceptions.handlers import service_exception_handler

pytestmark = pytest.mark.unit


class TestDeclaration:
    def test_the_session_dependency_is_function_scoped(self):
        """The whole fix is this keyword; the ordering tests below show what it buys."""
        assert DbSession.__metadata__[0].scope == "function"

    def test_the_session_factory_does_not_expire_on_commit(self):
        """chat_stream's generator reads conversation.id and user.id after the session has closed."""
        factory = create_session_factory(MagicMock())

        assert factory.kw["expire_on_commit"] is False


class _StubSession:
    """Just enough of AsyncSession for get_db_session's teardown, recording each call."""

    def __init__(self, events: list[str], fail_commit: bool = False) -> None:
        self.events = events
        self.fail_commit = fail_commit

    async def commit(self) -> None:
        self.events.append("commit")
        if self.fail_commit:
            raise IntegrityError("INSERT ...", {}, Exception("unique violation"))

    async def rollback(self) -> None:
        self.events.append("rollback")

    async def close(self) -> None:
        self.events.append("close")


async def _post(events: list[str], fail_commit: bool = False) -> int:
    """POST to a throwaway app wired like the real one; record the first body frame in `events`."""
    app = FastAPI()
    app.state.session_factory = lambda: _StubSession(events, fail_commit)
    app.add_exception_handler(ServiceError, service_exception_handler)

    @app.post("/write")
    async def write(db_session: DbSession) -> dict[str, bool]:
        events.append("handler")
        return {"ok": True}

    async def probed(scope: dict[str, Any], receive: Any, send: Any) -> None:
        async def probed_send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.body" and "body" not in events:
                events.append("body")
            await send(message)

        await app(scope, receive, probed_send)

    transport = ASGITransport(app=probed, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return (await client.post("/write")).status_code


class TestOrdering:
    async def test_the_commit_lands_before_the_first_body_frame(self):
        """Under the default "request" scope the order is handler, body, commit: a 200 for an uncommitted write."""
        events: list[str] = []

        assert await _post(events) == 200
        assert events == ["handler", "commit", "close", "body"]

    async def test_a_failing_commit_answers_409_not_200(self):
        """A conflict found at commit time must reach the client, not follow a 200 already sent."""
        events: list[str] = []

        assert await _post(events, fail_commit=True) == 409
        assert events == ["handler", "commit", "rollback", "close", "body"]
```

- [x] **Step 2: Run them to verify they fail**

Run: `APP_ENV=test uv run pytest tests/unit/database/test_dependencies.py -q`
Expected: **3 failed, 1 passed**.
- `test_the_session_dependency_is_function_scoped` fails because `scope` is `None`.
- `test_the_commit_lands_before_the_first_body_frame` fails with `"body"` before `"commit"`.
- `test_a_failing_commit_answers_409_not_200` fails with `200 == 409`.
- `test_the_session_factory_does_not_expire_on_commit` passes. It pins existing behaviour that this change now depends on.

- [x] **Step 3: Make `DbSession` function-scoped**

In `server/app/database/dependencies.py`, change the last line to:

```python
DbSession = Annotated[AsyncSession, Depends(get_db_session, scope="function")]
```

and replace `get_db_session`'s docstring `"""Core dependency for database sessions."""` with:

```python
    """One session and one transaction per request, committed before the response is sent.

    `DbSession` binds this with `scope="function"`, and that keyword is the
    transaction boundary: the post-`yield` block runs after the path
    operation returns and before the response goes on the wire. With the
    default `"request"` scope the commit ran after the bytes were sent, so a
    200 could precede a failed commit. `tests/unit/database/test_dependencies.py`
    pins the keyword and the order.

    Consequences routes rely on:
    - A commit-time failure reaches the exception handlers (a unique violation is a 409).
    - Deferred event handlers run after the commit and before the response, so they add
      to its latency.
    - The session is closed by the time a `BackgroundTasks` callable or a `StreamingResponse`
      body runs. Neither may use it; `expire_on_commit=False` is what lets them read
      attributes already loaded.
    """
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `APP_ENV=test uv run pytest tests/unit/database/test_dependencies.py -q`
Expected: **4 passed**.

- [x] **Step 5: Update the docs that describe the old timing**

`server/app/core/events.py`, module docstring, the `deferred` bullet. Replace

```
* deferred — the default. Queued in the request context and run by `flush()`
             after the publisher's commit, each in a session of its own. A
             failure is logged and counted, never raised: the response has
             been decided. For reactions, and the shape a queue will take.
```

with

```
* deferred — the default. Queued in the request context and run by `flush()`
             after the publisher's commit and before the response is sent,
             each in a session of its own, so they add to response latency.
             A failure is logged and counted, never raised: the write is
             durable and must not be reported as failed. For reactions, and
             the shape a queue will take.
```

`docs/architecture/server-modules.md:169`: replace `The deferred queue is request-scoped and drained by the \`DbSession\` dependency after its commit;` with `The deferred queue is request-scoped and drained by the \`DbSession\` dependency after its commit and before the response is sent;`.

`server/CLAUDE.md`, **Code Conventions**, add after `- All imports at the top of the file — never inside functions`:

```markdown
- DB writes end in `flush()`, never `commit()`: `DbSession` is `scope="function"`, so
  `get_db_session` commits after the route returns and before the response is sent
- A background task or a streaming body never uses the request's session — it is closed
  by then. Pass plain values; a task that needs the database opens its own from
  `request.app.state.session_factory`
```

- [x] **Step 6: Run the full suite and the checks**

Run: `APP_ENV=test uv run pytest tests -q`, then from the repo root `make check-server` and `make check-contract`.
Expected: **585 passed** (581 + 4), 5 contracts kept, no contract drift. `test_deferred_events_are_flushed_after_commit` and the chatbot streaming tests stay green.

- [x] **Step 7: Commit**

```bash
git add app/database/dependencies.py app/core/events.py tests/unit/database ../docs/architecture/server-modules.md CLAUDE.md
git commit -m "fix(server): commit before the response is sent

DbSession is now scope=\"function\": get_db_session commits after the route
returns and before the response goes out, instead of after it. A 200 no longer
precedes the commit, and a conflict at commit time answers 409 instead of
being lost behind a 200.

Claude-Session: https://claude.ai/code/session_01NFDrERAUYXLeBxBUSshgVA"
```

---

### Task 3: `erase_user` stops committing

With Task 2, the request's `DbSession` commits the cascade before the response, so `erase_user`'s own `commit()` is redundant. Its one apparent reason, clearing the org-role cache after the commit, doesn't hold. The cache maps `clerk_id` → org role and is refilled from Clerk's API (`resolve_org_role`), not from our `user` table. On both erasure paths Clerk has already deleted the user before `erase_user` runs.

**Files:**
- Modify: `server/app/modules/account/service.py` (`erase_user`: docstring and the `commit()` line)
- Modify: `server/app/modules/account/router/auth.py:67` (`delete_me` docstring step 7)
- Modify: `server/CLAUDE.md` (GDPR section, step 4)
- Test: `server/tests/unit/modules/account/test_service.py:50`

**Interfaces:**
- Consumes: Task 2's `DbSession` committing before the response.

- [x] **Step 1: Change the test to the new contract**

In `server/tests/unit/modules/account/test_service.py`, `test_erase_user_runs_full_cascade`, replace

```python
    session.commit.assert_awaited_once()
```

with

```python
    # The request's DbSession commits the cascade; erase_user never does.
    session.commit.assert_not_awaited()
```

- [x] **Step 2: Run it to verify it fails**

Run: `APP_ENV=test uv run pytest tests/unit/modules/account/test_service.py -q -k full_cascade`
Expected: FAIL with `Expected 'commit' to not have been awaited. Awaited 1 times.`

- [x] **Step 3: Remove the commit and fix the docstring**

In `server/app/modules/account/service.py`, `erase_user`: delete the line `await session.commit()` (between `session.add(user)` and `await user_cache.invalidate_user(...)`).

In its docstring, replace the paragraph

```
        Step order is contractual. Subscribers to USER_ERASING and the memory
        deletion run before `anonymize_user()`, because they are keyed by
        identifiers it destroys. The org-role cache is invalidated after the
        commit, using the clerk_id captured before anonymisation rewrote it;
        the supplier-link cache was already dropped inline, by supplier's own
        USER_ERASING subscriber, inside this transaction.
```

with

```
        Step order is contractual. Subscribers to USER_ERASING and the memory
        deletion run before `anonymize_user()`, because they are keyed by
        identifiers it destroys. The org-role cache is invalidated last, under
        the clerk_id captured before anonymisation rewrote it. Its position
        against the commit does not matter: it is refilled from Clerk, not
        from this table, and Clerk has already deleted the user.

        Not committed here: the caller's DbSession commits before the response
        is sent. delete_user_memory is irreversible, so anything a caller runs
        after this call that fails before the commit would roll back the
        anonymisation with the memories already gone. Neither caller runs
        anything after it today.
```

and the `Args:` line `session: Database session. Committed by this method.` with `session: Database session. Committed by the caller's DbSession.`

- [x] **Step 4: Update the route docstring and the GDPR section**

`server/app/modules/account/router/auth.py:67`: `7. Invalidate the org-role cache, after the commit — the supplier-link` becomes `7. Invalidate the org-role cache — the supplier-link` (the rest of the step is unchanged).

`server/CLAUDE.md`, **GDPR — Right to Erasure**:
- Step 4: `4. User PII anonymised via \`AnonymizableMixin.anonymize_user()\`, then commit` becomes `4. User PII anonymised via \`AnonymizableMixin.anonymize_user()\``.
- After step 5, add the line: `The request's \`DbSession\` commits the whole cascade before the response is sent; \`erase_user\` does not commit.`

- [x] **Step 5: Run the tests to verify they pass**

Run: `APP_ENV=test uv run pytest tests/unit/modules/account tests/integration/modules/account -q`
Expected: all pass. That covers the unit cascade tests and the integration erasure tests on both the route and the webhook path.

- [x] **Step 6: Confirm there's no other committer and run everything**

Run: `grep -rn "\.commit()" app`
Expected: exactly two hits, `app/database/dependencies.py` and `app/core/events.py` (the deferred handlers' own sessions).

Run: `APP_ENV=test uv run pytest tests -q`, then from the repo root `make check-server`.
Expected: **585 passed**, 5 contracts kept.

- [x] **Step 7: Commit**

```bash
git add app/modules/account/service.py app/modules/account/router/auth.py CLAUDE.md tests/unit/modules/account/test_service.py
git commit -m "refactor(server): erase_user no longer commits

The request's DbSession commits before the response now, so get_db_session is
the only committer. The org-role cache it clears is refilled from Clerk, not
from the user table, so clearing it before the commit is safe.

Claude-Session: https://claude.ai/code/session_01NFDrERAUYXLeBxBUSshgVA"
```
