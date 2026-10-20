# Server — FastAPI Backend

Continuation of the root `CLAUDE.md`. Covers `server/` conventions only — no repeated project or stack overview.

---

## Running the Server

All commands below run from `server/`. For the full Docker stack, use root `make` commands (see root `CLAUDE.md`).

Env file is selected by `APP_ENV`. Copy `.env.example` → `.env.development` before first run.

### Server-only Docker

`make help` lists the `docker-*` targets. They all drive `../docker-compose.dev.yml`, which bind-mounts `./server/app`
over the image's code. That is why `docker-run` takes no `ENV`: a
`ENV=production` variant would run production secrets against your working
tree. Production runs from `docker-compose.prod.yml`, via the root `Makefile`.

`docker-logs-server` and `docker-stop-server` delegate to
`scripts/logs-docker.sh` and `scripts/stop-docker.sh`, which address the
Compose *service* rather than a container name — neither compose file pins
one, and in a git worktree the project, and with it the container name,
differs.

### Database Migrations (Alembic)

The `make migrate*` targets (see `make help`) run on the **host** via `uv`, against
the DB named in `server/.env.<ENV>`. Use them to author revisions.

In Docker, migrations are a **discrete release phase**, not part of app startup.
A one-shot `migrate` service runs `alembic upgrade head`, and `server` is gated
on it via `depends_on: condition: service_completed_successfully`. A failed
migration therefore fails the `up` and leaves any previously running container
serving the old image, instead of crash-looping the app.

The service runs `scripts/migrate.sh`. **Add further release-phase steps there**
(seeding, backfills, first-admin bootstrap) rather than in the compose
`command:` — one script, two compose files pointing at it. Anything added must
be idempotent: it runs on every `up`, including a restart with nothing to do.

From the repo root: `make docker-migrate` applies them on demand,
`make docker-migrate-status` prints the current revision. Never reintroduce
`alembic upgrade` into `scripts/docker-entrypoint.sh` — that entrypoint is
env-prep only, for both services.

Two caveats:
- `depends_on` applies to `compose up`, not to reboots. After a Docker daemon or
  host restart, `server` comes back under its restart policy with no `migrate`
  run. Benign (the DB is already migrated), but it is not a startup guarantee.
- `app/`, `alembic/`, and `scripts/` are bind-mounted in dev, so the container
  always executes the working tree. `alembic.ini` is **not** — changes to it
  need `make docker-build-api`.

---

## Directory Structure

Module-first. The rules, the slots and the reasoning are in
[`docs/architecture/server.md`](../docs/architecture/server.md).

A module has a fixed set of slots — `router`, `schemas`, `models`, `service`,
`repository`, `dependencies`, `exceptions`, optionally `handlers` and `domain` —
and a root `__init__.py` that is its whole public surface. Another module
imports from that root and nowhere deeper; `account` cannot import
`conversation`, so it publishes events (`app/core/events.py`) that
they subscribe to. `make check-server` runs `lint-imports` over the contracts
in `pyproject.toml`, and `tests/unit/test_module_contracts.py` fails the suite
when a new module lacks its entries.

**Adding a module means adding its import to `app/main.py`**, whether or not
anything else imports it. A module's event subscribers (`USER_ERASING` and the
like) register only when the module is imported; a module that owns user-keyed
data but has no router would otherwise never load, and erasure would skip its
data with no exception and no failed request.
`test_main_imports_every_module_explicitly` is what catches it.

`integrations/` holds code that exists only because a third party does — one
package per provider, carrying the outbound client and the inbound
verification. What a provider's event *means* for our rows is decided in the
module that owns them: `app/modules/account/webhooks.py` for Clerk.

`data/` holds seed data — today `clerk-dev-seed.json`, which `make clerk-seed-users`
reads. It carries committed dev passwords, so `.dockerignore` keeps it out of the image;
new seed data goes there too.

---

## Code Conventions

- `async def` everywhere — no blocking I/O
- Type hints on all function signatures
- Pydantic models over raw dicts (RORO pattern)
- File names: `lowercase_with_underscores.py`
- All imports at the top of the file — never inside functions
- DB writes end in `flush()`, never `commit()`: `DbSession` is `scope="function"`, so
  `get_db_session` commits after the route returns and before the response is sent
- A background task or a streaming body never uses the request's session — it is closed
  by then. Pass plain values; a task that needs the database opens its own from
  `request.app.state.session_factory`

---

## Skills to Use

Invoke these before starting the relevant task. The `server-patterns` skill's
reference files are the long form of the conventions on this page.

