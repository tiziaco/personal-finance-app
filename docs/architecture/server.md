# Server — modules, the request path, and the seams between them

How `server/` is put together: one FastAPI process partitioned into modules, the layers
and rules between them, what happens to a request on its way in and out, how errors and
events travel, and where ownership is held. This describes the system as it stands and is
kept current. How the code inside a module is written — services, repositories, routes,
exceptions, subscribers — is in [`server/CLAUDE.md`](../../server/CLAUDE.md) and the
`server-patterns` skill; how a token becomes a user is in
[`authentication.md`](./authentication.md), and who may do what in
[`authorization.md`](./authorization.md). Neither is repeated here.

---

## 1. Shape

**A modular monolith: one package per bounded context, boundaries enforced by a linter.**
One process, one database, one migration history. The modules are the seams a split would
follow; the rules a new module must obey are enforced by tooling that fails the push when
they are broken.

Four layers, top to bottom. A layer imports downward only.

| Layer | Packages | Imports from |
| :---- | :---- | :---- |
| **Assembly** | `app/main.py`, `app/api/` (router assembly, middlewares, system endpoints) | everything below |
| **Modules** | `app/modules/<name>/` | other modules' package roots (§3), and everything below |
| **Adapters** | `app/integrations/<provider>/` (Clerk, the LLM providers), `app/agents/` (LangGraph base, memory, checkpointing, observability) | each other, and the foundation |
| **Foundation** | `app/core/`, `app/database/`, `app/exceptions/`, `app/models/base.py`, `app/schemas/base.py`, `app/utils/` | nothing above |

```
server/app/
├── main.py                   # the app, its lifespan, middleware and handler registration (§4–§7)
├── api/
│   ├── middlewares/          # security headers, CORS, access log, auth (JWT), logging context, Prometheus
│   ├── system/               # /, /health, /ready, and their schemas
│   └── v1/api.py             # assembles the modules' routers — nothing else
├── modules/
│   ├── account/              # the Clerk-backed identity: user row, CurrentUser, Clerk webhook handlers,
│   │                         #   JIT provisioning, erasure
│   ├── analytics/            # every calculation over the user's transactions; stores nothing.
│   │                         #   domain/ holds the pure functions (R9); history.py is AnalyticsHistory:
│   │                         #   one load of a user's rows and today, then any analysis over any
│   │                         #   DateRange in memory — insights' figures use one per generation
│   ├── conversation/         # the chatbot: conversations and chat routes, the agent dependency;
│   │                         #   finance/ is its feature sub-package: the chat's tools over analytics
│   │                         #   and transaction
│   ├── insights/             # AI-written insights: gathers analytics figures, calls agents/insights,
│   │                         #   stores one set per user
│   └── transaction/          # the user's transactions and the category list
├── integrations/
│   ├── clerk/                # client, exceptions, timestamps, webhooks/{verification,schemas} — the provider half
│   └── llm/                  # a provider adapter, not a domain
├── agents/                   # base/, shared/, chatbot/, the one-call agents (csv_mapping/, transaction_labeler/,
│                             #   insights/), plus messages.py (the Message type), graph.py, factory.py
├── core/                     # config, logging, metrics, limiter, metadata, events.py (§8)
├── database/                 # engine, dependencies.py (DbSession, the transaction boundary — §6)
├── exceptions/               # the exception hierarchy and the handlers (§7)
├── models/base.py            # shared mixins only, UserOwnedMixin among them; the domain models live in their modules
├── schemas/base.py           # ErrorResponse only; the domain schemas live in their modules
└── utils/                    # token verification, sanitisation
```

**`llm` is an adapter, not a module.** It holds nothing about the product. `Message` and the
graph helpers are `agents/`'s own types — an adapter importing a module's schema would break
R2 — and the chat request and response schemas are `conversation`'s.

