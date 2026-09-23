# Server — Modules

**Status:** implemented · designed 22 Sep 2026 · landed by [`2026-09-22-server-modules-design.md`](../superpowers/specs/2026-09-22-server-modules-design.md) on `refactor/server-modules` · **Owner:** Tiziano · **Last updated:** 22 Sep 2026
**Scope:** how `server/app/` is partitioned and the rules between the parts. Not the schema of any one module.

---

## 1. Approach

**A modular monolith: one package per bounded context, boundaries enforced by a linter.** This is a template. A fork adds its own contexts — warehouses, orders, projects, documents — and the value the template ships is not the three modules it comes with but the rules a fourth must obey and the tooling that fails the push when it does not. The boundary is the thing to get right first; the folder shape is how the boundary is made visible.

**What this is not.** Not tactical DDD by default: no `domain/application/infrastructure` tree inside a module, no repository interfaces, no DI container, no mapper between entities and tables. Each of those adds files for a reader who does not exist in a module of plain CRUD. A module that earns more gets exactly one thing more — a `domain` slot that may not import the ORM (§3, R9) — and the linter holds it to that. Not microservices: one process, one database, one migration history. The modules are the seams a split would follow if one were ever needed, and that is all they need to be.

**Rejected alternatives:**

- *Keep the layer folders and add the access rule only.* Cheaper now, and the rule is what matters. But every future context would spread across four folders, and the template's own three domains already showed the cost: the supplier code used to live inside the `user` service package, so the user service reached the supplier table directly and the two were one tangle (§7, D1).
- *Layered internals per module (`domain/`, `application/`, `infrastructure/`, `presentation/`).* The canonical DDD shape. It triples the file count per module and separates a service from its repository by two directories. The separation it actually buys — business rules that do not depend on the ORM — is a property of one file, not a tree, and the `domain` slot with a linter contract gives that property to the module that needs it without imposing the tree on the ones that do not. What a module gains on top of that is packages in place of files (§3), never layer folders.
- *An `api/` folder inside each module for its router and schemas.* Schemas are not only the API's: services take and return them, and other modules import a module's public schemas. A layer folder inside a domain folder is the pattern the move retires.

**Conventions:**

- The name is **`modules/`**, not `contexts/` or `domains/`. It is the term the modular-monolith literature uses.
- Inside a module, the existing conventions hold unchanged: a stateless service class with a module-level singleton, a repository that is the only place `select()` runs, domain exceptions inheriting `app/exceptions/base.py`, structured logging, `async` everywhere. See [`server/CLAUDE.md`](../../server/CLAUDE.md) and the `fastapi-service-patterns` skill.
- Every route keeps its explicit tag and `operation_id`. A tag becomes a module in the generated web client, so a module's router files map one-to-one onto its tags.

## 2. The layout

Four layers, top to bottom. A layer imports downward only.

| Layer | Packages | Imports from |
| :---- | :---- | :---- |
| **Assembly** | `app/main.py`, `app/api/` (router assembly, middlewares, system endpoints) | everything below |
| **Modules** | `app/modules/<name>/` | other modules' package roots (§4), and everything below |
| **Adapters** | `app/integrations/<provider>/` (Clerk, the LLM providers), `app/agents/` (LangGraph base, memory, checkpointing, observability) | foundation only |
| **Foundation** | `app/core/`, `app/database/`, `app/exceptions/`, `app/models/base.py`, `app/schemas/base.py`, `app/utils/` | nothing above |

The tree as implemented:

```
server/app/
├── main.py
├── api/
│   ├── middlewares/          # auth (JWT), access logging, CORS, logging context, security headers, Prometheus
│   ├── system/               # health + metrics endpoints, and their schemas
│   └── v1/api.py             # assembles the modules' routers — nothing else
├── modules/
│   ├── account/              # the Clerk-backed identity: user row, Role, CurrentUser/CurrentRole/CurrentOrgId,
│   │                         #   require_role, Clerk webhook handlers, JIT provisioning, erasure
│   ├── conversation/         # the chatbot: conversations and chat routes, the agent dependency
│   └── supplier/             # the example domain: the supplier row, its contact link, SupplierID
├── integrations/
│   ├── clerk/                # client, exceptions, timestamps, webhooks/{verification,schemas} — the provider half
│   └── llm/                  # a provider adapter, not a domain
├── agents/                   # base/, shared/, chatbot/, plus messages.py (the Message type), graph.py, factory.py
├── core/                     # config, logging, metrics, limiter, metadata, events.py (the dispatcher, §5)
├── database/                 # engine, session context, dependencies.py (the DbSession dependency)
├── exceptions/               # the exception hierarchy and the handlers
├── models/base.py            # shared mixins only, TenantMixin among them; the domain models live in their modules
├── schemas/base.py           # ErrorResponse only; the domain schemas live in their modules
└── utils/                    # token verification, sanitisation
```

