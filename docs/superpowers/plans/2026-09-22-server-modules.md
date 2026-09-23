# Server Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rotate `server/app/` from layer-first to module-first (`modules/account`, `modules/conversation`, `modules/supplier`), add the event dispatcher and the tenant-scoping check, and enforce the boundaries with import-linter — with no behaviour change and no schema change.

**Architecture:** Four layers importing downward only (Assembly → Modules → Adapters → Foundation), one package per bounded context with a fixed set of slots, modules forming a DAG with downward-pointing needs expressed as events. The supplier tangle inside the user service becomes a `supplier` module subscribing to three `account` events. Every rule is a linter contract or a unit test.

**Tech Stack:** Python 3.13, uv, FastAPI, SQLModel/SQLAlchemy async, Alembic, pytest + pytest-asyncio, import-linter, ruff, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-22-server-modules-design.md` (the delta and the mechanics) and `docs/architecture/server-modules.md` (the rules R1–R9, the slots, the decisions D1–D6). Read both before starting.

## Global Constraints

- **No behaviour changes, no schema changes.** `make check-contract` from the repo root must pass with no diff (`server/openapi.json` byte-identical), and `alembic revision --autogenerate` must produce an empty revision.
- **No compatibility shims.** A moved symbol is imported from its new home everywhere; the old path is deleted in the same task.
- **Every symbol keeps its name** unless the spec's §2 table renames it. Every route keeps its path, tag and `operation_id`.
- **Transient states are named.** Two tasks leave an upward import in place for exactly one task (called out in each); the linter that would reject them lands in Task 10.
- Run everything from `server/`: `APP_ENV=test uv run pytest …`, `uv run ruff check . && uv run ruff format --check .`. Integration tests need Docker running (testcontainers).
- Ruff: line length 119, google docstrings on every public function in `app/` (rule `D`; `tests/**` exempt), `F401` and `E402` are ignored globally so re-export `__init__` files need no `noqa`.
- Commits: `type(scope): lowercase summary` (see `git log`). The pre-commit hook regenerates the API contract on every commit touching `server/app/` and blocks if it moved — that is the byte-identical proof running on every task.
- Do not create `docs/architecture/decisions/`.

---

## File structure (end state)

```
server/app/
  main.py                              # + explicit `from app.modules import <name>` per module
  api/system/schemas.py                # from schemas/system.py
  api/v1/api.py                        # include_router(<module>.router) only
  core/events.py                       # NEW: EventDispatcher (inline + deferred), `events` singleton
  core/metrics.py                      # + app_event_handler_failures_total
  database/dependencies.py             # from api/dependencies/database.py; drains deferred events after commit
  models/base.py                       # + TenantMixin
  utils/cache.py                       # NEW: Miss / MISS sentinel shared by the two caches
  agents/messages.py                   # Message, from schemas/chat.py
  agents/graph.py                      # from utils/graph.py
  integrations/llm/                    # from services/llm/
  modules/__init__.py
  modules/account/{__init__,schemas,models,service,repository,dependencies,exceptions,webhooks,cache}.py
  modules/account/router/{__init__,auth,webhooks}.py
  modules/conversation/{__init__,schemas,models,service,dependencies,exceptions,handlers}.py
  modules/conversation/router/{__init__,conversation,chatbot}.py
  modules/supplier/{__init__,models,service,repository,dependencies,exceptions,handlers,cache}.py
server/tests/
  unit/core/test_events.py             # NEW
  unit/test_module_contracts.py        # NEW
  unit/models/test_tenant_tables.py    # NEW
  unit/modules/<name>/test_<slot>.py   # moved (R5)
  integration/modules/<name>/…         # moved (R5)
  integration/database/test_dependencies.py
```

Deleted at the end: `app/api/dependencies/`, `app/api/v1/{auth,webhooks,conversation,chatbot}.py`, `app/services/`, `app/models/{user,conversation,supplier,enums}.py`, `app/schemas/{auth,chat,conversation,system}.py`, `app/utils/graph.py`, `app/integrations/clerk/webhooks/dispatcher.py`, `app/integrations/clerk/webhooks/handlers/`.

---

### Task 1: Event dispatcher

**Files:**
- Create: `server/app/core/events.py`
- Modify: `server/app/core/metrics.py` (append one counter)
- Test: `server/tests/unit/core/test_events.py`

**Interfaces:**
- Produces: `events: EventDispatcher` singleton with
  - `on(event: str, *, inline: bool = False) -> Callable[[Handler], Handler]`
  - `subscribe(event: str, handler: Handler, *, inline: bool = False) -> Handler`
  - `handlers(event: str) -> tuple[Handler, ...]`
  - `begin() -> None` — starts an empty deferred queue for the current context
  - `async publish(event: str, **payload) -> int` — inline handlers run now with `**payload`; deferred ones are queued with `payload` minus `session`; returns run + queued
  - `async flush(session_factory: Callable[[], AsyncSession]) -> int` — drains the queue, one fresh session per handler, failures logged + counted, never raised
- Produces: `app_event_handler_failures_total` Counter in `app/core/metrics.py`, labels `event`, `handler`

- [ ] **Step 1: Write the failing tests**

```python
# server/tests/unit/core/test_events.py
"""Tests for the in-process event dispatcher (architecture §5)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.events import EventDispatcher

pytestmark = pytest.mark.unit


class FakeSession:
    """The subset of AsyncSession a deferred handler's context manager needs."""

    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def commit(self) -> None:
        self.committed = True


class FakeSessionFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeSession] = []

    def __call__(self) -> FakeSession:
        session = FakeSession()
        self.sessions.append(session)
        return session


async def test_publish_with_no_subscribers_returns_zero():
    dispatcher = EventDispatcher()
    assert await dispatcher.publish("nothing.happened", key="value") == 0


async def test_inline_handler_runs_at_publish_with_the_full_payload():
    dispatcher = EventDispatcher()
    handler = AsyncMock()
    dispatcher.subscribe("thing.done", handler, inline=True)

    count = await dispatcher.publish("thing.done", session="s", user_id="u1")

    handler.assert_awaited_once_with(session="s", user_id="u1")
    assert count == 1


async def test_inline_handlers_run_in_registration_order():
    dispatcher = EventDispatcher()
    order: list[str] = []

    @dispatcher.on("thing.done", inline=True)
    async def first(**_):
        order.append("first")

    @dispatcher.on("thing.done", inline=True)
    async def second(**_):
        order.append("second")

    await dispatcher.publish("thing.done")
    assert order == ["first", "second"]


async def test_inline_handler_exception_propagates_and_stops_the_sequence():
    dispatcher = EventDispatcher()
    second = AsyncMock()

    @dispatcher.on("thing.done", inline=True)
    async def first(**_):
        raise RuntimeError("boom")

    dispatcher.subscribe("thing.done", second, inline=True)

    with pytest.raises(RuntimeError, match="boom"):
        await dispatcher.publish("thing.done")
    second.assert_not_awaited()


def test_on_returns_the_handler_unchanged_and_lists_it():
    dispatcher = EventDispatcher()

    async def handler(**_):
        pass

    assert dispatcher.on("x")(handler) is handler
    assert dispatcher.handlers("x") == (handler,)


async def test_events_are_isolated_by_name():
    dispatcher = EventDispatcher()
    handler = AsyncMock()
    dispatcher.subscribe("a", handler, inline=True)
    await dispatcher.publish("b")
    handler.assert_not_awaited()


async def test_deferred_handler_is_queued_not_run_and_counted():
    dispatcher = EventDispatcher()
    handler = AsyncMock()
    dispatcher.subscribe("order.placed", handler)  # deferred is the default

    count = await dispatcher.publish("order.placed", session="publisher", order_id="o1")

    handler.assert_not_awaited()
    assert count == 1


async def test_flush_runs_deferred_handlers_with_their_own_session_and_no_publisher_session():
    dispatcher = EventDispatcher()
    handler = AsyncMock()
    dispatcher.subscribe("order.placed", handler)
    factory = FakeSessionFactory()
    await dispatcher.publish("order.placed", session="publisher", order_id="o1")

    ran = await dispatcher.flush(factory)

    assert ran == 1
    assert len(factory.sessions) == 1
    handler.assert_awaited_once_with(session=factory.sessions[0], order_id="o1")
    assert factory.sessions[0].committed is True


async def test_flush_empties_the_queue():
    dispatcher = EventDispatcher()
    dispatcher.subscribe("order.placed", AsyncMock())
    factory = FakeSessionFactory()
    await dispatcher.publish("order.placed", order_id="o1")

    assert await dispatcher.flush(factory) == 1
    assert await dispatcher.flush(factory) == 0
    assert len(factory.sessions) == 1


async def test_flush_on_an_empty_queue_is_a_noop():
    dispatcher = EventDispatcher()
    factory = FakeSessionFactory()
    assert await dispatcher.flush(factory) == 0
    assert factory.sessions == []


async def test_failing_deferred_handler_is_logged_counted_and_does_not_stop_the_others():
    dispatcher = EventDispatcher()
    second = AsyncMock()

    @dispatcher.on("order.placed")
    async def first(**_):
        raise RuntimeError("boom")

    dispatcher.subscribe("order.placed", second)
    factory = FakeSessionFactory()
    await dispatcher.publish("order.placed", order_id="o1")

    with (
        patch("app.core.events.logger") as logger,
        patch("app.core.events.app_event_handler_failures_total") as counter,
    ):
        ran = await dispatcher.flush(factory)

    assert ran == 2
    second.assert_awaited_once()
    logger.exception.assert_called_once()
    assert logger.exception.call_args.args[0] == "event_handler_failed"
    assert logger.exception.call_args.kwargs["event_name"] == "order.placed"
    assert logger.exception.call_args.kwargs["handler"].endswith("first")
    counter.labels.assert_called_once_with(event="order.placed", handler=logger.exception.call_args.kwargs["handler"])
    counter.labels.return_value.inc.assert_called_once()


async def test_begin_discards_whatever_was_queued_before():
    dispatcher = EventDispatcher()
    handler = AsyncMock()
    dispatcher.subscribe("order.placed", handler)
    await dispatcher.publish("order.placed", order_id="stale")

    dispatcher.begin()

    assert await dispatcher.flush(FakeSessionFactory()) == 0
    handler.assert_not_awaited()


async def test_inline_and_deferred_subscribers_of_one_event_both_count():
    dispatcher = EventDispatcher()
    inline = AsyncMock()
    deferred = AsyncMock()
    dispatcher.subscribe("thing.done", inline, inline=True)
    dispatcher.subscribe("thing.done", deferred)

    count = await dispatcher.publish("thing.done", session="s")

    assert count == 2
    inline.assert_awaited_once_with(session="s")
    deferred.assert_not_awaited()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/core/test_events.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.events'`

- [ ] **Step 3: Add the failure counter to metrics**

Append to `server/app/core/metrics.py`:

```python
# Deferred event handlers run after the publisher's commit, so a failure has
# nothing to fail: it is logged as `event_handler_failed` and counted here.
# `event` is a constant on a module root and `handler` a qualified function
# name, so neither label is caller-controlled.
app_event_handler_failures_total = Counter(
    "app_event_handler_failures_total",
    "Deferred event handlers that raised, by event and handler",
    ["event", "handler"],
)
```

- [ ] **Step 4: Write the dispatcher**

```python
# server/app/core/events.py
"""In-process domain events — the downward-pointing seam between modules.

Modules form a DAG (docs/architecture/server-modules.md, R6): `conversation`
and `supplier` import `account`, so `account` cannot import them. When the
lower module needs a higher one to act — erasing an account must clean up
its conversations — it publishes here and the higher module subscribes.

Two dispatch modes, chosen per subscription:

* inline   — runs in `publish()`, in registration order, in the publisher's
             session and transaction. A handler that raises stops the sequence
             and propagates: the publisher is mid-transaction and must not
             commit a half-done cascade. For cascades.
* deferred — the default. Queued in the request context and run by `flush()`
             after the publisher's commit, each in a session of its own. A
             failure is logged and counted, never raised: the response has
             been decided. For reactions, and the shape a queue will take.

A module subscribes at import time (`@events.on(NAME)`), so importing the
module is what registers it; `app/main.py` imports every module by name.
"""

from collections import defaultdict
from contextvars import ContextVar
from typing import (
    Any,
    Awaitable,
    Callable,
    NamedTuple,
)

from app.core.logging import logger
from app.core.metrics import app_event_handler_failures_total

Handler = Callable[..., Awaitable[None]]


class _Subscription(NamedTuple):
    handler: Handler
    inline: bool


class _Queued(NamedTuple):
    event: str
    handler: Handler
    payload: dict[str, Any]


# One queue per request context. The default is None, not a list: a mutable
# default would be shared by every context. `begin()` installs the list at the
# start of a request so that code running in a worker thread — which gets a
# *copy* of the context — appends to the same object the request will flush.
_queue: ContextVar[list[_Queued] | None] = ContextVar("app_events_queue", default=None)


def _qualified_name(handler: Handler) -> str:
    return f"{handler.__module__}.{getattr(handler, '__qualname__', repr(handler))}"


class EventDispatcher:
    """Registry of async handlers keyed by event name."""

    def __init__(self) -> None:
        """Start with no subscriptions."""
        self._subscriptions: dict[str, list[_Subscription]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler, *, inline: bool = False) -> Handler:
        """Register `handler` for `event`. Returns the handler unchanged."""
        self._subscriptions[event].append(_Subscription(handler, inline))
        return handler

    def on(self, event: str, *, inline: bool = False) -> Callable[[Handler], Handler]:
        """Decorator form of subscribe()."""

        def decorator(handler: Handler) -> Handler:
            return self.subscribe(event, handler, inline=inline)

        return decorator

    def handlers(self, event: str) -> tuple[Handler, ...]:
        """The handlers registered for `event`, in registration order."""
        return tuple(s.handler for s in self._subscriptions.get(event, ()))

    def begin(self) -> None:
        """Start an empty deferred queue for the current context."""
        _queue.set([])

    async def publish(self, event: str, **payload: Any) -> int:
        """Run the inline handlers now and queue the deferred ones.

        Inline handlers receive `payload` as keyword arguments, `session`
        included. Deferred handlers are queued with the payload minus
        `session`; `flush()` gives each one a session of its own.

        Returns the number of handlers run plus queued.
        """
        subscriptions = self._subscriptions.get(event, [])
        deferred_payload = {k: v for k, v in payload.items() if k != "session"}
        for subscription in subscriptions:
            if subscription.inline:
                await subscription.handler(**payload)
                continue
            queued = _queue.get()
            if queued is None:
                queued = []
                _queue.set(queued)
            queued.append(_Queued(event, subscription.handler, deferred_payload))
        logger.debug("event_published", event_name=event, handler_count=len(subscriptions))
        return len(subscriptions)

    async def flush(self, session_factory: Callable[[], Any]) -> int:
        """Run every queued deferred handler, each in a fresh session.

        A handler that raises is logged as `event_handler_failed`, counted on
        `app_event_handler_failures_total`, and skipped; the rest still run.
        Returns the number of handlers attempted. Callers outside a request —
        a script, a worker — call this themselves.
        """
        queued = _queue.get()
        if not queued:
            return 0
        _queue.set(None)
        for entry in queued:
            try:
                async with session_factory() as session:
                    await entry.handler(session=session, **entry.payload)
                    await session.commit()
            except Exception:
                handler_name = _qualified_name(entry.handler)
                logger.exception("event_handler_failed", event_name=entry.event, handler=handler_name)
                app_event_handler_failures_total.labels(event=entry.event, handler=handler_name).inc()
        return len(queued)


events = EventDispatcher()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/core/test_events.py -v`
Expected: 13 passed

- [ ] **Step 6: Lint and commit**

```bash
cd server && uv run ruff check . && uv run ruff format --check .
git add app/core/events.py app/core/metrics.py tests/unit/core/test_events.py
git commit -m "feat(core): in-process event dispatcher with inline and deferred subscriptions"
```

---

### Task 2: Regular packages and `TenantMixin`

**Files:**
- Create: `server/app/__init__.py`, `server/app/api/__init__.py`, `server/app/api/v1/__init__.py`, `server/app/core/__init__.py`, `server/app/models/__init__.py`, `server/app/modules/__init__.py`
- Modify: `server/app/models/base.py`
- Test: `server/tests/unit/models/test_models.py` (append one class)

**Interfaces:**
- Produces: `TenantMixin(SQLModel)` with `org_id: str = Field(index=True, nullable=False)` in `app.models.base`. No table adopts it in this slice.

- [ ] **Step 1: Write the failing test**

Append to `server/tests/unit/models/test_models.py`:

```python
from app.models.base import TenantMixin  # put with the other imports at the top


class TestTenantMixin:
    """The column every tenant-owned table gets (architecture §6)."""

    def test_org_id_is_indexed_and_not_nullable(self):
        field = TenantMixin.model_fields["org_id"]
        assert field.index is True
        assert field.nullable is False

    def test_org_id_is_a_required_string(self):
        assert TenantMixin.model_fields["org_id"].is_required()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/models/test_models.py -k TenantMixin -v`
Expected: FAIL with `ImportError: cannot import name 'TenantMixin'`

- [ ] **Step 3: Add the mixin**

Insert into `server/app/models/base.py` after `AnonymizableMixin` and before `BaseModel`:

```python
class TenantMixin(SQLModel):
    """The tenant column for a table owned by one Clerk organisation.

    `org_id` is the organisation id that arrives on the JWT and is stored on
    the user row. A table that carries it is scoped by it in every query; a
    table that does not must be listed, with a reason, in
    tests/unit/models/test_tenant_tables.py. Adding the mixin to an existing
    table is a migration with a backfill (architecture §6).
    """

    org_id: str = Field(index=True, nullable=False)
```

- [ ] **Step 4: Create the package markers**

Each file is a one-line docstring. `app/models/__init__.py` and `app/core/__init__.py` must not import anything (importing `app.core.config` from `app/core/__init__.py` would make every `app.core.X` import load settings).

```bash
cd server
printf '"""The FastAPI server."""\n' > app/__init__.py
printf '"""Assembly: system routes, the versioned router, middlewares."""\n' > app/api/__init__.py
printf '"""API v1 — includes each module'"'"'s router."""\n' > app/api/v1/__init__.py
printf '"""Foundation: settings, logging, metrics, limiter, events."""\n' > app/core/__init__.py
printf '"""Foundation: the base model and the mixins. Tables live in their module'"'"'s models slot."""\n' > app/models/__init__.py
mkdir -p app/modules
printf '"""The modules — one package per bounded context (docs/architecture/server-modules.md)."""\n' > app/modules/__init__.py
```

- [ ] **Step 5: Run the tests and the app import**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/models/test_models.py -v && APP_ENV=test uv run python -c "import app.main"`
Expected: all pass; the import prints nothing

- [ ] **Step 6: Commit**

```bash
git add app/__init__.py app/api/__init__.py app/api/v1/__init__.py app/core/__init__.py app/models/__init__.py app/modules/__init__.py app/models/base.py tests/unit/models/test_models.py
git commit -m "feat(models): TenantMixin, and every app package becomes a regular package"
```

---

### Task 3: `DbSession` moves to the foundation and drains deferred events

**Files:**
- Move: `server/app/api/dependencies/database.py` → `server/app/database/dependencies.py`
- Modify: `server/app/api/v1/auth.py`, `server/app/api/v1/webhooks.py`, `server/app/api/v1/conversation.py`, `server/app/api/dependencies/authentication.py`, `server/app/api/dependencies/conversation.py`, `server/tests/conftest.py`
- Move test: `server/tests/integration/dependencies/test_database.py` → `server/tests/integration/database/test_dependencies.py`

**Interfaces:**
- Produces: `from app.database.dependencies import DbSession, get_db_session` — same signatures as before. `get_db_session` calls `events.begin()` before yielding and `await events.flush(request.app.state.session_factory)` after `commit()`.

- [ ] **Step 1: Move the file and the test**

```bash
cd server
git mv app/api/dependencies/database.py app/database/dependencies.py
mkdir -p tests/integration/database && touch tests/integration/database/__init__.py
git mv tests/integration/dependencies/test_database.py tests/integration/database/test_dependencies.py
```

- [ ] **Step 2: Wire the dispatcher into the session dependency**

In `server/app/database/dependencies.py`, add `from app.core.events import events` to the imports, and change the body of `get_db_session`:

```python
    session = request.app.state.session_factory()
    events.begin()
    try:
        # Set RLS context if user is authenticated
        if hasattr(request.state, "user_id"):
            await set_session_context(session, request.state.user_id)

        yield session
        await session.commit()
        # Deferred handlers run only once the request's writes are durable; a
        # request that raised above never reaches this line, and its queue is
        # discarded with the request context (architecture §5).
        await events.flush(request.app.state.session_factory)
```

Everything else in the function (the `except` clauses, `finally`) stays as it is.

- [ ] **Step 3: Update every importer**

Replace `from app.api.dependencies.database import` with `from app.database.dependencies import` in:

- `app/api/v1/auth.py`, `app/api/v1/webhooks.py`, `app/api/v1/conversation.py`
- `app/api/dependencies/authentication.py`, `app/api/dependencies/conversation.py`
- `tests/conftest.py`
- `tests/integration/database/test_dependencies.py` — also its patch strings: `"app.api.dependencies.database.set_session_context"` → `"app.database.dependencies.set_session_context"`, same for `clear_session_context`.

```bash
cd server && grep -rl "app.api.dependencies.database" app tests | xargs sed -i '' 's/app\.api\.dependencies\.database/app.database.dependencies/g'
grep -rn "api.dependencies.database" app tests   # expect nothing
```

- [ ] **Step 4: Add the drain test**

Append to `server/tests/integration/database/test_dependencies.py`:

```python
async def test_deferred_events_are_flushed_after_commit(test_engine):
    """A deferred handler runs once the request's session has committed, with a session of its own."""
    from unittest.mock import AsyncMock

    from fastapi import Request

    from app.core.events import events

    handler = AsyncMock()
    events.subscribe("test.deferred", handler)
    factory = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    request = MagicMock(spec=Request)
    request.app.state.session_factory = factory
    request.state = MagicMock(spec=[])  # no user_id → no RLS context

    generator = get_db_session(request)
    session = await generator.__anext__()
    await events.publish("test.deferred", session=session, key="value")
    handler.assert_not_awaited()

    with pytest.raises(StopAsyncIteration):
        await generator.__anext__()

    handler.assert_awaited_once()
    assert handler.await_args.kwargs["key"] == "value"
    assert handler.await_args.kwargs["session"] is not session
```

Add `from sqlalchemy.orm import sessionmaker`, `from sqlalchemy.ext.asyncio import AsyncSession` and `from unittest.mock import MagicMock` to the file's imports if they are not already there.

- [ ] **Step 5: Run the suite**

Run: `cd server && APP_ENV=test uv run pytest tests/integration/database tests/unit -v`
Expected: all pass (the drain test needs Docker for the container)

- [ ] **Step 6: Commit**

```bash
git add -A app/database app/api tests/conftest.py tests/integration
git commit -m "refactor(database): DbSession moves to the foundation and drains deferred events after commit"
```

---

### Task 4: `services/llm` becomes the `integrations/llm` adapter

**Files:**
- Move: `server/app/services/llm/{__init__,service,exceptions}.py` → `server/app/integrations/llm/`
- Modify: `server/app/agents/chatbot/graph.py`, `server/tests/unit/exceptions/test_handlers_metrics.py`
- Move tests: `server/tests/unit/services/test_llm_{registry,service,service_import}.py` → `server/tests/unit/integrations/llm/`

**Interfaces:**
- Produces: `from app.integrations.llm import llm_service, LLMService, LLMRegistry, LLMAPIError, LLMFallbackExhaustedError, LLMRateLimitError, LLMServiceError, LLMStreamingError, LLMTimeoutError` — unchanged names.

- [ ] **Step 1: Move**

```bash
cd server
git mv app/services/llm app/integrations/llm
mkdir -p tests/unit/integrations/llm && touch tests/unit/integrations/llm/__init__.py
git mv tests/unit/services/test_llm_registry.py tests/unit/integrations/llm/test_registry.py
git mv tests/unit/services/test_llm_service.py tests/unit/integrations/llm/test_service.py
git mv tests/unit/services/test_llm_service_import.py tests/unit/integrations/llm/test_service_import.py
```

- [ ] **Step 2: Rewrite the import paths**

```bash
cd server && grep -rl "app.services.llm" app tests pyproject.toml | xargs sed -i '' 's/app\.services\.llm/app.integrations.llm/g'
grep -rnE "services\.llm|services/llm" app tests pyproject.toml
```

The last grep should show only the comment in `pyproject.toml` (`[tool.uv]` block) naming `tests/unit/services/test_llm_service_import.py`; change that path to `tests/unit/integrations/llm/test_service_import.py`. Then check `tests/unit/integrations/llm/test_service_import.py` itself: if it asserts on a module path string (for example that importing `app.services.llm.service` needs no key), the sed already rewrote it — read the file and confirm the assertion still names a module that exists.

- [ ] **Step 3: Run the moved tests and the agent tests**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/integrations/llm tests/unit/agents tests/unit/exceptions -v`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
cd server && uv run ruff check . && uv run ruff format --check .
git add -A app/services app/integrations app/agents tests pyproject.toml
git commit -m "refactor(integrations): the llm service is an adapter, not a domain service"
```

---

### Task 5: Graph helpers move under `agents/`, system schemas under `api/system/`

**Files:**
- Move: `server/app/utils/graph.py` → `server/app/agents/graph.py`; `server/app/schemas/system.py` → `server/app/api/system/schemas.py`
- Modify: `server/app/utils/__init__.py`, `server/app/agents/base/agent.py`, `server/app/agents/chatbot/graph.py`, `server/app/api/system/health.py`
- Move tests: `server/tests/unit/utils/test_graph.py` → `server/tests/unit/agents/test_graph.py`; `server/tests/unit/schemas/test_system_schemas.py` → `server/tests/unit/api/test_system_schemas.py`

**Interfaces:**
- Produces: `from app.agents.graph import dump_messages, prepare_messages, process_llm_response`; `from app.api.system.schemas import RootResponse, HealthResponse, ReadinessResponse, …`.
- Note: `Message` stays in `app/schemas/chat.py` until Task 8; `app/agents/graph.py` imports it from there (a legal downward import).

- [ ] **Step 1: Move the files and tests**

```bash
cd server
git mv app/utils/graph.py app/agents/graph.py
git mv app/schemas/system.py app/api/system/schemas.py
git mv tests/unit/utils/test_graph.py tests/unit/agents/test_graph.py
git mv tests/unit/schemas/test_system_schemas.py tests/unit/api/test_system_schemas.py
```

- [ ] **Step 2: Rewire imports**

- `app/agents/graph.py`: `from app.schemas import Message` → `from app.schemas.chat import Message`.
- `app/utils/__init__.py`: replace the whole file with `"""Foundation utilities: JWT verification, input sanitisation."""` (nothing exported).
- `app/agents/base/agent.py`: `from app.utils import dump_messages` → `from app.agents.graph import dump_messages`.
- `app/agents/chatbot/graph.py`: `from app.utils import (dump_messages, prepare_messages, process_llm_response)` → `from app.agents.graph import (…)` with the same names.
- `app/api/system/health.py`: `from app.schemas.system import (…)` → `from app.api.system.schemas import (…)`.
- `tests/unit/agents/test_graph.py`: `from app.utils.graph import` → `from app.agents.graph import`.
- `tests/unit/api/test_system_schemas.py`: `from app.schemas.system import` → `from app.api.system.schemas import`.

```bash
cd server && grep -rnE "app\.utils\.graph|app\.schemas\.system|from app\.utils import" app tests   # expect nothing
```

- [ ] **Step 3: Run tests**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents tests/unit/api tests/integration/api/test_health.py -v && APP_ENV=test uv run python -c "import app.main"`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
cd server && uv run ruff check . && uv run ruff format --check .
git add -A app tests
git commit -m "refactor: graph helpers live with the agents, system schemas with the system routes"
```

---

### Task 6: The `supplier` module (extracted from `services/user`)

The one non-mechanical part of the port, done in two halves. This task extracts the supplier code into its own module and makes `services/user` *delegate* to it; Task 8 replaces the delegation with events. Splitting it this way keeps the webhook handlers and their ~30 tests untouched here.

**Files:**
- Create: `server/app/utils/cache.py`, `server/app/modules/supplier/{__init__,service,cache,exceptions,dependencies}.py`
- Move: `server/app/models/supplier.py` → `server/app/modules/supplier/models.py`; `server/app/services/user/supplier_repository.py` → `server/app/modules/supplier/repository.py`
- Modify: `server/app/services/user/{__init__,service,cache,exceptions}.py`, `server/app/api/dependencies/authentication.py`, `server/app/integrations/clerk/webhooks/handlers/membership.py`, `server/alembic/env.py`, `server/tests/unit/conftest.py`, `server/tests/integration/conftest.py`
- Tests: create `server/tests/unit/modules/supplier/test_{service,cache}.py`; move `tests/unit/services/test_supplier_linking.py` (linking cases) and `tests/integration/services/test_supplier_repository.py` → `tests/integration/modules/supplier/test_repository.py`; edit `tests/unit/services/test_user_cache.py`, `tests/integration/services/test_user_service.py`, `tests/integration/api/test_auth_delete.py`

**Interfaces:**
- Produces: `from app.utils.cache import MISS, Miss`
- Produces: `from app.modules.supplier import supplier_service, SupplierID, get_supplier_id, SupplierNotLinkedError` with
  - `supplier_service.link_from_metadata(session, user_id: str, metadata: dict) -> Optional[str]`
  - `supplier_service.unlink_contact(session, user_id: str) -> Optional[str]`
  - `supplier_service.get_id_for_user(session, user_id: str) -> Optional[str]`
  - `supplier_cache` (`app.modules.supplier.cache`): `get_supplier_id`, `set_supplier_id`, `invalidate_user(*, user_id)`, `clear()`, `reset()`
- Transient (removed in Task 8): `UserService.link_supplier_from_metadata` and `UserService.unlink_supplier_contact` remain as one-line delegators; `services/user/service.py` imports `app.modules.supplier.service` and `.cache` (upward) inside the three call sites, not at module level — see Step 8's note on the cycle.
- Transient (rewritten in Task 7): `supplier/dependencies.py` imports `CurrentUser` from `app.api.dependencies.authentication`.

- [ ] **Step 1: The shared sentinel**

```python
# server/app/utils/cache.py
"""The cache-miss sentinel shared by the per-module caches.

A cached ``None`` is a legitimate value ("known not linked"), so reads return
``MISS`` for absence instead of ``None``. A class rather than a bare
``object()`` so it can appear in type hints; deliberately no ``__bool__``: the
protocol is ``is not MISS``, never truthiness.
"""

from typing import Final


class Miss:
    """Sentinel type meaning "no entry in the cache"."""

    __slots__ = ()

    def __repr__(self) -> str:
        """Return a readable marker for logs and test failure output."""
        return "<MISS>"


MISS: Final[Miss] = Miss()
```

- [ ] **Step 2: Move the model and the repository**

```bash
cd server
mkdir -p app/modules/supplier
git mv app/models/supplier.py app/modules/supplier/models.py
git mv app/services/user/supplier_repository.py app/modules/supplier/repository.py
```

In `app/modules/supplier/repository.py`: `from app.models.supplier import Supplier` → `from app.modules.supplier.models import Supplier`, and replace the module docstring's second paragraph ("Scoped to the fields the user service needs …") with: `Scoped to contact linking. Supplier lifecycle (create/update/delete) arrives with the first write route (architecture §8).`

In `alembic/env.py`: replace `from app.models.supplier import Supplier` with `import app.modules.supplier.models`.

- [ ] **Step 3: Write the failing supplier tests**

Create `server/tests/unit/modules/__init__.py`, `server/tests/unit/modules/supplier/__init__.py` (empty).

`server/tests/unit/modules/supplier/test_service.py` — the six linking cases from `tests/unit/services/test_supplier_linking.py`, rewritten to the new call shape. Move the file with `git mv tests/unit/services/test_supplier_linking.py tests/unit/modules/supplier/test_service.py`, then:

- replace `from app.models.supplier import Supplier` → `from app.modules.supplier.models import Supplier`; `from app.models.user import User` and `from app.services.user.service import UserService, merge_clerk_metadata` → `from app.modules.supplier.service import SupplierService`
- delete `make_user()` and pass a plain id: every `UserService().link_supplier_from_metadata(user, {…}, session)` becomes `SupplierService().link_from_metadata(session, "user-uuid-1", {…})` (the displaced-contact case uses `"user-uuid-2"` where it used a second user)
- patch strings: `app.services.user.service.supplier_repository.X` → `app.modules.supplier.service.supplier_repository.X`; `app.services.user.service.user_cache.invalidate_user` → `app.modules.supplier.service.supplier_cache.invalidate_user`
- cut the three `merge_*` tests plus `FakeMembership`/`FakeClerkUser` into a new `tests/unit/services/test_user_metadata.py` importing `from app.services.user.service import merge_clerk_metadata` (Task 7 moves it again)

`server/tests/unit/modules/supplier/test_cache.py` — the supplier-link cases cut from `tests/unit/services/test_user_cache.py` (the tests that call `set_supplier_id`/`get_supplier_id`, the `invalidate_user(user_id=…)` cases, and the "cached None is a value" case), importing `from app.modules.supplier.cache import SupplierCache` and `from app.utils.cache import MISS`. `UserCache(...)` → `SupplierCache(...)`; the constructor keeps `maxsize`, `ttl`, `timer` (no `role_ttl`). Leave the org-role cases in the old file, with `_MISS` → `MISS` imported from `app.utils.cache`.

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/supplier -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.modules.supplier.service'`

- [ ] **Step 4: The cache, the exception, the service**

```python
# server/app/modules/supplier/cache.py
"""In-memory cache of the user → supplier link.

``user_id -> supplier_id | None``. A cached ``None`` is a real value ("known
not linked"), which is why reads return ``MISS`` for absence.

Every public method is ``async def`` though nothing awaits: this is the seam
for a future Redis backend. ``TTLCache`` is not thread-safe and even reads
mutate its expiry bookkeeping; every access here is on the event loop thread.
"""

import time
from typing import (
    Callable,
    Final,
    Optional,
    Union,
)

from cachetools import TTLCache

from app.core.logging import logger
from app.utils.cache import MISS, Miss

DEFAULT_MAXSIZE: Final[int] = 10_000
DEFAULT_TTL: Final[float] = 300.0  # supplier links change rarely


class SupplierCache:
    """Bounded, TTL-expiring cache of supplier links, keyed by internal user_id."""

    def __init__(
        self,
        *,
        maxsize: int = DEFAULT_MAXSIZE,
        ttl: float = DEFAULT_TTL,
        timer: Callable[[], float] = time.monotonic,
    ) -> None:
        """Build the cache. ``timer`` is a monotonic clock, injected so tests can advance time."""
        self._supplier_id: "TTLCache[str, Optional[str]]" = TTLCache(maxsize=maxsize, ttl=ttl, timer=timer)

    async def get_supplier_id(self, user_id: str) -> Union[str, None, Miss]:
        """The cached link: a supplier id, ``None`` (known not linked), or ``MISS``."""
        supplier_id = self._supplier_id.get(user_id, MISS)
        if supplier_id is not MISS:
            logger.debug("supplier_id_cache_hit", user_id=user_id, linked=supplier_id is not None)
        return supplier_id

    async def set_supplier_id(self, user_id: str, supplier_id: Optional[str]) -> None:
        """Cache a ``user_id -> supplier_id`` mapping. ``None`` is a deliberate negative entry."""
        self._supplier_id[user_id] = supplier_id

    async def invalidate_user(self, *, user_id: str) -> None:
        """Drop the cached link for one user."""
        self._supplier_id.pop(user_id, None)
        logger.debug("supplier_cache_invalidated", user_id=user_id)

    async def clear(self) -> None:
        """Empty the cache. Async form, for parity with the Redis seam."""
        self.reset()

    def reset(self) -> None:
        """Synchronous ``clear()`` for pytest fixtures; never from a request path."""
        self._supplier_id.clear()


supplier_cache = SupplierCache()
```

```python
# server/app/modules/supplier/exceptions.py
"""Supplier domain exceptions."""

from app.exceptions.base import AuthorizationError


class SupplierNotLinkedError(AuthorizationError):
    """Raised when a request requires a supplier link but the current user has none.

    Surfaces to the client as 403 with error_code SUPPLIER_NOT_LINKED.
    Supplier portal users must accept an invitation (which links them during
    JIT provisioning) before any supplier-scoped endpoint will accept them.
    """

    error_code = "SUPPLIER_NOT_LINKED"
```

```python
# server/app/modules/supplier/service.py
"""Supplier service — the contact link between a supplier and a portal user."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.modules.supplier.cache import supplier_cache
from app.modules.supplier.repository import supplier_repository
from app.utils.cache import MISS


class SupplierService:
    """Links, unlinks and resolves the supplier a user manages."""

    @staticmethod
    async def link_from_metadata(session: AsyncSession, user_id: str, metadata: dict) -> Optional[str]:
        """Link a supplier to this user based on invitation metadata.

        Runs on every account sync (JIT provisioning and two webhooks), so it
        must be safely repeatable. Only an unlinked supplier is claimed, unless
        the metadata carries a truthy `replace` flag — so a retried event, or a
        second invite for an already-linked supplier, changes nothing.

        Args:
            session: DB session. Flushed, not committed.
            user_id: The user to link.
            metadata: Merged public metadata; read for `supplier_id` and `replace`.

        Returns:
            The linked Supplier.id, or None if nothing was linked.
        """
        supplier_id = metadata.get("supplier_id")
        if not supplier_id:
            return None

        replace_flag = bool(metadata.get("replace"))

        supplier = await supplier_repository.get_by_id(session, supplier_id)
        if supplier is None:
            logger.warning("supplier_link_target_missing", supplier_id=supplier_id, user_id=user_id)
            return None
        if supplier.contact_id is not None and not replace_flag:
            return None

        # Capture BEFORE overwriting. With replace_flag this is a RE-LINK: the
        # displaced contact holds a cached user_id -> supplier_id entry that is
        # now wrong, and once the old id is gone that entry is unreachable.
        previous_contact_id = supplier.contact_id
        supplier = await supplier_repository.set_contact_id(session, supplier, user_id)

        if previous_contact_id and previous_contact_id != user_id:
            await supplier_cache.invalidate_user(user_id=previous_contact_id)
        await supplier_cache.invalidate_user(user_id=user_id)

        logger.info(
            "supplier_linked",
            supplier_id=supplier.id,
            user_id=user_id,
            previous_contact_id=previous_contact_id,
            replace=replace_flag,
        )
        return supplier.id

    @staticmethod
    async def unlink_contact(session: AsyncSession, user_id: str) -> Optional[str]:
        """Clear Supplier.contact_id for any supplier this user manages.

        Anonymising the user row leaves Supplier.contact_id pointing at it,
        which still records *which supplier this person managed*. Clearing it
        removes that association; the supplier is left contact-less until
        someone is re-invited to it.

        Args:
            session: DB session. Flushed, not committed.
            user_id: Local User.id.

        Returns:
            The unlinked Supplier.id, or None if the user managed no supplier.
        """
        supplier = await supplier_repository.get_by_contact_id(session, user_id)
        if supplier is None:
            return None

        supplier = await supplier_repository.set_contact_id(session, supplier, None)
        await supplier_cache.invalidate_user(user_id=user_id)
        logger.info("supplier_unlinked", supplier_id=supplier.id, user_id=user_id)
        return supplier.id

    @staticmethod
    async def get_id_for_user(session: AsyncSession, user_id: str) -> Optional[str]:
        """Resolve the Supplier.id linked to this user, cache-first.

        A cached None is honoured as "known not linked" rather than treated as
        a miss. Returns None if no (non-soft-deleted) supplier is linked.
        """
        cached = await supplier_cache.get_supplier_id(user_id)
        if cached is not MISS:
            return cached

        supplier_id = await supplier_repository.get_id_by_contact_id(session, user_id)
        await supplier_cache.set_supplier_id(user_id, supplier_id)
        return supplier_id


supplier_service = SupplierService()
```

```python
# server/app/modules/supplier/dependencies.py
"""Supplier-scoped identity — resolves the caller's supplier_id."""

from typing import Annotated

from fastapi import Depends

from app.api.dependencies.authentication import CurrentUser  # Task 7 rewrites this to app.modules.account
from app.database.dependencies import DbSession
from app.modules.supplier.exceptions import SupplierNotLinkedError
from app.modules.supplier.service import supplier_service


async def get_supplier_id(current_user: CurrentUser, session: DbSession) -> str:
    """Resolve the supplier_id linked to the current user.

    Raises 403 SUPPLIER_NOT_LINKED if no Supplier.contact_id points at this user.

    Usage (value dep):
        async def handler(supplier_id: SupplierID, ...): ...
    """
    supplier_id = await supplier_service.get_id_for_user(session, current_user.id)
    if supplier_id is None:
        raise SupplierNotLinkedError(
            "User is not linked to a supplier — accept the invitation first",
            user_id=current_user.id,
        )
    return supplier_id


SupplierID = Annotated[str, Depends(get_supplier_id)]
```

```python
# server/app/modules/supplier/__init__.py
"""Supplier — the example domain: an external company and the portal user who manages it.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server-modules.md, R1). No router yet: the module
exists for the contact link and the supplier-scoped identity.
"""

from app.modules.supplier.dependencies import SupplierID, get_supplier_id
from app.modules.supplier.exceptions import SupplierNotLinkedError
from app.modules.supplier.service import supplier_service

__all__ = [
    "SupplierID",
    "SupplierNotLinkedError",
    "get_supplier_id",
    "supplier_service",
]
```

- [ ] **Step 5: Strip the supplier half out of `services/user`**

`app/services/user/cache.py`:
- delete `_Miss`, `_MISS`, `DEFAULT_TTL`, the `_supplier_id` TTLCache, `get_supplier_id`, `set_supplier_id`; add `from app.utils.cache import MISS, Miss`; `get_org_role` returns `Union[str, Miss]` and uses `MISS`
- constructor keeps only `maxsize`, `role_ttl`, `timer`
- `invalidate_user(self, *, clerk_id: str) -> None` — pops `_org_role[clerk_id]`, logs `user_cache_invalidated`; the no-argument warning branch goes
- `reset()` clears `_org_role` only; rewrite the module docstring to describe one cache

`app/services/user/exceptions.py`: delete `SupplierNotLinkedError`.

`app/services/user/__init__.py`: delete the `supplier_repository` import block and its two `__all__` entries.

`app/services/user/service.py`:
- imports: drop `supplier_repository`; `from app.services.user.cache import (_MISS, user_cache)` → `from app.services.user.cache import user_cache` plus `from app.utils.cache import MISS`; add `from app.modules.supplier.service import supplier_service  # transient upward import until Task 8` **inside each of the three call sites**, not at module level. A module-level import cycles, and importing the submodule rather than the root does not help: Python executes `app/modules/supplier/__init__.py` before any of its submodules, and that `__init__` imports `dependencies.py`, which imports `CurrentUser` from `app.api.dependencies.authentication`, which imports this file. A function-local import defers the whole chain to call time, after startup. `app/main.py` already uses this pattern. Task 8 deletes these imports with the delegators
- `resolve_org_role`: `_MISS` → `MISS`
- delete `get_supplier_id_for_user` entirely
- reduce the two remaining supplier methods to delegators (Task 8 deletes them):

```python
    async def link_supplier_from_metadata(self, user: User, metadata: dict, session: AsyncSession) -> Optional[str]:
        """Delegate to the supplier module. Replaced by the USER_SYNCED event in Task 8."""
        return await supplier_service.link_from_metadata(session, user.id, metadata)

    async def unlink_supplier_contact(self, user_id: str, session: AsyncSession) -> Optional[str]:
        """Delegate to the supplier module. Replaced by the USER_ERASING / USER_OFFBOARDED events in Task 8."""
        return await supplier_service.unlink_contact(session, user_id)
```

- `erase_user`: `await user_cache.invalidate_user(clerk_id=original_clerk_id, user_id=user.id)` → two lines: `await user_cache.invalidate_user(clerk_id=original_clerk_id)` and `await supplier_cache.invalidate_user(user_id=user.id)` (import `supplier_cache` from `app.modules.supplier.cache` — transient, Task 8 removes it)

`app/integrations/clerk/webhooks/handlers/membership.py`: the two `user_cache.invalidate_user(clerk_id=user.clerk_id, user_id=user.id)` calls become `await user_cache.invalidate_user(clerk_id=user.clerk_id)` followed by `await supplier_cache.invalidate_user(user_id=user.id)`; add `from app.modules.supplier.cache import supplier_cache` (transient, gone in Task 8).

`app/api/dependencies/authentication.py`: delete the "Supplier-scoped identity" block (`get_supplier_id`, `SupplierID`) and the `SupplierNotLinkedError` import.

- [ ] **Step 6: Fixtures and the tests that touch both caches**

`tests/unit/conftest.py` and `tests/integration/conftest.py` — the `clear_user_cache` fixture resets both:

```python
    from app.modules.supplier.cache import supplier_cache
    from app.services.user.cache import user_cache

    user_cache.reset()
    supplier_cache.reset()
    yield
    user_cache.reset()
    supplier_cache.reset()
```

`tests/integration/api/test_auth_delete.py`: import `supplier_cache` from `app.modules.supplier.cache` and `MISS` from `app.utils.cache`; `user_cache.set_supplier_id`/`get_supplier_id` → `supplier_cache.…`; `_MISS` → `MISS`; `from app.models.supplier import Supplier` → `from app.modules.supplier.models import Supplier`.

`tests/integration/services/test_user_service.py`: `service.get_supplier_id_for_user(x, db_session)` → `supplier_service.get_id_for_user(db_session, x)` (import from `app.modules.supplier`); `_MISS` → `MISS`; `Supplier` import path as above; any `user_cache.get_supplier_id` → `supplier_cache.get_supplier_id`.

`tests/unit/services/test_user_erasure.py`: the `invalidate.assert_awaited_once_with(clerk_id="user_abc", user_id=…)` → `invalidate.assert_awaited_once_with(clerk_id="user_abc")`.

`tests/unit/integrations/clerk/test_membership_handlers.py` and `test_user_handlers.py`: any assertion on `invalidate_user(clerk_id=…, user_id=…)` drops the `user_id` kwarg; patch string `app.services.user.cache.UserCache.set_org_role` is unchanged.

```bash
cd server
git mv tests/integration/services/test_supplier_repository.py tests/integration/modules/supplier/test_repository.py   # after: mkdir -p tests/integration/modules/supplier && touch tests/integration/modules/__init__.py tests/integration/modules/supplier/__init__.py
sed -i '' 's/app\.services\.user\.supplier_repository/app.modules.supplier.repository/; s/app\.models\.supplier/app.modules.supplier.models/' tests/integration/modules/supplier/test_repository.py
grep -rnE "models\.supplier|supplier_repository([^_a-z]|$)|_MISS|get_supplier_id_for_user|SupplierID|SupplierNotLinkedError" app tests | grep -vE "app/modules/supplier|tests/unit/modules/supplier|tests/integration/modules/supplier"
```

The last grep must show only `services/user/service.py`'s two delegators and the `MISS` imports.

- [ ] **Step 7: Run the whole suite**

Run: `cd server && APP_ENV=test uv run pytest tests -v`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
cd server && uv run ruff check . && uv run ruff format --check .
git add -A app tests alembic
git commit -m "refactor(supplier): the supplier code leaves the user service and becomes a module"
```

---

### Task 7: The `account` module (the move)

A pure move: every symbol keeps its name and behaviour. The two `Relationship`s go here because `User` and `Conversation` must drop them together; the conversation-name blanking they carried moves into `erase_user` as an explicit call (Task 9 moves it again, into the handler).

**Files:**
- Move (into `server/app/modules/account/`): `models/user.py` → `models.py` (+ `Role` from `models/enums.py`, which is deleted); `schemas/auth.py` → `schemas.py`; `services/user/{service,repository,cache,exceptions}.py` → same names; `api/dependencies/authentication.py` + `authorization.py` → `dependencies.py`; `api/v1/auth.py` → `router/auth.py`; `api/v1/webhooks.py` → `router/webhooks.py`
- Create: `modules/account/__init__.py`, `modules/account/router/__init__.py`
- Delete: `services/user/__init__.py`, `models/enums.py`
- Modify: `app/api/v1/api.py`, `app/api/system/health.py`, `app/api/dependencies/conversation.py`, `app/api/v1/{conversation,chatbot}.py`, `app/models/conversation.py`, `app/schemas/__init__.py`, `app/services/conversation/service.py`, `app/integrations/clerk/webhooks/handlers/{user,membership}.py`, `app/modules/supplier/dependencies.py`, `alembic/env.py`
- Tests: see Step 6

**Interfaces:**
- Produces: `from app.modules.account import user_service, Role, CurrentUser, CurrentRole, CurrentOrgId, InternalUserRole, PMOnly, ReviewerRole, SupplierRole, require_role, get_clerk_id, get_current_user, get_current_role, get_current_org_id, UserResponse, UserAlreadyExistsError, router`
- Produces: `conversation_service.blank_all_user_conversation_names(session, user_id) -> int`
- Consumes: `supplier_service` (Task 6), `DbSession` (Task 3)
- Transient (Task 8 removes): `app/integrations/clerk/webhooks/handlers/*.py` import `app.modules.account` (an adapter importing a module); `account/router/webhooks.py` imports `clerk_dispatcher` from `app.integrations.clerk.webhooks`.
- Transient (Task 9 removes): `account/service.py` imports `app.services.conversation`.

- [ ] **Step 1: Move the files**

```bash
cd server
mkdir -p app/modules/account/router
git mv app/models/user.py           app/modules/account/models.py
git mv app/schemas/auth.py          app/modules/account/schemas.py
git mv app/services/user/service.py     app/modules/account/service.py
git mv app/services/user/repository.py  app/modules/account/repository.py
git mv app/services/user/cache.py       app/modules/account/cache.py
git mv app/services/user/exceptions.py  app/modules/account/exceptions.py
git mv app/api/dependencies/authentication.py app/modules/account/dependencies.py
git mv app/api/v1/auth.py           app/modules/account/router/auth.py
git mv app/api/v1/webhooks.py       app/modules/account/router/webhooks.py
git rm -q app/services/user/__init__.py
```

- [ ] **Step 2: Models — `Role` joins `User`, the relationships go**

In `app/modules/account/models.py`:
- append the `Role` class from `app/models/enums.py` verbatim (with `from enum import StrEnum`), then `git rm -q app/models/enums.py`
- delete: the `TYPE_CHECKING` block, `Relationship` from the sqlmodel import, `List`/`TYPE_CHECKING` from typing, the `conversations:` field and its docstring line, the `for conversation in self.conversations:` loop, and the trailing `from app.models.conversation import Conversation  # noqa: E402`
- module docstring: `"""The user row and the organisation roles."""`

In `app/models/conversation.py`: delete the `TYPE_CHECKING` import block, `Relationship` from the import, the `user:` field and its docstring line. `foreign_key="user.id"` stays (R3).

In `alembic/env.py`: `from app.models.user import User` → `import app.modules.account.models`.

- [ ] **Step 3: Dependencies — one file**

Replace `app/modules/account/dependencies.py` with the merge of the old `authentication.py` and `authorization.py`, plus `CurrentOrgId`:

```python
"""Account dependencies — who is calling, with what role, in which organisation.

Resource-ownership checks ("does this supplier own this order?") live in the
owning module's service; nothing here touches a table but the user row.
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2AuthorizationCodeBearer

from app.core.config import settings
from app.core.logging import bind_context, logger
from app.database.dependencies import DbSession
from app.exceptions.base import AuthenticationError, AuthorizationError
from app.modules.account.models import Role, User
from app.modules.account.service import user_service

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=settings.auth.AUTHORIZE_URL,
    tokenUrl=settings.auth.TOKEN_URL,
    scopes={
        "openid": "OpenID Connect",
        "profile": "Profile information",
        "email": "Email address",
        "offline_access": "Refresh token",
    },
    auto_error=False,
)


def get_clerk_id(request: Request) -> str:
    """Extract clerk_id from request.state (set by AuthMiddleware)."""
    clerk_id = getattr(request.state, "clerk_id", None)
    if not clerk_id:
        logger.error("clerk_id_not_in_request_state")
        raise AuthenticationError("Authentication required")
    return clerk_id


async def get_current_user(
    request: Request,
    session: DbSession,
    clerk_id: str = Depends(get_clerk_id),
    _token: str = Depends(oauth2_scheme),
) -> User:
    """Get the current authenticated user with JIT provisioning."""
    try:
        org_id = getattr(request.state, "org_id", None)
        user = await user_service.resolve_user(clerk_id, org_id, session)
        request.state.user_id = user.id
        bind_context(user_id=user.id)
    except Exception as e:
        logger.error("user_provisioning_failed", clerk_id=clerk_id, error=str(e))
        raise AuthenticationError("Failed to provision user") from e
    return user


async def get_current_role(
    request: Request,
    _token: str = Depends(oauth2_scheme),
) -> Role:
    """Extract the org role from request.state, with Clerk API fallback.

    For JWTs with no org context (e.g. OIDC tokens), resolves the role from
    Clerk's org membership API (cached via UserService).

    This is the backend portability seam. When migrating to WorkOS or a
    DB-backed role table, only this function changes — all endpoints and
    require_role() calls remain unchanged.

    Raises:
        AuthorizationError: If no org role is present or the role is unrecognised.
    """
    raw = getattr(request.state, "org_role", None)

    if not raw:
        clerk_id = getattr(request.state, "clerk_id", None)
        if clerk_id:
            raw = await user_service.resolve_org_role(clerk_id)
            if raw:
                request.state.org_role = raw  # keep state consistent

    if not raw:
        raise AuthorizationError("No organization role in token")

    try:
        return Role(raw)
    except ValueError:
        raise AuthorizationError(f"Unknown role: {raw}")


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentRole = Annotated[Role, Depends(get_current_role)]


def get_current_org_id(user: CurrentUser) -> str:
    """The caller's organisation, read from the resolved user row.

    The row, not `request.state.org_id`: JIT provisioning fills the org from
    Clerk when the token carries none, so the row is authoritative once
    `get_current_user` has run (architecture §6).

    Raises:
        AuthorizationError: If the user belongs to no organisation.
    """
    if user.org_id is None:
        raise AuthorizationError("Organization membership required")
    return user.org_id


CurrentOrgId = Annotated[str, Depends(get_current_org_id)]


def require_role(*allowed: Role):
    """Dependency factory that enforces one of the allowed roles.

    Usage:
        @router.get("/projects", dependencies=[InternalUserRole])
        async def list_projects(user: CurrentUser, ...): ...

    Args:
        *allowed: One or more Role values that are permitted.

    Returns:
        A FastAPI Depends object suitable for use in the dependencies list.
    """

    def dependency(role: Role = Depends(get_current_role)) -> None:
        if role not in allowed:
            raise AuthorizationError(f"Role '{role}' is not permitted. Required: {[r.value for r in allowed]}")

    return Depends(dependency)


# Role guards — use in an endpoint's `dependencies=[...]` list.
InternalUserRole = require_role(Role.PROJECT_MANAGER, Role.REVIEWER, Role.APPROVER)  # any internal user
PMOnly = require_role(Role.PROJECT_MANAGER)
ReviewerRole = require_role(Role.PROJECT_MANAGER, Role.REVIEWER)
SupplierRole = require_role(Role.SUPPLIER)
```

Then `git rm -q app/api/dependencies/authorization.py`.

- [ ] **Step 4: Service, repository, cache, exceptions, schemas, routers, root**

Import rewrites inside the moved files (every `app.services.user.X` → `app.modules.account.X`; `app.models.user` → `app.modules.account.models`):

```bash
cd server
sed -E -i '' -e 's/app\.services\.user\.(service|repository|cache|exceptions)/app.modules.account.\1/g' \
          -e 's/app\.models\.user/app.modules.account.models/g' \
          -e 's/app\.models\.enums/app.modules.account.models/g' \
          -e 's/app\.schemas\.auth/app.modules.account.schemas/g' \
          app/modules/account/*.py app/modules/account/router/*.py
```

`app/modules/account/service.py`, `erase_user` — the name blanking that `anonymize_user()` lost, as an explicit step between the checkpoint deletion and the anonymisation:

```python
        conversation_ids = await conversation_service.soft_delete_all_user_conversations(session, user.id)
        for conv_id in conversation_ids:
            await delete_conversation_checkpoints(conv_id)

        await delete_user_memory(user.id)
        await self.unlink_supplier_contact(user.id, session)
        await conversation_service.blank_all_user_conversation_names(session, user.id)

        user.anonymize_user()
        session.add(user)
        await session.commit()
```

(delete the `session.refresh(user, attribute_names=["conversations"])` line and its comment). Its docstring's "Caching lives in …" line becomes `Caching lives in app/modules/account/cache.py — see UserCache.`

`app/services/conversation/service.py` — add, after `soft_delete_all_user_conversations`:

```python
    @staticmethod
    async def blank_all_user_conversation_names(session: AsyncSession, user_id: str) -> int:
        """Clear the name of every conversation a user owns, deleted or not.

        Part of erasure: a name is free text and may hold PII. Returns the
        number of rows touched.
        """
        statement = select(Conversation).where(Conversation.user_id == user_id)
        result = await session.execute(statement)
        conversations = result.scalars().all()

        for conv in conversations:
            conv.name = ""
            session.add(conv)

        await session.flush()
        logger.info("all_user_conversation_names_blanked", user_id=user_id, count=len(conversations))
        return len(conversations)
```

`app/modules/account/router/auth.py`: `router = APIRouter()` → `router = APIRouter(prefix="/auth", tags=["auth"])`; imports become `from app.database.dependencies import DbSession`, `from app.modules.account.dependencies import CurrentUser`, `from app.modules.account.schemas import UserResponse`, `from app.modules.account.service import user_service`.

`app/modules/account/router/webhooks.py`: `router = APIRouter()` → `router = APIRouter(prefix="/webhooks", tags=["webhooks"])`; `DbSession` import from `app.database.dependencies`; the `clerk_dispatcher` import stays on `app.integrations.clerk.webhooks` for this task.

```python
# server/app/modules/account/router/__init__.py
"""The account routes: the profile under /auth, the Clerk receiver under /webhooks."""

from fastapi import APIRouter

from app.modules.account.router.auth import router as auth_router
from app.modules.account.router.webhooks import router as webhooks_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(webhooks_router)
```

```python
# server/app/modules/account/__init__.py
"""Account — the Clerk-backed identity: the user row, the caller's identity, role and organisation, erasure.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server-modules.md, R1).

The dependency *getters* are exported alongside their Annotated aliases on
purpose: FastAPI keys dependency_overrides by the exact callable, so
get_current_user is the only way a test can stand in for CurrentUser.
"""

from app.modules.account.dependencies import (
    CurrentOrgId,
    CurrentRole,
    CurrentUser,
    InternalUserRole,
    PMOnly,
    ReviewerRole,
    SupplierRole,
    get_clerk_id,
    get_current_org_id,
    get_current_role,
    get_current_user,
    require_role,
)
from app.modules.account.exceptions import UserAlreadyExistsError
from app.modules.account.models import Role
from app.modules.account.router import router
from app.modules.account.schemas import UserResponse
from app.modules.account.service import user_service

__all__ = [
    "CurrentOrgId",
    "CurrentRole",
    "CurrentUser",
    "InternalUserRole",
    "PMOnly",
    "ReviewerRole",
    "Role",
    "SupplierRole",
    "UserAlreadyExistsError",
    "UserResponse",
    "get_clerk_id",
    "get_current_org_id",
    "get_current_role",
    "get_current_user",
    "require_role",
    "router",
    "user_service",
]
```

- [ ] **Step 5: Rewire the consumers**

`app/api/v1/api.py`:

```python
"""API v1 router — includes each module's router. Prefixes and tags live in the modules."""

from fastapi import APIRouter

from app.api.v1.chatbot import router as chatbot_router
from app.api.v1.conversation import router as conversation_router
from app.modules import account

api_router = APIRouter()
api_router.include_router(account.router)
api_router.include_router(conversation_router, prefix="/conversation", tags=["conversation"])
api_router.include_router(chatbot_router, prefix="/chatbot", tags=["chatbot"])
```

(The `auth`/`webhooks` lines go; the two conversation lines go in Task 9. Route order is unchanged for the schema: `webhooks` is `include_in_schema=False`.)

- `app/api/system/health.py`, `app/api/dependencies/conversation.py`, `app/api/v1/conversation.py`, `app/api/v1/chatbot.py`, `app/modules/supplier/dependencies.py`: `from app.api.dependencies.authentication import CurrentUser` → `from app.modules.account import CurrentUser`
- `app/integrations/clerk/webhooks/handlers/user.py` and `membership.py`: `from app.models.user import User` → `from app.modules.account.models import User`; `from app.services.user import (…)` → `from app.modules.account.cache import user_cache`, `from app.modules.account.repository import user_repository`, `from app.modules.account.service import user_service` (whichever each file used). Transient — Task 8 moves these handlers into `account`.
- `app/schemas/__init__.py`: delete the `UserResponse` import and `__all__` entry.

```bash
cd server && grep -rnE "app\.services\.user|app\.models\.user|app\.models\.enums|app\.schemas\.auth|api\.dependencies\.auth" app alembic   # expect nothing
```

- [ ] **Step 6: Move the tests**

```bash
cd server
mkdir -p tests/unit/modules/account tests/integration/modules/account/router
touch tests/unit/modules/account/__init__.py tests/integration/modules/account/__init__.py tests/integration/modules/account/router/__init__.py
git mv tests/unit/api/test_auth_dependencies.py        tests/unit/modules/account/test_dependencies.py
git mv tests/unit/services/test_user_cache.py           tests/unit/modules/account/test_cache.py
git mv tests/unit/services/test_user_erasure.py         tests/unit/modules/account/test_service.py
git mv tests/unit/services/test_user_repository_sync.py tests/unit/modules/account/test_repository.py
git mv tests/unit/models/test_enums.py                  tests/unit/modules/account/test_models.py
git mv tests/integration/api/test_auth.py               tests/integration/modules/account/router/test_auth.py
git mv tests/integration/api/test_auth_delete.py        tests/integration/modules/account/router/test_auth_delete.py
git mv tests/integration/api/test_webhooks.py           tests/integration/modules/account/router/test_webhooks.py
git mv tests/integration/dependencies/test_role_dependencies.py tests/integration/modules/account/test_dependencies.py
git mv tests/integration/services/test_user_service.py  tests/integration/modules/account/test_service.py
git mv tests/integration/services/test_user_repository.py tests/integration/modules/account/test_repository.py
```

Then:
- append the body of `tests/unit/services/test_user_metadata.py` (the three `merge_*` tests and the two fakes) to `tests/unit/modules/account/test_service.py`; `git rm` the old file
- cut `TestUserAnonymizeUser` from `tests/unit/models/test_models.py` into `tests/unit/modules/account/test_models.py`, minus `test_conversation_names_cleared` and `test_no_conversations_does_not_raise`, and minus any `conversations=`/`user.conversations = …` line in its `full_user` fixture. The mixin classes stay in `tests/unit/models/test_models.py`; fix their imports to `app.modules.account.models` / `app.models.conversation` as needed.
- cut `TestUserResponse` from `tests/unit/schemas/test_schemas.py` into a new `tests/unit/modules/account/test_schemas.py` (`from app.modules.account.schemas import UserResponse`)
- in `tests/unit/modules/account/test_service.py`: `make_user()` drops the `user.conversations = []` line; every erasure test adds `patch("app.modules.account.service.conversation_service.blank_all_user_conversation_names", new=AsyncMock(return_value=0))` beside the `soft_delete_all_user_conversations` patch
- add to `tests/integration/services/test_conversation_service.py`:

```python
async def test_blank_all_user_conversation_names_touches_deleted_rows_too(db_session, test_user):
    service = ConversationService()
    kept = await service.create_conversation(db_session, "conv-kept", test_user.id, name="Kept")
    gone = await service.create_conversation(db_session, "conv-gone", test_user.id, name="Gone")
    await service.soft_delete_conversation(db_session, gone.id)

    assert await service.blank_all_user_conversation_names(db_session, test_user.id) == 2

    await db_session.refresh(kept)
    await db_session.refresh(gone)
    assert (kept.name, gone.name) == ("", "")
```

Path rewrites across the whole test tree:

```bash
cd server
grep -rlE "app\.services\.user|app\.models\.user|app\.models\.enums|app\.schemas\.auth|app\.api\.dependencies\.auth|app\.api\.v1\.auth" tests | xargs sed -E -i '' \
  -e 's/app\.services\.user\.(service|repository|cache|exceptions)/app.modules.account.\1/g' \
  -e 's/app\.services\.user([^.a-z_]|$)/app.modules.account\1/g' \
  -e 's/app\.models\.user/app.modules.account.models/g' \
  -e 's/app\.models\.enums/app.modules.account.models/g' \
  -e 's/app\.schemas\.auth/app.modules.account.schemas/g' \
  -e 's/app\.api\.dependencies\.authentication/app.modules.account.dependencies/g' \
  -e 's/app\.api\.dependencies\.authorization/app.modules.account.dependencies/g' \
  -e 's/app\.api\.v1\.auth\./app.modules.account.router.auth./g'
grep -rnE "services\.user|models\.user|models\.enums|schemas\.auth|dependencies\.auth|api\.v1\.auth" tests   # expect nothing
```

- [ ] **Step 7: Run the whole suite and the contract**

Run: `cd server && APP_ENV=test uv run pytest tests -v && cd .. && make check-contract`
Expected: all pass; `check-contract` reports no diff

- [ ] **Step 8: Commit**

```bash
cd server && uv run ruff check . && uv run ruff format --check .
git add -A app tests alembic
git commit -m "refactor(account): the user service, its dependencies and routes become the account module"
```

---

### Task 8: The three `account` events; the Clerk handlers move into `account`

The behaviour-shaped half. `account` stops calling `supplier` and publishes `USER_SYNCED`, `USER_ERASING`, `USER_OFFBOARDED`; `supplier` subscribes inline. The Clerk webhook dispatcher and its handlers move from the adapter into `account/webhooks.py` (architecture D2), which removes the adapter's upward import.

**Files:**
- Create: `server/app/modules/account/webhooks.py` (dispatcher + handlers, one file), `server/app/modules/supplier/handlers.py`
- Delete: `server/app/integrations/clerk/webhooks/dispatcher.py`, `server/app/integrations/clerk/webhooks/handlers/`
- Modify: `server/app/modules/account/{__init__,service}.py`, `server/app/modules/account/router/webhooks.py`, `server/app/modules/supplier/__init__.py`, `server/app/integrations/clerk/webhooks/__init__.py`
- Tests: create `server/tests/unit/modules/account/test_webhooks.py` (from the two handler test files), `server/tests/unit/modules/supplier/test_handlers.py`; edit `tests/unit/modules/account/test_service.py`, `tests/integration/modules/account/router/test_webhooks.py`

**Interfaces:**
- Produces: `USER_SYNCED = "account.user_synced"`, `USER_ERASING = "account.user_erasing"`, `USER_OFFBOARDED = "account.user_offboarded"` on `app.modules.account` (defined in `service.py`)
- Payloads: `USER_SYNCED(session, user_id: str, metadata: dict)`; `USER_ERASING(session, user_id: str)`; `USER_OFFBOARDED(session, user_id: str)`
- Produces: `from app.modules.account.webhooks import clerk_dispatcher, ClerkEventDispatcher, handle_user_created, handle_user_updated, handle_user_deleted, handle_membership_created, handle_membership_updated, handle_membership_deleted, primary_email_from_payload, is_primary_email_verified`
- Consumes: `events` (Task 1), `supplier_service`, `supplier_cache` (Task 6)

- [ ] **Step 1: Write the failing supplier handler tests**

```python
# server/tests/unit/modules/supplier/test_handlers.py
"""The supplier module's reactions to account events (architecture §5)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.events import events
from app.modules.account import USER_ERASING, USER_OFFBOARDED, USER_SYNCED
from app.modules.supplier import handlers

pytestmark = pytest.mark.unit


@pytest.fixture
def session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    return s


def test_subscribes_inline_to_the_three_account_events():
    assert handlers.link_on_user_synced in events.handlers(USER_SYNCED)
    assert handlers.unlink_on_user_erasing in events.handlers(USER_ERASING)
    assert handlers.unlink_on_user_offboarded in events.handlers(USER_OFFBOARDED)


async def test_synced_links_from_the_merged_metadata(session):
    with patch("app.modules.supplier.handlers.supplier_service.link_from_metadata", new=AsyncMock()) as link:
        await handlers.link_on_user_synced(session=session, user_id="u1", metadata={"supplier_id": "sup_1"})
    link.assert_awaited_once_with(session, "u1", {"supplier_id": "sup_1"})


async def test_erasing_unlinks_and_drops_the_cached_link_even_when_nothing_was_linked(session):
    with (
        patch("app.modules.supplier.handlers.supplier_service.unlink_contact", new=AsyncMock(return_value=None)) as unlink,
        patch("app.modules.supplier.handlers.supplier_cache.invalidate_user", new=AsyncMock()) as invalidate,
    ):
        await handlers.unlink_on_user_erasing(session=session, user_id="u1")
    unlink.assert_awaited_once_with(session, "u1")
    invalidate.assert_awaited_once_with(user_id="u1")


async def test_offboarded_unlinks_and_logs_only_when_a_supplier_was_unlinked(session):
    with (
        patch("app.modules.supplier.handlers.supplier_service.unlink_contact", new=AsyncMock(return_value="sup_1")),
        patch("app.modules.supplier.handlers.supplier_cache.invalidate_user", new=AsyncMock()),
        patch("app.modules.supplier.handlers.logger") as logger,
    ):
        await handlers.unlink_on_user_offboarded(session=session, user_id="u1")
    logger.info.assert_called_once_with("supplier_unlinked_on_offboarding", user_id="u1", supplier_id="sup_1")


async def test_offboarded_does_not_log_an_unlink_when_there_was_none(session):
    with (
        patch("app.modules.supplier.handlers.supplier_service.unlink_contact", new=AsyncMock(return_value=None)),
        patch("app.modules.supplier.handlers.supplier_cache.invalidate_user", new=AsyncMock()) as invalidate,
        patch("app.modules.supplier.handlers.logger") as logger,
    ):
        await handlers.unlink_on_user_offboarded(session=session, user_id="u1")
    logger.info.assert_not_called()
    invalidate.assert_awaited_once_with(user_id="u1")
```

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/supplier/test_handlers.py -v`
Expected: FAIL with `ImportError: cannot import name 'USER_ERASING' from 'app.modules.account'`

- [ ] **Step 2: The event names and the publishes in `account/service.py`**

At the top of `app/modules/account/service.py`, after the imports:

```python
# Published for the modules above account (architecture §5). A subscriber
# imports the constant, so a renamed event is an import error, not a silent
# no-op.
USER_SYNCED = "account.user_synced"  # session, user_id, metadata — after JIT provisioning or a Clerk create
USER_ERASING = "account.user_erasing"  # session, user_id — before the row is anonymised
USER_OFFBOARDED = "account.user_offboarded"  # session, user_id — the user left their organisation
```

Imports: add `from app.core.events import events`; delete `from app.modules.supplier import supplier_service` and `from app.modules.supplier.cache import supplier_cache`.

`resolve_user`: `await self.link_supplier_from_metadata(user, merge_clerk_metadata(clerk_user), session)` →
`await events.publish(USER_SYNCED, session=session, user_id=user.id, metadata=merge_clerk_metadata(clerk_user))`

Delete `link_supplier_from_metadata` and `unlink_supplier_contact`.

`erase_user` becomes:

```python
        original_clerk_id = user.clerk_id

        # Inline subscribers run here, in this transaction, before the row is
        # anonymised: conversations (soft-delete, checkpoints, names) and the
        # supplier link. Their identifiers are what anonymize_user() destroys.
        subscriber_count = await events.publish(USER_ERASING, session=session, user_id=user.id)

        await delete_user_memory(user.id)

        user.anonymize_user()
        session.add(user)
        await session.commit()

        await user_cache.invalidate_user(clerk_id=original_clerk_id)

        logger.info("user_erased", user_id=user.id, subscriber_count=subscriber_count)
```

but keeping — for this task only — the direct conversation calls ahead of the publish, since `conversation` has no handler yet (Task 9 deletes these four lines and the two imports):

```python
        conversation_ids = await conversation_service.soft_delete_all_user_conversations(session, user.id)
        for conv_id in conversation_ids:
            await delete_conversation_checkpoints(conv_id)
        subscriber_count = await events.publish(USER_ERASING, session=session, user_id=user.id)
        await conversation_service.blank_all_user_conversation_names(session, user.id)
```

Update the `erase_user` docstring: "Step order is contractual. Subscribers to USER_ERASING and the memory deletion run before `anonymize_user()`, because they are keyed by identifiers it destroys. Cache invalidation happens after the commit, using the clerk_id captured before anonymisation rewrote it."

`app/modules/account/__init__.py`: `from app.modules.account.service import USER_ERASING, USER_OFFBOARDED, USER_SYNCED, user_service` and the three names in `__all__`.

- [ ] **Step 3: The supplier handlers**

```python
# server/app/modules/supplier/handlers.py
"""Subscriptions to account events.

All three are inline (architecture §5): a supplier's first request JIT-provisions
the user and resolves SupplierID in one transaction, so the link must exist
before the publisher commits; and an anonymised user row that still has a
Supplier.contact_id pointing at it is the association erasure exists to remove.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.core.logging import logger
from app.modules.account import USER_ERASING, USER_OFFBOARDED, USER_SYNCED
from app.modules.supplier.cache import supplier_cache
from app.modules.supplier.service import supplier_service


@events.on(USER_SYNCED, inline=True)
async def link_on_user_synced(session: AsyncSession, user_id: str, metadata: dict) -> None:
    """Claim the supplier named in the invitation metadata, if any."""
    await supplier_service.link_from_metadata(session, user_id, metadata)


@events.on(USER_ERASING, inline=True)
async def unlink_on_user_erasing(session: AsyncSession, user_id: str) -> None:
    """Drop the contact link and the cached link; the user is about to be anonymised."""
    await supplier_service.unlink_contact(session, user_id)
    await supplier_cache.invalidate_user(user_id=user_id)


@events.on(USER_OFFBOARDED, inline=True)
async def unlink_on_user_offboarded(session: AsyncSession, user_id: str) -> None:
    """Drop the contact link when the user leaves their organisation.

    Leaves the supplier contact-less with no signal to a project manager
    beyond this log line — a known cost, recorded in the webhooks design spec.
    """
    supplier_id = await supplier_service.unlink_contact(session, user_id)
    await supplier_cache.invalidate_user(user_id=user_id)
    if supplier_id is not None:
        logger.info("supplier_unlinked_on_offboarding", user_id=user_id, supplier_id=supplier_id)
```

`app/modules/supplier/__init__.py`: add `from app.modules.supplier import handlers` (with the comment `# @events.on is a module-level side effect: importing the root is what subscribes.`) — keep it *after* the other imports; it is not in `__all__`.

- [ ] **Step 4: The Clerk dispatcher and handlers move into `account/webhooks.py`**

Create `app/modules/account/webhooks.py` as the concatenation, in this order, of: the module docstring below; the imports; `ClerkEventDispatcher` from `integrations/clerk/webhooks/dispatcher.py`; the four helpers and six handlers from `handlers/user.py` and `handlers/membership.py`, verbatim except for the changes listed; the registration block from `dispatcher.py`.

```python
"""Clerk webhook dispatch and the account's handlers for it.

Dispatch and handlers sit together in the module that owns the rows they
write (architecture D2): the adapter (`app.integrations.clerk.webhooks`)
verifies and parses, this file decides what a Clerk event means for an
account. Handlers are registered by event type rather than selected with a
chain of conditionals, so each one stays independently testable and the
registry doubles as the list of events this app subscribes to.

Every handler must be idempotent. There is no dedup table: svix supplies
signature validity and a five-minute timestamp tolerance, and within that
window a replay must converge rather than duplicate.

Ordering: Clerk guarantees none. The user.* handlers compare the payload's
`updated_at` against `User.last_synced_at` and drop the stale one; the
membership handlers deliberately do not (reusing that column would conflate
two clocks). The one place a membership handler touches `last_synced_at` is
seeding UNSYNCED_EPOCH on a row it creates, so a *real* user.* event is never
mistaken for stale.
"""

from datetime import datetime
from typing import (
    Awaitable,
    Callable,
    Dict,
    Optional,
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.core.logging import logger
from app.integrations.clerk.timestamps import UNSYNCED_EPOCH, clerk_timestamp_to_datetime
from app.integrations.clerk.webhooks import WebhookContext
from app.modules.account.cache import user_cache
from app.modules.account.models import User
from app.modules.account.repository import user_repository
from app.modules.account.service import USER_OFFBOARDED, USER_SYNCED, user_service

WebhookHandler = Callable[[WebhookContext], Awaitable[None]]
```

Changes to the verbatim bodies:
- `handle_user_created`: last line `await user_service.link_supplier_from_metadata(user, data.get("public_metadata") or {}, session)` → `await events.publish(USER_SYNCED, session=session, user_id=user.id, metadata=data.get("public_metadata") or {})`
- `handle_membership_created`: same replacement
- `_sync_org_and_invalidate`: the two invalidation lines → `await user_cache.invalidate_user(clerk_id=user.clerk_id)` only (the supplier cache is the supplier module's to keep; `link_from_metadata` invalidates it on a link, and the offboarding handler on an unlink)
- `handle_membership_deleted`: from `supplier_id = await user_service.unlink_supplier_contact(user.id, session)` to the end → `await events.publish(USER_OFFBOARDED, session=session, user_id=user.id)` followed by `await user_cache.invalidate_user(clerk_id=user.clerk_id)`; drop the `supplier_unlinked_on_offboarding` log (it now lives in the supplier handler); trim the docstring's last paragraph to "Publishes USER_OFFBOARDED; the supplier module unlinks the contact."
- keep the `clerk_dispatcher = ClerkEventDispatcher()` and the `register(...)` block at the bottom, verbatim

Then:

```bash
cd server
git rm -rq app/integrations/clerk/webhooks/dispatcher.py app/integrations/clerk/webhooks/handlers
```

- `app/integrations/clerk/webhooks/__init__.py`: delete the `clerk_dispatcher` import and `__all__` entry; docstring's last clause becomes "`dispatcher` routing and the handlers live in the module that owns the rows — `app.modules.account.webhooks`."
- `app/modules/account/router/webhooks.py`: `clerk_dispatcher` comes from `app.modules.account.webhooks`; the other three names still from `app.integrations.clerk.webhooks`.

- [ ] **Step 5: Move and rewrite the tests**

```bash
cd server
git mv tests/unit/integrations/clerk/test_user_handlers.py tests/unit/modules/account/test_webhooks.py
```

Append the body of `tests/unit/integrations/clerk/test_membership_handlers.py` to it (drop its duplicate `ctx`, `session`, `clerk_has_the_user` fixtures, keeping the first file's; keep both `make_user`/`existing_user` helpers), then `git rm` the membership file. Then in `test_webhooks.py`:

- imports: everything from `app.integrations.clerk.webhooks.handlers.user` / `.membership` / `.dispatcher` → `from app.modules.account.webhooks import (…)`; `from app.modules.account import USER_OFFBOARDED, USER_SYNCED`
- every `patch("app.integrations.clerk.webhooks.handlers.user.user_service.link_supplier_from_metadata", …) as link` (and the membership equivalent) → `patch("app.modules.account.webhooks.events.publish", new=AsyncMock(return_value=1)) as publish`, and the assertion `link.assert_awaited_once_with(user, {…}, session)` → `publish.assert_awaited_once_with(USER_SYNCED, session=session, user_id=user.id, metadata={…})`
- every `patch("…membership.user_service.unlink_supplier_contact", …) as unlink` → `patch("app.modules.account.webhooks.events.publish", new=AsyncMock(return_value=1)) as publish`; `unlink.assert_awaited…` → `publish.assert_awaited_once_with(USER_OFFBOARDED, session=session, user_id=user.id)`; `unlink.assert_not_awaited()` → `publish.assert_not_awaited()`
- `test_deleted_logs_the_unlink_only_when_a_supplier_was_unlinked` and `test_deleted_logs_the_unlink_when_a_supplier_was_unlinked`: delete (covered by `tests/unit/modules/supplier/test_handlers.py`)
- `patch("app.integrations.clerk.webhooks.handlers.membership.logger")` → `patch("app.modules.account.webhooks.logger")`
- `test_both_event_spellings_dispatch`: `from app.integrations.clerk.webhooks.dispatcher import clerk_dispatcher` → `from app.modules.account.webhooks import clerk_dispatcher`

`tests/unit/modules/account/test_service.py` (the erasure tests): replace every `patch.object(UserService, "unlink_supplier_contact", …)` with `patch("app.modules.account.service.events.publish", new=AsyncMock(return_value=2)) as publish`; add to `test_erase_user_runs_full_cascade` the assertion `publish.assert_awaited_once_with(USER_ERASING, session=session, user_id="11111111-2222-3333-4444-555555555555")` (import `USER_ERASING` from `app.modules.account`); in `test_erase_user_clears_checkpoints_and_memory_before_anonymising` attach the publish mock to `parent` as `"publish"` and assert `call_order.index("publish") < call_order.index("anonymize_user")`; add:

```python
async def test_erase_user_logs_the_subscriber_count(session):
    user = make_user()
    with (
        patch("app.modules.account.service.conversation_service.soft_delete_all_user_conversations", new=AsyncMock(return_value=[])),
        patch("app.modules.account.service.conversation_service.blank_all_user_conversation_names", new=AsyncMock(return_value=0)),
        patch("app.modules.account.service.delete_user_memory", new=AsyncMock()),
        patch("app.modules.account.service.events.publish", new=AsyncMock(return_value=2)),
        patch("app.modules.account.service.user_cache.invalidate_user", new=AsyncMock()),
        patch("app.modules.account.service.logger") as logger,
    ):
        await UserService().erase_user(user, session)
    logger.info.assert_called_once_with("user_erased", user_id=user.id, subscriber_count=2)
```

`tests/integration/modules/account/router/test_webhooks.py`: `from app.integrations.clerk.webhooks.dispatcher import clerk_dispatcher` → `from app.modules.account.webhooks import clerk_dispatcher`. The end-to-end cases (`test_membership_deleted_for_matching_org_unlinks_supplier`, `test_user_deleted_anonymises…`) now exercise the real event path and need no change.

```bash
cd server && grep -rnE "link_supplier_from_metadata|unlink_supplier_contact|clerk\.webhooks\.handlers|clerk\.webhooks\.dispatcher|app\.modules\.supplier" app tests | grep -vE "^app/modules/supplier|^tests/.*/supplier/"
```

Expected: only `tests/integration/modules/account/test_service.py` (which legitimately uses `supplier_service` to observe the link) and `tests/integration/modules/account/router/test_auth_delete.py`.

- [ ] **Step 6: Run everything**

Run: `cd server && APP_ENV=test uv run pytest tests -v && cd .. && make check-contract`
Expected: all pass, no diff. The two subscribers for `USER_ERASING` at this point are only `supplier`'s (conversation's arrives in Task 9).

- [ ] **Step 7: Commit**

```bash
cd server && uv run ruff check . && uv run ruff format --check .
git add -A app tests
git commit -m "feat(account): USER_SYNCED, USER_ERASING and USER_OFFBOARDED replace the calls into supplier; clerk handlers move into account"
```

---

### Task 9: The `conversation` module; the old layer folders go

**Files:**
- Move (into `server/app/modules/conversation/`): `models/conversation.py` → `models.py`; `schemas/conversation.py` + `schemas/chat.py` (minus `Message`) → `schemas.py`; `services/conversation/{service,exceptions}.py` → same names; `api/dependencies/conversation.py` + `api/dependencies/agent.py` → `dependencies.py`; `api/v1/conversation.py` → `router/conversation.py`; `api/v1/chatbot.py` → `router/chatbot.py`
- Create: `modules/conversation/{__init__,handlers}.py`, `modules/conversation/router/__init__.py`, `app/agents/messages.py` (`Message`)
- Delete: `app/api/dependencies/` (whole folder), `app/services/` (whole folder), `app/schemas/{chat,conversation}.py`
- Modify: `app/api/v1/api.py`, `app/schemas/__init__.py`, `app/agents/graph.py`, `app/agents/base/agent.py`, `app/modules/account/service.py`, `alembic/env.py`
- Tests: see Step 5

**Interfaces:**
- Produces: `from app.modules.conversation import conversation_service, ConversationResponse, UserConversation, ChatbotAgentDep, get_user_conversation, get_chatbot_agent, ConversationAccessDeniedError, ConversationNotFoundError, ConversationServiceError, router`
- Produces: `from app.agents.messages import Message`
- Consumes: `USER_ERASING`, `CurrentUser` (account), `events`, `delete_conversation_checkpoints` (agents)
- Removes the last transient: `account/service.py` no longer imports conversation code.

- [ ] **Step 1: Write the failing handler test**

```python
# server/tests/unit/modules/conversation/test_handlers.py
"""The conversation module's reaction to USER_ERASING."""

