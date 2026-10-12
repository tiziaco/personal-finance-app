---
name: server-patterns
description: >
  Coding patterns and conventions for the FastAPI server. Use whenever creating or modifying a module, a service
  class, a repository, defining custom exceptions, adding error handling, writing or changing API routes,
  subscribing to or publishing an event between modules, or integrating a third-party provider in either direction.
  Trigger on tasks like "add a module", "add a service", "create an exception", "add an endpoint",
  "change a route's response", "handle this error", "implement a repository", "subscribe to an event",
  "react to another module's action", "inline or deferred", "my event handler never ran", "add a user-owned table", "wrap this SDK", "handle a webhook", or any
  feature work touching app/modules/, app/integrations/, app/api/, app/exceptions/ or app/core/events.py. Use even
  for partial tasks like "add a method to XService" — always follow the patterns below.
---

# Server Patterns

The server is a modular monolith: one package per bounded context under `app/modules/`, four layers that import
downward only. The architecture — the layers, the slots, rules R1–R9, the request path, errors, events and ownership —
is in `docs/architecture/server.md`, and this skill does not restate it. This skill covers how the code
inside that structure is written, and how a new module is put together and wired up. Read the relevant reference
file before writing any code.

## Reference files

| Topic | File | Read when… |
|---|---|---|
| Creating a module | `references/new-module.md` | **Adding a module** — the whole task: the two decisions, the slots, the four wiring edits, the tests that gate them. Start here; it cites the doc for the reasoning |
| Module boundaries, layers, ownership | `docs/architecture/server.md` §1–§3, §9 | Importing across modules, a foreign key or type hint to another module's table, adding a table to an existing module, or a module that has outgrown flat slots (packages-as-slots, a `domain` slot) |
| Events between modules | `references/events.md` | Publishing or subscribing to an event, choosing inline vs deferred, a subscriber that never runs, publishing from a script or worker |
| Services and repositories | `references/services.md` | Adding/modifying a service, a repository, or an event subscriber |
| Exceptions | `references/exceptions.md` | Defining new exception classes |
| Error handling | `references/error-handling.md` | Writing try/catch, retries, or fail-fast checks |
| External API adapters | `references/client-wrappers.md` | Wrapping a third-party SDK or HTTP client (outbound) |
| Inbound webhooks | `references/webhooks.md` | Receiving events a provider pushes to us (signature, dispatch, handlers) |
| API routes | `references/api-routes.md` | Adding or changing endpoints, ownership dependencies, the OpenAPI contract, input bounds, pagination, batch ops, deletes |
| Database operations | `references/database.md` | Querying, owner scoping, bulk ops, relationship loading, N+1 avoidance |

## Quick rules (always apply)

- Services: stateless orchestrator class + `@staticmethod async` methods + module-level singleton
- Services never touch the DB directly — every `select()`, `session.get()` and `session.execute()` lives in the
  module's `repository.py`, which is also a stateless class + `@staticmethod async` methods + module-level singleton
- A service can orchestrate more than one repository and/or external client wrapper — that's its job
- A route never receives `None`: either the service raises the domain exception, or the module's ownership
  dependency does (`UserConversation` in `app/modules/conversation/dependencies.py`). Repositories return `Optional`
- Parameter naming: `session: AsyncSession` in services and repositories, `db_session: DbSession` in routes
- Every module has its own `exceptions.py`; always inherit from a category class in `app/exceptions/base.py`
- `raise ... from e` on every external error to preserve the traceback
- `flush()` + `refresh()` after DB writes — never `commit()`; the `get_db_session` dependency owns the transaction.
  `DbSession` is `scope="function"`, so the commit runs after the route returns and before the response is sent.
  No carve-outs
- A background task or a `StreamingResponse` body never uses the request's session: by the time it runs, that
  session is committed and closed. Pass plain values; a task that needs the database opens its own from
  `request.app.state.session_factory`