The old `services` layer, the `dependencies` folder under `api/`, and the domain files that used to sit under `models/` and `schemas/` are gone from `app/`.

## 3. Anatomy of a module

Every module has the same seven slots, and may have two more:

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
  handlers.py        # optional: subscriptions to other modules' events (§5)
  domain.py          # optional: rules that must not depend on the ORM (R9)
```

**A slot is a file until it needs to be a package, and the import path never notices.** When one file grows past what fits in your head, or plainly holds two or three independent parts, that file becomes a package of the same name with an `__init__.py` re-exporting what the file exported. Nothing else in the module changes and no import anywhere changes. The decision is per slot, not per module. A module may also hold private helper files beyond the slots (`account/cache.py`); they are not on the root and nothing outside the module knows them.

**The public surface is `__init__.py`.** It exports the service singleton(s), the response schemas another module may return or embed, the dependencies another module's router may use (`CurrentUser` from `account`), the exceptions another module may catch, the enums another module may compare against, and the names of the events it publishes. It does not export the repository or the models. Everything a module does not export is private, and §4's enforcement holds other modules to that. Importing the root imports `handlers.py`, so importing a module is what registers its subscriptions.

**Not every module has every slot.** A module without routes has no `router.py`; a module that reacts to nothing has no `handlers.py`. Empty files are not created for symmetry.

**Worked example — `supplier`, the template's own cycle resolved.** Before this refactor, the `user` service package held `supplier_repository.py`, and the user service linked, unlinked and resolved suppliers by reaching the supplier table directly; the `SupplierID` dependency sat in the auth dependencies file beside `CurrentUser`. Two domains, one folder, calls in both directions. After the move:

```
app/modules/supplier/
  __init__.py          # supplier_service, SupplierID, get_supplier_id, SupplierNotLinkedError
  models.py            # Supplier — contact_id is a foreign key by table name, no relationship
  repository.py
  service.py           # link_from_metadata, unlink_contact, get_id_for_user
  dependencies.py      # SupplierID: the caller is the contact of a supplier
  handlers.py          # on USER_SYNCED → link; on USER_ERASING, USER_OFFBOARDED → unlink
  exceptions.py
  cache.py             # the user_id → supplier_id entries, private
```

`supplier` imports `account` (it needs `CurrentUser`). `account` never imports `supplier`: where the user service called `link_supplier_from_metadata` — JIT provisioning, the `user.created` and `organization_membership.created` webhook handlers — it publishes `USER_SYNCED`; where it called `unlink_supplier_contact` — erasure, `organization_membership.deleted` — it publishes `USER_ERASING` and `USER_OFFBOARDED`. The three subscriptions run inline (§5), because the caller's own request depends on them: a supplier's first request JIT-provisions the user and resolves `SupplierID` in the same transaction.

**A complex module climbs two rungs, per module, and R1 means nothing outside it notices.** Neither is triggered by size — many tables, many services, many routes are all absorbed by the first.

1. **Slots become packages.** `router/` with a file per tag, `models/` with a file per table, `service/` with a file per aggregate or per use case. This is the answer to "this domain has several services and several models", and it is the only rung most modules ever reach.
2. **A `domain` slot.** For rules you want to test without a database — an order's state machine, stock allocation, pricing. `domain.py`, or `domain/` when it grows, holds plain classes and functions and may not import `sqlmodel`, `sqlalchemy` or `fastapi`; the linter holds it to that (R9). Two flavours, and the module picks the cheaper one that fits: rules as pure functions and value types over plain values, which the service feeds from the model and applies back — no mapping at all; or domain dataclasses that the repository maps to and from rows, when the rules need the whole aggregate in hand. The service calls `domain`; `domain` never calls anything.

**Worked example — `orders`, as a fork on both rungs would build it:**

```
app/modules/orders/
  __init__.py          # order_service, the response schemas, OrderOwner, ORDER_PLACED, ORDER_CANCELLED
  router/
    __init__.py        # one APIRouter assembled from the files below
    orders.py          # tag "orders": place, list, get, cancel
    lines.py           # tag "order-lines"
  schemas/
    __init__.py  order.py  line.py
  models/
    __init__.py  order.py  line.py        # both carry TenantMixin (R7)
  service/
    __init__.py        # order_service, line_service
    order.py           # place, cancel: load the aggregate, call domain, persist, publish
    lines.py           # plain child CRUD
  repository/
    __init__.py  order.py  line.py
  domain.py            # rung 2: the Order state machine and Quantity — no ORM import
  handlers.py          # on inventory.STOCK_RESERVED
  dependencies.py      # OrderOwner: the order exists and belongs to the caller's org
  exceptions.py
