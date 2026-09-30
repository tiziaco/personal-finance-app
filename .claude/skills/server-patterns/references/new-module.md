# Adding a Module

This file is the order to do things in and the exact edits, because the wiring is spread across four files and
three tests fail one at a time. It is enough on its own for an ordinary module — a handful of tables, a router,
a service. The rule references (R1, R6, …) point at `docs/architecture/server.md` §3 for the reasoning; read
the section itself only when you need the *why*, or for the two cases this procedure stops at: a module complex
enough to want packages-as-slots or a `domain` slot (§2), and a data dependency that the DAG will not allow (R6).

Work the two decisions first, then the slots, then the wiring. The wiring is what a fork forgets, and it is the
half that is enforced.

## Decide two things before writing a file

**Is the table tenant-owned?** A table whose rows belong to one organisation carries `TenantMixin`, and every
repository method on it takes and filters by `org_id` (R7). Retrofitting this means a backfill, so decide now.
A table that is genuinely not tenant-owned goes in `ALLOWLIST` in `tests/unit/models/test_tenant_tables.py` with
the reason — the test fails until one of the two happens, which is the point.

**Does it hold data keyed to a user?** If so it subscribes to `account.USER_ERASING` in its `handlers` slot and
cleans up there, inline. `app/modules/conversation/handlers.py` is the model; the GDPR section of
`server/CLAUDE.md` is the obligation.

## The slots

Create only the slots the module has — empty files are not created for symmetry (§2):

```
app/modules/payment/
  __init__.py      # the public surface
  router.py        # omit if the module has no routes (supplier has none)
  schemas.py
  models.py        # omit if it owns no tables
  service.py       # PaymentService + payment_service singleton
  repository.py    # PaymentRepository + payment_repository singleton
  dependencies.py
  exceptions.py
  handlers.py      # only if it subscribes to another module's events
  domain.py        # only for rules that must not import the ORM (R9)
```

`__init__.py` exports the service singleton, the schemas another module may return or embed, the dependencies and
their getters, the exceptions another module may catch, and the names of the events it publishes — never the
repository or the models (§2, R1). If the module has a `handlers` slot, the root imports it for its side effect:

```python
# @events.on is a module-level side effect: importing the root is what subscribes.
from app.modules.payment import handlers
```

A slot becomes a package of the same name when it outgrows one file, and no import anywhere changes (§2).

## The wiring, in order

Each step is a failing test until it is done. `tests/unit/test_module_contracts.py` covers 1, 2, 3 and 4.

**1. Mount the router** — skip for a module without routes.

```python
# app/api/v1/api.py
from app.modules import account, conversation, payment
api_router.include_router(payment.router)
```

**2. Import the module in `app/main.py`** — every module, router or not, so its subscribers register.

```python
from app.modules import payment as _payment
```

**3. Import the models slot in `alembic/env.py`** — skip if the module owns no tables. R8: this list is the model
registry, and a slot missing from it is a table autogenerate never sees.

```python
import app.modules.payment.models
```

**4. Add the import-linter contracts in `server/pyproject.toml`.** This is *N+1 edits, not one* — the R1 contracts
are symmetric, and `test_module_contracts.py` asserts each module forbids exactly the set of all the others:

- the new module's own R1 contract, forbidding every existing module's submodules, with
  `allow_indirect_imports = true`
- `"app.modules.payment.*"` appended to the `forbidden_modules` of **every module already there**
- `app.modules.payment` placed in the R6 DAG layers — `|` between siblings that must not import each other, `:`
  between those that may

Miss the second bullet and three parametrized tests fail naming the modules whose lists are short.

**5. Create the migration** — skip if the module owns no tables.

```bash
make -C server migrate-create ENV=development MSG="add payment tables"
make -C server migrate ENV=development
```

**6. Regenerate the contract** — only if the module added routes.

```bash
make gen-contract
```

## Where the module sits in the DAG

Modules form a DAG, and the R6 contract is where you declare it. A module imports those below it directly. When
it needs a module *above* it to act, it publishes an event and the higher module subscribes — `references/events.md`
has when, how, and which dispatch mode.

If the new module needs another module's *data* and the dependency points the wrong way, the data belongs
elsewhere — that is a modelling answer, not an event (R6).

Foreign keys to another module's table are declared by table name, never by importing the class, and there are no
ORM relationships across modules (R3). A type hint on another module's model goes under `TYPE_CHECKING` (R4).

## Tests

Mirror the tree: `tests/unit/modules/payment/` and `tests/integration/modules/payment/`, one test file per slot
file (R5).

## Verify

```bash
cd server && uv run pytest tests/unit/test_module_contracts.py tests/unit/models/test_tenant_tables.py \
                          tests/unit/api/test_openapi_contract.py
make check-server        # ruff, format, lint-imports — the R1/R2/R6/R9 contracts
```

`make check-server` runs `lint-imports`, so a boundary violation fails here and again in
`.github/workflows/module-boundaries.yml`. The three test files are the gaps the linter cannot see: a contract
nobody wrote, a table nobody scoped, a route with no `operation_id`.