from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.conversation import handlers

pytestmark = pytest.mark.unit


def test_subscribes_inline_to_user_erasing():
    assert handlers.erase_on_user_erasing in events.handlers(USER_ERASING)


async def test_soft_deletes_clears_checkpoints_then_blanks_names_in_that_order():
    session = AsyncMock()
    session.add = MagicMock()
    parent = MagicMock()
    soft_delete = AsyncMock(return_value=["conv_1", "conv_2"])
    checkpoints = AsyncMock()
    blank = AsyncMock(return_value=2)
    parent.attach_mock(soft_delete, "soft_delete")
    parent.attach_mock(checkpoints, "checkpoints")
    parent.attach_mock(blank, "blank")

    with (
        patch("app.modules.conversation.handlers.conversation_service.soft_delete_all_user_conversations", new=soft_delete),
        patch("app.modules.conversation.handlers.delete_conversation_checkpoints", new=checkpoints),
        patch("app.modules.conversation.handlers.conversation_service.blank_all_user_conversation_names", new=blank),
    ):
        await handlers.erase_on_user_erasing(session=session, user_id="u1")

    assert [c[0] for c in parent.mock_calls] == ["soft_delete", "checkpoints", "checkpoints", "blank"]
    assert checkpoints.await_args_list == [call("conv_1"), call("conv_2")]
    blank.assert_awaited_once_with(session, "u1")