**Agents get module knowledge by injection.** `app.agents` may not import a module (R2), so the
chatbot knows nothing about money. `conversation/finance/` builds a `Toolkit` (the tools, and a
preamble the model reads each turn) and `main.py` hands it over at startup:
`initialize_agents(checkpointer, agent_toolkits())`, where `agent_toolkits()` maps agent
names to toolkits (`{"chatbot": finance_toolkit()}`); a route test runs a lookup through it
against a seeded user, so a lost entry fails the suite. The route builds a
`TurnContext(user_id, session_factory, cache)` per turn and passes it in
`config["configurable"]["turn_context"]`; tools read the user from it, never from an argument,
and share one `AnalyticsHistory` through its `cache`. The chat routes release the request's
DB connection before the model call, so a tool opens its own short-lived session from the
context's factory. The tool schemas sent to the model carry no regex `pattern` (a Decimal
argument's made gpt-5-mini return empty replies), so money arguments are JSON numbers parsed
to Decimal; a test guards it. The stream's typed events are documented in
`app/agents/chatbot/events.py`.

## 2. Modules

Every module draws on the same eight slots, and may have two more:

```
app/modules/<name>/
  __init__.py        # the public surface (below)
  router.py          # APIRouter, carrying its own prefix and tags; registered by app/api/v1/api.py
  schemas.py         # request/response models
  models.py          # the SQLModel tables this module owns
  service.py         # orchestration; the only thing another module may call
  repository.py      # all DB access; private to the module
  dependencies.py    # FastAPI dependencies this module provides or needs
  exceptions.py      # domain exceptions, inheriting app/exceptions/base.py
  handlers.py        # optional: subscriptions to other modules' events (§8)
  domain.py          # optional: rules that must not depend on the ORM (R9)
```

**A slot is a file until it needs to be a package, and the import path never notices.** A
file that grows past what fits in your head, or plainly holds independent parts, becomes a
package of the same name whose `__init__.py` re-exports what the file exported. The decision
is per slot, not per module. A module may also hold private helper files beyond the slots.
A module has only the slots it uses — one that reacts to nothing has no `handlers.py`;
empty files are not created for symmetry.

**The public surface is `__init__.py`.** It exports the service singleton(s), the response
schemas another module may return or embed, the dependencies another module's router may use,
the exceptions another module may catch, the enums another module may compare against, and
the names of the events it publishes. It does not export the repository or the models.
Importing the root imports `handlers.py`, so importing a module is what registers its
subscriptions.

**A FastAPI dependency lives in the module whose business it is**, on its root: `CurrentUser`
is `account`'s; `UserConversation` and `ChatbotAgentDep` are `conversation`'s. `DbSession` has no
domain in it and lives in `app/database/dependencies.py`.

**A module grows on two rungs, and nothing outside it notices.**

1. **Slots become packages.** `router/` with a file per tag, `models/` with a file per table,
   `service/` with a file per aggregate or use case. Many tables, services and routes are all
   absorbed here.
2. **A `domain` slot**, for rules worth testing without a database — a state machine, stock
   allocation, pricing. `domain.py`, or `domain/`, holds plain classes and functions and
   imports no ORM and no framework (R9). Either pure functions over plain values that the
   service feeds from the model, or domain dataclasses the repository maps to and from rows
   when the rules need the whole aggregate. The service calls `domain`; `domain` calls nothing.

A module with several implementations of one port — three warehouse systems behind one
`StockSource` — keeps them in a `clients` slot behind a `Protocol` declared in `domain`.

**A module on both rungs**, as a `transactions` module would be:

```
app/modules/transactions/
  __init__.py          # transaction_service, the response schemas, TransactionOwner, TRANSACTION_IMPORTED
  router/
    __init__.py        # one APIRouter assembled from the files below
    transactions.py    # tag "transactions": create, list, get, delete
    imports.py         # tag "transaction-imports"
  schemas/   __init__.py  transaction.py  import_.py
  models/    __init__.py  transaction.py  import_.py   # both carry UserOwnedMixin (R7)
  service/
    __init__.py        # transaction_service, import_service
    transaction.py     # create, categorise: load the aggregate, call domain, persist, publish
    imports.py         # plain child CRUD
  repository/  __init__.py  transaction.py  import_.py
  domain.py            # the categorisation rules and Money — no ORM import
  handlers.py          # on an event from a module below it
  dependencies.py      # TransactionOwner: the transaction exists and is the caller's, else 404
  exceptions.py
```

On every rung the root stays the only import surface and R1–R10 hold. A module on the second
rung beside one that is all files is an expected state.