| Situation | Skill |
|-----------|-------|
| Adding or changing a module, service, repository, route, exception, event subscriber, or a third-party adapter | `/server-patterns` |
| Calling or inspecting a Clerk backend endpoint by hand | `/clerk-backend-api` |
| Writing, running or debugging any test | `/server-testing` |

---

## Logging (structlog)

```python
# ✅ Correct
logger.info("transactions_imported", count=count, source=source)
logger.exception("db_query_failed", table="transactions")

# ❌ Wrong
logger.info(f"Document {doc_id} uploaded")  # no f-strings in events
logger.error("something failed")  # use .exception() to preserve tracebacks
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
from app.modules.documents.exceptions import DocumentNotFoundError

raise DocumentNotFoundError("Document not found", document_id=doc_id)


# In a route — no try/except needed
@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    return await document_service.get(doc_id)
```

Base exceptions, and the HTTP status each maps to, live in `app/exceptions/base.py`.
Each module defines its own exceptions extending these, in `app/modules/<name>/exceptions.py`; integration exceptions go in `app/integrations/<provider>/exceptions.py`.

---

## API Contract

`server/openapi.json` is a committed artifact. It generates the frontend's
TanStack Query hooks, TypeScript types and Zod validators, so the schema is a
published interface, not a by-product.

The schema's `info` block and its `/api/v1` prefix come from
`[tool.app.metadata]` and `[project]` in `pyproject.toml`, loaded by
`app/core/metadata.py`. Never move them into `Settings`: an env-derived title or
prefix makes the exported artifact machine-dependent, which
`tests/unit/scripts/test_export_openapi.py` asserts against. To rename the service in
a fork, change them there, run `make gen-contract` and commit the output.
`.env.example`'s `PROJECT_NAME` is unrelated — it only names Docker images and containers.

Every route must therefore declare:

- **An explicit tag.** Tags become directory names and module boundaries in the
  generated client. Untagged routes collapse into a `default` bucket.
- **An explicit camelCase `operation_id`** — `getMe`, `listConversations`.
  FastAPI's auto-generated ids (`health_check_health_get`) become hook names
  like `useHealthCheckHealthGet`.
- **Either a `response_model` or `status_code=204`.** A route with neither
  generates `unknown` on the client. `Dict[str, Any]` is not a response model:
  it emits `additionalProperties: true` and generates
  `{[key: string]: unknown}`.

Two further rules:

- **Server-to-server routes declare `include_in_schema=False`.** The Clerk
  webhook receiver already does; the frontend must never get a hook for it.
- **Streaming routes declare `tags=["streaming"]`** and are exempt from the
  response-body rule. They have no JSON body, and orval excludes the tag. They
  remain visible in Swagger.

**`operation_id` is a public frontend symbol.** Renaming a handler renames a
hook. Treat it as a breaking change.

**Regenerate in the same commit.** After changing any route, run
`make gen-contract` from the repo root — it re-exports the spec and regenerates
the client — and commit both outputs alongside the route change.
`make check-contract` does the same and then fails on drift; that is what CI
runs, and what `make docker-build*` gates on. With `core.hooksPath` configured
(root `CLAUDE.md`), the pre-commit hook regenerates and blocks any commit that
touches `app/` without them.

`tests/unit/api/test_openapi_contract.py` enforces the three per-route rules
mechanically. It needs no database.

---

## Authentication

- Clerk JWTs verified by `AuthMiddleware` (RS256); `clerk_id` set on `request.state`
- Use `CurrentUser` from `app.modules.account` for protected endpoints. It is the only identity dependency: there are no organisations and no roles. Ownership of a row is the owning module's dependency, and a miss — including another user's row — is a 404:
  ```python
  from app.modules.account import CurrentUser
  ```