```

Create `tests/unit/modules/conversation/__init__.py`. Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/conversation -v` → FAIL, `No module named 'app.modules.conversation'`.

- [ ] **Step 2: `Message` moves under `agents/`**

Create `app/agents/messages.py` with the `Message` class cut from `app/schemas/chat.py` (with its `re`, `Literal`, `BaseModel`, `Field`, `field_validator` imports) and the docstring `"""The chat message exchanged with an agent — the shape every agent's history uses."""`. Then:
- `app/agents/graph.py`: `from app.schemas.chat import Message` → `from app.agents.messages import Message`
- `app/agents/base/agent.py`: `from app.schemas import Message` → `from app.agents.messages import Message`
- `app/schemas/chat.py` is not touched here: Step 3 deletes it.

- [ ] **Step 3: Move the module's files**

```bash
cd server
mkdir -p app/modules/conversation/router
git mv app/models/conversation.py            app/modules/conversation/models.py
git mv app/schemas/conversation.py           app/modules/conversation/schemas.py
git mv app/services/conversation/service.py     app/modules/conversation/service.py
git mv app/services/conversation/exceptions.py  app/modules/conversation/exceptions.py
git mv app/api/dependencies/conversation.py  app/modules/conversation/dependencies.py
git mv app/api/v1/conversation.py            app/modules/conversation/router/conversation.py
git mv app/api/v1/chatbot.py                 app/modules/conversation/router/chatbot.py
```