**A feature sub-package** is the third way a module grows: one concept with its own small tables and routes, kept together instead of spread across slot packages. `transaction/imports/` holds its own `router`, `service`, `repository`, `schemas`, `models`, `domain` and `handlers`. It calls the module's core — rows are written only through `transaction_service` — and the core never imports it (R10). The module root re-exports what the outside needs (`imports_router`), so R1 is unchanged; the R9 contract covers `app.modules.*.*.domain` for it. `conversation/finance/` is the second: it has no routes, only a `Toolkit` the root re-exports (`finance_toolkit`), and `conversation`'s core never imports it (R10).

Settings live in `app/core/config.py`; a module with settings of its own gets a nested model
there named for it, so `settings.<module>.X` reads like the rest. Every route keeps an
explicit tag and `operation_id`, because a tag becomes a folder in the generated web client.

## 3. The rules

**R1 — Across modules, only the package root.** A module imports another as
`from app.modules.<other> import …`, never `.repository`, `.models`, `.service` or any other
submodule. A name is on the root if something outside its own slot file needs it, and every
consumer imports it from there. A dependency's *getter* is surface too: FastAPI keys
`dependency_overrides` by the exact callable, so `get_current_user` is how a test stands in
for `CurrentUser`.

**R2 — Down the layers only.** A module imports adapters and the foundation; adapters import
the foundation; the foundation imports nothing above itself. An adapter that needs domain
logic moves that logic up into the module that owns the table: the Clerk webhook handlers
live in `account/webhooks.py`, with the receiver on `account`'s router
(`include_in_schema=False`), and signature verification and the event schemas stay in
`integrations/clerk`.

**R3 — A module owns its tables.** Its models are in its `models` slot and nowhere else. A
foreign key to another module's table is declared by table name (`foreign_key="user.id"`).
There are no ORM relationships across modules: a module that needs the other side of a key
asks the owning module's service. Reading another module's data at volume goes through a query
interface the owner publishes and indexes for it — never a shared repository.

**R4 — Model instances may cross, classes may not.** A module may hand out its own model
instances through its surface (`CurrentUser` yields a `User`); the receiver treats them as
read-only, imports the class only under `TYPE_CHECKING`, and never mutates or persists what it
did not load.

**R5 — Tests mirror the tree.** `tests/unit/modules/<name>/` and
`tests/integration/modules/<name>/`, one test file per slot file.

**R6 — Modules form a DAG.** If `conversation` imports `account`, `account` does not import
`conversation` — two roots importing each other is a circular import that fails at startup. When
a lower module needs a higher one to *act*, it publishes an event (§8). When it needs the
higher one's *data*, the data belongs elsewhere.

**R7 — A user-owned table carries `UserOwnedMixin`**, and every repository method on it takes
the user id. A table that is not user-owned is allowlisted with its reason (§9).

**R8 — Migrations are global.** One Alembic history in `server/alembic/versions/`.
`alembic/env.py` imports every module's `models` slot so autogenerate sees the whole schema;
the list lives there because a registry under `app/` would break R1 or R2. A module with
tables is one import line there.

**R9 — The `domain` slot imports neither the ORM nor the framework** — no `sqlmodel`,
`sqlalchemy` or `fastapi`. It calls nothing above the standard library and the foundation's
value types.

**R10 — A module's core never imports its feature sub-package.** The sub-package calls the core;
the module root alone re-exports from it (§2).