- A route that carries a rate limit takes `@limiter.limit(settings.rate_limits.endpoints.<NAME>[0])` — a setting,
  never a literal — and then `request: Request` is its first parameter. There is no `SlowAPIMiddleware`, so an
  undecorated route is unlimited; today that is `GET /auth/me` and the webhook receiver (the latter deliberately —
  see `references/webhooks.md`)
- Every route declares a camelCase `operation_id`, a tag on its router, and a `response_model` or `204` —
  `tests/unit/api/test_openapi_contract.py` fails otherwise. After any route change run `make gen-contract`; the
  pre-commit hook blocks drift
- Bound free text on input (`max_length` on the form field or schema), store it as typed, and never put a length
  limit on a response model
- Structured logging: `logger.info("snake_case_event", key=value)` — never f-strings
- Rows that must be retained but hidden soft-delete (`SoftDeleteMixin.soft_delete()`). Personal data does not: it is
  erased — see the GDPR section of `server/CLAUDE.md`
- A user-owned table carries `UserOwnedMixin` (`user_id`, FK `user.id`) or a row in `test_owned_tables.py`'s ALLOWLIST
  (R7); every repository query on it filters `user_id`
- Across modules, import only from the package root: `from app.modules.account import CurrentUser`. Never
  `.repository`, `.models` or `.service` of another module (R1)
- Layers import downward only: modules → adapters (`app/integrations`, `app/agents`) → foundation (`app/core`,
  `app/database`, `app/exceptions`, `app/utils`, the base model and schema). `app/api` and `app/main.py` import
  anything (R2)
- A module owns its tables. A foreign key to another module's table is declared by table name
  (`foreign_key="user.id"`); there are no ORM relationships across modules (R3)
- Another module's model class is imported only under `TYPE_CHECKING`, for a type hint (R4)
- Tests mirror the tree: `tests/unit/modules/<name>/` and `tests/integration/modules/<name>/`, one test file per slot
  file (R5). Load the `server-testing` skill before writing one
- Modules form a DAG. When a lower module needs a higher one to act, it publishes on `app/core/events.py` and the
  higher module subscribes with `@events.on(NAME)` in its `handlers.py`, choosing inline or deferred on purpose; the
  event name is a constant exported from the publisher's root. `account` publishes `USER_SYNCED` and `USER_ERASING`
  (R6; `references/events.md`)

## File layout for a new module

```
app/modules/payment/
  __init__.py      # public surface: payment_service, public schemas, dependencies, exceptions, event names
  router.py        # APIRouter(prefix="/payments", tags=["payments"]); mounted by app/api/v1/api.py
  schemas.py
  models.py        # the tables this module owns; UserOwnedMixin or an allowlist row; FK to other modules by name
  service.py       # PaymentService (orchestrator) + payment_service singleton
  repository.py    # PaymentRepository (DB ops) + payment_repository singleton
  dependencies.py
  exceptions.py
  handlers.py      # only if it subscribes to another module's events; the root imports it
```

A slot becomes a package of the same name when it outgrows one file, and a module without routes has no
`router.py` (every module has routes today). Wiring it up is four edits — `app/api/v1/api.py`, `app/main.py`, `alembic/env.py` and
the import-linter contracts in `pyproject.toml` — and the last of those touches *every* module, not just the new
one: the R1 contracts are symmetric and `tests/unit/test_module_contracts.py` checks each one names all the
others. Follow `references/new-module.md`; it has the order, the exact edits and the tests that gate them.

If the module holds data keyed to a user, subscribe to `USER_ERASING` in its `handlers.py` and clean up there,
inline (GDPR section of `server/CLAUDE.md`; `app/modules/conversation/handlers.py` is the model). If a provider pushes
events about the module's table, the handlers and their dispatch are a further file, `webhooks.py`, as in `account`.

An external-API adapter lives in `app/integrations/<provider>/`, not `app/modules/` — and has no
`repository.py`. It has `client.py` (SDK wrapper + error translation) and `exceptions.py`, plus `webhooks/` if the
provider pushes events to us. See `references/client-wrappers.md` for the outbound half and
`references/webhooks.md` for the inbound one.