`app/modules/conversation/schemas.py`: append `ChatRequest`, `ChatResponse`, `ConversationHistory`, `StreamResponse` from `app/schemas/chat.py`, with `from typing import List` and `from app.agents.messages import Message`; docstring `"""Conversation and chat request/response schemas."""`. Then `git rm -q app/schemas/chat.py`.

`app/modules/conversation/dependencies.py`: append `get_chatbot_agent` and `ChatbotAgentDep` from `app/api/dependencies/agent.py` (drop the trailing "Future agent dependencies" comment); imports become `from app.agents.chatbot.graph import ChatbotAgent`, `from app.database.dependencies import DbSession`, `from app.modules.account import CurrentUser`, `from app.modules.conversation.exceptions import ConversationAccessDeniedError, ConversationNotFoundError`, `from app.modules.conversation.models import Conversation`, `from app.modules.conversation.service import conversation_service`, `from app.utils.sanitization import sanitize_string`. Then:

```bash
cd server && git rm -rq app/api/dependencies app/services
```

`app/modules/conversation/service.py`: `from app.models.conversation import Conversation` → `from app.modules.conversation.models import Conversation`; `from app.services.conversation.exceptions import` → `from app.modules.conversation.exceptions import`.

`app/modules/conversation/router/conversation.py`: `router = APIRouter(prefix="/conversation", tags=["conversation"])`; imports: `from app.database.dependencies import DbSession`, `from app.modules.account import CurrentUser`, `from app.modules.conversation.dependencies import UserConversation`, `from app.modules.conversation.schemas import ConversationResponse`, `from app.modules.conversation.service import conversation_service`.