**Enforcement.** R1, R2 and R6 are [`import-linter`](https://import-linter.readthedocs.io/)
contracts in `server/pyproject.toml`, run by `make check-server` (the pre-push hook) and by
`.github/workflows/module-boundaries.yml` on every pull request and push to `main`. R2 is one
`layers` contract over the four layers, with `app.main` above `app.api`; siblings in a layer
joined by `:` may import each other. R6 is a second `layers` contract listing the modules in
dependency order; modules that do not depend on each other share a layer with `|`. R1 is one
`forbidden` contract per module, listing every other module's submodules. Type-checking-only
imports are excluded from the graph, which lets R4's hint through; every directory under `app/`
carries an `__init__.py` because the graph builder needs regular packages. R9 is a `forbidden` contract too: it
forbids `sqlmodel`, `sqlalchemy` and `fastapi` in `app.modules.*.domain` and
`app.modules.*.*.domain`. R10 is one `forbidden` contract per feature sub-package, with the
core's slots as sources: `transaction/imports/` has one, `conversation/finance/` the other.

A new module is three edits to `pyproject.toml` before it is enforced.
`tests/unit/test_module_contracts.py` fails when a module is missing its R1 contract, is absent
from the R6 order, has a `models` slot `alembic/env.py` does not import (R8), or is not imported
by `app/main.py` (§4). R7 is `tests/unit/models/test_owned_tables.py`. R3, R4 and R5 are review
items.

## 4. Startup

`app/main.py` builds the app at import time and does the rest in its lifespan.

**At import:** every module is imported by name — `account`, `conversation` —
whether or not it has a router. A module that only subscribes to events would otherwise
never load, and `publish()` would run zero handlers with no error. Then `.env` is loaded,
the Langfuse client is created, the middlewares (§5) and exception handlers (§7) are
registered, and the system router is mounted at the root and the v1 router under
`/api/v1`. In production `/docs`, `/redoc` and the OpenAPI JSON are not served.

**In the lifespan**, before the first request: the database engine and its session factory,
the LangGraph Postgres checkpointer, and every agent with its compiled graph. They are put on
`app.state` — `engine`, `session_factory`, `agents`, `limiter` — which is how dependencies
reach them. On shutdown the checkpointer's connection pool and the engine are closed.

Migrations are not part of startup: they are a separate release phase
([`server/CLAUDE.md`](../../server/CLAUDE.md), **Database Migrations**).

## 5. A request's path

The middlewares, outermost first:

| Middleware | Does |
| :---- | :---- |
| `SecurityHeadersMiddleware` | adds `nosniff`, `X-Frame-Options: DENY`, a referrer policy, and HSTS in production |
| `CorrelationIdMiddleware` | reads or mints `X-Request-ID`; the id is bound to every log line and returned in `ErrorResponse` bodies (§7) |
| `CORSMiddleware` | allows `settings.cors.ALLOWED_ORIGINS`, with credentials |
| `AccessLogMiddleware` | one structured line per request with status and duration; skips `/health`, `/ready`, `/metrics` |
| `AuthMiddleware` | verifies a Bearer token if present and sets `clerk_id` (from `sub`) on `request.state`; never rejects |
| `LoggingContextMiddleware` | binds `clerk_id` to the log context for the rest of the request, and clears it after |
| Prometheus instrumentator | records `http_requests_total` and latency per route template; serves `/metrics` |

**The middleware stack decides nothing.** A missing or invalid token passes through with an
empty identity; a route that needs a person declares `CurrentUser`, and that dependency is
where a 401 comes from ([`authentication.md`](./authentication.md) §3). Every authorization
decision is a dependency too ([`authorization.md`](./authorization.md) §2).

**Routes.** System endpoints sit at the root: `/` and `/health` are public, `/ready` requires
a user. Everything else is under `/api/v1`, assembled in `app/api/v1/api.py` from each module's
router. The API contract — tags, `operation_id`, response models, the committed
`openapi.json` — is in [`server/CLAUDE.md`](../../server/CLAUDE.md), **API Contract**.

**Rate limits are per route.** `slowapi`, keyed by client address, applied by a
`@limiter.limit(settings.rate_limits.endpoints.<NAME>[0])` decorator. There is no
`SlowAPIMiddleware`, so an undecorated route is unlimited.

## 6. Dependencies and the transaction

**`DbSession` is the transaction boundary.** `get_db_session` opens one session per request,
starts the request's event queue (§8), and yields. It is bound with `scope="function"`, so its
post-`yield` block runs after the route returns and before the response is sent: it commits,
then runs the deferred event handlers. A commit-time failure therefore reaches the exception
handlers — a unique violation is a 409, not a 200 followed by a lost write.

Consequences code relies on:

- Services and repositories `flush()`, never `commit()`. The one exception is
  `release_connection` (`app/database/dependencies.py`): a request that awaits a model call
  commits its work so far first, so the pool connection is not held idle in a transaction for
  seconds. The chat routes, the title, insights' generate and the import's model calls use it.
- Deferred event handlers add to the response's latency.
- By the time a `BackgroundTasks` callable or a `StreamingResponse` body runs, the request's
  session is committed and closed. They take plain values and, if they need the database,
  open a session from `request.app.state.session_factory`.

**The other dependencies are the modules'** (§2): identity from `account`,
ownership checks (`UserConversation`) from the module that owns the row. A route
never receives `None` — the service or the ownership dependency raises first.

## 7. Errors

**Services raise domain exceptions; the handlers translate them to HTTP.** Every domain
exception inherits a category class in `app/exceptions/base.py`, which fixes its status and
`error_code`:

| Category | Status |
| :---- | :---- |
| `AuthenticationError` | 401 |
| `AuthorizationError` | 403 |
| `NotFoundError` | 404 |
| `ConflictError`, `DatabaseConflictError` | 409 |
| `ValidationError` | 422 |
| `ServiceError` (the root), `DatabaseError` | 500 |
| `ServiceUnavailableError` — under it `AuthUnavailableError`, `UserProvisioningError`, `LLMServiceError`, `CategorisationUnavailableError` — and `DatabaseConnectionError` | 503 |

**A 401 means the request's credentials, nothing else.** The web retries a 401 once with
a fresh token and signs out on the second ([`web-app.md`](./web-app.md) §5), so a failure
behind valid credentials is never a 401: an outage is a `ServiceUnavailableError` (503).
The server unable to check a token — Clerk's signing keys unreachable, `CLERK_ISSUER`
not a URL, an unexpected failure — is `AuthUnavailableError` (`AUTH_UNAVAILABLE`).
Provisioning lets a typed error keep its status (the server's own Clerk secret refused
is `ClerkAuthenticationError`, 502; a Clerk rate limit 429) and wraps anything else in
`UserProvisioningError` (`USER_PROVISIONING_FAILED`). A valid token for a user Clerk no
longer has is a 401. `tests/unit/exceptions/test_exceptions.py` fails if any other
exception answers 401.

Modules subclass these in their `exceptions` slot; adapters in
`app/integrations/<provider>/exceptions.py`. Keyword arguments to the constructor become the
exception's `context`.

Four handlers, registered in `app/main.py`:

| Exception | Response |
| :---- | :---- |
| `RateLimitExceeded` | 429, slowapi's body |
| `RequestValidationError` | 422, `{detail, errors: [{field, message}]}` |
| `ServiceError` | its status, as `ErrorResponse` — `error`, `message`, `correlation_id`, and `details` = the exception's `context`. A 4xx is logged as a warning, a 5xx with its traceback |
| anything else | a generic 500 with no cause, logged with the traceback |

**An exception's `context` reaches the client** as `details`, so it never carries PII.
`app_exceptions_total` counts both of the last two, by `error_code` and exception class.

**Database errors are translated where the transaction ends.** `get_db_session` rolls back
and raises `DatabaseConflictError` on an `IntegrityError` (logging the constraint name, never
the values), `DatabaseConnectionError` on an `OperationalError`, and `DatabaseError` on any
other driver error.

An exception raised after a streaming response has started reaches no handler: the status is
already on the wire.

## 8. Events

`app/core/events.py` is the seam for the one direction the DAG forbids: a lower module that
needs a higher one to act. A module that is higher and needs a lower one to act calls its
service, so the dependency graph stays readable from the imports.

**The mechanism.** One dispatcher per process, a registry keyed by event name. A module
subscribes with `@events.on(NAME)` in its `handlers` slot, at import time. A publisher calls
`await events.publish(NAME, session=session, **payload)`, never knows who listens, and gets
back the number of handlers run plus queued. Names are constants on the publisher's root,
namespaced by module (`USER_ERASING = "account.user_erasing"`), so a renamed event is an
import error.

**Two dispatch modes, per subscription:**

- **Inline** (`inline=True`) runs inside `publish()`, in the publisher's session and
  transaction. A handler that raises stops the sequence and propagates, and the request rolls
  back.
- **Deferred**, the default, is queued and run by `DbSession` after the commit and before the
  response, each handler in a session of its own, without the publisher's `session` in its
  payload. A handler that raises is logged as `event_handler_failed`, counted on
  `app_event_handler_failures_total`, and skipped. A request that rolls back discards its
  queue. A deferred handler that publishes another deferred event is drained in the same
  flush, up to five rounds.

Subscribers to one event run in registration order, which is import order. Outside a request
there is no `DbSession`, so an entry point that publishes calls `events.begin()` and
`events.flush(session_factory)` itself. Every entry point today is a request, and a deferred
handler that fails is lost ([`../TODO.md`](../TODO.md), **Server — events beyond the
request**).

**The events as they stand.** All are inline.

| Event | Published by | Payload | Subscribers | Why inline |
| :---- | :---- | :---- | :---- | :---- |
| `account.USER_SYNCED` | JIT provisioning; the `user.created` webhook handler | `user_id`, `metadata` (Clerk public metadata — merged from the API on JIT, the webhook's own on the webhook path) | none yet — the hook for seeding a new user's data on first sign-up | the seeding it is for runs in the request that provisions the user |
| `account.USER_ERASING` | `erase_user`, before `anonymize_user()` | `user_id` | `conversation` — soft-deletes the rows, blanks their names, deletes their checkpoints; `transaction` — hard-deletes every transaction the user owns; `transaction.imports` — hard-deletes the user's mapping profiles and held upload; `insights` — deletes the stored set | the subscriber's identifiers are what `anonymize_user()` destroys |
| `transaction.TRANSACTIONS_ALL_DELETED` | `delete_all_on_request` (Settings' "delete all transactions"; not erasure, which `USER_ERASING` covers) | `user_id` | `insights` — deletes the stored set | the set quotes the deleted rows and must not outlive them in a half-committed request |

`erase_user` logs `subscriber_count`: zero means the modules were never imported. Memory
deletion during erasure is a direct call — `agents/` is an adapter, below every module.

When to publish, which mode to pick and the pitfalls are in the `server-patterns` skill,
`references/events.md`.

## 9. Ownership

The user is the tenant: there are no organisations and no roles. A request's identity is
the `sub` claim, which `AuthMiddleware` puts on `request.state` as `clerk_id` and which
`CurrentUser` resolves to the `user` row — provisioning it on first sight.

Four pieces hold the boundary:

- **`UserOwnedMixin`** in `app/models/base.py` declares the indexed, non-null `user_id` an
  owned table carries (R7).
- **`CurrentUser`**, on `account`'s root, yields the resolved user.
- **Ownership dependencies** in the owning module (`UserConversation`) answer 404 for a row
  that is missing, soft-deleted or another user's — the same code for all three.
- **`tests/unit/models/test_owned_tables.py`** fails on any table under `app/modules/` that
  neither carries the mixin nor is in its allowlist with a reason. The allowlist holds
  `user`, the owner itself.

Each table's reasoning is stated in its data-model doc ([`../data-model/`](../data-model/README.md)).

## 10. Observability and configuration

- **Logs** are structlog: `snake_case` event names with key-value context, JSON unless
  `settings.logging.FORMAT` says otherwise. Every line carries the `correlation_id` and, once known, `clerk_id` and
  `user_id` (bound by `CurrentUser`). The conventions are in
  [`server/CLAUDE.md`](../../server/CLAUDE.md), **Logging**.
- **Metrics** are Prometheus at `/metrics`: the HTTP series from the instrumentator, and the
  application's own in `app/core/metrics.py` — LLM and tool latency, `app_exceptions_total`,
  `app_event_handler_failures_total`. What scrapes them is in
  [`setup/infrastructure.md`](../setup/infrastructure.md).
- **Traces** of every LLM call go to Langfuse.
- **Settings** are one `Settings` object in `app/core/config.py`, nested per concern
  (`settings.database`, `settings.auth`, `settings.rate_limits`, …), read from
  `server/.env.<APP_ENV>`. An unrecognised `APP_ENV` fails at startup, and so does a
  model id that is not an OpenRouter `provider/model` id (`OpenRouterModel`). The OpenAPI title,
  version and prefix are code, from `pyproject.toml` via `app/core/metadata.py`, never
  settings.

## 11. Where each piece lives

| Concern | Where |
| :---- | :---- |
| Middleware order, handler registration, lifespan | `app/main.py` |
| Token parsing | `app/api/middlewares/auth.py`, `app/utils/auth.py` |
| Identity dependency | `app/modules/account/dependencies.py` |
| The transaction, DB error translation, the deferred flush | `app/database/dependencies.py` |
| Exception categories and handlers | `app/exceptions/base.py`, `app/exceptions/handlers.py` |
| The event dispatcher | `app/core/events.py` |
| Subscriptions | `app/modules/<name>/handlers.py` |
| Rate limiter | `app/core/limiter.py`, limits in `settings.rate_limits` |
| Metrics | `app/core/metrics.py`, `app/api/middlewares/prometheus.py` |
| Module boundaries | `server/pyproject.toml` (import-linter), `tests/unit/test_module_contracts.py` |
| Ownership | `app/models/base.py`, `tests/unit/models/test_owned_tables.py` |
