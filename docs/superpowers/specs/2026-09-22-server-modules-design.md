# Server Modules — Design

**Status:** implemented
**Branch:** `refactor/server-modules`
**Ports:** [`tiziaco/flyorbit`](https://github.com/tiziaco/flyorbit) `docs/architecture/server-modules.md` as landed by PR #5 (21 Sep 2026), adapted for a template with its own example domain and multi-tenancy
**Architecture:** the rules, the layout and the decisions this slice implements are in [`docs/architecture/server-modules.md`](../../architecture/server-modules.md). This spec is the delta from the port and the mechanics of the move; it does not restate the rules.

---

## Goal

Rotate `server/app/` from layer-first (`api/`, `models/`, `schemas/`, `services/`) to module-first (`modules/account/`, `modules/conversation/`, `modules/supplier/`), enforce the boundaries with import-linter in the pre-push hook and CI, and put in place the two mechanisms a fork needs before its first new module: an event dispatcher for the downward-pointing dependency, and a tenant-scoping check that a new table cannot forget.

**No behaviour changes and no schema changes.** `server/openapi.json` must come out of `make check-contract` byte-identical, and `alembic revision --autogenerate` must produce an empty revision. Those two facts are the proof that this is a move.

---

## Why this differs from the port

flyorbit and this repo share a skeleton — `account`, `conversation`, `agents/`, `integrations/clerk`, `integrations/llm` all match — so most of the port is the same files landing in the same places. Five things are different, and they are what this spec is about.

1. **This is a template.** flyorbit's doc records how one product is partitioned. Here the rules are the product: a fork will add modules the template never sees, so the enforcement has to catch a module nobody wrote a contract for. Hence the completeness test (§6).
2. **The template has its own cycle, and flyorbit did not.** `services/user/` holds `supplier_repository.py`; the user service links, unlinks and resolves suppliers by reaching the table directly, and the `SupplierID` dependency sits next to `CurrentUser`. That is the tangle the modular structure exists to remove, and the port has to resolve it, not move it (§3).
3. **Multi-tenancy is the template's identity.** flyorbit is B2C. Here `org_id` arrives on every JWT and is meant to scope queries, yet no table but `user` carries it and nothing checks that a new one does (§5).
4. **Events get a second dispatch mode.** flyorbit's dispatcher runs every handler in the publisher's transaction. That is right for a cascade and wrong for a reaction, and the work fork of this template will put reactions on an external queue — which is after-commit by nature. Deciding the semantics now means the queue lands later without changing the publishers (§4).
5. **"Layered" is one slot, not a tree.** flyorbit rejected `domain/application/infrastructure` outright and left it there. Here the doc says what a complex module does instead: slots become packages, and a `domain` slot with a linter contract holds the rules that must not import the ORM (architecture §3, R9, D6). Nothing in this slice creates one — the rule is what ships.

---

## 1. Target structure

```
server/app/
├── main.py
├── api/
│   ├── middlewares/                 # unchanged
│   ├── system/                      # health.py, + schemas.py (from schemas/system.py)
│   └── v1/api.py                    # includes each module's router; no prefixes or tags of its own
├── modules/
│   ├── __init__.py
│   ├── account/
│   │   ├── __init__.py              # user_service, Role, CurrentUser, CurrentRole, CurrentOrgId, require_role,
│   │   │                            #   the getters, UserResponse, UserAlreadyExistsError, USER_SYNCED,
│   │   │                            #   USER_ERASING, USER_OFFBOARDED, router
│   │   ├── router/{__init__,auth,webhooks}.py
│   │   ├── schemas.py               # UserResponse
│   │   ├── models.py                # User (no Relationship), Role
│   │   ├── service.py               # resolve_user, resolve_org_role, erase_user, exists_in_clerk, delete_user_from_clerk
│   │   ├── repository.py
│   │   ├── dependencies.py          # get_clerk_id, get_current_user, get_current_role, get_current_org_id, require_role
│   │   ├── exceptions.py
│   │   ├── webhooks.py              # the Clerk event dispatcher and the user/membership handlers
│   │   └── cache.py                 # org_role entries only
│   ├── conversation/
│   │   ├── __init__.py              # conversation_service, ConversationResponse, UserConversation, ChatbotAgentDep,
│   │   │                            #   the getters, the exceptions, router
│   │   ├── router/{__init__,conversation,chatbot}.py
│   │   ├── schemas.py               # ConversationResponse, ChatRequest, ChatResponse, ConversationHistory, StreamResponse
│   │   ├── models.py                # Conversation (no Relationship)
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── dependencies.py
│   │   ├── exceptions.py
│   │   └── handlers.py              # on USER_ERASING
│   └── supplier/
│       ├── __init__.py              # supplier_service, SupplierID, get_supplier_id, SupplierNotLinkedError
│       ├── models.py                # Supplier
│       ├── service.py               # link_from_metadata, unlink_contact, get_id_for_user
│       ├── repository.py
│       ├── dependencies.py
│       ├── exceptions.py
│       ├── handlers.py              # on USER_SYNCED, USER_ERASING, USER_OFFBOARDED
│       └── cache.py                 # supplier_id entries
├── integrations/
│   ├── clerk/                       # client, exceptions, timestamps, webhooks/{verification,schemas,exceptions}
│   └── llm/                         # from services/llm
├── agents/                          # + messages.py (Message), graph.py (from utils/graph.py)
├── core/                            # + events.py
├── database/                        # + dependencies.py (DbSession, from api/dependencies/database.py)
├── exceptions/                      # unchanged
├── models/base.py                   # + TenantMixin
├── schemas/base.py                  # ErrorResponse only; schemas/__init__.py exports nothing
└── utils/                           # auth.py, sanitization.py
```

`conversation` has no `repository.py` today — the service runs its own queries. Whether to split one out is not this slice's question; the file moves as it is.

---

## 2. The moves

Mechanical. Every symbol keeps its name unless the table says otherwise.

| Today | After |
| :---- | :---- |
| `api/v1/auth.py` | `modules/account/router/auth.py` — the `/auth` prefix and `auth` tag move from `api.py` into the file |
| `api/v1/webhooks.py` | `modules/account/router/webhooks.py` — `/webhooks`, `webhooks`, still `include_in_schema=False` |
| `api/v1/conversation.py`, `api/v1/chatbot.py` | `modules/conversation/router/{conversation,chatbot}.py` — `/conversation`, `/chatbot` and their tags move into the files |
| `api/v1/api.py` | stays; `include_router(<module>.router)` for each module, nothing else |
| `api/dependencies/database.py` | `database/dependencies.py` |
| `api/dependencies/authentication.py` | `modules/account/dependencies.py`, minus `get_supplier_id` / `SupplierID` → `modules/supplier/dependencies.py` |
| `api/dependencies/authorization.py` | `modules/account/dependencies.py` |
| `api/dependencies/conversation.py`, `api/dependencies/agent.py` | `modules/conversation/dependencies.py` |
| `models/user.py` | `modules/account/models.py` — the `conversations` `Relationship` and the trailing circular import go |
| `models/enums.py` | `Role` into `modules/account/models.py`; the file goes |
| `models/conversation.py` | `modules/conversation/models.py` — the `user` `Relationship` goes; `foreign_key="user.id"` stays |
| `models/supplier.py` | `modules/supplier/models.py` |
| `schemas/auth.py` | `modules/account/schemas.py` |
| `schemas/conversation.py` | `modules/conversation/schemas.py` |
| `schemas/chat.py` | `Message` → `agents/messages.py`; the rest → `modules/conversation/schemas.py` |
| `schemas/system.py` | `api/system/schemas.py` |
| `schemas/__init__.py` | emptied — `ErrorResponse` is imported from `app.schemas.base` |
| `services/user/service.py` | `modules/account/service.py`, minus `link_supplier_from_metadata`, `unlink_supplier_contact`, `get_supplier_id_for_user` — they become `supplier_service.link_from_metadata(session, user_id, metadata)`, `unlink_contact(session, user_id)`, `get_id_for_user(session, user_id)` (§3) |
| `services/user/repository.py` | `modules/account/repository.py` |
| `services/user/supplier_repository.py` | `modules/supplier/repository.py` |
| `services/user/cache.py` | split: the `org_role` methods → `modules/account/cache.py`; the `supplier_id` methods → `modules/supplier/cache.py`; `invalidate_user` exists on both, each clearing its own keys |
| `services/user/exceptions.py` | `SupplierNotLinkedError` → `modules/supplier/exceptions.py`; the rest → `modules/account/exceptions.py` |
| `services/conversation/{service,exceptions}.py` | `modules/conversation/{service,exceptions}.py` |
| `services/llm/*` | `integrations/llm/*` |
| `integrations/clerk/webhooks/dispatcher.py`, `handlers/{user,membership}.py` | `modules/account/webhooks.py`, one file — dispatch and handlers together (architecture D2) |
| `integrations/clerk/webhooks/__init__.py` | stops exporting `clerk_dispatcher` |
| `utils/graph.py` | `agents/graph.py` |

Every directory under `app/` gets an `__init__.py` — import-linter's graph builder needs regular packages, and `app/` itself, `app/api/`, `app/api/v1/`, `app/core/` and `app/models/` are namespace packages today (`app/services/` too, but it goes).

`alembic/env.py` imports `app.modules.<name>.models` for the three modules in place of the three `app.models.*` imports.

---

## 3. The `supplier` module and the three events

This is the one part of the port that is not a move. The user service calls supplier code in three places; each becomes a published event, and `supplier` subscribes.

| Call site in `account` | Today | After |
| :---- | :---- | :---- |
| `resolve_user`, after `create_or_get` | `await self.link_supplier_from_metadata(user, merged_metadata, session)` | `await events.publish(USER_SYNCED, session=session, user_id=user.id, metadata=merged_metadata)` |
| `handle_user_created`, `handle_membership_created` (webhooks) | the same call | the same publish |
| `erase_user` | `await self.unlink_supplier_contact(user.id, session)` | `await events.publish(USER_ERASING, session=session, user_id=user.id)` |
| `handle_membership_deleted` (webhook) | the same call | `await events.publish(USER_OFFBOARDED, session=session, user_id=user.id)` |

`supplier/handlers.py` subscribes to all three with `inline=True`. `USER_SYNCED` must be inline: a supplier's first request JIT-provisions the user and then resolves `SupplierID`, in one transaction, and a deferred link would make that first request a 403. The two unlinks are inline because they are part of the erasure and offboarding cascades: an anonymised user row that still has a `Supplier.contact_id` pointing at it is the association erasure exists to remove.

`erase_user` also publishes `USER_ERASING` for `conversation`, replacing the direct call to `conversation_service.soft_delete_all_user_conversations` and the checkpoint loop. `conversation/handlers.py` soft-deletes the user's conversations, deletes their checkpoints, then blanks their names through a new `blank_all_user_conversation_names` (the loop that `anonymize_user()` loses with the relationship; every conversation of the user, deleted or not, as the relationship loaded them) — `delete_conversation_checkpoints` is in `agents/`, below `conversation`, so that call moves with the handler. The resulting order inside `erase_user`:

1. `publish(USER_ERASING)` — inline: conversations soft-deleted, names blanked, checkpoints gone; supplier unlinked
2. `delete_user_memory` — a direct call, `agents/` is an adapter
3. `anonymize_user()`, `commit`
4. cache invalidation on the captured `clerk_id`

Step 1 must precede step 3 for the reason the code already states: checkpoints and memories are keyed by identifiers `anonymize_user()` destroys. The `user_erased` log line gains `subscriber_count` from the publish return value, so a run with no subscribers — an entry point that never imported the modules — is visible.

**Event names** are constants on `account`'s root, namespaced: `USER_SYNCED = "account.user_synced"`, `USER_ERASING = "account.user_erasing"`, `USER_OFFBOARDED = "account.user_offboarded"`. A subscriber imports the constant, so a renamed event is an import error, not a silent no-op.

**Payloads** carry the session and plain values or the publisher's own model instance (R4). `USER_SYNCED` carries `user_id` and the merged metadata dict; the other two carry `user_id`.

---

## 4. Events: the dispatcher

`app/core/events.py`, ported from flyorbit and extended with a per-subscription mode.

```python
@events.on(USER_ERASING, inline=True)
async def unlink_on_erasure(session: AsyncSession, user_id: str) -> None: ...

@events.on(ORDER_PLACED)                      # deferred — the default
async def reserve_stock(session: AsyncSession, order_id: str) -> None: ...

subscriber_count = await events.publish(USER_ERASING, session=session, user_id=user.id)
```

**Inline** handlers run in `publish()`, in registration order, with the payload as keyword arguments; a handler that raises stops the sequence and propagates — the publisher is mid-transaction and must not commit a half-done cascade. This is flyorbit's dispatcher unchanged.

**Deferred** handlers are appended to a request-scoped queue (a `ContextVar`) with their payload, minus `session`. `get_db_session` in `app/database/dependencies.py` drains the queue after its `commit()`: each handler gets a session of its own from the session factory, is awaited, and a failure is caught, logged as `event_handler_failed` with the event name and the handler's qualified name, counted on a Prometheus counter, and not re-raised. The response has already been decided by then; the reaction is a retry candidate, not a reason to fail the command. A request that rolls back never drains: the queue is discarded with the request context.

`publish()` returns the number of handlers run plus queued. `events.flush(session_factory)` drains the queue explicitly for a caller outside a request — a script, the future worker; the factory is a parameter because the dispatcher lives below `app/database`. `events.begin()` opens an empty queue at the start of a request, so code that runs in a worker thread (which sees a *copy* of the context) appends to the list the request will flush.

The dispatcher is a singleton in the foundation and imports nothing above `app/core/logging` and `app/core/metrics`. `app/database/dependencies.py` importing `app/core/events` is a sibling import inside the foundation layer.

**Tests**: `tests/unit/core/test_events.py` — registration order, inline propagation, deferred queueing and draining, a failing deferred handler is logged and does not stop the others, `flush()` on an empty queue is a no-op.

---

## 5. Tenancy

Three pieces, none of which changes the schema.

**`TenantMixin`** in `app/models/base.py`, beside `TimestampMixin` and `SoftDeleteMixin`: `org_id: str = Field(index=True, nullable=False)`. No table adopts it in this slice (architecture §6).

**`CurrentOrgId`** in `modules/account/dependencies.py`, on the root: `get_current_org_id(user: CurrentUser) -> str`, raising `AuthorizationError("Organization membership required")` when `user.org_id` is `None`. Derived from the user row, not `request.state.org_id`: JIT provisioning fills the org from Clerk when the token has none, so the row is authoritative after resolution. No route uses it in this slice; it is the first thing a fork's router will ask for.

**`tests/unit/models/test_tenant_tables.py`**: imports every module's `models` slot, walks `SQLModel.metadata.tables`, and asserts each table either comes from a class carrying `TenantMixin` or is in the allowlist. The allowlist, in the test, with a reason per entry:

| Table | Reason |
| :---- | :---- |
| `user` | `org_id` is nullable — erasure clears it so an anonymised row cannot single out a one-contact supplier org |
| `conversation` | owned through its user; the user's org is the tenant |
| `supplier` | no write route yet; adopts the mixin with the first one, and the column needs a backfill that has no source until then |

A new table fails the test until it either carries the mixin or gets a row here. That is the entire mechanism.

---

## 6. Enforcement

**`server/pyproject.toml`** gains `[tool.importlinter]` with `root_package = "app"`, `exclude_type_checking_imports = true`, and:

- **R2**, one `layers` contract: `app.main` / `app.api` / `app.modules` / `app.integrations : app.agents` / `app.core : app.database : app.exceptions : app.models : app.schemas : app.utils`.
- **R6**, one `layers` contract: `app.modules.conversation | app.modules.supplier` / `app.modules.account`.
- **R1**, three `forbidden` contracts, one per module, each listing the other two modules' `.*`, with `allow_indirect_imports = true` — a module's own `__init__` re-exporting its submodules would otherwise register as an indirect import for every consumer of the root.

`import-linter` joins `[dependency-groups] dev`. `make check-server` in the root `Makefile` appends `&& uv run lint-imports`, so the pre-push hook runs it.

**`app/main.py`** imports every module by name (`from app.modules import supplier as _supplier`). A module with subscribers and no router — `supplier` — is otherwise never imported, and `events.publish` runs zero handlers with no error.

**`tests/unit/test_module_contracts.py`** parses the `[tool.importlinter]` table and lists `app/modules/*/`. For every module it asserts: an R1 contract whose `source_modules` is that module and whose `forbidden_modules` names every other module's `.*`; membership in the R6 contract's `layers`; if the module has a `models` slot, an import of it in `alembic/env.py`; and a `from app.modules import <name>` line in `app/main.py`. Adding a module without the four edits fails the unit suite.

**`.github/workflows/module-boundaries.yml`**, ported: checkout, uv with `--group dev --group test`, then `uv run lint-imports`, `uv run ruff check .`, `uv run ruff format --check .`, and `APP_ENV=test uv run pytest tests/unit/test_module_contracts.py tests/unit/models/test_tenant_tables.py tests/unit/core/test_events.py`. No database, no `.env`, no secrets.

---

## 7. Tests move

R5: `tests/unit/modules/<name>/` and `tests/integration/modules/<name>/`, one file per slot file. New alongside the moves: `tests/unit/modules/supplier/test_handlers.py` and `tests/unit/modules/conversation/test_handlers.py` for the subscribers, `tests/unit/modules/supplier/test_{service,cache}.py` for the extracted code. The `_MISS` sentinel both caches need becomes `MISS` in `app/utils/cache.py`. What moves:

| Today | After |
| :---- | :---- |
| `tests/unit/api/test_auth_dependencies.py` | `tests/unit/modules/account/test_dependencies.py` |
| `tests/unit/services/test_user_{cache,erasure,repository_sync}.py` | `tests/unit/modules/account/test_{cache,service,repository}.py` |
| `tests/unit/services/test_supplier_linking.py` | `tests/unit/modules/supplier/test_service.py` |
| `tests/unit/integrations/clerk/test_{user,membership}_handlers.py` | `tests/unit/modules/account/test_webhooks.py` |
| `tests/unit/services/test_llm_*.py` | `tests/unit/integrations/llm/` |
| `tests/unit/models/test_enums.py`, `test_models.py` | per module: `tests/unit/modules/<name>/test_models.py`; what tests `models/base.py` stays |
| `tests/unit/schemas/test_schemas.py` | per module; `Message`'s cases → `tests/unit/agents/test_messages.py` |
| `tests/unit/schemas/test_system_schemas.py` | `tests/unit/api/test_system_schemas.py` |
| `tests/unit/utils/test_graph.py` | `tests/unit/agents/test_graph.py` |
| `tests/integration/api/test_auth*.py`, `test_webhooks.py` | `tests/integration/modules/account/router/test_{auth,auth_delete,webhooks}.py` — the router slot is a package, so its tests mirror it file for file |
| `tests/integration/api/test_conversations.py`, `test_chatbot.py` | `tests/integration/modules/conversation/router/test_{conversation,chatbot}.py` |
| `tests/integration/dependencies/test_conversation_access.py`, `test_role_dependencies.py` | `tests/integration/modules/{conversation,account}/test_dependencies.py` |
| `tests/integration/dependencies/test_database.py` | `tests/integration/database/test_dependencies.py` |
| `tests/integration/services/test_{user_service,user_repository}.py` | `tests/integration/modules/account/` |
| `tests/integration/services/test_supplier_repository.py` | `tests/integration/modules/supplier/test_repository.py` |
| `tests/integration/services/test_conversation_service.py` | `tests/integration/modules/conversation/test_service.py` |

Tests that override dependencies do so through the getters exported on the module root (`app.dependency_overrides[get_current_user] = …`), which is why the getters are on the root (architecture R1).

The erasure tests change shape: what asserted that `erase_user` called `conversation_service` and `supplier_repository` now asserts that it published `USER_ERASING`, and the cascades are tested in their own modules' handler tests. New: `tests/unit/core/test_events.py`, `tests/unit/test_module_contracts.py`, `tests/unit/models/test_tenant_tables.py`.

---

## 8. Documentation to update

| File | Change |
| :---- | :---- |
| `server/CLAUDE.md` | **Directory Structure** replaced with the module map and a pointer to the architecture doc; **Exception Handling** paths (`app/services/<name>/exceptions.py` → `app/modules/<name>/exceptions.py`); **Authentication** (`CurrentUser` from `app.modules.account`); **Testing** tree; **GDPR** step list rewritten around `USER_ERASING` |
| `.claude/skills/fastapi-service-patterns/SKILL.md` and `references/{services,exceptions,client-wrappers,webhooks}.md` | every `app/services/` and `app/api/dependencies/` path; the webhook reference's "handlers live with the provider" rule inverted to D3 |
| `server/docs/authentication.md`, `gdpr-compliance-guide.md`, `gdpr-erasure-findings.md` | paths, and the erasure order in §3 |
| `docs/setup/making-it-yours.md` | "replacing the example domain" becomes "delete `app/modules/supplier/` and its three contract entries" |
| `docs/README.md` | an **Architecture** section, done in this commit |
| `README.md` | the `docs/` line in the repo tree |
| `docs/architecture/server-modules.md` | **Status** flipped to implemented, the tree in §2 confirmed against the result |

---

## 9. Out of scope

- **Any schema change.** `TenantMixin` on `supplier`, per-org uniqueness of `code` and `vat_number`, a `conversation.org_id` — all seams (architecture §8).
- **A `domain` slot or its contract.** No module in the template holds rules that earn one.
- **The worker entrypoint and the queue.** Designed in the seams table; nothing in the template runs outside a request.
- **A `conversation` repository.** The service's queries move as they are.
- **Renaming `supplier` or the roles.** Still the fork's job; this slice makes it a folder deletion plus three lines.

---

## 10. Verification

In order, each a gate for the next:

1. `make check-contract` from the root — **passes with no diff**. Same paths, same tags, same `operation_id`s; the client is untouched. This is the proof that no public surface moved.
2. `cd server && APP_ENV=development uv run alembic revision --autogenerate -m probe` produces a revision with empty `upgrade()` and `downgrade()`; delete it. Proof of no schema change.
3. `make check-server` — ruff clean, `lint-imports` reports every contract kept.
4. `cd server && make test` — the full suite green, including the three new unit files.
5. `make docker-run-core` and a supplier-role sign-in through the supplier portal: the first request JIT-provisions and resolves `SupplierID` in one go (the inline `USER_SYNCED` path). `DELETE /api/v1/auth/me` on a user with conversations: the conversations are soft-deleted with blank names, the supplier is contact-less, `user_erased` logs `subscriber_count=2`.
6. A deliberate `from app.modules.supplier.repository import supplier_repository` in `account/service.py` fails `lint-imports`; a `mkdir app/modules/probe` with a `models.py` fails `test_module_contracts.py` and `test_tenant_tables.py`. Revert both.