`app/modules/conversation/router/chatbot.py`: `router = APIRouter(prefix="/chatbot", tags=["chatbot"])`; imports: `from app.modules.account import CurrentUser`, `from app.modules.conversation.dependencies import ChatbotAgentDep, UserConversation`, `from app.modules.conversation.schemas import ChatRequest, ChatResponse, ConversationHistory, StreamResponse`, `from app.agents.messages import Message`.

```python
# server/app/modules/conversation/router/__init__.py
"""The conversation routes: CRUD under /conversation, chat under /chatbot."""

from fastapi import APIRouter

from app.modules.conversation.router.chatbot import router as chatbot_router
from app.modules.conversation.router.conversation import router as conversation_router

router = APIRouter()
router.include_router(conversation_router)
router.include_router(chatbot_router)
```

```python
# server/app/modules/conversation/handlers.py
"""Subscriptions to account events."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.shared.checkpointing import delete_conversation_checkpoints
from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.conversation.service import conversation_service


@events.on(USER_ERASING, inline=True)
async def erase_on_user_erasing(session: AsyncSession, user_id: str) -> None:
    """Erase what a user's conversations hold: the rows are soft-deleted, the messages gone, the names blank.

    Inline, in the publisher's transaction and before the user row is
    anonymised. Checkpoints are keyed by conversation id and hold the message
    text, so they go before the names — a test observes the name at the
    moment each checkpoint is deleted.
    """
    conversation_ids = await conversation_service.soft_delete_all_user_conversations(session, user_id)
    for conversation_id in conversation_ids:
        await delete_conversation_checkpoints(conversation_id)
    await conversation_service.blank_all_user_conversation_names(session, user_id)
```