- Users are JIT-provisioned in the local DB on first request via `UserService`
- Conversation ownership enforced by the `UserConversation` dependency (404 `CONVERSATION_NOT_FOUND` for a missing or another user's conversation)

---

## Settings Access

Pydantic nested models in `app/core/config.py`.

```python
# ✅ Correct — unpack SecretStr
api_key = settings.llm.OPENROUTER_API_KEY.get_secret_value()

# ❌ Wrong — returns SecretStr object, not the string
api_key = settings.llm.OPENROUTER_API_KEY
```

---

## Agent Architecture

A conversational agent extends `BaseAgent` (`app/agents/base/`) and implements `create_graph()`.
A one-shot call whose answer must be JSON of a known shape — the CSV import's `csv_mapping` and
`transaction_labeler` — is a plain function over `ask_json()` (`app/agents/shared/structured.py`),
traced with `create_trace_config()`, with no graph and no checkpoint.

**Shared components:**
- `app/agents/shared/memory/` — `get_relevant_memory()`, `update_memory()`, `delete_user_memory()`
- `app/agents/shared/checkpointing/` — `AsyncPostgresSaver` for LangGraph persistence, plus `delete_conversation_checkpoints()` and its set-based `delete_conversations_checkpoints()`
- `app/agents/shared/observability/` — `create_graph_config()` wires Langfuse callbacks; `create_trace_config()` does it for a call outside a graph

**Toolkits.** The chatbot's tools are injected, never imported: `app.agents` may not import a module (R2), so a module builds a `Toolkit` (`app/agents/chatbot/toolkit.py`) and `main.py` passes it to `initialize_agents`. A tool reads the user from `TurnContext.user_id` and never takes a user argument; it opens its own session from `TurnContext.session_factory`, because the route releases the request's connection before the model call. **A tool's argument schema must carry no regex `pattern`** (a Decimal's made gpt-5-mini return empty replies): take money as a JSON number; `test_schemas.py` guards it. Bad arguments raise `ToolArgumentError` (its text goes to the model); any other crash reaches the model as a fixed message. The wiring is in [`architecture/server.md`](../docs/architecture/server.md) §1.

`BaseAgent` provides `get_response()`, `get_stream_response()` and `get_chat_history()` with memory and tracing built in. Clearing a conversation is **not** an agent method: checkpoints are keyed by `thread_id` in tables every agent shares, so use `delete_conversation_checkpoints()` from `app/agents/shared/checkpointing/` and do not take an agent parameter just to reach it. All LLM calls must have Langfuse tracing. All retries must use `tenacity` with exponential backoff.

---

## Testing

Before writing or debugging a test, read the **`/server-testing`** skill: an unmarked file
that `make` never runs and a lifespan that never runs
both fail far from their cause.

Run from `server/`: `make test*` (see `make help`), or target a file or test name:

```bash
APP_ENV=test uv run pytest tests/unit/modules/account/test_service.py
APP_ENV=test uv run pytest -k "test_name"
```

Coverage runs only under `make test-coverage`; the HTML report goes to `htmlcov/`. The pytest
config is `pytest.ini` — pytest ignores `[tool.pytest.ini_options]` while that file exists.

New tests mirror the `app/` structure: a test for `app/modules/account/service.py` goes in `tests/unit/modules/account/test_service.py`. Unit tests mock external deps (DB, Clerk, LLM); integration tests use a real DB.

**A whole-object assertion pins a field-to-column mapping only if every field holds a
distinguishable value.** When a fixture leaves most fields at a shared default (`None`,
`0`, `False`), two transposed fields still pass `assert result == expected` — the object
is the right shape. Give each field of a multi-field row its own value first.

**A test that pins known-wrong behaviour names its [`BUGS.md`](../docs/BUGS.md) entry**
in a comment, so the fix is what changes it — invert it then, don't delete it.

---

## GDPR — Right to Erasure

When a user is deleted (`DELETE /api/v1/auth/me`, or Clerk's `user.deleted`), `account`'s `erase_user` runs, in order:

1. Clerk deletion, by the route only — on the webhook path Clerk's deletion is the trigger (JWTs immediately invalidated)
2. `USER_ERASING` published, inline: `conversation` soft-deletes the user's conversations, hard-deletes the LangGraph checkpoints of every conversation they own (soft-deleted ones included), and blanks their names; `transaction` hard-deletes every transaction the user owns, soft-deleted ones included
3. mem0 memories deleted (`delete_user_memory`)
4. User PII anonymised via `AnonymizableMixin.anonymize_user()`

The request's `DbSession` commits the whole cascade before the response is sent; `erase_user` does not commit.

Steps 2 and 3 run before step 4 because they are keyed by identifiers `anonymize_user()` destroys. The `user_erased` log line carries `subscriber_count`; a module that owns user-keyed data subscribes to `USER_ERASING` in its `handlers.py`.

Rules:
- Never use `SoftDeleteMixin` on `User` — it leaves PII in the DB
- New models with PII implement `AnonymizableMixin` and an `anonymize_*()` method, or — when nothing references their rows — are hard-deleted by their module's `USER_ERASING` subscriber (`transaction`)
- Always call `delete_conversation_checkpoints()` before blanking or soft-deleting a conversation
- Erasure clears checkpoints for every conversation the user owns, soft-deleted ones included — never only the active ones