```

There is no third rung. Regrouping these slots under `domain/`, `application/`, `infrastructure/` and `presentation/` moves files without separating anything the `domain` slot has not already separated, and it is the layer-folder-inside-a-domain-folder that §1 retires. A module with several implementations of one port — three warehouse systems behind one `StockSource` — keeps them in a `clients` slot, a file and then a package, behind a `Protocol` declared in `domain`.

What does not change on any rung: the root as the only import surface, R1–R9, and the DAG. A fork whose `orders` module is on the second rung and whose `carriers` module is all files is the intended state, not an inconsistency.

## 4. The rules

**R1 — Across modules, only the package root.** A module imports another module as `from app.modules.<other> import …`, never `app.modules.<other>.repository`, `.models`, `.service` or any other submodule. What the root does not export, the other module cannot have.

**What belongs on the root.** A name is on the package root if something outside its own slot file legitimately needs it, and where a name is on the root, every consumer imports it from there. A dependency's *getter* is surface, not an implementation detail behind its `Annotated` alias: FastAPI keys `dependency_overrides` by the exact callable, so `get_current_user` is the only way a test can stand in for `CurrentUser`. An exception class nothing raises is dead code, not surface.

**R2 — Down the layers only.** A module imports adapters and the foundation; adapters import the foundation; the foundation imports nothing above itself. `app/api/` and `app/main.py` import anything. An adapter that needs domain logic — a Clerk webhook that updates a user — is an adapter that is holding domain logic, and the logic moves up into the module that owns the table (§7, D2).

**R3 — A module owns its tables.** Its models are in its `models` slot and nowhere else. A foreign key to another module's table is declared by table name (`foreign_key="user.id"`), never by importing the other module's model class. There are **no ORM relationships across modules**: a module that needs the other side of a key asks the other module's service.

**R4 — Model instances may cross, classes may not.** A module may hand its own model instances out through its public surface (`CurrentUser` yields a `User`), and the receiving module treats them as read-only values. It never imports the class except under `TYPE_CHECKING` for a type hint, and never mutates or persists what it did not load.

**R5 — Tests mirror the tree.** `tests/unit/modules/<name>/` and `tests/integration/modules/<name>/`, one test file per slot file. Adapter and foundation tests stay where they are.

**R6 — Modules form a DAG.** If `supplier` imports `account`, `account` does not import `supplier`. Two package roots that import each other is a Python circular import, and it fails at startup, not in review. When a lower module needs a higher one to *act*, it publishes an event and the higher module subscribes (§5). When it needs the higher one's *data*, the dependency is pointing the wrong way and the data belongs elsewhere.

**R7 — A tenant-owned table carries `TenantMixin`.** A table whose rows belong to one organisation declares `org_id` through the mixin, and every repository method on it takes the org id. A table that is not tenant-owned says so in the allowlist, with the reason (§6). This is the one cross-cutting concern where per-module forgetfulness is a data leak rather than noise, so it is a test, not a convention.

**R8 — Migrations are global.** One database, one Alembic history in `server/alembic/versions/`. A module's migration is an ordinary revision that happens to touch its tables; there are no per-module histories. `alembic/env.py` imports every module's `models` slot so autogenerate sees the whole schema. That list lives in `env.py` and not in a registry under `app/`, because a registry in the foundation would import the modules (R2), and one in `app/modules/` would import every sibling's models (R1). Adding a module with tables means adding one import line there.

**R9 — The `domain` slot imports neither the ORM nor the framework.** `domain.py`, or `domain/`, may not import `sqlmodel`, `sqlalchemy` or `fastapi`. That one restriction is the whole of what the slot means: rules that can be tested without a database and survive a change of persistence. The service calls `domain`; `domain` calls nothing above the standard library and the foundation's value types.

**Enforcement.** R1, R2 and R6 are contracts for [`import-linter`](https://import-linter.readthedocs.io/), configured in `server/pyproject.toml` and run by `make check-server`, so a violation fails the pre-push hook. `.github/workflows/module-boundaries.yml` runs them in CI on every pull request and every push to `main` — `git push --no-verify` skips the hook, and the boundaries are the codebase's load-bearing invariant. R2 is one `layers` contract over the four layers. R6 is a second `layers` contract listing the modules in dependency order; modules that do not depend on each other share a layer with `|`, which forbids them from importing each other. R1 is one `forbidden` contract per module, listing every other module's submodules. R9 is a `forbidden` contract too, and lands with the first `domain` slot (§8). Type-checking-only imports are excluded from the graph, which is what lets R4's hint through. Every directory under `app/` carries an `__init__.py`, because the graph builder needs regular packages.

That enumeration is the cost to watch: a new module is three edits to `pyproject.toml` before it is enforced, and CI cannot fail a contract nobody wrote. `tests/unit/test_module_contracts.py` closes that gap — it lists `app/modules/*/`, and fails if any module is missing its R1 contract, missing from the R6 order, or has a `models` slot that `alembic/env.py` does not import (R8). R7 is `tests/unit/models/test_tenant_tables.py`: every `table=True` model under `app/modules/` either carries `TenantMixin` or is named in the allowlist. R3, R4 and R5 are review items — R3's half about relationships would also surface as an R1 violation, since a relationship needs the class.

## 5. Events

`app/core/events.py` is the seam for the one dependency direction the DAG forbids: a lower module that needs a higher one to act. A registry keyed by event name; a module subscribes with `@events.on(NAME)` in its `handlers` slot, and the root imports that slot so importing the module is what registers it. A publisher calls `await events.publish(NAME, session=session, **payload)` and never knows who listens or how. Events are for the downward-pointing case only: a module that is *higher* in the DAG and needs a lower one to act calls its service directly, so that the dependency graph stays readable from the imports alone.

**Two dispatch modes, chosen per subscription.** **Deferred** is the default: the handler runs after the publisher's session commits, in a session of its own, and a failure is logged as `event_handler_failed`, counted, and never raised — the command succeeded, the reaction did not, and that is a retry, not a 500. **`inline=True`** runs the handler in the publisher's session and transaction, in registration order, and a failure propagates: for a cascade that is part of the command's own consistency, where committing half of it would be wrong. The deferred queue is request-scoped and drained by the `DbSession` dependency after its commit; a request that rolls back discards it. An entry point that runs outside a request — a script, a worker — drains it with `events.flush()`, or its deferred handlers silently never run. `publish()` returns the number of handlers run plus queued, and the publisher logs it as `subscriber_count`: zero on an erasure is the signal that the modules were never imported.

**Names** are constants on the publishing module's root, namespaced by module: `USER_ERASING = "account.user_erasing"`. A subscriber imports the constant, so a renamed event is an import error, not a silent no-op. **Payloads** carry the session and plain values, or the publisher's own model instance under R4.

**The events as they stand.** All three are cascades and say so; the default exists for the reactions a fork will add.

| Event | Published by | Payload | Subscribers | Mode |
| :---- | :---- | :---- | :---- | :---- |
| `account.USER_SYNCED` | JIT provisioning; the `user.created` and `organization_membership.created` webhook handlers | `user_id`, the merged Clerk public metadata | `supplier` — links the supplier named in the metadata to this user | inline: a supplier's first request JIT-provisions the user and resolves `SupplierID` in the same transaction |
| `account.USER_ERASING` | `erase_user`, before `anonymize_user()` | `user_id` | `conversation` — soft-deletes the rows, blanks their names, deletes their checkpoints; `supplier` — clears `contact_id` | inline: an anonymised row that still has a `Supplier.contact_id` pointing at it is the association erasure exists to remove |
| `account.USER_OFFBOARDED` | the `organization_membership.deleted` webhook handler | `user_id` | `supplier` — clears `contact_id` | inline: part of the revocation |

Memory deletion during erasure stays a direct call from `account`: `agents/` is an adapter, below every module, and needs no event.

## 6. Tenancy

Multi-tenancy is Clerk Organizations. The org id arrives on the JWT, `AuthMiddleware` puts it on `request.state`, and JIT provisioning writes it to the user row — filling it from Clerk's membership API when the token carries none, so the row is authoritative once the user is resolved.

Three pieces hold the boundary. **`TenantMixin`** in `app/models/base.py`, beside `TimestampMixin` and `SoftDeleteMixin`, declares the indexed, non-null `org_id` a tenant-owned table carries (R7). **`CurrentOrgId`** in `account/dependencies.py`, on the root, yields the resolved user's `org_id` and raises `AuthorizationError` when it is null — derived from the row, not from `request.state`, for the reason above. **`tests/unit/models/test_tenant_tables.py`** walks every table under `app/modules/` and fails on one that neither carries the mixin nor appears in its allowlist.

No table adopts the mixin today, and the allowlist says why for each:

| Table | Why not tenant-owned |
| :---- | :---- |
| `user` | `org_id` is nullable — erasure clears it, because a supplier organisation typically has one portal contact, and retaining the org on an anonymised row would still single that person out |
| `conversation` | owned through its user; the user's org is the tenant |
| `supplier` | no write route yet; adopts the mixin with the first one, because the column needs a backfill and nothing writes the table today (§8) |

The first new table fails the test until it either carries the mixin or adds a row here. That is the entire mechanism, and it is a test rather than a convention because forgetting it is a data leak.

## 7. Decisions

Where something lives, and why not elsewhere. The rules above are what the code obeys; these rows are the reasoning it cannot hold.

| # | Question | Decision |
| :---- | :---- | :---- |
| D1 | Where does the supplier code live? It used to sit inside the `user` service package, and the user service called it in both directions. | **Its own module, `supplier`, below `account` in the DAG.** It is the template's example domain and the thing a fork renames first; a fork should be able to delete the folder. The user service's three supplier calls became the three events in §5. |
| D2 | The Clerk webhook handlers write the `user` table. The provider's verification, schemas, dispatch and handlers used to live together so the flow read top to bottom. | **The handlers and the dispatcher live in `account/webhooks.py`; verification and event schemas stay in `integrations/clerk`.** The handlers are account logic that happens to be triggered by a provider. R2 wins over the top-to-bottom read; the flow still reads in one file, one level up. The receiver route is part of `account`'s router, still `include_in_schema=False`. |
| D3 | Where do the FastAPI dependencies live? `CurrentUser`, `CurrentRole` and `require_role` are used by every router. | **Each in the module whose business it is, exported from its root.** `CurrentUser`, `CurrentRole`, `CurrentOrgId`, `require_role` resolve the caller's identity — `account`. `UserConversation` and `ChatbotAgentDep` — `conversation`. `SupplierID` — `supplier`. Left in `app/api/`, every module's router would import upward, an R2 violation. `DbSession` is session lifecycle with no domain in it and lives in `app/database/dependencies.py`. |
| D4 | Where does `Role` live? | **`account/models.py`**, exported from the root. It is the platform role off the Clerk token — identity. |
| D5 | Is `llm` a domain or an adapter? | **An adapter: `integrations/llm`.** It exists because LLM providers do, and holds nothing about the product. `Message` and the graph helpers live in `agents/` — they are its own types, and an adapter importing a module's schema is an R2 violation. The chat request and response schemas are `conversation`'s. |
| D6 | Layered internals (`domain/`, `application/`, `infrastructure/`, `presentation/`) for a complex module? | **No.** They regroup the slots under layer folders — the pattern §1 retires — and separate nothing the `domain` slot does not (§3). Several implementations of one port are a `clients` slot behind a `Protocol` in `domain`. The entity-to-table mapping question arises only in the second flavour of the `domain` slot, and the module that takes it decides and records it here. |

## 8. Seams

Each row is a place the current design deliberately leaves open, what closes it, and the shape it takes when it does — decided now so that a fork does not re-decide it.

| Seam | Closes with | As |
| :---- | :---- | :---- |
| R9 is a rule without a contract | The first `domain` slot | One `forbidden` contract: `app.modules.*.domain` may not import `sqlmodel`, `sqlalchemy`, `fastapi` |
| Every entry point is a request | The first job that must not run in one | `app/workers/main.py` in the Assembly layer, the mirror of `api/v1/api.py`: imports every module's root and registers its `handlers`, then drains with `events.flush()`. A module's queue consumers are a delivery mechanism like its router, and live in the module |
| The deferred mode runs handlers in-process | The first subscriber that must run on a worker | The same `publish()` calls; a deferred subscription whose handler enqueues to the queue (SQS or similar). Deferred already means after-commit, so the transport does not change the publisher's semantics |
| A deferred handler that fails is logged and lost | The first one whose loss is unacceptable — billing, an external notification | An `outbox` table written in the publisher's transaction and drained by the worker, replacing the in-memory queue for those events |
| `supplier` is on the tenancy allowlist | The first supplier write route | `TenantMixin` on the table, its backfill, and `org_id` on every `supplier` repository method |
| All settings are in `app/core/config.py` | The first module with settings of its own | A nested model in `config.py` named for the module, so `settings.<module>.X` reads like the rest |
| A module reads another's data only through its service, one call at a time | The first module that reads another's data at volume | A query interface the owning module publishes, indexed for the reader — never a shared repository |
| The module root is an import surface | Never planned | It is also the interface a split into a separate service would keep, and that is all it needs to be |