```python
# server/app/modules/conversation/__init__.py
"""Conversation — a user's chat threads and the chatbot that answers in them.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server-modules.md, R1).
"""

from app.modules.conversation.dependencies import (
    ChatbotAgentDep,
    UserConversation,
    get_chatbot_agent,
    get_user_conversation,
)
from app.modules.conversation.exceptions import (
    ConversationAccessDeniedError,
    ConversationNotFoundError,
    ConversationServiceError,
)
from app.modules.conversation.router import router
from app.modules.conversation.schemas import ConversationResponse
from app.modules.conversation.service import conversation_service

# @events.on is a module-level side effect: importing the root is what subscribes.
from app.modules.conversation import handlers

__all__ = [
    "ChatbotAgentDep",
    "ConversationAccessDeniedError",
    "ConversationNotFoundError",
    "ConversationResponse",
    "ConversationServiceError",
    "UserConversation",
    "conversation_service",
    "get_chatbot_agent",
    "get_user_conversation",
    "router",
]
```

Note `services/conversation/__init__.py` used to instantiate `conversation_service`; the instance now comes from `service.py`'s own `conversation_service = ConversationService()` line, which already exists.

- [ ] **Step 4: The last rewires**

`app/api/v1/api.py` — final form:

```python
"""API v1 router — includes each module's router. Prefixes and tags live in the modules."""

from fastapi import APIRouter

from app.modules import account, conversation

api_router = APIRouter()
api_router.include_router(account.router)
api_router.include_router(conversation.router)
```

`app/schemas/__init__.py` — final form: `"""Cross-cutting schemas. ErrorResponse lives in app.schemas.base; a module's schemas live in its schemas slot."""` and nothing else.

`app/modules/account/service.py`: delete the four conversation lines added in Task 8 Step 2 and the imports `from app.services.conversation import conversation_service` and `from app.agents.shared.checkpointing import delete_conversation_checkpoints`, leaving `erase_user` exactly as the Task 8 listing shows.

`alembic/env.py`: `from app.models.conversation import Conversation` → `import app.modules.conversation.models`. The three module imports are now the whole models registry; add the comment `# Every module's models slot, so SQLModel.metadata is complete (architecture R8).`

```bash
cd server && grep -rnE "app\.services|app\.api\.dependencies|app\.models\.conversation|app\.schemas\.chat|app\.schemas\.conversation|app\.schemas import|app\.api\.v1\.(conversation|chatbot)" app alembic   # expect nothing
```

- [ ] **Step 5: Move the tests**

```bash
cd server
mkdir -p tests/unit/modules/conversation tests/integration/modules/conversation/router tests/unit/agents
touch tests/integration/modules/conversation/__init__.py tests/integration/modules/conversation/router/__init__.py
git mv tests/integration/api/test_conversations.py tests/integration/modules/conversation/router/test_conversation.py
git mv tests/integration/api/test_chatbot.py       tests/integration/modules/conversation/router/test_chatbot.py
git mv tests/integration/dependencies/test_conversation_access.py tests/integration/modules/conversation/test_dependencies.py
git mv tests/integration/services/test_conversation_service.py    tests/integration/modules/conversation/test_service.py
git rm -q tests/integration/dependencies/__init__.py tests/integration/services/__init__.py 2>/dev/null; rmdir tests/integration/dependencies tests/integration/services 2>/dev/null
```

Then:
- `tests/unit/schemas/test_schemas.py`: `TestMessage` → new `tests/unit/agents/test_messages.py` (`from app.agents.messages import Message`); `TestChatRequest`, `TestChatResponse`, `TestConversationHistory`, `TestStreamResponse`, `TestConversationResponse` → new `tests/unit/modules/conversation/test_schemas.py` (`from app.modules.conversation.schemas import …`, `from app.agents.messages import Message`); `TestErrorResponse` stays in `tests/unit/schemas/test_schemas.py` importing only `app.schemas.base`
- `tests/unit/models/test_models.py`: any `Conversation` import → `app.modules.conversation.models`
- `tests/unit/agents/test_graph.py`: `from app.schemas.chat import Message` → `from app.agents.messages import Message`
- `tests/integration/conftest.py`: `from app.api.dependencies.agent import get_chatbot_agent` → `from app.modules.conversation import get_chatbot_agent`; `from app.schemas.chat import Message` → `from app.agents.messages import Message`; in `stub_checkpoint_deletion`, the three patch targets become `app.modules.conversation.router.chatbot.delete_conversation_checkpoints`, `app.modules.conversation.router.conversation.delete_conversation_checkpoints` and `app.modules.conversation.handlers.delete_conversation_checkpoints` (yield the handler's stub, and reword the docstring's last sentence: the erasure path is now the conversation handler)
- `tests/unit/modules/account/test_service.py`: delete the `soft_delete_all_user_conversations` / `blank_all_user_conversation_names` / `delete_conversation_checkpoints` patches from every erasure test, and the `checkpoints.await_count == 2` assertion; the order test keeps `delete_user_memory` and `publish` before `anonymize_user`
- `tests/integration/modules/account/router/test_auth_delete.py`: `from app.models.conversation import Conversation` → `from app.modules.conversation.models import Conversation`; its two `TestDeleteMeCheckpointCleanup` cases now observe the conversation handler through the shared fixture and need no other change

```bash
cd server
grep -rlE "app\.models\.conversation|app\.services\.conversation|app\.api\.dependencies|app\.schemas\.chat|app\.schemas\.conversation|app\.api\.v1\.(conversation|chatbot)" tests | xargs sed -E -i '' \
  -e 's/app\.models\.conversation/app.modules.conversation.models/g' \
  -e 's/app\.services\.conversation\.(service|exceptions)/app.modules.conversation.\1/g' \
  -e 's/app\.services\.conversation/app.modules.conversation/g' \
  -e 's/app\.api\.dependencies\.conversation/app.modules.conversation.dependencies/g' \
  -e 's/app\.api\.dependencies\.agent/app.modules.conversation.dependencies/g' \
  -e 's/app\.schemas\.chat/app.modules.conversation.schemas/g' \
  -e 's/app\.schemas\.conversation/app.modules.conversation.schemas/g' \
  -e 's/app\.api\.v1\.conversation\./app.modules.conversation.router.conversation./g' \
  -e 's/app\.api\.v1\.chatbot\./app.modules.conversation.router.chatbot./g'
grep -rnE "app\.services|app\.api\.dependencies|app\.models\.(user|conversation|supplier|enums)|app\.schemas\.(auth|chat|conversation|system)|app\.api\.v1\.(auth|webhooks|conversation|chatbot)" tests   # expect nothing
```

- [ ] **Step 6: Run everything**

Run: `cd server && APP_ENV=test uv run pytest tests -v && cd .. && make check-contract`
Expected: all pass; no diff. `USER_ERASING` now has two subscribers; the integration erasure test `test_checkpoints_are_deleted_before_anonymisation` proves the handler order (name is "Before" when the checkpoint is deleted, "" afterwards).

- [ ] **Step 7: Commit**

```bash
cd server && uv run ruff check . && uv run ruff format --check .
git add -A app tests alembic
git commit -m "refactor(conversation): the conversation service, routes and schemas become a module; it erases its own data on USER_ERASING"
```

---

### Task 10: import-linter contracts in the pre-push hook and CI

**Files:**
- Modify: `server/pyproject.toml` (`[dependency-groups] dev`, `[tool.importlinter]`), `Makefile` (root, `check-server`), `server/uv.lock` (via `uv add`)
- Create: `.github/workflows/module-boundaries.yml`

**Interfaces:**
- Produces: `uv run lint-imports` exits 0 from `server/`; the contract names `R2: …`, `R6: …`, `R1: <module> …` that Task 11's completeness test parses.

- [ ] **Step 1: Install import-linter**

```bash
cd server && uv add --group dev "import-linter>=2.0"
uv run lint-imports; echo "exit=$?"
```

Expected: exit 1 with "Could not read any configuration" — proving the tool runs before the config exists.

- [ ] **Step 2: The contracts**

Append to `server/pyproject.toml`:

```toml
[tool.importlinter]
root_package = "app"
# R4 lets a module type-hint another's model under TYPE_CHECKING.
exclude_type_checking_imports = true

[[tool.importlinter.contracts]]
name = "R2: layers import downward only"
type = "layers"
# ':' joins siblings that may import each other; '|' would forbid it.
layers = [
    "app.main",
    "app.api",
    "app.modules",
    "app.integrations : app.agents",
    "app.core : app.database : app.exceptions : app.models : app.schemas : app.utils",
]

[[tool.importlinter.contracts]]
name = "R6: modules form a DAG — a module imports only those listed below it"
type = "layers"
layers = [
    # '|' forbids these siblings from importing each other; ':' would permit it.
    "app.modules.conversation | app.modules.supplier",
    "app.modules.account",
]

# R1: one contract per module, listing every OTHER module's submodules.
# allow_indirect_imports: a module's own __init__ re-exporting its submodules
# (the public surface) would otherwise register as an indirect import into
# that submodule for every consumer of the root. Direct bypass is what this
# forbids. tests/unit/test_module_contracts.py checks the list is complete.

[[tool.importlinter.contracts]]
name = "R1: account reaches other modules only through their package roots"
type = "forbidden"
source_modules = ["app.modules.account"]
forbidden_modules = ["app.modules.conversation.*", "app.modules.supplier.*"]
allow_indirect_imports = true

[[tool.importlinter.contracts]]
name = "R1: conversation reaches other modules only through their package roots"
type = "forbidden"
source_modules = ["app.modules.conversation"]
forbidden_modules = ["app.modules.account.*", "app.modules.supplier.*"]
allow_indirect_imports = true

[[tool.importlinter.contracts]]
name = "R1: supplier reaches other modules only through their package roots"
type = "forbidden"
source_modules = ["app.modules.supplier"]
forbidden_modules = ["app.modules.account.*", "app.modules.conversation.*"]
allow_indirect_imports = true
```

Run: `cd server && uv run lint-imports`
Expected: `Contracts: 5 kept, 0 broken.` If a contract is broken, the report names the import chain: fix the import (it is a real violation left over from Tasks 3–9), never the contract.

- [ ] **Step 3: Prove it bites**

```bash
cd server
printf '\nfrom app.modules.supplier.repository import supplier_repository  # probe\n' >> app/modules/account/service.py
uv run lint-imports; echo "exit=$?"
git checkout app/modules/account/service.py
```

Expected: exit 1, with both `R6` (account → supplier) and `R1: account …` reported broken. The checkout restores the file.

- [ ] **Step 4: The hook and CI**

Root `Makefile`, the `check-server` target and its help line:

```make
	@echo "  make check-server       - ruff check + ruff format --check + lint-imports"
…
check-server:
	@cd server && uv run ruff check . && uv run ruff format --check . && uv run lint-imports
```

```yaml
# .github/workflows/module-boundaries.yml
name: Module boundaries

on:
  pull_request:
  push:
    branches: [main]

# Reads the repo and writes nothing back.
permissions:
  contents: read

jobs:
  import-contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      # --group dev pulls in import-linter and ruff, --group test pulls in
      # pytest; the default sync installs only the base project dependencies.
      - name: Sync Python dependencies
        working-directory: server
        run: uv sync --frozen --group dev --group test

      # No database, no .env, no secrets: import-linter builds a static import
      # graph, ruff reads files, and the three unit files below import the app
      # without connecting to anything. This is `make check-server` split into
      # named steps, so a failure says which one broke.
      - name: Import contracts hold
        working-directory: server
        run: uv run lint-imports

      - name: Lint
        working-directory: server
        run: uv run ruff check .

      - name: Format
        working-directory: server
        run: uv run ruff format --check .

      - name: Module completeness and tenancy hold
        working-directory: server
        run: APP_ENV=test uv run pytest tests/unit/test_module_contracts.py tests/unit/models/test_tenant_tables.py tests/unit/core/test_events.py -v
```

(The last step's two new files land in Task 11; the workflow is committed here and first runs green after Task 11 — both tasks go in one push.)

- [ ] **Step 5: Run the gate as the hook would**

Run: `make check-server` from the repo root
Expected: ruff clean, `Contracts: 5 kept, 0 broken.`

- [ ] **Step 6: Commit**

```bash
git add server/pyproject.toml server/uv.lock Makefile .github/workflows/module-boundaries.yml
git commit -m "build(server): import-linter enforces R1, R2 and R6 in check-server and CI"
```

---

### Task 11: The two completeness checks and the explicit module imports

A fork adds a module the template never saw. Three things must not be forgettable: its R1/R6 contracts and its `alembic/env.py` line (`test_module_contracts.py`), its tables' tenancy (`test_tenant_tables.py`), and its import at startup (`main.py`) — a module with subscribers and no router (`supplier`) is otherwise never imported, and `events.publish` runs zero handlers with no error.

**Files:**
- Modify: `server/app/main.py`
- Create: `server/tests/unit/test_module_contracts.py`, `server/tests/unit/models/test_tenant_tables.py`

**Interfaces:**
- Consumes: the `[tool.importlinter]` table (Task 10), `TenantMixin` (Task 2), the three `models` slots.

- [ ] **Step 1: Write the failing contracts test**

```python
# server/tests/unit/test_module_contracts.py
"""Every module under app/modules/ is wired into the three places a fork must not forget.

R1 and R6 are import-linter contracts in pyproject.toml; a module without one is
simply unchecked. alembic/env.py is the models registry (R8); a models slot it
does not import is a table Alembic never sees. app/main.py imports every module
by name so that subscribers register even for a module with no router.
"""

import ast
import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

SERVER = Path(__file__).resolve().parents[2]
MODULES_DIR = SERVER / "app" / "modules"


def _modules() -> list[str]:
    return sorted(p.name for p in MODULES_DIR.iterdir() if p.is_dir() and (p / "__init__.py").exists())


def _contracts() -> list[dict]:
    config = tomllib.loads((SERVER / "pyproject.toml").read_text())
    return config["tool"]["importlinter"]["contracts"]


def _has_models_slot(name: str) -> bool:
    return (MODULES_DIR / name / "models.py").exists() or (MODULES_DIR / name / "models" / "__init__.py").exists()


def test_there_are_modules():
    assert _modules(), "app/modules/ holds no package — the test would pass vacuously"


@pytest.mark.parametrize("name", _modules())
def test_module_has_an_r1_contract_naming_every_other_module(name):
    matches = [
        c for c in _contracts() if c["type"] == "forbidden" and c.get("source_modules") == [f"app.modules.{name}"]
    ]
    assert len(matches) == 1, f"pyproject.toml needs exactly one R1 forbidden contract with source_modules = ['app.modules.{name}']"
    expected = {f"app.modules.{other}.*" for other in _modules() if other != name}
    assert set(matches[0]["forbidden_modules"]) == expected, f"the R1 contract for {name} must forbid exactly {sorted(expected)}"
    assert matches[0].get("allow_indirect_imports") is True, f"the R1 contract for {name} needs allow_indirect_imports = true"


@pytest.mark.parametrize("name", _modules())
def test_module_is_placed_in_the_r6_dag(name):
    r6 = next(c for c in _contracts() if c["name"].startswith("R6"))
    placed = {token.strip() for layer in r6["layers"] for token in layer.split("|")}
    assert f"app.modules.{name}" in placed, f"add app.modules.{name} to the R6 layers in pyproject.toml"


@pytest.mark.parametrize("name", [m for m in _modules() if _has_models_slot(m)])
def test_models_slot_is_imported_by_alembic_env(name):
    tree = ast.parse((SERVER / "alembic" / "env.py").read_text())
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert f"app.modules.{name}.models" in imported, f"alembic/env.py must `import app.modules.{name}.models`"


def test_main_imports_every_module_explicitly():
    tree = ast.parse((SERVER / "app" / "main.py").read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "app.modules"
        for alias in node.names
    }
    missing = sorted(set(_modules()) - imported)
    assert not missing, (
        f"module(s) {missing} have no `from app.modules import <name>` line in app/main.py; "
        "add one so their event subscribers register even without a router"
    )
```

- [ ] **Step 2: Write the failing tenancy test**

```python
# server/tests/unit/models/test_tenant_tables.py
"""Every table is tenant-scoped or listed here with a reason (architecture §6).

A new table fails this test until it either carries TenantMixin or gets a row in
ALLOWLIST. That is the entire mechanism: the decision cannot be skipped, only made.
"""

import importlib
import pkgutil

import pytest
from sqlmodel import SQLModel

import app.modules
from app.models.base import TenantMixin

pytestmark = pytest.mark.unit

# Table name -> why it carries no org_id. Delete a row when the table adopts the mixin.
ALLOWLIST: dict[str, str] = {
    "user": "org_id is nullable — erasure clears it so an anonymised row cannot single out a one-contact supplier org",
    "conversation": "owned through its user; the user's org is the tenant",
    "supplier": "no write route yet; adopts the mixin with the first one, and the backfill has no source until then",
}


def _import_every_models_slot() -> None:
    for module in pkgutil.iter_modules(app.modules.__path__):
        try:
            importlib.import_module(f"app.modules.{module.name}.models")
        except ModuleNotFoundError as e:
            if e.name != f"app.modules.{module.name}.models":
                raise


def _subclasses(cls: type) -> set[type]:
    found: set[type] = set()
    for sub in cls.__subclasses__():
        found.add(sub)
        found |= _subclasses(sub)
    return found


def _tenant_tables() -> set[str]:
    return {
        getattr(cls, "__tablename__", None)
        for cls in _subclasses(SQLModel)
        if issubclass(cls, TenantMixin)
        and cls is not TenantMixin
        and getattr(cls, "__tablename__", None) in SQLModel.metadata.tables
    }


def test_every_table_is_tenant_scoped_or_allowlisted():
    _import_every_models_slot()
    tables = set(SQLModel.metadata.tables)
    offenders = sorted(tables - _tenant_tables() - set(ALLOWLIST))
    assert not offenders, (
        f"table(s) {offenders} carry no org_id: add TenantMixin to the model, "
        "or add the table to ALLOWLIST in this file with the reason it is not tenant-owned"
    )


def test_allowlist_names_only_tables_that_exist():
    _import_every_models_slot()
    stale = sorted(set(ALLOWLIST) - set(SQLModel.metadata.tables))
    assert not stale, f"ALLOWLIST names table(s) {stale} that no models slot defines — remove the rows"


def test_allowlist_does_not_shadow_a_tenant_table():
    _import_every_models_slot()
    shadowed = sorted(set(ALLOWLIST) & _tenant_tables())
    assert not shadowed, f"table(s) {shadowed} carry TenantMixin; remove them from ALLOWLIST"
```

Run: `cd server && APP_ENV=test uv run pytest tests/unit/test_module_contracts.py tests/unit/models/test_tenant_tables.py -v`
Expected: `test_main_imports_every_module_explicitly` FAILS naming `['account', 'conversation', 'supplier']`; everything else passes (the contracts exist since Task 10; every table is allowlisted).

- [ ] **Step 3: Import every module in `main.py`**

In `server/app/main.py`, after `from app.database.engine import (…)` and before `from app.exceptions import (…)`:

```python
# Every module by name, whether or not it has a router. A module that only
# subscribes to events (supplier) would otherwise never be imported, and
# events.publish() would run zero handlers with no error.
# tests/unit/test_module_contracts.py checks this list against app/modules/.
from app.modules import account as _account
from app.modules import conversation as _conversation
from app.modules import supplier as _supplier
```

- [ ] **Step 4: Run the two files and the probe from the spec's §10.6**

```bash
cd server && APP_ENV=test uv run pytest tests/unit/test_module_contracts.py tests/unit/models/test_tenant_tables.py -v
mkdir -p app/modules/probe && printf '"""probe"""\n' > app/modules/probe/__init__.py
printf 'from sqlmodel import Field\nfrom app.models.base import BaseModel\n\n\nclass Probe(BaseModel, table=True):\n    """probe"""\n\n    id: str = Field(primary_key=True)\n' > app/modules/probe/models.py
APP_ENV=test uv run pytest tests/unit/test_module_contracts.py tests/unit/models/test_tenant_tables.py -q 2>&1 | tail -8
rm -r app/modules/probe
```

Expected: first run all pass. The probe run fails `test_module_has_an_r1_contract…[probe]`, `test_module_is_placed_in_the_r6_dag[probe]`, `test_models_slot_is_imported_by_alembic_env[probe]`, `test_main_imports_every_module_explicitly` and `test_every_table_is_tenant_scoped_or_allowlisted` (naming `probe`). The `rm` removes the probe.

- [ ] **Step 5: Full suite, gate, CI file**

Run: `cd server && APP_ENV=test uv run pytest tests -v && cd .. && make check-server && make check-contract`
Expected: all green, no diff.

- [ ] **Step 6: Commit**

```bash
git add server/app/main.py server/tests/unit/test_module_contracts.py server/tests/unit/models/test_tenant_tables.py
git commit -m "test(server): a module cannot be added without its contracts, its alembic line, its tenancy decision and its startup import"
```

---

### Task 12: Documentation

Every path that named the old layout, and the erasure order. No code changes.

**Files:**
- Modify: `server/CLAUDE.md`, `.claude/skills/fastapi-service-patterns/SKILL.md`, `.claude/skills/fastapi-service-patterns/references/{services,exceptions,client-wrappers,webhooks,api-routes}.md`, `server/docs/{authentication,gdpr-compliance-guide,gdpr-erasure-findings}.md`, `docs/setup/making-it-yours.md`, `README.md`, `docs/architecture/server-modules.md`, `docs/superpowers/specs/2026-09-22-server-modules-design.md`

- [ ] **Step 1: `server/CLAUDE.md`**

Replace the **Directory Structure** section (the tree and the paragraph after it) with:

````markdown
## Directory Structure

Module-first. The rules, the slots and the reasoning are in
[`docs/architecture/server-modules.md`](../docs/architecture/server-modules.md); this is the map.

```
server/
├── app/
│   ├── main.py              # Assembly: middlewares, handlers, routers, and an import of every module
│   ├── api/
│   │   ├── v1/api.py        # include_router(<module>.router) — prefixes and tags live in the modules
│   │   ├── system/          # Health, readiness, root — and their schemas
│   │   └── middlewares/     # Auth (JWT), access logging, correlation ID, rate limiting, metrics
│   ├── modules/             # One package per bounded context; import another only from its root
│   │   ├── account/         # User row, identity/role/org dependencies, Clerk webhooks, erasure
│   │   ├── conversation/    # Conversations and the chatbot routes; erases on USER_ERASING
│   │   └── supplier/        # The example domain: the contact link and SupplierID
│   ├── agents/              # LangGraph agents: base/, chatbot/, shared/, messages.py, graph.py
│   ├── integrations/        # Third-party adapters: clerk/ (client + webhook verification), llm/
│   ├── core/                # config, logging, metrics, limiter, events
│   ├── database/            # engine, session factory, DbSession (app/database/dependencies.py)
│   ├── exceptions/          # base.py — the exception hierarchy; handlers.py
│   ├── models/base.py       # BaseModel and the mixins, TenantMixin included
│   ├── schemas/base.py      # ErrorResponse
│   └── utils/               # JWT verification, sanitisation, the cache-miss sentinel
├── alembic/env.py           # Imports every module's models slot — the registry
└── tests/                   # Mirrors app/: tests/unit/modules/<name>/test_<slot>.py
```

A module has a fixed set of slots — `router`, `schemas`, `models`, `service`,
`repository`, `dependencies`, `exceptions`, optionally `handlers` and `domain` —
and a root `__init__.py` that is its whole public surface. Another module
imports from that root and nowhere deeper; `account` cannot import
`conversation` or `supplier`, so it publishes events (`app/core/events.py`) that
they subscribe to. `make check-server` runs `lint-imports` over the contracts
in `pyproject.toml`, and `tests/unit/test_module_contracts.py` fails the suite
when a new module lacks its entries.

`integrations/` holds code that exists only because a third party does — one
package per provider, carrying the outbound client and the inbound
verification. What a provider's event *means* for our rows is decided in the
module that owns them: `app/modules/account/webhooks.py` for Clerk.
````

**Exception Handling**: the example import becomes `from app.modules.documents.exceptions import DocumentNotFoundError`; the closing sentence becomes "Each module defines its own exceptions extending these, in `app/modules/<name>/exceptions.py`; integration exceptions go in `app/integrations/<provider>/exceptions.py`."

**Authentication**: the second bullet becomes:
```markdown
- Use `CurrentUser` from `app.modules.account` for protected endpoints; `CurrentRole`, `CurrentOrgId` and the `require_role(...)` guards come from the same root:
  ```python
  from app.modules.account import CurrentUser, PMOnly
  ```
```

**Testing**: replace the tree with:

```
tests/
├── unit/                  # Pure logic, no external deps — mock everything external
│   ├── modules/<name>/    # One file per slot file: test_service.py, test_handlers.py, …
│   ├── agents/  api/  config/  core/  exceptions/  integrations/  middleware/  models/  schemas/  utils/
│   ├── test_module_contracts.py   # every module has its contracts, its alembic line, its main.py import
│   └── models/test_tenant_tables.py  # every table carries org_id or is allowlisted with a reason
└── integration/           # Requires a live DB (testcontainers)
    ├── modules/<name>/    # routes under router/, then test_service.py, test_repository.py, …
    ├── api/  database/  exceptions/
```

and the example path line: "New tests mirror the `app/` structure: a test for `app/modules/account/cache.py` goes in `tests/unit/modules/account/test_cache.py`." The `pytest` example path becomes `tests/unit/modules/account/test_cache.py`.

**GDPR — Right to Erasure**: replace the numbered list with:

```markdown
When a user is deleted (`DELETE /api/v1/auth/me`, or Clerk's `user.deleted`), `account`'s `erase_user` runs, in order:

1. Clerk deletion, by the route only — on the webhook path Clerk's deletion is the trigger (JWTs immediately invalidated)
2. `USER_ERASING` published, inline: `conversation` soft-deletes the user's conversations, hard-deletes their LangGraph checkpoints, and blanks their names; `supplier` clears `Supplier.contact_id`
3. mem0 memories deleted (`delete_user_memory`)
4. User PII anonymised via `AnonymizableMixin.anonymize_user()`, then commit
5. The role cache invalidated under the clerk_id captured before step 4

Steps 2 and 3 run before step 4 because they are keyed by identifiers `anonymize_user()` destroys. The `user_erased` log line carries `subscriber_count`; a module that owns user-keyed data subscribes to `USER_ERASING` in its `handlers.py`.
```

Keep the three "Rules" bullets; the third becomes "Always call `delete_conversation_checkpoints()` before blanking or soft-deleting a conversation".

- [ ] **Step 2: The skill**

`.claude/skills/fastapi-service-patterns/SKILL.md`:
- frontmatter trigger: `app/services/, app/integrations/, app/api/, or app/exceptions/` → `app/modules/, app/integrations/, app/api/, or app/exceptions/`
- **File layout for a new domain** — replace the tree and the two paragraphs after it with:

````markdown
```
app/
  modules/
    payment/
      __init__.py      # the public surface: what other modules may import
      router.py        # APIRouter(prefix="/payments", tags=["payments"])
      schemas.py
      models.py        # tables carry TenantMixin (or a row in tests/unit/models/test_tenant_tables.py)
      service.py       # PaymentService class (orchestrator) + payment_service singleton
      repository.py    # PaymentRepository class (DB ops) + payment_repository singleton
      dependencies.py
      exceptions.py    # Domain-specific exception classes
      handlers.py      # only if it subscribes to another module's events
```

An external-API adapter lives in `app/integrations/<provider>/`, not `app/modules/` — and has no
`repository.py`. It has `client.py` (SDK wrapper + error translation) and `exceptions.py`, plus `webhooks/` for
verifying what the provider pushes to us; what those events *mean* for a module's rows is decided in that module
(`app/modules/account/webhooks.py` for Clerk). See `references/client-wrappers.md` and `references/webhooks.md`.

Then, in this order — each is a test until done: `include_router(payment.router)` in `app/api/v1/api.py`;
`from app.modules import payment` in `app/main.py`; `import app.modules.payment.models` in `alembic/env.py`; an R1
contract and an R6 layer entry in `pyproject.toml`. `docs/architecture/server-modules.md` has the rules.
````

`references/services.md`: `# app/services/payment/repository.py` → `# app/modules/payment/repository.py`; both `# app/services/payment/service.py` → `# app/modules/payment/service.py`.
`references/exceptions.md`: heading `## Domain exceptions (\`app/services/<domain>/exceptions.py\`)` → `app/modules/<name>/exceptions.py`.
`references/client-wrappers.md`: every `app/services/` → `app/modules/` (lines 5, 7, 45, 142); line 7's "`app/services/` holds *domain* logic" → "`app/modules/` holds *domain* logic".
`references/api-routes.md`: `from app.api.dependencies.auth import CurrentUser` → `from app.modules.account import CurrentUser`; `from app.api.dependencies.database import DbSession` → `from app.database.dependencies import DbSession`.
`references/webhooks.md`, the **Handlers** paragraph: "They call into `app/services/<domain>/`; nothing in `services/` imports them." → "They live in the module that owns the rows they write (`app/modules/account/webhooks.py`), beside the dispatcher; the provider package under `app/integrations/` only verifies and parses, and imports nothing from `app/modules/`."

- [ ] **Step 3: `server/docs/*`**

`authentication.md`: headings 3, 4, 6, 7 and the caches section: `app/api/dependencies/auth.py` → `app/modules/account/dependencies.py`; `app/services/user/service.py` → `app/modules/account/service.py`; `app/services/user/repository.py` → `app/modules/account/repository.py`; "Supplier Repository — `app/services/user/supplier_repository.py`" → "Supplier link — `app/modules/supplier/` (`USER_SYNCED` subscriber)"; "In-Memory Caches — `app/services/user/cache.py`" → "In-Memory Caches — `app/modules/account/cache.py` (org role) and `app/modules/supplier/cache.py` (supplier link)"; `app/integrations/clerk/webhooks/handlers/membership.py` → `app/modules/account/webhooks.py`.

`gdpr-compliance-guide.md`: the `app/services/user/api.py` header and the three imports at lines ~179–181 describe code that predates the current erasure path; replace that block with a pointer: "The current erasure cascade is `erase_user` in `app/modules/account/service.py`; see server/CLAUDE.md, *GDPR — Right to Erasure*, for the order." Replace `app/api/dependencies/database` → `app/database/dependencies`.

`gdpr-erasure-findings.md`: `app/models/user.py` → `app/modules/account/models.py`; `app/models/conversation.py` → `app/modules/conversation/models.py`; `app/models/supplier.py` → `app/modules/supplier/models.py`; `app/services/user/service.py` → `app/modules/account/service.py`. Line references (`:59-73`, `:310`) are stale either way — drop the `:NN` suffixes. Under the A1 finding, add one sentence: "Since the modules refactor the conversation-name blanking is done by `conversation`'s `USER_ERASING` handler, not by `anonymize_user()`."

- [ ] **Step 4: Setup doc, README, the two design docs**

`docs/setup/making-it-yours.md` §4, the table's first two rows become:

```markdown
| `Supplier` model, repository, link service and `SupplierID` | `server/app/modules/supplier/` — delete the folder, its three lines in `server/pyproject.toml` (`[tool.importlinter]`: the `R1: supplier` contract and the `app.modules.supplier` token in the R6 layers, plus the `account`/`conversation` contracts' `app.modules.supplier.*` entries), its `import` in `server/alembic/env.py`, its line in `server/app/main.py`, and its row in `server/tests/unit/models/test_tenant_tables.py`; then `server/alembic/versions/*_add_supplier_table.py` |
| Role names | `server/app/modules/account/models.py` **and** `web-app/packages/auth/src/permissions.ts` — **and the Clerk dashboard** (see [`clerk.md`](./clerk.md) §2) |
```

(the old "Supplier-scoped identity" row is folded into the first).

`README.md` line 99: `├── docs/                          # Setup guides, RBAC, design history` → `├── docs/                          # Setup guides, RBAC, architecture, design history`.

`docs/architecture/server-modules.md` header: `**Status:** proposed · designed 22 Sep 2026 · implemented by …` → `**Status:** implemented · designed 22 Sep 2026 · landed by [\`2026-09-22-server-modules-design.md\`](../superpowers/specs/2026-09-22-server-modules-design.md) on \`refactor/server-modules\``. Then read §2's tree against `find server/app/modules -name '*.py' | sort` and correct any file the tree lists that does not exist or omits that does.

`docs/superpowers/specs/2026-09-22-server-modules-design.md`: `**Status:** approved, not yet implemented` → `**Status:** implemented`.

- [ ] **Step 5: Nothing names the old layout**

```bash
git grep -nE "app/services|app\.services|api/dependencies|api\.dependencies|services/user|models/enums|schemas/chat|utils/graph|webhooks/handlers" -- ':!docs/superpowers' ':!server/openapi.json' ':!web-app'
```

Expected: no output. (`docs/superpowers/` is the dated record and keeps the old names by design — `docs/README.md`, *History*.)

- [ ] **Step 6: Commit**

```bash
git add server/CLAUDE.md .claude/skills/fastapi-service-patterns server/docs docs README.md
git commit -m "docs: the module layout replaces the layer layout everywhere the docs name a path"
```

---

### Task 13: Verification (spec §10)

Each step gates the next. Nothing here changes code; a failure sends you back to the task that owns the file.

- [ ] **Step 1: The contract is byte-identical**

Run: `make check-contract` from the repo root
Expected: no diff, exit 0. `git diff --stat server/openapi.json web-app/packages/api-client/src/generated` prints nothing.

- [ ] **Step 2: No schema change**

```bash
cd server && make docker-run-db ENV=development 2>/dev/null || true   # or `make docker-run-db` from the root
cd server && APP_ENV=development uv run alembic upgrade head && APP_ENV=development uv run alembic revision --autogenerate -m probe
```

Open the newest file under `server/alembic/versions/`: `upgrade()` and `downgrade()` must each contain only `pass`. Then delete that file (`git status` shows it untracked). If anything else is in it, a model changed shape — find it and revert.

- [ ] **Step 3: The gate**

Run: `make check-server`
Expected: ruff clean, `Contracts: 5 kept, 0 broken.`

- [ ] **Step 4: The suite**

Run: `cd server && make test`
Expected: green, including `tests/unit/core/test_events.py`, `tests/unit/test_module_contracts.py`, `tests/unit/models/test_tenant_tables.py`, `tests/unit/modules/supplier/test_handlers.py`, `tests/unit/modules/conversation/test_handlers.py`.

- [ ] **Step 5: Live smoke (manual — needs the dev stack and a Clerk supplier user)**

`make docker-run-core` from the root, then:
1. Sign in to the supplier portal as a freshly invited supplier user (invitation metadata carrying `supplier_id`). The first request must succeed and the server log must show `jit_provisioning_user` followed by `supplier_linked` in the same request — the inline `USER_SYNCED` path.
2. As a user with at least one conversation: `DELETE /api/v1/auth/me`. The log shows `all_user_conversations_soft_deleted`, `all_user_conversation_names_blanked`, `supplier_unlinked` (if linked) and `user_erased … subscriber_count=2`. In the database: the conversations have `deleted_at` set and `name = ''`; the supplier's `contact_id` is NULL; the user row is anonymised.

If the stack cannot be run, say so in the report rather than marking this step done.

- [ ] **Step 6: The guards bite (already exercised in Task 10 Step 3 and Task 11 Step 4)**

Re-run both probes once more against the final tree, then confirm `git status` is clean.

- [ ] **Step 7: Report**

List the commit range, the outcome of each of the six steps, and any spec deviation the executor made (each must be justified by a failing test or a broken contract, not by convenience).
