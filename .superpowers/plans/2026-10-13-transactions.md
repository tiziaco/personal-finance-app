# Transactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Roadmap step 2 — a `transaction` module and table with a server-owned category list, a `/transactions` page to browse, filter, add, edit, delete and recategorise, a Settings "Delete all", a dev seed, and the email-uniqueness fix.

**Architecture:** A new server module `app/modules/transaction/` (above `account`, beside `conversation` in the R6 DAG) owns the table, the category list and every route under `/api/v1/transactions`. The web page is a URL-state `ServerDataTable` built from the `examples/orders/` pattern; `@app/data-table` gains generic row selection, a bulk bar, a phone card layout, date presets and a checkbox-group filter.

**Tech Stack:** FastAPI 0.141 + SQLModel + Alembic + PostgreSQL 18 (asyncpg); pytest + testcontainers; Next.js 16, TanStack Query/Table, nuqs, Base UI, orval-generated client; Vitest + Testing Library.

**Spec:** `.superpowers/specs/2026-10-13-transactions-design.md` — read it first. `.superpowers/BRIEF.md` holds the ownership rules and the eight conditions shared with step 3.

## Global Constraints

- Work in this worktree (`.claude/worktrees/transactions`, slot 1: web 3010, API 8110, Postgres 5444). Never `make clean` / `make rebuild`.
- Never touch `server/app/modules/conversation/`, the chat UI, `server/app/api/middlewares/`, the `(dashboard)/layout.tsx` inset container, or any existing fixture in a `conftest.py` (new fixtures go in new conftest files or beside existing ones).
- Never hand-edit `server/openapi.json`, `web-app/packages/api-client/src/generated/`, `server/uv.lock` or `pnpm-lock.yaml`; run `make gen-contract` (repo root) after every route change and commit its output in the same commit.
- Never change `version` in `server/pyproject.toml`.
- In `server/app/core/config.py` add only the `TRANSACTIONS` rate-limit line; step 3 edits other sections.
- Server conventions (load `server-patterns` before server code, `server-testing` before server tests): services and repositories are stateless classes with `@staticmethod async` methods + a module-level singleton; DB access only in `repository.py`; writes `flush()`, never `commit()`; every route has a camelCase `operation_id`, the router's tag, a `response_model` or 204, and `@limiter.limit(settings.rate_limits.endpoints.TRANSACTIONS[0])` with `request: Request` first; structured logs `logger.info("snake_case", key=value)` and no merchant/description text in logs or exception context.
- Web conventions (load `web-app-patterns` before web code, `web-app-testing` before web tests): Base UI `render` prop, never `asChild`; `@app/ui/<name>` subpath imports; types and hooks only from `@app/api-client`; never render `error.message`/`error.body`; list state only in the URL state hook; loading returns a skeleton; kebab-case files; `"use client"` only where needed.
- Amounts are `Decimal`/strings end to end — never `float`/`Number` arithmetic on an amount.
- Category slugs (exact, in display order): `income, salary, transportation, household_utilities, tax_fines, food_groceries, food_delivery, bars_restaurants, atm, insurances, shopping, education, family_friends, donations_charity, healthcare_drug_stores, leisure_entertainment, media_electronics, savings_investments, travel_holidays, miscellaneous`.
- Page size 20, `limit` max 100, batch `ids` 1–100 distinct, `search` ≤ 100, `merchant` 1–255 after strip, `description` ≤ 1,000, amount ≤ 12 digits / 2 places.
- Commit after every task with a message in the repo's style (`feat(transactions): …`, `fix(account): …`, `docs: …`). Run from the worktree root unless a step says `server/` or `web-app/`.
- Before the server tasks: Docker running; `make docker-run-db ENV=development && make -C server migrate ENV=development`.

## Review Focus

1. **An empty PATCH (`{}`)** — the edit dialog sends only changed fields, so "Save" with no change sends `{}`; the row must come back unchanged, `confidence` and `updated_at` untouched (Task 3).
2. **Inverted bounds** — `date_from` after `date_to`, or `amount_min` above `amount_max`, answers 200 with no items, never a 500 (Task 4).
3. **A comma decimal in the amount field** — a Berlin user types `-4,50`; the dialog must send `"-4.50"`, and reject `4,505` and `abc` inline (Task 12).
4. **A page past the end** — `offset` beyond `total` returns `items: []` with the real `total` (Task 4).
5. **Case and padding in the fingerprint** — `"  SPÄTI "` and `"späti"` (and a description differing only in case) produce the same fingerprint, so the duplicate check fires (Task 3).

---

## File map

**Server — create**
- `server/app/modules/transaction/{__init__,models,schemas,repository,service,dependencies,exceptions,handlers,router}.py`
- `server/alembic/versions/<ts>_<rev>_user_email_not_unique.py`, `server/alembic/versions/<ts>_<rev>_add_transaction.py` (autogenerated)
- `server/data/transactions-seed.csv`, `server/scripts/seed_transactions.py`
- Tests: `server/tests/unit/modules/transaction/{__init__,test_schemas,test_service,test_handlers}.py`, `server/tests/integration/modules/transaction/{__init__,conftest,test_repository,test_service,test_erasure}.py`, `server/tests/integration/modules/transaction/router/{__init__,test_transactions}.py`, `server/tests/unit/scripts/test_seed_transactions.py`, `server/tests/integration/scripts/{__init__,test_seed_transactions}.py`

**Server — modify**
- `server/app/modules/account/{models,repository,service}.py`; `server/tests/integration/modules/account/{test_repository,test_service}.py`, `server/tests/integration/modules/account/router/test_webhooks.py` (new tests only)
- `server/app/main.py`, `server/app/api/v1/api.py`, `server/alembic/env.py`, `server/pyproject.toml` (`[tool.importlinter]` only), `server/app/core/config.py` (one line), `server/Makefile`, root `Makefile`

**Web — create**
- `web-app/packages/ui/src/primitives/{alert-dialog,calendar,checkbox,switch,textarea}.tsx` (`popover` already exists)
- `web-app/packages/components/src/forms/{date-picker.tsx,date-picker.test.tsx}`
- `web-app/packages/api-client/src/query-provider.test.tsx`
- `web-app/packages/data-table/src/table/{row-selection.ts,row-selection.test.ts,data-table-bulk-bar.tsx,data-table-selection.test.tsx,data-table-cards.test.tsx}`, `web-app/packages/data-table/src/url-state/date-presets.{ts,test.ts}`, `web-app/packages/data-table/src/filters/filter-checkbox-group.{tsx,test.tsx}`
- `web-app/apps/web/src/app/(dashboard)/transactions/{page,loading}.tsx`
- `web-app/apps/web/src/components/transactions/`: `transactions-table-params.ts(+.test.ts)`, `use-transactions-table-state.ts(+.test.tsx)`, `use-categories.ts(+.test.tsx)`, `use-invalidate-transactions.ts`, `format.ts(+.test.ts)`, `use-transaction-columns.tsx`, `transaction-filters.tsx(+.test.tsx)`, `transaction-card.tsx`, `transactions-table.tsx(+.test.tsx)`, `transaction-form-dialog.tsx(+.test.tsx)`, `amount-input.ts(+.test.ts)`, `delete-transactions-dialog.tsx`, `bulk-category-dialog.tsx`, `category-picker.tsx`
- `web-app/apps/web/src/components/settings/data-settings.tsx(+.test.tsx)`

**Web — modify**
- `web-app/packages/ui/src/index.ts`, `web-app/packages/ui/package.json` (if a primitive needs a dependency)
- `web-app/packages/api-client/src/query-provider.tsx`
- `web-app/packages/data-table/src/table/{data-table-core.tsx,server-data-table.tsx}`, `web-app/packages/data-table/src/filters/date-filter-control.tsx`, `web-app/packages/data-table/src/labels.ts`, `web-app/packages/data-table/package.json` (exports)
- `web-app/apps/web/src/lib/hub-nav.ts`, `web-app/apps/web/src/app/(dashboard)/layout.tsx` (`SETTINGS_TABS` only)

**Docs** — Task 15.

---

## Task 1: Email is no longer unique (account)

Fixes `BUGS.md` "A re-registered or changed email locks the new account out with a 401". Spec §2.4.

**Files:**
- Modify: `server/app/modules/account/models.py:38`, `server/app/modules/account/repository.py` (remove `get_by_email`, docstring of `create_or_get`), `server/app/modules/account/service.py` (`resolve_user` docstring)
- Modify tests: `server/tests/integration/modules/account/test_repository.py`, `server/tests/integration/modules/account/test_service.py`, `server/tests/integration/modules/account/router/test_webhooks.py`
- Create: `server/alembic/versions/<autogen>_user_email_not_unique.py`
- Docs: `docs/BUGS.md`, `docs/TODO.md`, `docs/data-model/account.md`

**Interfaces:**
- Consumes: nothing new.
- Produces: `User.email` non-unique; `UserRepository.get_by_email` removed (nothing on the server looks a user up by email). Alembic head becomes this revision; Task 2's revision chains off it.

- [x] **Step 1: Invert the two tests that pin the bug, add JIT and webhook tests**

In `tests/integration/modules/account/test_repository.py` replace `test_create_duplicate_email_raises` and `test_genuine_conflict_raises_user_already_exists` with:

```python
    async def test_create_allows_an_email_another_clerk_id_holds(self, db_session, saved_user):
        """Clerk owns email uniqueness; clerk_id is the identity (data-model/account.md D3)."""
        user = await UserRepository.create(
            db_session,
            clerk_id="clerk_unique_999",
            email=saved_user.email,
        )
        assert user.id != saved_user.id
        assert user.email == saved_user.email
```

and in `TestCreateOrGetUser`:

```python
    async def test_held_email_with_new_clerk_id_creates_a_second_user(self, db_session, saved_user):
        """The lockout in BUGS.md: a stale row holding the email no longer blocks a new account."""
        user = await UserRepository.create_or_get(
            db_session,
            clerk_id="clerk_cog_new_account",
            email=saved_user.email,
        )
        assert user.clerk_id == "clerk_cog_new_account"
        assert user.id != saved_user.id
```

Delete `test_get_by_email_found` and `test_get_by_email_not_found` (the method goes in Step 3). Remove the now-unused `UserAlreadyExistsError` import if nothing else in the file uses it.

In `tests/integration/modules/account/test_service.py`, inside `TestJITProvisioning`, add:

```python
    @patch("app.modules.account.service.clerk_client.get_primary_email")
    @patch("app.modules.account.service.clerk_client.get_user")
    async def test_jit_provisions_onto_an_email_a_stale_row_holds(
        self, mock_get_user, mock_get_email, service, db_session, existing_user
    ):
        """BUGS.md reproduction: same email, new clerk_id → a new user, not UserAlreadyExistsError."""
        mock_get_user.return_value = self._make_clerk_user("clerk_jit_reregistered")
        mock_get_email.return_value = existing_user.email

        user = await service.resolve_user(db_session, "clerk_jit_reregistered")

        assert user.clerk_id == "clerk_jit_reregistered"
        assert user.id != existing_user.id
```

In `tests/integration/modules/account/router/test_webhooks.py`, append (uses the file's own `post`, `USER_DATA`, autouse `clerk_has_the_user`):

```python
async def test_user_created_with_an_email_a_stale_row_holds_persists(client, db_session):
    """A second Clerk account on a held email is provisioned, not rejected."""
    stale = User(clerk_id="user_stale", email="ada@e2e.test")
    db_session.add(stale)
    await db_session.flush()

    response = await post(client, "user.created", USER_DATA)

    assert response.status_code == 204
    user = await UserRepository.get_by_clerk_id(db_session, "user_e2e")
    assert user is not None
    assert user.email == "ada@e2e.test"
```

- [x] **Step 2: Run them — expect failures**

Run (from `server/`): `APP_ENV=test uv run pytest tests/integration/modules/account -v`
Expected: the four new tests FAIL (IntegrityError / UserAlreadyExistsError / non-204).

- [x] **Step 3: Drop the constraint in the model and the email lookup**

`app/modules/account/models.py`:

```python
    clerk_id: str = Field(unique=True, index=True)
    # Not unique: Clerk owns email uniqueness and clerk_id is the identity (data-model/account.md D3).
    email: str = Field(index=True)
```

`app/modules/account/repository.py`: delete `get_by_email`. Replace the `create_or_get` docstring with:

```python
        """Create a user, or return the existing one if a concurrent request won the race.

        Two requests JIT-provisioning the same clerk_id can race; the loser's
        insert hits the unique constraint on clerk_id. Roll back and return the
        winner's row rather than surfacing a conflict.

        Raises UserAlreadyExistsError when the re-fetch by clerk_id finds
        nothing: the IntegrityError was not that race. Email is not unique
        (Clerk owns it), so no email collision reaches here.
        """
```

`app/modules/account/service.py` `resolve_user` docstring, the `UserAlreadyExistsError` line becomes: `UserAlreadyExistsError: an IntegrityError that was not the clerk_id race — see UserRepository.create_or_get.`

- [x] **Step 4: Run the account tests — expect pass**

Run: `APP_ENV=test uv run pytest tests/integration/modules/account tests/unit/modules/account -v`
Expected: PASS.

- [x] **Step 5: Generate the migration and read it**

Run (from `server/`): `make migrate-create ENV=development MSG="user email not unique"`
Open the new file under `alembic/versions/`. `down_revision` must be `'0c7838405158'`. `upgrade()` must be exactly a drop of `ix_user_email` and a create of `ix_user_email` on `["email"]` with `unique=False`; `downgrade()` the reverse with `unique=True`. Remove anything else autogenerate added. Then:

Run: `make migrate ENV=development && APP_ENV=test uv run pytest tests/integration/database/test_migrations.py -v`
Expected: PASS (migrated schema equals the models).

- [x] **Step 6: Close the bug and the TODO, record the decision**

- `docs/BUGS.md`: delete the whole "A re-registered or changed email locks the new account out with a 401" entry.
- `docs/TODO.md`: delete the "Server — email uniqueness, before the first finance table" section.
- `docs/data-model/account.md`: in the sketch, `email` comment becomes `-- not unique: Clerk owns uniqueness; '<anonymous id>@anonymized.local' after erasure`; in §3 the `ix_user_email` row becomes `| ix_user_email | no | looking a row up by email by hand — nothing on the server does |`; add to §4:

```markdown
- **D3 — email is not unique (13 Oct 2026).** Clerk owns email uniqueness and `clerk_id` is the
  identity. A unique `email` let a stale row — a deletion or an email change whose webhook was
  missed — lock the next account with that address out with a 401. Nothing on the server looks a
  user up by email, so nothing depends on it being unique. Rejected: reclaiming the stale row in
  JIT when Clerk no longer has its `clerk_id`, which costs a Clerk call on a collision for a
  guarantee nothing reads.
```

Update the doc's status block: `Last updated: 13 Oct 2026`; the source-of-truth line names both revisions.

- [x] **Step 7: Commit**

```bash
git add server/app/modules/account server/tests/integration/modules/account server/alembic/versions docs/BUGS.md docs/TODO.md docs/data-model/account.md
git commit -m "fix(account): email is not unique; Clerk owns it, clerk_id is the identity"
```

---

## Task 2: The transaction module, its table and the category list

Spec §2, §2.2, §3.1, `GET /categories` from §3.2. Load `server-patterns` → `references/new-module.md` first.

**Files:**
- Create: `server/app/modules/transaction/{__init__,models,schemas,exceptions,repository,service,router}.py` (repository/service minimal here, grown in Tasks 3–6)
- Modify: `server/app/api/v1/api.py`, `server/app/main.py`, `server/alembic/env.py`, `server/pyproject.toml`, `server/app/core/config.py`
- Create: `server/alembic/versions/<autogen>_add_transaction.py`
- Test: `server/tests/unit/modules/transaction/{__init__,test_schemas}.py`, `server/tests/integration/modules/transaction/{__init__,conftest}.py`, `server/tests/integration/modules/transaction/router/{__init__,test_transactions}.py`

**Interfaces:**
- Consumes: `UserOwnedMixin`, `SoftDeleteMixin`, `UUIDPrimaryKeyMixin`, `BaseModel` from `app.models.base`; `CurrentUser` from `app.modules.account`.
- Produces:
  - `app.modules.transaction.models.Transaction` (fields per spec §2: `date: dt.date`, `merchant: str`, `amount: Decimal`, `description: Optional[str]`, `original_category: Optional[str]`, `category: str`, `confidence: float`, `is_recurring: bool`, `fingerprint: str`, plus mixins).
  - `app.modules.transaction.schemas`: `CATEGORIES: list[tuple[str, str]]`, `Category` (StrEnum), `category_label(category: str) -> str`, `CategoryResponse {value: Category, label: str}`.
  - Root exports: `router`, `CATEGORIES`, `Category`, `category_label`.
  - Route `GET /api/v1/transactions/categories`, `operation_id="listTransactionCategories"`.
  - Test fixtures in `tests/integration/modules/transaction/conftest.py`: `other_user`, `make_transaction` (Task 3 fills its body).

- [x] **Step 1: Write the failing schema test**

`tests/unit/modules/transaction/test_schemas.py`:

```python
"""The category list: one definition, slugs in display order."""

import pytest

from app.modules.transaction import CATEGORIES, Category, category_label

pytestmark = pytest.mark.unit

SLUGS = [
    "income", "salary", "transportation", "household_utilities", "tax_fines", "food_groceries",
    "food_delivery", "bars_restaurants", "atm", "insurances", "shopping", "education",
    "family_friends", "donations_charity", "healthcare_drug_stores", "leisure_entertainment",
    "media_electronics", "savings_investments", "travel_holidays", "miscellaneous",
]


def test_categories_are_the_twenty_slugs_in_display_order():
    assert [slug for slug, _ in CATEGORIES] == SLUGS


def test_enum_is_built_from_the_list():
    assert [c.value for c in Category] == SLUGS


def test_labels_are_the_product_names():
    assert category_label("food_groceries") == "Food & Groceries"
    assert category_label("atm") == "ATM"


def test_an_unknown_slug_labels_as_itself():
    assert category_label("no_such_slug") == "no_such_slug"
```

Create empty `tests/unit/modules/transaction/__init__.py`.

- [x] **Step 2: Run it — expect an import failure**

Run: `APP_ENV=test uv run pytest tests/unit/modules/transaction -v` → FAIL (`ModuleNotFoundError`).

- [x] **Step 3: Write `schemas.py` (categories part), `models.py`, `exceptions.py`**

`app/modules/transaction/schemas.py`:

```python
"""Transaction request/response schemas, and the category list."""

from enum import StrEnum

from pydantic import BaseModel, Field

# The category list: the only copy. Order is display order; slugs are what is
# stored and sent, labels what the web shows (served by GET /categories).
# Renaming a label touches nothing else. Renaming or removing a slug needs an
# UPDATE for the rows that hold it (docs/data-model/transaction.md).
CATEGORIES: list[tuple[str, str]] = [
    ("income", "Income"),
    ("salary", "Salary"),
    ("transportation", "Transportation"),
    ("household_utilities", "Household & Utilities"),
    ("tax_fines", "Tax & Fines"),
    ("food_groceries", "Food & Groceries"),
    ("food_delivery", "Food Delivery"),
    ("bars_restaurants", "Bars & Restaurants"),
    ("atm", "ATM"),
    ("insurances", "Insurances"),
    ("shopping", "Shopping"),
    ("education", "Education"),
    ("family_friends", "Family & Friends"),
    ("donations_charity", "Donations & Charity"),
    ("healthcare_drug_stores", "Healthcare & Drug Stores"),
    ("leisure_entertainment", "Leisure & Entertainment"),
    ("media_electronics", "Media & Electronics"),
    ("savings_investments", "Savings & Investments"),
    ("travel_holidays", "Travel & Holidays"),
    ("miscellaneous", "Miscellaneous"),
]

Category = StrEnum("Category", [(slug, slug) for slug, _ in CATEGORIES])

_LABELS = dict(CATEGORIES)


def category_label(category: str) -> str:
    """The display label for a slug; an unknown slug labels as itself."""
    return _LABELS.get(category, category)


class CategoryResponse(BaseModel):
    """One category, as the web lists it."""

    value: Category = Field(..., description="The category's slug, as stored and sent")
    label: str = Field(..., description="The category's display name")
```

`app/modules/transaction/models.py`:

```python
"""The transaction row."""

import datetime as dt
from decimal import Decimal
from typing import Optional

from sqlalchemy import CHAR, Column, Index
from sqlmodel import Field

from app.models.base import BaseModel, SoftDeleteMixin, UserOwnedMixin, UUIDPrimaryKeyMixin


class Transaction(BaseModel, UUIDPrimaryKeyMixin, UserOwnedMixin, SoftDeleteMixin, table=True):
    """One movement of money on one of the user's accounts.

    Deletes: one row or a batch is soft-deleted (hidden everywhere, kept);
    "delete all" and erasure (USER_ERASING) hard-delete every row the user
    owns. Nothing references a transaction, so removing rows breaks no FK.

    `category` is a Category slug, validated by the app only — the database
    knows no list, so changing the list needs no migration
    (docs/data-model/transaction.md). `fingerprint` is the sha256 of
    user|date|merchant|amount|description (service.fingerprint), recomputed
    on every edit; it is not unique.
    """

    __table_args__ = (
        Index("ix_transaction_user_id_date", "user_id", "date"),
        Index("ix_transaction_user_id_fingerprint", "user_id", "fingerprint"),
    )

    date: dt.date
    merchant: str = Field(max_length=255)
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    description: Optional[str] = Field(default=None, max_length=1000)
    original_category: Optional[str] = Field(default=None, max_length=255)
    category: str = Field(max_length=64)
    confidence: float
    is_recurring: bool = Field(default=False)
    fingerprint: str = Field(sa_column=Column(CHAR(64), nullable=False))
```

`app/modules/transaction/exceptions.py`:

```python
"""Transaction module domain exceptions."""

from app.exceptions.base import ConflictError, NotFoundError


class TransactionNotFoundError(NotFoundError):
    """A transaction is missing, soft-deleted, or another user's."""

    error_code = "TRANSACTION_NOT_FOUND"


class DuplicateTransactionError(ConflictError):
    """A manual add matches an active transaction's fingerprint."""

    error_code = "DUPLICATE_TRANSACTION"
```

- [x] **Step 4: The categories route, an empty repository and service, the root**

`app/modules/transaction/repository.py`:

```python
"""Transaction repository: every query, each one scoped by user_id."""


class TransactionRepository:
    """Repository for transaction database operations."""


transaction_repository = TransactionRepository()
```

`app/modules/transaction/service.py`:

```python
"""Transaction service."""

from app.modules.transaction.schemas import CATEGORIES, CategoryResponse


class TransactionService:
    """Orchestrates transaction operations."""

    @staticmethod
    def list_categories() -> list[CategoryResponse]:
        """Every category, in display order."""
        return [CategoryResponse(value=slug, label=label) for slug, label in CATEGORIES]


transaction_service = TransactionService()
```

`app/modules/transaction/router.py`:

```python
"""Transaction routes under /transactions. Named paths are declared before /{transaction_id}."""

from typing import List

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.limiter import limiter
from app.modules.account import CurrentUser
from app.modules.transaction.schemas import CategoryResponse
from app.modules.transaction.service import transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get(
    "/categories",
    operation_id="listTransactionCategories",
    response_model=List[CategoryResponse],
    summary="List the categories",
    description="Every category a transaction can carry, in display order.",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTIONS[0])
async def list_categories(request: Request, user: CurrentUser) -> List[CategoryResponse]:
    """The category list; the web's only source of category labels."""
    return transaction_service.list_categories()
```

`app/modules/transaction/__init__.py`:

```python
"""Transaction — the user's transactions and the category list.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).
"""

from app.modules.transaction.exceptions import (  # noqa: I001
    DuplicateTransactionError,
    TransactionNotFoundError,
)
from app.modules.transaction.router import router
from app.modules.transaction.schemas import CATEGORIES, Category, CategoryResponse, category_label
from app.modules.transaction.service import transaction_service

__all__ = [
    "CATEGORIES",
    "Category",
    "CategoryResponse",
    "DuplicateTransactionError",
    "TransactionNotFoundError",
    "category_label",
    "router",
    "transaction_service",
]
```

`app/core/config.py`, in `RateLimitEndpointSettings` after `MESSAGES`:

```python
    TRANSACTIONS: List[str] = Field(default_factory=lambda: ["120 per minute"])
```

- [x] **Step 5: Run the schema test — expect pass; then the module-contract tests — expect fail**

Run: `APP_ENV=test uv run pytest tests/unit/modules/transaction -v` → PASS.
Run: `APP_ENV=test uv run pytest tests/unit/test_module_contracts.py tests/unit/models/test_owned_tables.py -v` → FAIL naming `transaction` (no R1 contract, not in R6, not imported by main/alembic).

- [x] **Step 6: Wire it (four edits)**

`app/api/v1/api.py`:

```python
from app.modules import account, conversation, transaction

api_router = APIRouter()
api_router.include_router(account.router)
api_router.include_router(conversation.router)
api_router.include_router(transaction.router)
```

`app/main.py`, beside the other module imports:

```python
from app.modules import transaction as _transaction
```

`alembic/env.py`, beside the other models imports:

```python
import app.modules.transaction.models
```

`pyproject.toml` `[tool.importlinter]`:

```toml
[[tool.importlinter.contracts]]
name = "R6: modules form a DAG — a module imports only those listed below it"
type = "layers"
layers = [
    "app.modules.conversation | app.modules.transaction",
    "app.modules.account",
]
```

`forbidden_modules` of the `account` contract becomes `["app.modules.conversation.*", "app.modules.transaction.*"]`; of the `conversation` contract `["app.modules.account.*", "app.modules.transaction.*"]`; and add:

```toml
[[tool.importlinter.contracts]]
name = "R1: transaction reaches other modules only through their package roots"
type = "forbidden"
source_modules = ["app.modules.transaction"]
forbidden_modules = ["app.modules.account.*", "app.modules.conversation.*"]
allow_indirect_imports = true
```

- [x] **Step 7: Route test and fixtures**

`tests/integration/modules/transaction/conftest.py`:

```python
"""Fixtures for the transaction module's integration tests."""

import datetime as dt
from decimal import Decimal

import pytest
import pytest_asyncio

from app.modules.account.models import User


@pytest_asyncio.fixture
async def other_user(db_session):
    """A second user, to prove another user's rows answer 404."""
    user = User(clerk_id="user_other_txn", email="other_txn@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def make_transaction(db_session):
    """Insert a transaction for a user; every field overridable. Filled in by Task 3."""

    async def _make(user, **overrides):
        raise NotImplementedError("make_transaction is implemented in Task 3")

    return _make
```

Create empty `__init__.py` in `tests/integration/modules/transaction/` and `.../router/`. `tests/integration/modules/transaction/router/test_transactions.py`:

```python
"""Transaction routes against a real database."""

import pytest

from app.modules.transaction import CATEGORIES

pytestmark = pytest.mark.integration

BASE = "/api/v1/transactions"


class TestListCategories:
    async def test_unauthenticated_returns_401(self, client):
        assert (await client.get(f"{BASE}/categories")).status_code == 401

    async def test_lists_every_category_in_display_order(self, authenticated_client):
        response = await authenticated_client.get(f"{BASE}/categories")
        assert response.status_code == 200
        assert response.json() == [{"value": slug, "label": label} for slug, label in CATEGORIES]
```

- [x] **Step 8: Migration**

Run (from `server/`): `make migrate-create ENV=development MSG="add transaction"`. Read the file: `down_revision` is Task 1's revision; `upgrade()` creates `transaction` with the columns of spec §2 (`date` DATE, `amount` NUMERIC(12,2), `fingerprint` CHAR(64), `confidence` FLOAT, `user_id` FK `user.id`), indexes `ix_transaction_user_id_date`, `ix_transaction_user_id_fingerprint`, `ix_transaction_user_id`, `ix_transaction_created_at`, `ix_transaction_deleted_at`; nothing else. Then `make migrate ENV=development`.

- [x] **Step 9: Run everything that gates a module**

Run: `APP_ENV=test uv run pytest tests/unit tests/integration/modules/transaction tests/integration/database/test_migrations.py -v` → PASS.
Run (repo root): `make check-server` → PASS (ruff + lint-imports).
Run (repo root): `make gen-contract` — `listTransactionCategories` appears in `server/openapi.json`; `web-app/packages/api-client/src/generated/endpoints/transactions/` and `types/category.ts`, `types/categoryResponse.ts` are created.

- [x] **Step 10: Commit**

```bash
git add server web-app/packages/api-client/src/generated
git commit -m "feat(transactions): the transaction module, its table and the category list"
```

---

## Task 3: Fingerprint, create (with the duplicate check), update, delete

Spec §2.3, §3.2 (`POST`, `PATCH /{id}`, `DELETE /{id}`), §3.2.2, §3.3. Review Focus 1 and 5.

**Files:**
- Modify: `server/app/modules/transaction/{schemas,repository,service,router,__init__}.py`, `server/tests/integration/modules/transaction/conftest.py` (`make_transaction` body — a fixture this task created, not an existing one)
- Create: `server/app/modules/transaction/dependencies.py`
- Test: `server/tests/unit/modules/transaction/test_service.py`, `server/tests/integration/modules/transaction/test_service.py`, `server/tests/integration/modules/transaction/router/test_transactions.py`

**Interfaces:**
- Consumes: Task 2's `Transaction`, `Category`, exceptions.
- Produces:
  - `service.fingerprint(user_id: uuid.UUID, date: dt.date, merchant: str, amount: Decimal, description: Optional[str]) -> str`
  - schemas `TransactionCreate`, `TransactionUpdate`, `TransactionResponse`, `TransactionImport` (fields: `date, merchant, amount, description, category: Category, confidence: float, is_recurring, original_category`)
  - `transaction_service.create(session, user_id, body: TransactionCreate) -> Transaction` (raises `DuplicateTransactionError` with context `existing_transaction_id=str`)
  - `transaction_service.update(session, transaction: Transaction, body: TransactionUpdate) -> Transaction`
  - `transaction_service.soft_delete(session, transaction: Transaction) -> None`
  - `transaction_service.get_for_user(session, user_id, transaction_id) -> Optional[Transaction]`
  - `transaction_service.import_many(session, user_id, rows: list[TransactionImport]) -> int`
  - repository: `get_active_for_user`, `find_active_by_fingerprint`, `add`, `add_many`, `save`
  - `dependencies.UserTransaction` (Annotated) and `get_user_transaction`
  - routes `createTransaction` (201), `updateTransaction`, `deleteTransaction` (204)

- [x] **Step 1: Failing unit tests for the fingerprint**

`tests/unit/modules/transaction/test_service.py`:

```python
"""The fingerprint recipe (spec §2.3), pinned to its input string."""

import datetime as dt
import hashlib
import uuid
from decimal import Decimal

import pytest

from app.modules.transaction.service import fingerprint

pytestmark = pytest.mark.unit

USER = uuid.UUID("0199a8b0-0000-7000-8000-000000000001")


def _sha(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_recipe():
    expected = _sha(f"{USER}|2026-03-03|späti|-4.50|late snack")
    assert fingerprint(USER, dt.date(2026, 3, 3), "Späti", Decimal("-4.5"), "Late snack") == expected


def test_merchant_and_description_ignore_case_and_padding():
    a = fingerprint(USER, dt.date(2026, 3, 3), "  SPÄTI ", Decimal("-4.50"), "  LATE snack ")
    b = fingerprint(USER, dt.date(2026, 3, 3), "späti", Decimal("-4.5"), "late snack")
    assert a == b


def test_no_description_is_the_empty_string():
    expected = _sha(f"{USER}|2026-03-03|rewe|-12.70|")
    assert fingerprint(USER, dt.date(2026, 3, 3), "REWE", Decimal("-12.7"), None) == expected


def test_negative_zero_is_zero():
    assert fingerprint(USER, dt.date(2026, 3, 3), "x", Decimal("-0.00"), None) == fingerprint(
        USER, dt.date(2026, 3, 3), "x", Decimal("0"), None
    )


def test_amount_is_never_a_float():
    expected = _sha(f"{USER}|2026-03-03|x|0.10|")
    assert fingerprint(USER, dt.date(2026, 3, 3), "x", Decimal("0.1"), None) == expected
```

Run: `APP_ENV=test uv run pytest tests/unit/modules/transaction/test_service.py -v` → FAIL (ImportError).

- [x] **Step 2: Implement the fingerprint**

In `service.py` add (imports at the top of the file):

```python
import datetime as dt
import hashlib
import uuid
from decimal import Decimal
from typing import Optional

_CENT = Decimal("0.01")


def fingerprint(
    user_id: uuid.UUID, date: dt.date, merchant: str, amount: Decimal, description: Optional[str]
) -> str:
    """sha256 of user|date|merchant|amount|description — the duplicate key (docs/data-model/transaction.md).

    Merchant and description are stripped and casefolded; the amount is the
    Decimal at two places, never a float, and -0.00 is 0.00. Step 4's import
    uses the same function, so the two can never disagree.
    """
    cents = amount.quantize(_CENT)
    if cents == 0:
        cents = Decimal("0.00")
    raw = f"{user_id}|{date:%Y-%m-%d}|{merchant.strip().casefold()}|{cents:.2f}|{(description or '').strip().casefold()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

Run the unit tests → PASS.

- [x] **Step 3: Schemas**

Append to `schemas.py` (add `import datetime as dt`, `import uuid`, `from datetime import datetime`, `from decimal import Decimal`, `from typing import Annotated, Optional`, `from pydantic import StringConstraints, field_validator, model_validator` at the top):

```python
Merchant = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Amount = Annotated[Decimal, Field(max_digits=12, decimal_places=2, allow_inf_nan=False)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    return value or None


class TransactionCreate(BaseModel):
    """A transaction added by hand. Confidence is 1; no original category."""

    date: dt.date = Field(..., description="The day the transaction happened")
    merchant: Merchant = Field(..., description="Who was paid, or who paid")
    amount: Amount = Field(..., description="Money out is negative, money in positive; a decimal string")
    description: Optional[Description] = Field(None, description="Free text; blank is stored as null")
    category: Category = Field(..., description="The category slug")
    is_recurring: bool = Field(False, description="Whether it recurs")
    allow_duplicate: bool = Field(
        False, description="Add even when an active transaction has the same date, merchant, amount and description"
    )

    _description = field_validator("description")(_blank_to_none)


class TransactionUpdate(BaseModel):
    """A partial edit. An omitted field is untouched; `description: null` clears it."""

    date: Optional[dt.date] = Field(None, description="The day the transaction happened")
    merchant: Optional[Merchant] = Field(None, description="Who was paid, or who paid")
    amount: Optional[Amount] = Field(None, description="A decimal string")
    description: Optional[Description] = Field(None, description="Free text; null or blank clears it")
    category: Optional[Category] = Field(None, description="The category slug")
    is_recurring: Optional[bool] = Field(None, description="Whether it recurs")

    _description = field_validator("description")(_blank_to_none)

    @model_validator(mode="after")
    def _required_fields_are_not_null(self) -> "TransactionUpdate":
        for name in ("date", "merchant", "amount", "category", "is_recurring"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class TransactionImport(BaseModel):
    """A row written by the seed (and by step 4's import): confidence and original category are its own."""

    date: dt.date
    merchant: Merchant
    amount: Amount
    description: Optional[Description] = None
    category: Category
    confidence: float = Field(..., ge=0, le=1)
    is_recurring: bool = False
    original_category: Optional[Annotated[str, StringConstraints(max_length=255)]] = None


class TransactionResponse(BaseModel):
    """A transaction as the API returns it."""

    id: uuid.UUID = Field(..., description="The transaction id")
    date: dt.date = Field(..., description="The day it happened")
    merchant: str = Field(..., description="Who was paid, or who paid")
    amount: Decimal = Field(..., description="Money out negative, money in positive; a decimal string")
    description: Optional[str] = Field(None, description="Free text")
    original_category: Optional[str] = Field(None, description="The bank's category, as imported")
    category: Category = Field(..., description="The category slug")
    confidence: float = Field(..., description="How sure the categoriser was, 0 to 1; 1 for a manual entry or edit")
    is_recurring: bool = Field(..., description="Whether it recurs")
    created_at: datetime = Field(..., description="When the row was created")
    updated_at: datetime = Field(..., description="When the row was last changed")

    model_config = {"from_attributes": True}
```

(`TransactionResponse.category` typed `Category`: a row whose slug was later removed from the list would fail serialisation — Task 7's seed maps unknown slugs to `miscellaneous`, and renaming a slug ships with its UPDATE, so a stored slug is always in the enum.)

- [x] **Step 4: Fill `make_transaction`, then failing integration tests for the service**

Replace the `make_transaction` fixture in `tests/integration/modules/transaction/conftest.py`:

```python
@pytest.fixture
def make_transaction(db_session):
    """Insert a transaction for a user; every field overridable."""

    async def _make(user, **overrides):
        fields = {
            "date": dt.date(2026, 3, 3),
            "merchant": "Späti",
            "amount": Decimal("-4.50"),
            "description": None,
            "category": "food_groceries",
            "confidence": 0.8,
            "is_recurring": False,
            "original_category": None,
        } | overrides
        txn = Transaction(
            user_id=user.id,
            fingerprint=fingerprint(user.id, fields["date"], fields["merchant"], fields["amount"], fields["description"]),
            **fields,
        )
        db_session.add(txn)
        await db_session.flush()
        await db_session.refresh(txn)
        return txn

    return _make
```

and add `from app.modules.transaction.models import Transaction` and `from app.modules.transaction.service import fingerprint` to the conftest's top-level imports.

`tests/integration/modules/transaction/test_service.py`:

```python
"""TransactionService against a real database."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.transaction import DuplicateTransactionError
from app.modules.transaction.schemas import TransactionCreate, TransactionImport, TransactionUpdate
from app.modules.transaction.service import fingerprint, transaction_service

pytestmark = pytest.mark.integration


def _create(**overrides) -> TransactionCreate:
    return TransactionCreate(
        **(
            {
                "date": dt.date(2026, 3, 3),
                "merchant": "Späti",
                "amount": "-4.50",
                "category": "food_groceries",
            }
            | overrides
        )
    )


class TestCreate:
    async def test_sets_confidence_one_and_the_fingerprint(self, db_session, test_user):
        txn = await transaction_service.create(db_session, test_user.id, _create(description="Snack"))
        assert txn.confidence == 1.0
        assert txn.original_category is None
        assert txn.fingerprint == fingerprint(test_user.id, dt.date(2026, 3, 3), "Späti", Decimal("-4.50"), "Snack")

    async def test_a_duplicate_raises_with_the_existing_id(self, db_session, test_user, make_transaction):
        existing = await make_transaction(test_user)
        with pytest.raises(DuplicateTransactionError) as caught:
            await transaction_service.create(db_session, test_user.id, _create(merchant="  SPÄTI "))
        assert caught.value.context == {"existing_transaction_id": str(existing.id)}

    async def test_allow_duplicate_adds_it(self, db_session, test_user, make_transaction):
        existing = await make_transaction(test_user)
        txn = await transaction_service.create(db_session, test_user.id, _create(allow_duplicate=True))
        assert txn.id != existing.id
        assert txn.fingerprint == existing.fingerprint

    async def test_a_soft_deleted_twin_is_no_duplicate(self, db_session, test_user, make_transaction):
        twin = await make_transaction(test_user)
        await transaction_service.soft_delete(db_session, twin)
        txn = await transaction_service.create(db_session, test_user.id, _create())
        assert txn.id != twin.id

    async def test_another_users_twin_is_no_duplicate(self, db_session, test_user, other_user, make_transaction):
        await make_transaction(other_user)
        txn = await transaction_service.create(db_session, test_user.id, _create())
        assert txn.user_id == test_user.id


class TestUpdate:
    async def test_recomputes_the_fingerprint_and_sets_confidence_one(self, db_session, test_user, make_transaction):
        txn = await make_transaction(test_user, confidence=0.4)
        updated = await transaction_service.update(db_session, txn, TransactionUpdate(merchant="REWE"))
        assert updated.merchant == "REWE"
        assert updated.confidence == 1.0
        assert updated.fingerprint == fingerprint(test_user.id, txn.date, "REWE", txn.amount, None)

    async def test_category_only_edit_keeps_the_fingerprint(self, db_session, test_user, make_transaction):
        txn = await make_transaction(test_user)
        before = txn.fingerprint
        updated = await transaction_service.update(db_session, txn, TransactionUpdate(category="shopping"))
        assert updated.fingerprint == before

    async def test_null_description_clears_it(self, db_session, test_user, make_transaction):
        txn = await make_transaction(test_user, description="Old")
        updated = await transaction_service.update(
            db_session, txn, TransactionUpdate.model_validate({"description": None})
        )
        assert updated.description is None

    async def test_empty_patch_changes_nothing(self, db_session, test_user, make_transaction):
        """Review Focus 1: Save with no change sends {}."""
        txn = await make_transaction(test_user, confidence=0.4)
        updated_at = txn.updated_at
        updated = await transaction_service.update(db_session, txn, TransactionUpdate())
        assert updated.confidence == 0.4
        assert updated.updated_at == updated_at


class TestImportMany:
    async def test_keeps_confidence_and_original_category(self, db_session, test_user):
        rows = [
            TransactionImport(
                date=dt.date(2026, 3, 1), merchant="REWE", amount="-12.70", category="food_groceries",
                confidence=0.9, original_category="Presentment",
            ),
            TransactionImport(
                date=dt.date(2026, 3, 2), merchant="Employer GmbH", amount="2400.00", category="salary",
                confidence=1.0, is_recurring=True,
            ),
        ]
        assert await transaction_service.import_many(db_session, test_user.id, rows) == 2
```

Run: `APP_ENV=test uv run pytest tests/integration/modules/transaction/test_service.py -v` → FAIL (methods missing).

- [x] **Step 5: Repository and service methods**

`repository.py`:

```python
"""Transaction repository: every query, each one scoped by user_id."""

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.modules.transaction.models import Transaction


class TransactionRepository:
    """Repository for transaction database operations."""

    @staticmethod
    async def get_active_for_user(
        session: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> Optional[Transaction]:
        """One active transaction of this user's, or None (missing, deleted or another user's)."""
        statement = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        )
        return (await session.execute(statement)).scalar_one_or_none()

    @staticmethod
    async def find_active_by_fingerprint(
        session: AsyncSession, user_id: uuid.UUID, fingerprint: str
    ) -> Optional[Transaction]:
        """The oldest active transaction of this user's with this fingerprint, or None."""
        statement = (
            select(Transaction)
            .where(
                Transaction.user_id == user_id,
                Transaction.fingerprint == fingerprint,
                Transaction.deleted_at.is_(None),
            )
            .order_by(Transaction.created_at)
            .limit(1)
        )
        return (await session.execute(statement)).scalar_one_or_none()

    @staticmethod
    async def add(session: AsyncSession, transaction: Transaction) -> Transaction:
        """Insert one transaction and flush."""
        session.add(transaction)
        await session.flush()
        await session.refresh(transaction)
        logger.info("transaction_created", transaction_id=transaction.id, user_id=transaction.user_id)
        return transaction

    @staticmethod
    async def add_many(session: AsyncSession, transactions: list[Transaction]) -> int:
        """Insert many transactions with one flush (batched into multi-row INSERTs by the driver)."""
        session.add_all(transactions)
        await session.flush()
        return len(transactions)

    @staticmethod
    async def save(session: AsyncSession, transaction: Transaction) -> Transaction:
        """Flush changes made to a loaded transaction."""
        session.add(transaction)
        await session.flush()
        await session.refresh(transaction)
        return transaction


transaction_repository = TransactionRepository()
```

`service.py` — add to the class (keep `fingerprint` and `list_categories`; imports at top: `from sqlalchemy.ext.asyncio import AsyncSession`, `from app.core.logging import logger`, the models, schemas, exceptions, repository):

```python
    @staticmethod
    async def get_for_user(
        session: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> Optional[Transaction]:
        """One active transaction of this user's, or None."""
        return await transaction_repository.get_active_for_user(session, user_id, transaction_id)

    @staticmethod
    async def create(session: AsyncSession, user_id: uuid.UUID, body: TransactionCreate) -> Transaction:
        """Add a transaction by hand. Raises DuplicateTransactionError on an active twin, unless allowed."""
        key = fingerprint(user_id, body.date, body.merchant, body.amount, body.description)
        if not body.allow_duplicate:
            existing = await transaction_repository.find_active_by_fingerprint(session, user_id, key)
            if existing:
                # The id only: the caller already holds the fields that matched, and
                # merchant text would otherwise reach the error log.
                raise DuplicateTransactionError(
                    "A transaction with the same date, merchant, amount and description exists",
                    existing_transaction_id=str(existing.id),
                )
        transaction = Transaction(
            user_id=user_id,
            date=body.date,
            merchant=body.merchant,
            amount=body.amount,
            description=body.description,
            category=body.category,
            confidence=1.0,
            is_recurring=body.is_recurring,
            fingerprint=key,
        )
        return await transaction_repository.add(session, transaction)

    @staticmethod
    async def update(session: AsyncSession, transaction: Transaction, body: TransactionUpdate) -> Transaction:
        """Apply a partial edit. An empty edit changes nothing; any edit sets confidence to 1."""
        changes = {name: getattr(body, name) for name in body.model_fields_set}
        if not changes:
            return transaction
        for name, value in changes.items():
            setattr(transaction, name, value)
        transaction.confidence = 1.0
        transaction.fingerprint = fingerprint(
            transaction.user_id, transaction.date, transaction.merchant, transaction.amount, transaction.description
        )
        logger.info("transaction_updated", transaction_id=transaction.id, fields=sorted(changes))
        return await transaction_repository.save(session, transaction)

    @staticmethod
    async def soft_delete(session: AsyncSession, transaction: Transaction) -> None:
        """Hide one transaction from every list; the row stays."""
        transaction.soft_delete()
        await transaction_repository.save(session, transaction)
        logger.info("transaction_soft_deleted", transaction_id=transaction.id)

    @staticmethod
    async def import_many(session: AsyncSession, user_id: uuid.UUID, rows: list[TransactionImport]) -> int:
        """Insert rows that carry their own confidence and original category (the seed; step 4's import)."""
        transactions = [
            Transaction(
                user_id=user_id,
                fingerprint=fingerprint(user_id, row.date, row.merchant, row.amount, row.description),
                **row.model_dump(),
            )
            for row in rows
        ]
        count = await transaction_repository.add_many(session, transactions)
        logger.info("transactions_imported", user_id=user_id, count=count)
        return count
```

Run the service tests → PASS.

- [x] **Step 6: Ownership dependency and the three routes — failing route tests first**

Append to `router/test_transactions.py` (add `import uuid` and `from uuid_utils.compat import uuid7` at the top):

```python
VALID = {"date": "2026-03-03", "merchant": "Späti", "amount": "-4.50", "category": "food_groceries"}


class TestCreate:
    async def test_creates_and_returns_201(self, authenticated_client):
        response = await authenticated_client.post(BASE, json=VALID | {"description": "  "})
        assert response.status_code == 201
        body = response.json()
        assert body["amount"] == "-4.50"  # a string on the wire
        assert body["confidence"] == 1.0
        assert body["description"] is None
        assert uuid.UUID(body["id"]).version == 7
        assert "fingerprint" not in body and "user_id" not in body

    async def test_accepts_a_json_number_amount(self, authenticated_client):
        response = await authenticated_client.post(BASE, json=VALID | {"amount": 12.5})
        assert response.status_code == 201
        assert response.json()["amount"] == "12.50"

    @pytest.mark.parametrize(
        "patch",
        [
            {"amount": "1.005"},
            {"amount": "1234567890123"},
            {"merchant": "   "},
            {"merchant": "x" * 256},
            {"description": "x" * 1001},
            {"category": "no_such_slug"},
            {"date": "2026-02-30"},
        ],
    )
    async def test_invalid_input_is_422(self, authenticated_client, patch):
        assert (await authenticated_client.post(BASE, json=VALID | patch)).status_code == 422

    async def test_a_duplicate_is_409_with_the_existing_id(self, authenticated_client, test_user, make_transaction):
        existing = await make_transaction(test_user)
        response = await authenticated_client.post(BASE, json=VALID)
        assert response.status_code == 409
        assert response.json()["error"] == "DUPLICATE_TRANSACTION"
        assert response.json()["details"] == {"existing_transaction_id": str(existing.id)}

    async def test_allow_duplicate_is_201(self, authenticated_client, test_user, make_transaction):
        await make_transaction(test_user)
        assert (await authenticated_client.post(BASE, json=VALID | {"allow_duplicate": True})).status_code == 201


class TestUpdate:
    async def test_partial_edit(self, authenticated_client, test_user, make_transaction):
        txn = await make_transaction(test_user, description="Old", confidence=0.4)
        response = await authenticated_client.patch(f"{BASE}/{txn.id}", json={"description": None})
        assert response.status_code == 200
        assert response.json()["description"] is None
        assert response.json()["merchant"] == "Späti"
        assert response.json()["confidence"] == 1.0

    async def test_null_on_a_required_field_is_422(self, authenticated_client, test_user, make_transaction):
        txn = await make_transaction(test_user)
        assert (await authenticated_client.patch(f"{BASE}/{txn.id}", json={"merchant": None})).status_code == 422

    async def test_another_users_transaction_is_404(self, authenticated_client, other_user, make_transaction):
        txn = await make_transaction(other_user)
        response = await authenticated_client.patch(f"{BASE}/{txn.id}", json={"merchant": "x"})
        assert response.status_code == 404
        assert response.json()["error"] == "TRANSACTION_NOT_FOUND"

    async def test_a_missing_id_is_404(self, authenticated_client):
        assert (await authenticated_client.patch(f"{BASE}/{uuid7()}", json={"merchant": "x"})).status_code == 404


class TestDelete:
    async def test_soft_deletes_and_answers_204(self, authenticated_client, test_user, make_transaction, db_session):
        txn = await make_transaction(test_user)
        assert (await authenticated_client.delete(f"{BASE}/{txn.id}")).status_code == 204
        await db_session.refresh(txn)
        assert txn.deleted_at is not None
        assert (await authenticated_client.delete(f"{BASE}/{txn.id}")).status_code == 404

    async def test_another_users_transaction_is_404(self, authenticated_client, other_user, make_transaction):
        txn = await make_transaction(other_user)
        assert (await authenticated_client.delete(f"{BASE}/{txn.id}")).status_code == 404
```

Run: `APP_ENV=test uv run pytest tests/integration/modules/transaction/router -v` → the new classes FAIL (405/404).

`dependencies.py`:

```python
"""Transaction ownership dependency for FastAPI endpoints."""

import uuid
from typing import Annotated

from fastapi import Depends, Path

from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.transaction.exceptions import TransactionNotFoundError
from app.modules.transaction.models import Transaction
from app.modules.transaction.service import transaction_service


async def get_user_transaction(
    user: CurrentUser,
    db_session: DbSession,
    transaction_id: uuid.UUID = Path(...),
) -> Transaction:
    """The caller's active transaction. Missing, deleted or another user's all answer 404 alike."""
    transaction = await transaction_service.get_for_user(db_session, user.id, transaction_id)
    if not transaction:
        raise TransactionNotFoundError(f"Transaction {transaction_id} not found", transaction_id=str(transaction_id))
    return transaction


UserTransaction = Annotated[Transaction, Depends(get_user_transaction)]
```

Routes, appended to `router.py` **after** `/categories` (Tasks 4 and 5 add `""` GET and `/batch` routes *above* the `/{transaction_id}` ones — keep `/{transaction_id}` routes last in the file):

```python
@router.post(
    "",
    operation_id="createTransaction",
    response_model=TransactionResponse,
    status_code=201,
    summary="Add a transaction",
    description="Add a transaction by hand. 409 DUPLICATE_TRANSACTION when an active one has the same "
    "date, merchant, amount and description, unless allow_duplicate is true.",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTIONS[0])
async def create_transaction(
    request: Request, body: TransactionCreate, db_session: DbSession, user: CurrentUser
) -> TransactionResponse:
    """Add a transaction by hand."""
    transaction = await transaction_service.create(db_session, user.id, body)
    return TransactionResponse.model_validate(transaction)


@router.patch(
    "/{transaction_id}",
    operation_id="updateTransaction",
    response_model=TransactionResponse,
    summary="Edit a transaction",
    description="Change some fields of a transaction. Omitted fields are untouched; description: null clears it.",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTIONS[0])
async def update_transaction(
    request: Request, body: TransactionUpdate, transaction: UserTransaction, db_session: DbSession
) -> TransactionResponse:
    """Edit one transaction."""
    return TransactionResponse.model_validate(await transaction_service.update(db_session, transaction, body))


@router.delete(
    "/{transaction_id}",
    operation_id="deleteTransaction",
    status_code=204,
    summary="Delete a transaction",
    description="Hide a transaction from every list and analytic. The row is kept.",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTIONS[0])
async def delete_transaction(request: Request, transaction: UserTransaction, db_session: DbSession) -> None:
    """Soft-delete one transaction."""
    await transaction_service.soft_delete(db_session, transaction)
```

Add `DbSession`, `TransactionCreate`, `TransactionUpdate`, `TransactionResponse`, `UserTransaction` imports. Export `TransactionImport`, `TransactionResponse`, `UserTransaction`, `get_user_transaction` from `__init__.py`.

- [x] **Step 7: Run, gate, regenerate, commit**

Run: `APP_ENV=test uv run pytest tests/unit/modules/transaction tests/integration/modules/transaction tests/unit/api -v` → PASS.
Run (repo root): `make check-server && make gen-contract`.

```bash
git add server web-app/packages/api-client/src/generated
git commit -m "feat(transactions): add, edit and delete, with a fingerprint and the manual duplicate check"
```

---

## Task 4: The list — filters, search, ordering, pagination

Spec §3.2.1. Review Focus 2 and 4.

**Files:**
- Modify: `server/app/modules/transaction/{schemas,repository,service,router,__init__}.py`
- Test: `server/tests/integration/modules/transaction/test_repository.py`, `server/tests/integration/modules/transaction/router/test_transactions.py`

**Interfaces:**
- Consumes: Task 3's `make_transaction`, `TransactionResponse`.
- Produces:
  - schemas: `TransactionOrdering = Literal["date", "-date", "amount", "-amount", "merchant", "-merchant"]`, `TransactionFilters` (pydantic: `date_from, date_to: Optional[dt.date]`, `category: Optional[list[Category]]`, `amount_min, amount_max: Optional[Decimal]`, `is_recurring: Optional[bool]`), `TransactionListResponse {items, total, offset, limit}`
  - `transaction_repository.list_active_for_user(session, user_id, filters, ordering, search, offset, limit) -> tuple[list[Transaction], int]`
  - `transaction_service.list(...)` same signature
  - route `GET /api/v1/transactions`, `operation_id="listTransactions"`; generated web names `useListTransactions`, `ListTransactionsParams`, `ListTransactionsOrdering`

- [x] **Step 1: Failing repository tests**

`tests/integration/modules/transaction/test_repository.py`:

```python
"""The list query: every filter, search, ordering and paging."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.transaction.repository import transaction_repository
from app.modules.transaction.schemas import TransactionFilters

pytestmark = pytest.mark.integration


async def _list(db_session, user, filters=None, ordering="-date", search=None, offset=0, limit=20):
    return await transaction_repository.list_active_for_user(
        db_session, user.id, filters or TransactionFilters(), ordering, search, offset, limit
    )


@pytest.fixture
async def rows(test_user, make_transaction):
    """Five distinguishable rows for test_user."""
    return {
        "rewe": await make_transaction(test_user, date=dt.date(2026, 1, 5), merchant="REWE", amount=Decimal("-30.00"), category="food_groceries"),
        "salary": await make_transaction(test_user, date=dt.date(2026, 1, 27), merchant="Employer GmbH", amount=Decimal("2400.00"), category="salary", is_recurring=True),
        "rent": await make_transaction(test_user, date=dt.date(2026, 2, 1), merchant="Landlord", amount=Decimal("-900.00"), category="household_utilities", is_recurring=True),
        "bar": await make_transaction(test_user, date=dt.date(2026, 2, 14), merchant="Bar 100%_off", amount=Decimal("-18.50"), category="bars_restaurants"),
        "spati": await make_transaction(test_user, date=dt.date(2026, 2, 28), merchant="Späti", amount=Decimal("-4.50"), category="food_groceries"),
    }


def _merchants(items):
    return [t.merchant for t in items]


async def test_default_is_newest_first_with_total(db_session, test_user, rows):
    items, total = await _list(db_session, test_user)
    assert total == 5
    assert _merchants(items) == ["Späti", "Bar 100%_off", "Landlord", "Employer GmbH", "REWE"]


async def test_date_bounds_are_inclusive(db_session, test_user, rows):
    f = TransactionFilters(date_from=dt.date(2026, 1, 27), date_to=dt.date(2026, 2, 14))
    items, total = await _list(db_session, test_user, f)
    assert total == 3
    assert set(_merchants(items)) == {"Employer GmbH", "Landlord", "Bar 100%_off"}


async def test_inverted_bounds_are_empty_not_an_error(db_session, test_user, rows):
    """Review Focus 2."""
    f = TransactionFilters(date_from=dt.date(2026, 3, 1), date_to=dt.date(2026, 1, 1), amount_min=Decimal("10"), amount_max=Decimal("-10"))
    assert await _list(db_session, test_user, f) == ([], 0)


async def test_any_of_several_categories(db_session, test_user, rows):
    f = TransactionFilters(category=["salary", "bars_restaurants"])
    items, _ = await _list(db_session, test_user, f)
    assert set(_merchants(items)) == {"Employer GmbH", "Bar 100%_off"}


async def test_amount_bounds_on_the_signed_amount(db_session, test_user, rows):
    f = TransactionFilters(amount_max=Decimal("-18.50"))
    items, _ = await _list(db_session, test_user, f)
    assert set(_merchants(items)) == {"REWE", "Landlord", "Bar 100%_off"}


async def test_recurring(db_session, test_user, rows):
    items, _ = await _list(db_session, test_user, TransactionFilters(is_recurring=True))
    assert set(_merchants(items)) == {"Employer GmbH", "Landlord"}


async def test_search_is_a_case_insensitive_substring(db_session, test_user, rows):
    items, _ = await _list(db_session, test_user, search="SPÄ")
    assert _merchants(items) == ["Späti"]


@pytest.mark.parametrize("term", ["%", "_", "100%_"])
async def test_search_matches_like_wildcards_literally(db_session, test_user, rows, term):
    items, _ = await _list(db_session, test_user, search=term)
    assert _merchants(items) == ["Bar 100%_off"]


async def test_backslash_in_search_is_literal(db_session, test_user, rows):
    assert await _list(db_session, test_user, search="\\") == ([], 0)


@pytest.mark.parametrize(
    "ordering, first",
    [("date", "REWE"), ("-date", "Späti"), ("amount", "Landlord"), ("-amount", "Employer GmbH"), ("merchant", "Bar 100%_off"), ("-merchant", "Späti")],
)
async def test_orderings(db_session, test_user, rows, ordering, first):
    items, _ = await _list(db_session, test_user, ordering=ordering)
    assert items[0].merchant == first


async def test_same_day_ties_break_newest_created_first(db_session, test_user, make_transaction):
    first = await make_transaction(test_user, merchant="A", date=dt.date(2026, 3, 1))
    second = await make_transaction(test_user, merchant="B", date=dt.date(2026, 3, 1))
    items, _ = await _list(db_session, test_user)
    assert [t.id for t in items] == [second.id, first.id]


async def test_paging_and_a_page_past_the_end(db_session, test_user, rows):
    """Review Focus 4."""
    page, total = await _list(db_session, test_user, offset=2, limit=2)
    assert _merchants(page) == ["Landlord", "Employer GmbH"]
    assert total == 5
    assert await _list(db_session, test_user, offset=40, limit=20) == ([], 5)


async def test_soft_deleted_and_other_users_rows_never_appear(db_session, test_user, other_user, rows, make_transaction):
    rows["rewe"].soft_delete()
    await db_session.flush()
    await make_transaction(other_user, merchant="Theirs")
    items, total = await _list(db_session, test_user)
    assert total == 4
    assert "REWE" not in _merchants(items) and "Theirs" not in _merchants(items)
```

Run → FAIL (`TransactionFilters` / `list_active_for_user` missing).

- [x] **Step 2: Implement**

`schemas.py` (add `Literal`, `List` imports):

```python
TransactionOrdering = Literal["date", "-date", "amount", "-amount", "merchant", "-merchant"]


class TransactionFilters(BaseModel):
    """The list's filters. Every bound is inclusive; amounts are signed."""

    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None
    category: Optional[List[Category]] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None
    is_recurring: Optional[bool] = None


class TransactionListResponse(BaseModel):
    """One page of transactions."""

    items: List[TransactionResponse] = Field(..., description="The transactions on this page")
    total: int = Field(..., description="Active transactions matching the filters, across all pages")
    offset: int = Field(..., description="Rows skipped")
    limit: int = Field(..., description="Page size")
```

`repository.py` (add `from sqlalchemy import func`, `from app.modules.transaction.schemas import TransactionFilters`):

```python
_ORDER_COLUMNS = {
    "date": Transaction.date,
    "amount": Transaction.amount,
    "merchant": func.lower(Transaction.merchant),
}


def _escape_like(term: str) -> str:
    """Make %, _ and \\ match themselves in an ILIKE pattern escaped with \\."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
```

and in the class:

```python
    @staticmethod
    async def list_active_for_user(
        session: AsyncSession,
        user_id: uuid.UUID,
        filters: TransactionFilters,
        ordering: str,
        search: Optional[str],
        offset: int,
        limit: int,
    ) -> tuple[list[Transaction], int]:
        """One page of a user's active transactions and the filtered total.

        Every ordering ends in created_at DESC, id DESC so pages are stable.
        """
        conditions = [Transaction.user_id == user_id, Transaction.deleted_at.is_(None)]
        if filters.date_from is not None:
            conditions.append(Transaction.date >= filters.date_from)
        if filters.date_to is not None:
            conditions.append(Transaction.date <= filters.date_to)
        if filters.category:
            conditions.append(Transaction.category.in_([c.value for c in filters.category]))
        if filters.amount_min is not None:
            conditions.append(Transaction.amount >= filters.amount_min)
        if filters.amount_max is not None:
            conditions.append(Transaction.amount <= filters.amount_max)
        if filters.is_recurring is not None:
            conditions.append(Transaction.is_recurring == filters.is_recurring)
        if search:
            conditions.append(Transaction.merchant.ilike(f"%{_escape_like(search)}%", escape="\\"))

        total = (await session.execute(select(func.count()).select_from(Transaction).where(*conditions))).scalar_one()

        column = _ORDER_COLUMNS[ordering.lstrip("-")]
        primary = column.desc() if ordering.startswith("-") else column.asc()
        statement = (
            select(Transaction)
            .where(*conditions)
            .order_by(primary, Transaction.created_at.desc(), Transaction.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list((await session.execute(statement)).scalars().all())
        return items, total
```

`service.py`:

```python
    @staticmethod
    async def list(
        session: AsyncSession,
        user_id: uuid.UUID,
        filters: TransactionFilters,
        ordering: str,
        search: Optional[str],
        offset: int,
        limit: int,
    ) -> tuple[list[Transaction], int]:
        """One page of a user's active transactions and the filtered total."""
        return await transaction_repository.list_active_for_user(
            session, user_id, filters, ordering, search, offset, limit
        )
```

Run the repository tests → PASS.

- [x] **Step 3: The route — failing route tests first**

Append to `router/test_transactions.py`:

```python
class TestList:
    async def test_unauthenticated_returns_401(self, client):
        assert (await client.get(BASE)).status_code == 401

    async def test_envelope_and_string_amounts(self, authenticated_client, test_user, make_transaction):
        await make_transaction(test_user)
        response = await authenticated_client.get(BASE)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1 and body["offset"] == 0 and body["limit"] == 20
        assert body["items"][0]["amount"] == "-4.50"

    async def test_repeated_category_and_every_param(self, authenticated_client, test_user, make_transaction):
        await make_transaction(test_user, category="salary", amount=Decimal("100"))
        await make_transaction(test_user, category="atm", merchant="ATM", amount=Decimal("-50"))
        response = await authenticated_client.get(
            BASE,
            params=[
                ("category", "salary"), ("category", "atm"), ("date_from", "2026-01-01"), ("date_to", "2026-12-31"),
                ("amount_min", "-100"), ("amount_max", "100"), ("is_recurring", "false"), ("search", "a"),
                ("ordering", "amount"), ("offset", "0"), ("limit", "5"),
            ],
        )
        assert response.status_code == 200
        assert [t["category"] for t in response.json()["items"]] == ["atm", "salary"]

    async def test_inverted_bounds_answer_200_empty(self, authenticated_client):
        response = await authenticated_client.get(BASE, params={"date_from": "2026-03-01", "date_to": "2026-01-01"})
        assert response.status_code == 200
        assert response.json()["items"] == []

    @pytest.mark.parametrize(
        "params",
        [{"limit": 101}, {"limit": 0}, {"offset": -1}, {"ordering": "fingerprint"}, {"category": "no_such_slug"}, {"search": "x" * 101}],
    )
    async def test_bounds_are_422(self, authenticated_client, params):
        assert (await authenticated_client.get(BASE, params=params)).status_code == 422
```

(add `from decimal import Decimal` at the top). Run → FAIL. Add the route to `router.py` directly after `/categories` and before `POST ""`:

```python
@router.get(
    "",
    operation_id="listTransactions",
    response_model=TransactionListResponse,
    summary="List transactions",
    description="One page of the caller's transactions, newest first by default. Bounds are inclusive; "
    "category repeats; search matches the merchant.",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTIONS[0])
async def list_transactions(
    request: Request,
    db_session: DbSession,
    user: CurrentUser,
    date_from: Optional[dt.date] = Query(None, description="On or after this day"),
    date_to: Optional[dt.date] = Query(None, description="On or before this day"),
    category: Optional[List[Category]] = Query(None, description="Any of these categories; repeat the parameter"),
    amount_min: Optional[Decimal] = Query(None, description="Signed amount at least this"),
    amount_max: Optional[Decimal] = Query(None, description="Signed amount at most this"),
    is_recurring: Optional[bool] = Query(None, description="Only recurring, or only not"),
    search: Optional[str] = Query(None, max_length=100, description="Merchant contains, case-insensitive"),
    ordering: TransactionOrdering = Query("-date", description="Sort field; '-' for descending"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> TransactionListResponse:
    """List the caller's active transactions."""
    filters = TransactionFilters(
        date_from=date_from, date_to=date_to, category=category,
        amount_min=amount_min, amount_max=amount_max, is_recurring=is_recurring,
    )
    items, total = await transaction_service.list(db_session, user.id, filters, ordering, search, offset, limit)
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in items], total=total, offset=offset, limit=limit
    )
```

(imports: `datetime as dt`, `Decimal`, `Optional`, `List`, `Query`, the new schemas.) Export `TransactionFilters`, `TransactionListResponse` from the root.

- [x] **Step 4: Run, gate, regenerate, check the generated URL builder, commit**

Run: `APP_ENV=test uv run pytest tests/integration/modules/transaction tests/unit/api -v` → PASS.
Run (repo root): `make check-server && make gen-contract`.
Open `web-app/packages/api-client/src/generated/endpoints/transactions/transactions.ts`, find `getListTransactionsUrl`: an array `category` must be appended once per value (`category=a&category=b`). If orval joins it with commas instead, stop and report — the server expects repeats (Task 11's params test also pins this).

```bash
git add server web-app/packages/api-client/src/generated
git commit -m "feat(transactions): list with filters, search, ordering and paging"
```

---

## Task 5: Batches, delete all, erasure

Spec §2.1, §3.2 (`PATCH /batch`, `DELETE /batch`, `DELETE ""`), §3.4.

**Files:**
- Create: `server/app/modules/transaction/handlers.py`
- Modify: `server/app/modules/transaction/{schemas,repository,service,router,__init__}.py`
- Test: `server/tests/unit/modules/transaction/test_handlers.py`, `server/tests/integration/modules/transaction/test_erasure.py`, additions to `test_service.py` and `router/test_transactions.py`

**Interfaces:**
- Consumes: Task 3/5 pieces; `USER_ERASING`, `user_service` from `app.modules.account`; integration fixture `stub_checkpoint_deletion` (existing, unmodified).
- Produces:
  - schemas `BatchIds` (`ids: List[uuid.UUID]`, 1–100, distinct), `BatchCategoryUpdate(BatchIds)` + `category: Category`, `BatchUpdateResponse {updated: int}`, `BatchDeleteResponse {deleted: int}`, `DeleteAllResponse {deleted: int}`
  - repository `set_category_for_ids`, `soft_delete_ids` → `list[uuid.UUID]`; `delete_all_for_user` → `int`
  - service `batch_update_category(session, user_id, ids, category) -> int`, `batch_soft_delete(session, user_id, ids) -> int`, `delete_all_for_user(session, user_id) -> int`
  - routes `batchUpdateTransactionCategory`, `batchDeleteTransactions`, `deleteAllTransactions`
  - `handlers.erase_on_user_erasing` subscribed inline to `USER_ERASING`

- [x] **Step 1: Failing tests**

`tests/unit/modules/transaction/test_handlers.py`:

```python
"""The transaction module's reaction to USER_ERASING."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.transaction import handlers

pytestmark = pytest.mark.unit

USER_ID = uuid.UUID("0199a8b0-0000-7000-8000-000000000001")


def test_subscribes_inline_to_user_erasing():
    matches = [s for s in events.subscriptions(USER_ERASING) if s.handler is handlers.erase_on_user_erasing]
    assert matches, "erase_on_user_erasing is not subscribed to USER_ERASING"
    assert matches[0].inline


async def test_hard_deletes_every_transaction():
    session = AsyncMock()
    with patch("app.modules.transaction.handlers.transaction_service.delete_all_for_user", new=AsyncMock(return_value=3)) as delete_all:
        await handlers.erase_on_user_erasing(session=session, user_id=USER_ID)
    delete_all.assert_awaited_once_with(session, USER_ID)
```

`tests/integration/modules/transaction/test_erasure.py`:

```python
"""Erasure leaves the user no transaction rows, soft-deleted ones included."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from app.modules.account import user_service
from app.modules.transaction.models import Transaction

pytestmark = pytest.mark.integration


async def test_erase_user_hard_deletes_their_transactions(db_session, test_user, other_user, make_transaction, stub_checkpoint_deletion):
    await make_transaction(test_user)
    gone = await make_transaction(test_user, merchant="Deleted earlier")
    gone.soft_delete()
    kept = await make_transaction(other_user)

    with patch("app.modules.account.service.delete_user_memory", new=AsyncMock()):
        await user_service.erase_user(db_session, test_user)
    await db_session.flush()

    remaining = (await db_session.execute(select(Transaction))).scalars().all()
    assert [t.id for t in remaining] == [kept.id]
```

Append to `tests/integration/modules/transaction/test_service.py`:

```python
class TestBatches:
    async def test_recategorise_sets_confidence_one(self, db_session, test_user, make_transaction):
        a = await make_transaction(test_user, confidence=0.3)
        b = await make_transaction(test_user, merchant="REWE", confidence=0.5)
        assert await transaction_service.batch_update_category(db_session, test_user.id, [a.id, b.id], "shopping") == 2
        await db_session.refresh(a)
        assert (a.category, a.confidence) == ("shopping", 1.0)

    async def test_one_foreign_id_raises(self, db_session, test_user, other_user, make_transaction):
        """The raise is what makes the session dependency roll the batch back (the route test proves it)."""
        mine = await make_transaction(test_user)
        theirs = await make_transaction(other_user)
        with pytest.raises(TransactionNotFoundError):
            await transaction_service.batch_update_category(db_session, test_user.id, [mine.id, theirs.id], "shopping")

    async def test_a_soft_deleted_id_counts_as_missing(self, db_session, test_user, make_transaction):
        a = await make_transaction(test_user)
        a.soft_delete()
        await db_session.flush()
        with pytest.raises(TransactionNotFoundError):
            await transaction_service.batch_soft_delete(db_session, test_user.id, [a.id])

    async def test_delete_all_removes_soft_deleted_rows_too(self, db_session, test_user, other_user, make_transaction):
        await make_transaction(test_user)
        hidden = await make_transaction(test_user, merchant="Hidden")
        hidden.soft_delete()
        await make_transaction(other_user)
        assert await transaction_service.delete_all_for_user(db_session, test_user.id) == 2
```

(import `TransactionNotFoundError` from `app.modules.transaction`.)

Append to `router/test_transactions.py`:

```python
class TestBatchRoutes:
    async def test_recategorise(self, authenticated_client, test_user, make_transaction):
        a = await make_transaction(test_user)
        response = await authenticated_client.patch(f"{BASE}/batch", json={"ids": [str(a.id)], "category": "shopping"})
        assert response.status_code == 200
        assert response.json() == {"updated": 1}

    async def test_a_foreign_id_is_404_and_nothing_changes(self, authenticated_client, test_user, other_user, make_transaction, db_session):
        mine = await make_transaction(test_user)
        theirs = await make_transaction(other_user)
        await db_session.commit()  # the 404 rolls the request back; committed rows survive it
        response = await authenticated_client.patch(
            f"{BASE}/batch", json={"ids": [str(mine.id), str(theirs.id)], "category": "shopping"}
        )
        assert response.status_code == 404
        await db_session.refresh(mine)
        assert mine.category == "food_groceries"

    async def test_batch_delete(self, authenticated_client, test_user, make_transaction):
        a = await make_transaction(test_user)
        b = await make_transaction(test_user, merchant="REWE")
        response = await authenticated_client.request("DELETE", f"{BASE}/batch", json={"ids": [str(a.id), str(b.id)]})
        assert response.status_code == 200
        assert response.json() == {"deleted": 2}
        assert (await authenticated_client.get(BASE)).json()["total"] == 0

    async def test_no_ids_is_422(self, authenticated_client):
        response = await authenticated_client.request("DELETE", f"{BASE}/batch", json={"ids": []})
        assert response.status_code == 422

    async def test_101_ids_is_422(self, authenticated_client):
        ids = [str(uuid7()) for _ in range(101)]
        response = await authenticated_client.request("DELETE", f"{BASE}/batch", json={"ids": ids})
        assert response.status_code == 422

    async def test_duplicate_ids_are_422(self, authenticated_client):
        some = str(uuid7())
        response = await authenticated_client.patch(f"{BASE}/batch", json={"ids": [some, some], "category": "atm"})
        assert response.status_code == 422

    async def test_delete_all(self, authenticated_client, test_user, other_user, make_transaction):
        await make_transaction(test_user)
        await make_transaction(other_user)
        response = await authenticated_client.delete(BASE)
        assert response.status_code == 200
        assert response.json() == {"deleted": 1}
```

Run all three files → FAIL.

- [x] **Step 2: Implement**

`schemas.py`:

```python
class BatchIds(BaseModel):
    """1–100 distinct transaction ids."""

    ids: List[uuid.UUID] = Field(..., min_length=1, max_length=100, description="Transaction ids, distinct")

    @field_validator("ids")
    @classmethod
    def _distinct(cls, ids: List[uuid.UUID]) -> List[uuid.UUID]:
        if len(set(ids)) != len(ids):
            raise ValueError("ids must be distinct")
        return ids


class BatchCategoryUpdate(BatchIds):
    """Give every listed transaction one category."""

    category: Category = Field(..., description="The category slug")


class BatchUpdateResponse(BaseModel):
    updated: int = Field(..., description="Transactions changed")


class BatchDeleteResponse(BaseModel):
    deleted: int = Field(..., description="Transactions deleted")


class DeleteAllResponse(BaseModel):
    deleted: int = Field(..., description="Transactions permanently removed, earlier deleted ones included")
```

`repository.py` (add `from datetime import UTC, datetime`, `from sqlalchemy import delete, update`):

```python
    @staticmethod
    async def set_category_for_ids(
        session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID], category: str
    ) -> list[uuid.UUID]:
        """Recategorise this user's active rows among `ids` in one UPDATE; return the ids changed."""
        statement = (
            update(Transaction)
            .where(Transaction.id.in_(ids), Transaction.user_id == user_id, Transaction.deleted_at.is_(None))
            .values(category=category, confidence=1.0, updated_at=datetime.now(UTC))
            .returning(Transaction.id)
        )
        return list((await session.execute(statement)).scalars().all())

    @staticmethod
    async def soft_delete_ids(session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID]) -> list[uuid.UUID]:
        """Stamp deleted_at on this user's active rows among `ids` in one UPDATE; return the ids changed."""
        now = datetime.now(UTC)
        statement = (
            update(Transaction)
            .where(Transaction.id.in_(ids), Transaction.user_id == user_id, Transaction.deleted_at.is_(None))
            .values(deleted_at=now, updated_at=now)
            .returning(Transaction.id)
        )
        return list((await session.execute(statement)).scalars().all())

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> int:
        """Permanently remove every row this user owns, soft-deleted included; return the count."""
        result = await session.execute(delete(Transaction).where(Transaction.user_id == user_id))
        logger.info("all_user_transactions_deleted", user_id=user_id, count=result.rowcount)
        return result.rowcount
```

`service.py`:

```python
    @staticmethod
    def _require_all(ids: list[uuid.UUID], changed: list[uuid.UUID]) -> None:
        """All or nothing: raising makes the session dependency roll the batch back."""
        if len(changed) != len(ids):
            missing = sorted(str(i) for i in set(ids) - set(changed))
            raise TransactionNotFoundError("One or more transactions not found", missing_ids=missing)

    @staticmethod
    async def batch_update_category(session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID], category: str) -> int:
        """Recategorise up to 100 transactions, all or none."""
        changed = await transaction_repository.set_category_for_ids(session, user_id, ids, category)
        TransactionService._require_all(ids, changed)
        return len(changed)

    @staticmethod
    async def batch_soft_delete(session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID]) -> int:
        """Soft-delete up to 100 transactions, all or none."""
        changed = await transaction_repository.soft_delete_ids(session, user_id, ids)
        TransactionService._require_all(ids, changed)
        return len(changed)

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> int:
        """Permanently remove every transaction a user owns: Settings' delete-all and erasure."""
        return await transaction_repository.delete_all_for_user(session, user_id)
```

`handlers.py`:

```python
"""Subscriptions to account events."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.transaction.service import transaction_service


@events.on(USER_ERASING, inline=True)
async def erase_on_user_erasing(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Permanently remove every transaction the user owns, soft-deleted ones included.

    Inline, in the publishing transaction and before the user row is
    anonymised. Merchants, amounts and descriptions are personal financial
    data; nothing references a transaction, so the rows go rather than being
    anonymised (docs/data-model/transaction.md).
    """
    await transaction_service.delete_all_for_user(session, user_id)
```

`__init__.py`: add at the end

```python
# @events.on is a module-level side effect: importing the root is what subscribes.
from app.modules.transaction import handlers  # noqa: E402
```

Routes in `router.py`, placed **after** `GET ""` / `POST ""` and **before** the `/{transaction_id}` routes:

```python
@router.patch(
    "/batch",
    operation_id="batchUpdateTransactionCategory",
    response_model=BatchUpdateResponse,
    summary="Recategorise transactions",
    description="Give up to 100 transactions one category. All or nothing: one missing id changes none (404).",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTIONS[0])
async def batch_update_category(
    request: Request, body: BatchCategoryUpdate, db_session: DbSession, user: CurrentUser
) -> BatchUpdateResponse:
    """Recategorise many transactions."""
    return BatchUpdateResponse(
        updated=await transaction_service.batch_update_category(db_session, user.id, body.ids, body.category)
    )


@router.delete(
    "/batch",
    operation_id="batchDeleteTransactions",
    response_model=BatchDeleteResponse,
    summary="Delete transactions",
    description="Hide up to 100 transactions. All or nothing: one missing id deletes none (404).",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTIONS[0])
async def batch_delete(request: Request, body: BatchIds, db_session: DbSession, user: CurrentUser) -> BatchDeleteResponse:
    """Soft-delete many transactions."""
    return BatchDeleteResponse(deleted=await transaction_service.batch_soft_delete(db_session, user.id, body.ids))


@router.delete(
    "",
    operation_id="deleteAllTransactions",
    response_model=DeleteAllResponse,
    summary="Delete all transactions",
    description="Permanently remove every transaction the caller owns, earlier deleted ones included.",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTIONS[0])
async def delete_all(request: Request, db_session: DbSession, user: CurrentUser) -> DeleteAllResponse:
    """Permanently delete all of the caller's transactions."""
    return DeleteAllResponse(deleted=await transaction_service.delete_all_for_user(db_session, user.id))
```

- [x] **Step 3: Run, gate, regenerate, commit**

Run: `APP_ENV=test uv run pytest tests/unit tests/integration/modules -v` → PASS (account's erasure tests too: `subscriber_count` is now 2).
Run (repo root): `make check-server && make gen-contract`.

```bash
git add server web-app/packages/api-client/src/generated
git commit -m "feat(transactions): batch recategorise and delete, delete all, erasure"
```

---

## Task 6: Seed data (controller task — needs the user)

Spec §5.1. **The controller does this task itself, not a subagent**: it reads data outside the repo and ends at a user review gate. Nothing from the source is committed before the user approves the output.

**Files:**
- Create: `server/data/transactions-seed.csv`
- Scratch (never committed): `<scratchpad>/seed-prep/prepare.py`

**Interfaces:**
- Produces: `server/data/transactions-seed.csv` with header `date,merchant,amount,description,category,confidence,is_recurring,original_category`; `date` ISO; `amount` 2-place decimal; `category` a slug from the Global Constraints list; `is_recurring` `true`/`false`; empty cell = null.

- [x] **Step 1: Write the prep script in the scratchpad.** Inputs: `/Users/tizianoiacovelli/projects/personal-finance-reaserch/src/data/transactions_50pct.csv` (columns `Booking Date, Value Date, Partner Name, Partner Iban, Type, Payment Reference, Account Name, Amount (EUR), Original Amount, Original Currency, Exchange Rate`) and `/Users/tizianoiacovelli/projects/pf-legacy/server/tests/data/test_transactions_400.csv`. Run with `python3 -I`. It: drops the IBAN, value date, account name, original amount, currency and exchange rate; maps each transfer/debit/MoneyBeam counterpart (`Type` in `Debit Transfer, Credit Transfer, Direct Debit, MoneyBeam`) to a consistent stand-in (salary payer → "Employer GmbH", rent → "Landlord", each person → "Friend A", "Friend B", …, family → "Family"), and rewrites `Payment Reference` to a generic one ("Salary 02/2023", "Rent", "Transfer"); strips street names and numbers from local shops' card merchants; multiplies every amount by one factor drawn once from `random.uniform(0.8, 1.2)` and re-quantises to cents (`Decimal`, `ROUND_HALF_EVEN`); maps merchants to categories from the 400-row file (legacy display names → slugs) and writes a `uncategorised.txt` of the rest; sets `original_category` = `Type`; sets `confidence` from the 400-row file's row, else `0.9`; marks recurring from a short list (salary, rent, insurances, subscriptions).
- [x] **Step 2: Categorise the ~314 uncategorised merchants by hand** into the script's override map, one slug each; re-run until `uncategorised.txt` is empty.
- [x] **Step 3: Self-check the output for PII**: no IBAN-shaped string (`[A-Z]{2}\d{2}[A-Z0-9]{10,30}`), no `Partner Name` from a transfer row survives, no street-number pattern (`\b\d{1,4}[a-z]?\b` after a street word: `str`, `straße`, `strasse`, `allee`, `platz`, `weg`, `damm`, `ufer`, `Alt `), no email, no person's name (grep the stand-in map's keys against the output). Fix and re-run until clean.
- [x] **Step 4: STOP — ask the user to review `server/data/transactions-seed.csv`** (show row count, date span, category counts, the stand-in names used, and the scale factor's existence but not its value). Wait for explicit approval. Apply any changes they ask for.
- [x] **Step 5: Commit the CSV only**

```bash
git add server/data/transactions-seed.csv
git commit -m "chore(seed): anonymised, categorised transactions for the dev seed"
```

---

## Task 7: The seed script

Spec §5.2.

**Files:**
- Create: `server/scripts/seed_transactions.py`, `server/tests/unit/scripts/test_seed_transactions.py`, `server/tests/integration/scripts/__init__.py`, `server/tests/integration/scripts/test_seed_transactions.py`
- Modify: `server/Makefile`, root `Makefile`

**Interfaces:**
- Consumes: `transaction_service.import_many`, `transaction_service.delete_all_for_user`, `TransactionImport`, `Category` (module root); `user_service.resolve_user` (account root); `create_session_factory`, `initialize_database_engine`, `close_database_engine` (`app.database`); `settings.ENVIRONMENT`, `Environment` (`app.core.config`).
- Produces: `shift_months(d, months) -> date`, `months_to_current(newest, today) -> int`, `load_rows(path, today) -> tuple[list[TransactionImport], Counter[str]]`, `seed(session, clerk_id, today) -> int`, CLI `--clerk-id`.

- [x] **Step 1: Failing unit tests**

`tests/unit/scripts/test_seed_transactions.py`:

```python
"""The seed's date shift and CSV parsing."""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from seed_transactions import load_rows, months_to_current, shift_months  # noqa: E402

pytestmark = pytest.mark.unit

HEADER = "date,merchant,amount,description,category,confidence,is_recurring,original_category\n"


def test_shift_keeps_the_day_of_month():
    assert shift_months(date(2026, 1, 27), 9) == date(2026, 10, 27)


def test_shift_clamps_to_the_months_length():
    assert shift_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_shift_crosses_a_year():
    assert shift_months(date(2025, 11, 15), 3) == date(2026, 2, 15)


def test_months_to_current():
    assert months_to_current(date(2026, 1, 23), date(2026, 10, 13)) == 9
    assert months_to_current(date(2026, 10, 1), date(2026, 10, 13)) == 0


def _csv(tmp_path, body):
    path = tmp_path / "seed.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def test_rows_move_so_the_newest_lands_this_month_and_future_rows_drop(tmp_path):
    path = _csv(
        tmp_path,
        "2026-01-10,REWE,-12.70,,food_groceries,0.9,false,Presentment\n"
        "2026-01-20,Späti,-4.50,,food_groceries,0.9,false,Presentment\n",
    )
    rows, unknown = load_rows(path, today=date(2026, 10, 13))
    assert [r.date for r in rows] == [date(2026, 10, 10)]  # 2026-10-20 is after today
    assert rows[0].amount == Decimal("-12.70")
    assert rows[0].original_category == "Presentment"
    assert rows[0].description is None
    assert not unknown


def test_an_unknown_slug_becomes_miscellaneous_and_is_counted(tmp_path):
    path = _csv(tmp_path, "2026-10-01,X,-1.00,,retired_slug,0.9,true,\n")
    rows, unknown = load_rows(path, today=date(2026, 10, 13))
    assert rows[0].category == "miscellaneous"
    assert rows[0].is_recurring is True
    assert unknown == {"retired_slug": 1}
```

Run: `APP_ENV=test uv run pytest tests/unit/scripts/test_seed_transactions.py -v` → FAIL (ImportError).

- [x] **Step 2: Implement `scripts/seed_transactions.py`**

```python
"""Fill a dev user's transactions from server/data/transactions-seed.csv.

Development only. Replaces the user's transactions — rerunning resets them.
Dates move forward by whole months so the newest row falls in the current
month (the day of month is kept, clamped to the month's length); a row that
would land after today is dropped. A slug the category list no longer has is
filed under miscellaneous, and reported.

    make -C server seed-transactions CLERK_ID=user_...
"""

import argparse
import asyncio
import calendar
import csv
import sys
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Environment, settings
from app.core.logging import logger
from app.database import close_database_engine, create_session_factory, initialize_database_engine
from app.modules.account import user_service
from app.modules.transaction import Category, TransactionImport, transaction_service

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "transactions-seed.csv"
_SLUGS = {c.value for c in Category}


def shift_months(d: date, months: int) -> date:
    """`d` moved forward `months` whole months, its day clamped to the target month's length."""
    index = d.year * 12 + (d.month - 1) + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def months_to_current(newest: date, today: date) -> int:
    """Whole months from `newest`'s month to `today`'s."""
    return (today.year * 12 + today.month) - (newest.year * 12 + newest.month)


def load_rows(path: Path, today: date) -> tuple[list[TransactionImport], Counter]:
    """The seed rows, dates shifted, rows after today dropped; plus a count of unknown slugs."""
    with path.open(encoding="utf-8", newline="") as f:
        raw = list(csv.DictReader(f))
    if not raw:
        return [], Counter()
    months = months_to_current(max(date.fromisoformat(r["date"]) for r in raw), today)
    unknown: Counter = Counter()
    rows: list[TransactionImport] = []
    for r in raw:
        shifted = shift_months(date.fromisoformat(r["date"]), months)
        if shifted > today:
            continue
        category = r["category"]
        if category not in _SLUGS:
            unknown[category] += 1
            category = "miscellaneous"
        rows.append(
            TransactionImport(
                date=shifted,
                merchant=r["merchant"],
                amount=Decimal(r["amount"]),
                description=r["description"] or None,
                category=category,
                confidence=float(r["confidence"]),
                is_recurring=r["is_recurring"] == "true",
                original_category=r["original_category"] or None,
            )
        )
    return rows, unknown


async def seed(session: AsyncSession, clerk_id: str, today: date, path: Path = SEED_FILE) -> int:
    """Replace the user's transactions with the seed. Resolves the user as a request would (JIT from Clerk)."""
    user = await user_service.resolve_user(session, clerk_id)
    rows, unknown = load_rows(path, today)
    if unknown:
        print(f"warning: filed under miscellaneous, slugs no longer in the list: {dict(unknown)}", file=sys.stderr)
    await transaction_service.delete_all_for_user(session, user.id)
    count = await transaction_service.import_many(session, user.id, rows)
    logger.info("transactions_seeded", user_id=user.id, count=count)
    return count


async def _main(clerk_id: str) -> None:
    engine = await initialize_database_engine()
    try:
        async with create_session_factory(engine)() as session:
            count = await seed(session, clerk_id, date.today())
            await session.commit()
        print(f"seeded {count} transactions for {clerk_id}")
    finally:
        await close_database_engine(engine)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clerk-id", required=True, help="The Clerk user id (user_...) to seed")
    args = parser.parse_args()
    if settings.ENVIRONMENT != Environment.DEVELOPMENT:
        sys.exit(f"refusing to seed: APP_ENV is {settings.ENVIRONMENT.value}, not development")
    asyncio.run(_main(args.clerk_id))
```

(Check `initialize_database_engine`'s signature in `app/database/engine.py` and adapt the call if it takes arguments.)

Run the unit tests → PASS.

- [x] **Step 3: Integration test**

`tests/integration/scripts/test_seed_transactions.py` (and an empty `__init__.py`):

```python
"""The seed against the container database, with the real seed file."""

import sys
from datetime import date
from pathlib import Path

import pytest
from sqlmodel import func, select

from app.modules.transaction.models import Transaction

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from seed_transactions import SEED_FILE, seed  # noqa: E402

pytestmark = pytest.mark.integration

TODAY = date(2026, 10, 13)


async def test_seeds_the_file_within_the_shifted_range_and_reseeding_resets(db_session, test_user):
    count = await seed(db_session, test_user.clerk_id, TODAY)
    assert count > 900
    newest, oldest = (
        await db_session.execute(select(func.max(Transaction.date), func.min(Transaction.date)))
    ).one()
    assert newest <= TODAY and (newest.year, newest.month) == (2026, 10)
    assert oldest < date(2024, 1, 1)

    assert await seed(db_session, test_user.clerk_id, TODAY) == count
    total = (await db_session.execute(select(func.count()).select_from(Transaction))).scalar_one()
    assert total == count
    assert SEED_FILE.exists()
```

Run: `APP_ENV=test uv run pytest tests/integration/scripts -v` → PASS.

- [x] **Step 4: Make targets**

`server/Makefile`, after `export-openapi` (and in its `.PHONY` and `help` if it has them):

```make
seed-transactions:
	@test -n "$(CLERK_ID)" || (echo "usage: make seed-transactions CLERK_ID=user_..." && exit 1)
	@bash -c "source scripts/set_env.sh development && PYTHONPATH=. uv run python scripts/seed_transactions.py --clerk-id $(CLERK_ID)"
```

Root `Makefile`: add `seed-transactions` to `.PHONY`; under the Clerk lines of `help`: `@echo "  make seed-transactions CLERK_ID=… - Replace a dev user's transactions with the seed"`; and

```make
seed-transactions:
	@$(MAKE) -C server seed-transactions CLERK_ID=$(CLERK_ID)
```

Run by hand once: `make seed-transactions CLERK_ID=<a dev user's id from server/data/clerk-dev-seed.json or the Clerk dashboard>` → `seeded N transactions`.

- [x] **Step 5: Gate and commit**

Run (repo root): `make check-server`.

```bash
git add server/scripts/seed_transactions.py server/tests/unit/scripts/test_seed_transactions.py server/tests/integration/scripts server/Makefile Makefile
git commit -m "feat(seed): make seed-transactions fills a dev user's transactions"
```

---

## Task 8: UI primitives, the date picker and the mutation opt-out

Spec §4.6, §4.4. Load `web-app-patterns` → `references/components.md`.

**Files:**
- Create: `web-app/packages/ui/src/primitives/{alert-dialog,calendar,checkbox,switch,textarea}.tsx`, `web-app/packages/components/src/forms/date-picker.tsx`, `web-app/packages/components/src/forms/date-picker.test.tsx`, `web-app/packages/api-client/src/query-provider.test.tsx`
- Modify: `web-app/packages/ui/src/index.ts`, `web-app/packages/ui/package.json` (`react-day-picker` and whatever else the calendar's docs list), `web-app/packages/api-client/src/query-provider.tsx`

**Interfaces:**
- Produces: `@app/ui/calendar` (`Calendar`, the shadcn Base UI calendar on `react-day-picker`); `@app/components/forms/date-picker` (`DatePicker({ value: string; onChange: (iso: string) => void; id?: string; placeholder?: string })` — `value`/`onChange` are local ISO `YYYY-MM-DD`, "" when empty); `@app/ui/alert-dialog` (`AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogFooter, AlertDialogTitle, AlertDialogDescription, AlertDialogAction, AlertDialogCancel`), `@app/ui/checkbox` (`Checkbox`: Base UI, `checked`, `indeterminate`, `onCheckedChange(checked: boolean)`), `@app/ui/switch` (`Switch`: `checked`, `onCheckedChange`), `@app/ui/textarea` (`Textarea`). Mutation `meta: { silentStatuses: number[] }` suppresses `QueryProvider`'s toast for those statuses.

> **Orchestrator, 13 Oct 2026:** follow `components.md` (install by hand if the CLI can't resolve the alias); condition 6's merge rule still holds; step 3 adds no `packages/ui` primitives, but report which path was taken anyway. `feat/chat-screen` moves `toastForError` verbatim into a new `packages/api-client/src/toast-for-error.ts` and imports it in `query-provider.tsx`: change **only** the `MutationCache` `onError` line (Step 3 below), never the body of `toastForError`, so the merge is a union. A status check inside `toastForError` itself needs the orchestrator's OK first.

- [x] **Step 1: Add the five primitives** (`alert-dialog`, `calendar` — https://ui.shadcn.com/docs/components/base/calendar —, `checkbox`, `switch`, `textarea`). Condition 6 of the brief says "with the shadcn CLI, no hand edits"; `components.md` says the CLI cannot resolve this repo's alias. Try the CLI first, from `web-app/packages/ui`: `pnpm dlx shadcn@latest add alert-dialog calendar checkbox switch textarea`. If it writes `src/primitives/<name>.tsx` with working imports, keep its output untouched (then `pnpm exec prettier --write` them). If it fails, install each by hand from `ui.shadcn.com/docs/components/base/<name>` (Manual tab, Base UI variant), `cn` from `@app/core/lib/utils`, prettier — and **report to the controller which path was taken**, so it can tell the orchestrator (step 3 must take the same path). Add each primitive's exports to `src/index.ts`.
- [x] **Step 1b: The date picker (the shadcn Date Picker pattern: `Popover` + `Calendar`), test first**

`packages/components/src/forms/date-picker.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { DatePicker } from "./date-picker"

describe("DatePicker", () => {
  it("shows the placeholder when empty", () => {
    render(<DatePicker value="" onChange={() => {}} placeholder="Pick a date" />)
    expect(screen.getByRole("button", { name: /Pick a date/ })).toBeInTheDocument()
  })

  it("shows the chosen day as a local date", () => {
    render(<DatePicker value="2026-03-03" onChange={() => {}} />)
    expect(screen.getByRole("button", { name: /2026|Mar|3/ })).toHaveTextContent(/3/)
  })

  it("reports a picked day as local ISO, never shifted by the timezone", () => {
    const onChange = vi.fn()
    render(<DatePicker value="2026-03-03" onChange={onChange} />)
    fireEvent.click(screen.getByRole("button"))
    fireEvent.click(screen.getByRole("button", { name: /March 14/ }))
    expect(onChange).toHaveBeenCalledWith("2026-03-14")
  })
})
```

(react-day-picker names its day buttons with the full date, e.g. "Saturday, March 14th, 2026"; adjust the matcher to what it renders.)

`packages/components/src/forms/date-picker.tsx`:

```tsx
"use client"

import { useState } from "react"
import { CalendarIcon } from "lucide-react"
import { Button } from "@app/ui/button"
import { Calendar } from "@app/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@app/ui/popover"
import { cn } from "@app/core/lib/utils"

const pad = (n: number) => String(n).padStart(2, "0")
/** Local calendar date ↔ ISO YYYY-MM-DD. Never toISOString, which is UTC and shifts the day. */
const toIso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const fromIso = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number)
  return new Date(y, m - 1, d)
}
const display = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" })

/** One day, picked from a calendar in a popover. The value is a local ISO date, "" when empty. */
export function DatePicker({
  value,
  onChange,
  id,
  placeholder = "Pick a date",
}: {
  value: string
  onChange: (iso: string) => void
  id?: string
  placeholder?: string
}) {
  const [open, setOpen] = useState(false)
  const selected = value ? fromIso(value) : undefined
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button id={id} variant="outline" className={cn("w-full justify-start font-normal", !selected && "text-muted-foreground")} />
        }
      >
        <CalendarIcon />
        {selected ? display.format(selected) : placeholder}
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={selected}
          defaultMonth={selected}
          onSelect={(day) => {
            if (day) onChange(toIso(day))
            setOpen(false)
          }}
        />
      </PopoverContent>
    </Popover>
  )
}
```

Run (from `web-app/`): `pnpm test packages/components` → PASS.

- [x] **Step 2: Failing test for the opt-out**

`web-app/packages/api-client/src/query-provider.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { useMutation } from "@tanstack/react-query"
import { toast } from "sonner"
import { QueryProvider } from "./query-provider"
import { ApiError } from "./errors"

vi.mock("sonner", () => ({ toast: { error: vi.fn() } }))

const failWith = (status: number) => () => Promise.reject(new ApiError(status, null, null))

describe("QueryProvider mutation toasts", () => {
  beforeEach(() => vi.mocked(toast.error).mockClear())

  it("toasts a failed mutation", async () => {
    const { result } = renderHook(() => useMutation({ mutationFn: failWith(409) }), { wrapper: QueryProvider })
    result.current.mutate()
    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1))
  })

  it("stays silent for a status the mutation handles itself", async () => {
    const { result } = renderHook(
      () => useMutation({ mutationFn: failWith(409), meta: { silentStatuses: [409] } }),
      { wrapper: QueryProvider },
    )
    result.current.mutate()
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(toast.error).not.toHaveBeenCalled()
  })

  it("still toasts other statuses", async () => {
    const { result } = renderHook(
      () => useMutation({ mutationFn: failWith(500), meta: { silentStatuses: [409] } }),
      { wrapper: QueryProvider },
    )
    result.current.mutate()
    await waitFor(() => expect(toast.error).toHaveBeenCalledTimes(1))
  })
})
```

(Check `ApiError`'s constructor in `src/errors.ts` and match its argument order.) Run (from `web-app/`): `pnpm test packages/api-client` → the silent test FAILS.

- [x] **Step 3: Implement** in `query-provider.tsx`:

```tsx
        // Mutations toast: the user just acted and is waiting for a result. A
        // mutation that answers some statuses itself — the add dialog explains
        // a 409 inline — lists them in meta.silentStatuses.
        mutationCache: new MutationCache({
          onError: (error, _variables, _context, mutation) => {
            const silent = mutation.meta?.silentStatuses
            if (error instanceof ApiError && Array.isArray(silent) && silent.includes(error.status)) return
            toastForError(error)
          },
        }),
```

Run → PASS.

- [x] **Step 4: Gate and commit**

Run (repo root): `make check-web && make test-web`.

```bash
git add web-app/packages/ui web-app/packages/components/src/forms web-app/packages/api-client/src/query-provider.tsx web-app/packages/api-client/src/query-provider.test.tsx web-app/pnpm-lock.yaml
git commit -m "feat(ui): alert-dialog, calendar, checkbox, switch, textarea, a date picker; a mutation can silence a status it handles"
```

---

## Task 9: `@app/data-table` — row selection and the bulk bar

Spec §4.3.

**Files:**
- Create: `web-app/packages/data-table/src/table/row-selection.ts`, `row-selection.test.ts`, `data-table-bulk-bar.tsx`, `data-table-selection.test.tsx`
- Modify: `web-app/packages/data-table/src/table/data-table-core.tsx`, `web-app/packages/data-table/src/labels.ts`

**Interfaces:**
- Consumes: `@app/ui/checkbox`.
- Produces on `DataTableBaseProps<TData, TValue>` (so both `ClientDataTable` and `ServerDataTable` get them):
  - `enableRowSelection?: boolean` — adds a leading checkbox column (header toggles the page)
  - `renderBulkActions?: (selected: TData[], clearSelection: () => void) => React.ReactNode` — shown in a bar above the table while any row is selected
  - `pruneSelection(selection: RowSelectionState, ids: Iterable<string>): RowSelectionState`

- [x] **Step 1: Failing tests**

`row-selection.test.ts`:

```ts
import { describe, it, expect } from "vitest"
import { pruneSelection } from "./row-selection"

describe("pruneSelection", () => {
  it("keeps only rows still on screen", () => {
    expect(pruneSelection({ a: true, b: true, c: true }, ["b", "c", "d"])).toEqual({ b: true, c: true })
  })
  it("drops unselected entries", () => {
    expect(pruneSelection({ a: false, b: true }, ["a", "b"])).toEqual({ b: true })
  })
  it("returns the same object when nothing changes", () => {
    const s = { a: true }
    expect(pruneSelection(s, ["a"])).toBe(s)
  })
})
```

`data-table-selection.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { ServerDataTable } from "./server-data-table"
import type { ColumnDef } from "./columns"

type Row = { id: string; name: string }
const columns: ColumnDef<Row>[] = [{ accessorKey: "name", id: "name", header: "Name" }]
const controls = {
  sorting: [],
  pagination: { pageIndex: 0, pageSize: 20 },
  totalCount: 2,
  onSortingChange: () => {},
  onPaginationChange: () => {},
}

function renderTable(data: Row[], renderBulkActions = vi.fn((rows: Row[]) => <span>{rows.length} chosen</span>)) {
  const utils = render(
    <ServerDataTable columns={columns} data={data} controls={controls} enableRowSelection renderBulkActions={renderBulkActions} />,
  )
  return { ...utils, renderBulkActions }
}

describe("row selection", () => {
  const page1 = [{ id: "a", name: "A" }, { id: "b", name: "B" }]

  it("shows the bulk bar only while rows are selected", async () => {
    renderTable(page1)
    expect(screen.queryByText(/selected/)).toBeNull()
    await userEvent.click(screen.getAllByRole("checkbox", { name: "Select row" })[0])
    expect(screen.getByText("1 selected")).toBeInTheDocument()
    expect(screen.getByText("1 chosen")).toBeInTheDocument()
  })

  it("the header checkbox selects the page, Clear empties it", async () => {
    renderTable(page1)
    await userEvent.click(screen.getByRole("checkbox", { name: "Select all on this page" }))
    expect(screen.getByText("2 selected")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Clear selection" }))
    expect(screen.queryByText(/selected/)).toBeNull()
  })

  it("drops selected rows that leave the screen (a page or filter change)", async () => {
    const { rerender, renderBulkActions } = renderTable(page1)
    await userEvent.click(screen.getAllByRole("checkbox", { name: "Select row" })[0])
    rerender(
      <ServerDataTable columns={columns} data={[{ id: "c", name: "C" }]} controls={controls} enableRowSelection renderBulkActions={renderBulkActions} />,
    )
    expect(screen.queryByText(/selected/)).toBeNull()
  })

  it("adds no checkbox column unless enabled", () => {
    render(<ServerDataTable columns={columns} data={page1} controls={controls} />)
    expect(screen.queryByRole("checkbox")).toBeNull()
  })
})
```

(If `@testing-library/user-event` is not a dependency of the packages project, use `fireEvent.click` instead.) Run (from `web-app/`): `pnpm test packages/data-table` → FAIL.

- [x] **Step 2: Implement**

`row-selection.ts`:

```ts
import type { RowSelectionState } from "@tanstack/react-table"

/**
 * The selection restricted to rows on screen. Selection never outlives its
 * rows: a page, filter, sort or search change that removes a row deselects
 * it, so a bulk action only ever touches rows the user can see.
 */
export function pruneSelection(selection: RowSelectionState, ids: Iterable<string>): RowSelectionState {
  const visible = new Set(ids)
  const kept = Object.keys(selection).filter((id) => selection[id] && visible.has(id))
  if (kept.length === Object.keys(selection).length) return selection
  return Object.fromEntries(kept.map((id) => [id, true]))
}
```

`data-table-bulk-bar.tsx`:

```tsx
"use client"

import type { ReactNode } from "react"
import { X } from "lucide-react"
import { Button } from "@app/ui/button"
import { labels } from "../labels"

/** "N selected", the page's actions, and Clear. Rendered by DataTableCore while rows are selected. */
export function DataTableBulkBar({ count, onClear, children }: { count: number; onClear: () => void; children?: ReactNode }) {
  return (
    <div role="toolbar" aria-label={labels.bulkActions} className="mb-2 flex flex-wrap items-center gap-2 rounded-lg border bg-muted/50 px-3 py-1.5">
      <span className="text-sm font-medium tabular-nums">{labels.selectedCount(count)}</span>
      <div className="flex flex-wrap items-center gap-2">{children}</div>
      <Button variant="ghost" size="sm" className="ml-auto" onClick={onClear} aria-label={labels.clearSelection}>
        <X />
      </Button>
    </div>
  )
}
```

`labels.ts` adds:

```ts
  selectRow: "Select row",
  selectAllOnPage: "Select all on this page",
  selectedCount: (n: number) => `${n} selected`,
  clearSelection: "Clear selection",
  bulkActions: "Bulk actions",
```

`data-table-core.tsx`:
1. Import `type RowSelectionState` from `@tanstack/react-table`, `Checkbox` from `@app/ui/checkbox`, `pruneSelection`, `DataTableBulkBar`.
2. Add to `DataTableBaseProps`:

```ts
  /** a leading checkbox column; selection holds only rows on screen */
  enableRowSelection?: boolean
  /** the bulk bar's actions, shown while rows are selected */
  renderBulkActions?: (selected: TData[], clearSelection: () => void) => React.ReactNode
```

3. Destructure both (`enableRowSelection = false`). State and pruning, after the `expanded` state:

```ts
  const [rowSelection, setRowSelection] = React.useState<RowSelectionState>({})
  const rowIdOf = getRowId ?? defaultGetRowId
  const selection = enableRowSelection
    ? pruneSelection(rowSelection, data.map((row, i) => rowIdOf(row, i)))
    : {}
  const handleSelectionChange: OnChangeFn<RowSelectionState> = (updater) =>
    setRowSelection(typeof updater === "function" ? updater(selection) : updater)
```

4. In `cols`, prepend when `enableRowSelection` (before the expander), and add `enableRowSelection` to the memo deps:

```tsx
const selectColumn: ColumnDef<TData, TValue> = {
  id: "select",
  enableSorting: false,
  enableHiding: false,
  meta: { width: "2.5rem" },
  header: ({ table }) => (
    <Checkbox
      aria-label={labels.selectAllOnPage}
      checked={table.getIsAllPageRowsSelected()}
      indeterminate={table.getIsSomePageRowsSelected()}
      onCheckedChange={(checked) => table.toggleAllPageRowsSelected(checked)}
    />
  ),
  cell: ({ row }) => (
    <Checkbox
      aria-label={labels.selectRow}
      checked={row.getIsSelected()}
      onCheckedChange={(checked) => row.toggleSelected(checked)}
      onClick={(event) => event.stopPropagation()}
    />
  ),
}
```

(Note: `canSort` in the header render already requires `def.header` to be truthy and `enableSorting` — the select header must not render a sort button; `enableSorting: false` ensures that.)
5. `useReactTable`: add `enableRowSelection`, `onRowSelectionChange: handleSelectionChange`, and `rowSelection: selection` in `state`.
6. Just above `<div data-slot="table-container" …>`:

```tsx
      {enableRowSelection && Object.keys(selection).length > 0 && (
        <DataTableBulkBar count={Object.keys(selection).length} onClear={() => setRowSelection({})}>
          {renderBulkActions?.(
            table.getSelectedRowModel().rows.map((r) => r.original),
            () => setRowSelection({}),
          )}
        </DataTableBulkBar>
      )}
```

Run → PASS.

- [x] **Step 3: Gate and commit**

Run (repo root): `make check-web && make test-web`.

```bash
git add web-app/packages/data-table
git commit -m "feat(data-table): row selection and a bulk-action bar"
```

---

## Task 10: `@app/data-table` — phone cards, date presets, checkbox-group filter

Spec §4.2 (filters), §4.3 (phone layout).

**Files:**
- Create: `web-app/packages/data-table/src/table/data-table-cards.test.tsx`, `web-app/packages/data-table/src/url-state/date-presets.ts`, `date-presets.test.ts`, `web-app/packages/data-table/src/filters/filter-checkbox-group.tsx`, `filter-checkbox-group.test.tsx`
- Modify: `web-app/packages/data-table/src/table/data-table-core.tsx`, `web-app/packages/data-table/src/filters/date-filter-control.tsx`, `web-app/packages/data-table/src/labels.ts`, `web-app/packages/data-table/package.json` (exports)

**Interfaces:**
- Produces:
  - `DataTableBaseProps.renderCard?: (row: Row<TData>) => React.ReactNode` — below 768px (`useIsMobile`) the body is a list of cards; toolbar, chips and pager stay
  - `@app/data-table/url-state/date-presets`: `DATE_PRESETS = ["today", "this_week", "this_month", "last_month"] as const`, `type DatePreset`, `datePresetValue(preset: DatePreset, today: Date): DateFilterValue` (a `range`; weeks start Monday)
  - `DateFilterControl` prop `presets?: boolean` — preset buttons above the mode select
  - `@app/data-table/filters/filter-checkbox-group`: `FilterCheckboxGroup<T extends string>({ label, options: {value: T; label: string}[], value: T[], onChange: (value: T[]) => void })`

- [x] **Step 1: Failing tests**

`date-presets.test.ts`:

```ts
import { describe, it, expect } from "vitest"
import { datePresetValue } from "./date-presets"

const wed = new Date(2026, 9, 14) // Wed 14 Oct 2026, local time

describe("datePresetValue", () => {
  it("today", () => expect(datePresetValue("today", wed)).toEqual({ mode: "range", date1: "2026-10-14", date2: "2026-10-14" }))
  it("this week starts Monday", () => expect(datePresetValue("this_week", wed)).toEqual({ mode: "range", date1: "2026-10-12", date2: "2026-10-18" }))
  it("a Sunday belongs to the week before", () =>
    expect(datePresetValue("this_week", new Date(2026, 9, 18))).toEqual({ mode: "range", date1: "2026-10-12", date2: "2026-10-18" }))
  it("this month", () => expect(datePresetValue("this_month", wed)).toEqual({ mode: "range", date1: "2026-10-01", date2: "2026-10-31" }))
  it("last month across a year", () =>
    expect(datePresetValue("last_month", new Date(2026, 0, 10))).toEqual({ mode: "range", date1: "2025-12-01", date2: "2025-12-31" }))
})
```

`filter-checkbox-group.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { FilterCheckboxGroup } from "./filter-checkbox-group"

const options = [{ value: "a", label: "Alpha" }, { value: "b", label: "Beta" }] as const

describe("FilterCheckboxGroup", () => {
  it("adds and removes values, keeping option order", () => {
    const onChange = vi.fn()
    const { rerender } = render(<FilterCheckboxGroup label="Category" options={[...options]} value={["b"]} onChange={onChange} />)
    fireEvent.click(screen.getByRole("checkbox", { name: "Alpha" }))
    expect(onChange).toHaveBeenLastCalledWith(["a", "b"])
    rerender(<FilterCheckboxGroup label="Category" options={[...options]} value={["a", "b"]} onChange={onChange} />)
    fireEvent.click(screen.getByRole("checkbox", { name: "Beta" }))
    expect(onChange).toHaveBeenLastCalledWith(["a"])
  })
})
```

`data-table-cards.test.tsx`:

```tsx
import { describe, it, expect, vi, afterEach } from "vitest"
import { render, screen } from "@testing-library/react"
import { ServerDataTable } from "./server-data-table"
import type { ColumnDef } from "./columns"

type Row = { id: string; name: string }
const columns: ColumnDef<Row>[] = [{ accessorKey: "name", id: "name", header: "Name" }]
const controls = { sorting: [], pagination: { pageIndex: 0, pageSize: 20 }, totalCount: 1, onSortingChange: () => {}, onPaginationChange: () => {} }

function setWidth(px: number) {
  Object.defineProperty(window, "innerWidth", { configurable: true, value: px })
}

describe("renderCard", () => {
  afterEach(() => setWidth(1024))

  it("renders cards instead of the table on a phone", () => {
    setWidth(400)
    render(<ServerDataTable columns={columns} data={[{ id: "a", name: "A" }]} controls={controls} renderCard={(row) => <p>card {row.original.name}</p>} />)
    expect(screen.getByText("card A")).toBeInTheDocument()
    expect(screen.queryByRole("table")).toBeNull()
  })

  it("keeps the table on a desktop", () => {
    setWidth(1024)
    render(<ServerDataTable columns={columns} data={[{ id: "a", name: "A" }]} controls={controls} renderCard={(row) => <p>card {row.original.name}</p>} />)
    expect(screen.getByRole("table")).toBeInTheDocument()
  })

  it("shows the empty message in card mode too", () => {
    setWidth(400)
    render(<ServerDataTable columns={columns} data={[]} controls={controls} renderCard={() => null} noDataMessage="Nothing here" />)
    expect(screen.getByText("Nothing here")).toBeInTheDocument()
  })
})
```

Run (from `web-app/`): `pnpm test packages/data-table` → FAIL.

- [x] **Step 2: Implement**

`date-presets.ts`:

```ts
import type { DateFilterValue } from "./date-filter"

export const DATE_PRESETS = ["today", "this_week", "this_month", "last_month"] as const
export type DatePreset = (typeof DATE_PRESETS)[number]

const pad = (n: number) => String(n).padStart(2, "0")
/** Local calendar date as ISO YYYY-MM-DD — never toISOString, which is UTC. */
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const range = (from: Date, to: Date): DateFilterValue => ({ mode: "range", date1: iso(from), date2: iso(to) })

/** A preset as a closed range around `today`. Weeks start on Monday. */
export function datePresetValue(preset: DatePreset, today: Date): DateFilterValue {
  const y = today.getFullYear()
  const m = today.getMonth()
  const d = today.getDate()
  switch (preset) {
    case "today":
      return range(today, today)
    case "this_week": {
      const back = (today.getDay() + 6) % 7 // days since Monday
      return range(new Date(y, m, d - back), new Date(y, m, d - back + 6))
    }
    case "this_month":
      return range(new Date(y, m, 1), new Date(y, m + 1, 0))
    case "last_month":
      return range(new Date(y, m - 1, 1), new Date(y, m, 0))
  }
}
```

`labels.ts` adds:

```ts
  datePresets: { today: "Today", this_week: "This week", this_month: "This month", last_month: "Last month" },
```

`date-filter-control.tsx`: add prop `presets = false`; inside `FilterField`, before the `FilterSelect`:

```tsx
      {presets && (
        <div className="flex flex-wrap gap-1">
          {DATE_PRESETS.map((preset) => (
            <Button key={preset} type="button" variant="outline" size="xs" onClick={() => onChange(datePresetValue(preset, new Date()))}>
              {labels.datePresets[preset]}
            </Button>
          ))}
        </div>
      )}
```

(import `Button` from `@app/ui/button`; if `size="xs"` does not exist on the button, use `"sm"`.)

`filter-checkbox-group.tsx`:

```tsx
"use client"

import { useId } from "react"
import { Checkbox } from "@app/ui/checkbox"

/** Several values from a fixed list. The value keeps the options' order. */
export function FilterCheckboxGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: { value: T; label: string }[]
  value: T[]
  onChange: (value: T[]) => void
}) {
  const id = useId()
  const chosen = new Set(value)
  const toggle = (option: T, on: boolean) => {
    const next = new Set(chosen)
    if (on) next.add(option)
    else next.delete(option)
    onChange(options.map((o) => o.value).filter((v) => next.has(v)))
  }
  return (
    <fieldset className="space-y-1">
      <legend className="text-xs font-medium text-muted-foreground">{label}</legend>
      <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
        {options.map((o) => (
          <label key={o.value} htmlFor={`${id}-${o.value}`} className="flex items-center gap-2 text-sm">
            <Checkbox id={`${id}-${o.value}`} checked={chosen.has(o.value)} onCheckedChange={(on) => toggle(o.value, on)} />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
```

`data-table-core.tsx`: add `renderCard?: (row: Row<TData>) => React.ReactNode` to `DataTableBaseProps`, destructure it, `const isMobile = useIsMobile()` (import from `@app/ui/hooks/use-mobile`), `const asCards = Boolean(renderCard) && isMobile`. When `asCards`, render in place of the `table-container` div:

```tsx
        <ul className={cn("space-y-2", isPending && "opacity-60 transition-opacity")} aria-busy={isPending || undefined}>
          {errorMessage != null ? (
            <li role="alert" className="py-6 text-center text-destructive">{errorMessage}</li>
          ) : isLoading ? (
            Array.from({ length: SKELETON_ROWS }, (_, i) => (
              <li key={i}><Skeleton className="h-16 w-full" /></li>
            ))
          ) : rows.length === 0 ? (
            <li className="py-6 text-center text-muted-foreground">{noDataMessage}</li>
          ) : (
            rows.map((row) => <li key={row.id}>{renderCard!(row)}</li>)
          )}
        </ul>
```

The bulk bar (Task 9) is not rendered in card mode (selection is desktop-only per the feature doc): guard it with `!asCards`. The pager renders in both modes.

`package.json` exports add:

```json
    "./url-state/date-presets": "./src/url-state/date-presets.ts",
    "./filters/filter-checkbox-group": "./src/filters/filter-checkbox-group.tsx",
```

Run → PASS.

- [x] **Step 3: Gate and commit**

Run (repo root): `make check-web && make test-web`.

```bash
git add web-app/packages/data-table
git commit -m "feat(data-table): phone cards, date presets and a checkbox-group filter"
```

---

## Task 11: The transactions page — list, filters, cards, empty states

Spec §4.1, §4.2. Copy the shape of `.claude/skills/web-app-patterns/examples/orders/` (read all its files first).

**Files (all under `web-app/apps/web/src/`):**
- Create: `components/transactions/{transactions-table-params.ts,transactions-table-params.test.ts,use-transactions-table-state.ts,use-transactions-table-state.test.tsx,use-categories.ts,use-categories.test.tsx,format.ts,format.test.ts,use-transaction-columns.tsx,transaction-filters.tsx,transaction-filters.test.tsx,transaction-card.tsx,transactions-table.tsx,transactions-table.test.tsx}`, `app/(dashboard)/transactions/page.tsx`, `app/(dashboard)/transactions/loading.tsx`
- Modify: `lib/hub-nav.ts`

**Interfaces:**
- Consumes (generated, `@app/api-client/endpoints/transactions` and `@app/api-client/types`): `useListTransactions`, `useListTransactionCategories`, `getListTransactionsUrl`, `ListTransactionsOrdering`, `ListTransactionsParams`, `Category`, `CategoryResponse`, `TransactionResponse`. From earlier tasks: `enableRowSelection`, `renderBulkActions`, `renderCard`, `FilterCheckboxGroup`, `DateFilterControl presets`.
- Produces:
  - `TRANSACTIONS_PAGE_SIZE = 20`, `transactionsParsers`, `loadTransactionsTableParams`, `TransactionsFilters { categories: Category[]; amountMin: string | null; amountMax: string | null; recurring: boolean | null; date: DateFilterValue }`, `EMPTY_TRANSACTIONS_FILTERS`, `toTransactionsFilters`, `fromTransactionsFilters`, `toTransactionsQuery(v): ListTransactionsParams`, `hasActiveTransactionsFilters(v): boolean`
  - `useTransactionsTableState`
  - `useCategories(): { categories: CategoryResponse[]; label: (slug: string) => string }`
  - `formatAmount(amount: string): string` (EUR, `Intl.NumberFormat`), `formatDate(iso: string): string`, `isExpense(amount: string): boolean`, `isLowConfidence(c: number): boolean` (`< 0.7`)
  - `useTransactionColumns(label: (slug: string) => string)` — read-only columns here; Task 12 adds the category picker, the row menu and an `actions` argument
  - `TransactionsTable` (the client view)

- [x] **Step 1: Params file + failing tests**

`transactions-table-params.ts`:

```ts
import {
  createLoader,
  compactQuery,
  dateMode,
  dateVal,
  DATE_FILTER_MODES,
  parseAsArrayOf,
  parseAsBoolean,
  parseAsInteger,
  parseAsString,
  parseAsStringLiteral,
  toOffsetLimit,
  type DateFilterValue,
  type Values,
} from "@app/data-table/url-state/params"
import { EMPTY_DATE_FILTER, isDateFilterActive } from "@app/data-table/url-state/date-filter"
import { Category, ListTransactionsOrdering, type ListTransactionsParams } from "@app/api-client/types"

/** ≤ the route's `limit` cap (100). */
export const TRANSACTIONS_PAGE_SIZE = 20

/** One parser set per API contract: every key is forwarded by toTransactionsQuery (except date_mode). */
export const transactionsParsers = {
  page: parseAsInteger.withDefault(1),
  ordering: parseAsStringLiteral(Object.values(ListTransactionsOrdering)),
  search: parseAsString.withDefault(""),
  category: parseAsArrayOf(parseAsStringLiteral(Object.values(Category))).withDefault([]),
  amount_min: parseAsString,
  amount_max: parseAsString,
  is_recurring: parseAsBoolean,
  date_mode: parseAsStringLiteral(DATE_FILTER_MODES), // UI-only
  date_from: parseAsString,
  date_to: parseAsString,
}

export const loadTransactionsTableParams = createLoader(transactionsParsers)

type TransactionsValues = Values<typeof transactionsParsers>

export interface TransactionsFilters {
  categories: Category[]
  amountMin: string | null
  amountMax: string | null
  recurring: boolean | null
  date: DateFilterValue
}

export const EMPTY_TRANSACTIONS_FILTERS: TransactionsFilters = {
  categories: [],
  amountMin: null,
  amountMax: null,
  recurring: null,
  date: EMPTY_DATE_FILTER,
}

export function toTransactionsFilters(v: TransactionsValues): TransactionsFilters {
  return {
    categories: v.category,
    amountMin: v.amount_min,
    amountMax: v.amount_max,
    recurring: v.is_recurring,
    date: { mode: v.date_mode ?? dateMode(v.date_from, v.date_to), date1: v.date_from ?? "", date2: v.date_to ?? "" },
  }
}

export function fromTransactionsFilters(f: TransactionsFilters): Partial<TransactionsValues> {
  return {
    category: f.categories.length > 0 ? f.categories : null,
    amount_min: f.amountMin || null,
    amount_max: f.amountMax || null,
    is_recurring: f.recurring,
    date_mode: f.date.mode,
    date_from: dateVal(f.date, 1),
    date_to: dateVal(f.date, 2),
  }
}

export function toTransactionsQuery(v: TransactionsValues): ListTransactionsParams {
  const { date } = toTransactionsFilters(v)
  return compactQuery({
    ...toOffsetLimit(v.page, TRANSACTIONS_PAGE_SIZE),
    ordering: v.ordering,
    search: v.search,
    category: v.category.length > 0 ? v.category : null,
    amount_min: v.amount_min,
    amount_max: v.amount_max,
    is_recurring: v.is_recurring,
    date_from: dateVal(date, 1),
    date_to: dateVal(date, 2),
  })
}

/** Any filter or search narrows the list: the empty state then offers to clear them. */
export function hasActiveTransactionsFilters(v: TransactionsValues): boolean {
  const f = toTransactionsFilters(v)
  return (
    v.search !== "" ||
    f.categories.length > 0 ||
    f.amountMin != null ||
    f.amountMax != null ||
    f.recurring != null ||
    isDateFilterActive(f.date)
  )
}
```

`transactions-table-params.test.ts`:

```ts
import { describe, it, expect } from "vitest"
import { getListTransactionsUrl } from "@app/api-client/endpoints/transactions"
import {
  fromTransactionsFilters,
  hasActiveTransactionsFilters,
  loadTransactionsTableParams,
  toTransactionsFilters,
  toTransactionsQuery,
} from "./transactions-table-params"

const load = (qs: string) => loadTransactionsTableParams(new URLSearchParams(qs))

describe("transactions table params", () => {
  it("round-trips every filter key", () => {
    const values = load(
      "category=salary,atm&amount_min=-100&amount_max=50.5&is_recurring=true&date_mode=range&date_from=2026-01-01&date_to=2026-02-01",
    )
    expect(fromTransactionsFilters(toTransactionsFilters(values))).toEqual({
      category: ["salary", "atm"],
      amount_min: "-100",
      amount_max: "50.5",
      is_recurring: true,
      date_mode: "range",
      date_from: "2026-01-01",
      date_to: "2026-02-01",
    })
  })

  it("drops an unknown category and an unknown ordering", () => {
    const v = load("category=salary,retired_slug&ordering=-fingerprint")
    expect(v.ordering).toBeNull()
    expect(toTransactionsFilters(v).categories).toEqual(["salary"])
  })

  it("builds the query: offset/limit, no date_mode, no unset keys", () => {
    expect(toTransactionsQuery(load("page=3&search=rewe&date_mode=gte&date_from=2026-01-01&ordering=amount"))).toEqual({
      offset: 40,
      limit: 20,
      search: "rewe",
      ordering: "amount",
      date_from: "2026-01-01",
    })
  })

  it("never forwards a date the mode hides", () => {
    expect(toTransactionsQuery(load("date_mode=gte&date_to=2026-02-01"))).not.toHaveProperty("date_to")
  })

  it("repeats category in the request URL", () => {
    const url = getListTransactionsUrl(toTransactionsQuery(load("category=salary,atm")))
    expect(url).toContain("category=salary&category=atm")
  })

  it("knows when the list is narrowed", () => {
    expect(hasActiveTransactionsFilters(load(""))).toBe(false)
    expect(hasActiveTransactionsFilters(load("search=x"))).toBe(true)
    expect(hasActiveTransactionsFilters(load("is_recurring=false"))).toBe(true)
  })
})
```

`use-transactions-table-state.ts`:

```ts
import { createUrlTableStateHook } from "@app/data-table/url-state/use-url-table-state"
import { fromTransactionsFilters, toTransactionsFilters, transactionsParsers } from "./transactions-table-params"

export const useTransactionsTableState = createUrlTableStateHook({
  parsers: transactionsParsers,
  toFilters: toTransactionsFilters,
  fromFilters: fromTransactionsFilters,
})
```

`use-transactions-table-state.test.tsx` — copy `examples/orders/use-orders-table-state.test.tsx`, rename, and assert: setting `categories: ["salary"]` writes `category=salary` and resets `page`; `setSearch("rewe")` writes `search=rewe`.

Run (from `web-app/`): `pnpm test apps/web/src/components/transactions` → PASS for params and hook once written (they pin existing generated code; the URL test fails if Task 4's check was skipped).

- [x] **Step 2: Categories hook and formatters, test first**

`format.test.ts`:

```ts
import { describe, it, expect } from "vitest"
import { formatAmount, isExpense, isLowConfidence } from "./format"

describe("format", () => {
  it("formats an amount string as EUR without float maths", () => {
    expect(formatAmount("-4.50")).toMatch(/4[.,]50/)
    expect(formatAmount("1234567890.12")).toMatch(/1.?234.?567.?890[.,]12/)
  })
  it("reads the sign from the string", () => {
    expect(isExpense("-0.01")).toBe(true)
    expect(isExpense("0.00")).toBe(false)
  })
  it("flags confidence below 70%", () => {
    expect(isLowConfidence(0.69)).toBe(true)
    expect(isLowConfidence(0.7)).toBe(false)
  })
})
```

`format.ts`:

```ts
const eur = new Intl.NumberFormat(undefined, { style: "currency", currency: "EUR" })
const day = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" })

/**
 * EUR for display. Intl formats a decimal string exactly (no float rounding)
 * in engines that support string input; the cast is only for the DOM lib's types.
 */
export const formatAmount = (amount: string) => eur.format(amount as unknown as number)

export const isExpense = (amount: string) => amount.trim().startsWith("-") && /[1-9]/.test(amount)

/** ISO YYYY-MM-DD → "3 Mar 2026", read as a local calendar date. */
export function formatDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number)
  return day.format(new Date(y, m - 1, d))
}

export const LOW_CONFIDENCE = 0.7
export const isLowConfidence = (confidence: number) => confidence < LOW_CONFIDENCE
```

`use-categories.ts`:

```ts
"use client"

import { useMemo } from "react"
import { useListTransactionCategories } from "@app/api-client/endpoints/transactions"

/**
 * The category list from the server, fetched once per session. `label` falls
 * back to the slug until it arrives, and for a slug the list no longer has.
 */
export function useCategories() {
  const { data } = useListTransactionCategories({ query: { staleTime: Infinity } })
  return useMemo(() => {
    const categories = data ?? []
    const labels = new Map<string, string>(categories.map((c) => [c.value, c.label]))
    return { categories, label: (slug: string) => labels.get(slug) ?? slug }
  }, [data])
}
```

`use-categories.test.tsx`: mock `@app/api-client/endpoints/transactions` (`vi.mock(..., async (orig) => ({ ...(await orig()), useListTransactionCategories: vi.fn() }))`), assert `label("food_groceries")` is `"food_groceries"` while `data` is `undefined` and `"Food & Groceries"` once it is `[{ value: "food_groceries", label: "Food & Groceries" }]`.

Run → PASS.

- [x] **Step 3: Columns, card, filters, table, page, nav**

`use-transaction-columns.tsx` (Task 12 extends it with the menu and picker):

```tsx
"use client"

import { useMemo } from "react"
import type { ColumnDef } from "@app/data-table/columns"
import type { TransactionResponse } from "@app/api-client/types"
import { cn } from "@app/core/lib/utils"
import { formatAmount, formatDate, isExpense, isLowConfidence } from "./format"

// Sortable ids are ListTransactionsOrdering fields (date, amount, merchant).
export function useTransactionColumns(label: (slug: string) => string): ColumnDef<TransactionResponse>[] {
  return useMemo<ColumnDef<TransactionResponse>[]>(
    () => [
      { accessorKey: "date", id: "date", header: "Date", meta: { width: "8rem" }, cell: ({ row }) => formatDate(row.original.date) },
      { accessorKey: "merchant", id: "merchant", header: "Merchant" },
      {
        accessorKey: "amount",
        id: "amount",
        header: "Amount",
        meta: { align: "right", width: "8rem" },
        cell: ({ row }) => (
          <span className={isExpense(row.original.amount) ? "text-destructive" : "text-success"}>
            {formatAmount(row.original.amount)}
          </span>
        ),
      },
      { id: "category", header: "Category", enableSorting: false, cell: ({ row }) => label(row.original.category) },
      {
        id: "confidence",
        header: "Confidence",
        enableSorting: false,
        meta: { align: "right", width: "6rem" },
        cell: ({ row }) => {
          const c = row.original.confidence
          return <span className={cn(isLowConfidence(c) ? "text-warning" : "text-muted-foreground")}>{Math.round(c * 100)}%</span>
        },
      },
    ],
    [label],
  )
}
```

(Check `globals.css` for `text-success` / `text-warning` tokens; if absent use `text-emerald-600 dark:text-emerald-400` / `text-amber-600 dark:text-amber-400`.)

`transaction-card.tsx`:

```tsx
import type { TransactionResponse } from "@app/api-client/types"
import { Card, CardContent } from "@app/ui/card"
import { formatAmount, formatDate, isExpense } from "./format"

export function TransactionCard({ transaction, categoryLabel }: { transaction: TransactionResponse; categoryLabel: string }) {
  return (
    <Card size="sm">
      <CardContent className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate font-medium">{transaction.merchant}</p>
          <p className="text-xs text-muted-foreground">{`${formatDate(transaction.date)} · ${categoryLabel}`}</p>
        </div>
        <span className={isExpense(transaction.amount) ? "text-destructive tabular-nums" : "text-success tabular-nums"}>
          {formatAmount(transaction.amount)}
        </span>
      </CardContent>
    </Card>
  )
}
```

(drop `size="sm"` if `Card` has no size prop.)

`transaction-filters.tsx` — `TransactionsFilterPanel` and `TransactionsFilterChips`, both `{ filters, setFilters, categories, label }`:
- Panel: `FilterPanel` with `activeCount` = count of `[categories.length>0, amountMin!=null, amountMax!=null, recurring!=null, isDateFilterActive(date)]`; `onClearAll={() => setFilters(EMPTY_TRANSACTIONS_FILTERS)}`. Inside: `<DateFilterControl label="Date" presets value={filters.date} onChange={(date) => setFilters((f) => ({ ...f, date }))} />`; `<FilterCheckboxGroup label="Category" options={categories.map((c) => ({ value: c.value, label: c.label }))} value={filters.categories} onChange={(categories) => setFilters((f) => ({ ...f, categories }))} />`; two `FilterField`s with `<Input type="number" step="0.01" inputMode="decimal">` for min and max amount (empty string → `null`); a `FilterSelect` for recurring with options `""` "Any", `"true"` "Recurring", `"false"` "Not recurring".
- Chips: one chip per selected category (`Category: ${label(c)}`, remove that one), `Amount ≥ ${amountMin}`, `Amount ≤ ${amountMax}`, `Recurring`/`Not recurring`, and `dateFilterLabel("Date", date)`.

`transaction-filters.test.tsx`: render the chips with `{ categories: ["salary", "atm"], amountMin: "-50", … }` and assert each chip text, that removing the `salary` chip calls `setFilters` with a function producing `categories: ["atm"]`, and that the panel's badge shows the active count.

`transactions-table.tsx`:

```tsx
"use client"

import { keepPreviousData } from "@tanstack/react-query"
import { useListTransactions } from "@app/api-client/endpoints/transactions"
import type { TransactionResponse } from "@app/api-client/types"
import { ServerDataTable } from "@app/data-table/server-data-table"
import { TableSearchInput } from "@app/data-table/table-search-input"
import { toServerTableControls } from "@app/data-table/table-state"
import { Button } from "@app/ui/button"
import { messages } from "@app/core/constants/messages"
import { TransactionsFilterChips, TransactionsFilterPanel } from "./transaction-filters"
import { TransactionCard } from "./transaction-card"
import { EMPTY_TRANSACTIONS_FILTERS, TRANSACTIONS_PAGE_SIZE, hasActiveTransactionsFilters, toTransactionsQuery } from "./transactions-table-params"
import { useCategories } from "./use-categories"
import { useTransactionColumns } from "./use-transaction-columns"
import { useTransactionsTableState } from "./use-transactions-table-state"

export function TransactionsTable() {
  const state = useTransactionsTableState()
  const { categories, label } = useCategories()
  const columns = useTransactionColumns(label)
  const { data, isPending, isPlaceholderData, isError } = useListTransactions(toTransactionsQuery(state.query), {
    query: { placeholderData: keepPreviousData },
  })
  const narrowed = hasActiveTransactionsFilters(state.query)

  const empty = narrowed ? (
    <div className="space-y-2">
      <p>No transactions match your filters.</p>
      <Button variant="outline" size="sm" onClick={() => { state.setSearch(""); state.setFilters(EMPTY_TRANSACTIONS_FILTERS) }}>
        Clear filters
      </Button>
    </div>
  ) : (
    <p>No transactions yet.</p>
  )

  return (
    <ServerDataTable<TransactionResponse, unknown>
      columns={columns}
      data={data?.items ?? []}
      controls={toServerTableControls(state, { pageSize: TRANSACTIONS_PAGE_SIZE, totalCount: data?.total ?? 0 })}
      isLoading={isPending}
      isPending={isPlaceholderData}
      errorMessage={isError && !data ? messages.toasts.genericError : undefined}
      noDataMessage={empty}
      renderCard={(row) => <TransactionCard transaction={row.original} categoryLabel={label(row.original.category)} />}
      toolbar={
        <>
          <TableSearchInput value={state.search} onChange={state.setSearch} placeholder="Search merchants" />
          <TransactionsFilterPanel filters={state.filters} setFilters={state.setFilters} categories={categories} />
        </>
      }
      belowToolbar={<TransactionsFilterChips filters={state.filters} setFilters={state.setFilters} label={label} />}
    />
  )
}
```

(Task 12 adds the "Add transaction" `headerActions`, selection and the menu; the "No transactions yet" state gains its **Add a transaction** button there.)

`transactions-table.test.tsx`: wrap in `withNuqsTestingAdapter` from `@app/data-table/url-state/testing`; mock `useListTransactions` and `useListTransactionCategories`. Assert: (1) `useListTransactions` was called with `{ offset: 0, limit: 20 }` for an empty URL and with `category: ["salary"]` for `?category=salary`; (2) with `items: []` and no filters the text "No transactions yet." shows; (3) with `items: []` and `?search=x` "No transactions match your filters." and a **Clear filters** button show; (4) a row's confidence `0.5` renders `50%` with the warning class.

`app/(dashboard)/transactions/page.tsx`:

```tsx
import { TransactionsTable } from "@/components/transactions/transactions-table"

export default function TransactionsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Transactions</h1>
      <TransactionsTable />
    </div>
  )
}
```

`loading.tsx`: copy `app/(dashboard)/loading.tsx`'s shape — a heading skeleton and five `Skeleton className="h-10 w-full"` rows. Read `references/pages.md` for page copy and loading rules.

`lib/hub-nav.ts`:

```ts
import { ArrowLeftRightIcon, HomeIcon } from "lucide-react"
…
export const HUB_NAV: NavItem[] = [
  { title: "Home", url: "/home", icon: HomeIcon },
  { title: "Transactions", url: "/transactions", icon: ArrowLeftRightIcon },
]
```

- [x] **Step 4: Run, check by hand, commit**

Run (repo root): `make check-web && make test-web` → PASS.
By hand (`make seed-transactions CLERK_ID=…` first, then the stack per `/run-stack`, web on 3010): open `/transactions`; apply a category filter, sort by amount, page 2, press Back — chips, rows, pager move together; narrow the window below 768px — cards replace the table.

```bash
git add web-app/apps/web/src
git commit -m "feat(transactions): the transactions page — list, filters, search, sort, cards"
```

---

## Task 12: Add, edit, delete one, recategorise one

Spec §4.2 (dialog, row menu, chip), §4.4. Review Focus 3.

**Files (under `web-app/apps/web/src/components/transactions/`):**
- Create: `amount-input.ts`, `amount-input.test.ts`, `use-invalidate-transactions.ts`, `transaction-form-dialog.tsx`, `transaction-form-dialog.test.tsx`, `delete-transactions-dialog.tsx`, `category-picker.tsx`
- Modify: `use-transaction-columns.tsx`, `transactions-table.tsx`, `transactions-table.test.tsx`

**Interfaces:**
- Consumes: `useCreateTransaction`, `useUpdateTransaction`, `useDeleteTransaction`, `getListTransactionsQueryKey` (generated); `TransactionCreate`, `TransactionUpdate` types; `AlertDialog*`, `Switch`, `Textarea`, `Dialog*`, `DropdownMenu*` from `@app/ui`; `DatePicker` from `@app/components/forms/date-picker`; `ApiError` from `@app/api-client` (check its export path in `src/index.ts`).
- Produces:
  - `parseAmount(input: string): string | null` — `"-4,50"` → `"-4.50"`, `"12"` → `"12.00"`, `null` for invalid
  - `useInvalidateTransactions(): () => Promise<void>`
  - `TransactionFormDialog({ mode: "add" } | { mode: "edit"; transaction }, open, onOpenChange)`
  - `DeleteTransactionsDialog({ ids, open, onOpenChange, onDeleted? })` — 1 id → `deleteTransaction`, more → `batchDeleteTransactions` (Task 13 uses it for bulk)
  - `CategoryPicker({ value, onChange, categories })` — a dropdown menu of categories
  - `useTransactionColumns(label, actions: { onEdit: (t) => void; onDelete: (t) => void; onRecategorise: (t, category: Category) => void; categories: CategoryResponse[] })`

- [x] **Step 1: Amount parsing, test first**

`amount-input.test.ts`:

```ts
import { describe, it, expect } from "vitest"
import { parseAmount } from "./amount-input"

describe("parseAmount", () => {
  it.each([
    ["-4,50", "-4.50"],
    ["-4.5", "-4.50"],
    ["12", "12.00"],
    [" 2400.00 ", "2400.00"],
    ["+3,2", "3.20"],
    ["9999999999.99", "9999999999.99"],
  ])("%s → %s", (input, expected) => expect(parseAmount(input)).toBe(expected))

  it.each(["", "abc", "4,505", "1.2.3", "-", "12345678901.00", "1e3"])("rejects %s", (input) =>
    expect(parseAmount(input)).toBeNull(),
  )
})
```

`amount-input.ts`:

```ts
const AMOUNT = /^([+-]?)(\d{1,10})(?:[.,](\d{1,2}))?$/

/**
 * A typed amount as the API's decimal string: a comma or a dot for the
 * decimals, at most two places and ten integer digits (NUMERIC(12,2)).
 * Never parsed to a float. Returns null when it is not an amount.
 */
export function parseAmount(input: string): string | null {
  const match = AMOUNT.exec(input.trim())
  if (!match) return null
  const [, sign, whole, cents = ""] = match
  return `${sign === "-" ? "-" : ""}${whole}.${cents.padEnd(2, "0")}`
}
```

Run → PASS.

- [x] **Step 2: The dialog, test first**

`transaction-form-dialog.test.tsx` — mock `useCreateTransaction`/`useUpdateTransaction` (capture the options passed and expose a `mutate` spy), mock `useListTransactionCategories`, wrap in a `QueryClientProvider`. Cases:
1. Add: with the dialog's date preset to `2026-03-03` (pass a `today` prop, or mock the clock with `vi.setSystemTime`), fill merchant `Späti`, amount `-4,50`, pick a category, submit → `mutate` called with `{ data: { date: "2026-03-03", merchant: "Späti", amount: "-4.50", category: "food_groceries", description: null, is_recurring: false, allow_duplicate: false } }`; the create hook received `mutation.meta.silentStatuses: [409]`.
2. Amount `4,505` → inline error "Enter an amount like -4.50", `mutate` not called (Review Focus 3).
3. Add, `mutate`'s `onError` invoked with `new ApiError(409, …)` → the notice "You already have a transaction on 3 Mar 2026 at Späti for −€4.50." and buttons **Add anyway** / **Cancel** show; **Add anyway** calls `mutate` again with `allow_duplicate: true`; editing the merchant field hides the notice.
4. Edit an existing `{ merchant: "Späti", amount: "-4.50", description: "Old", … }`: change only the description to empty and submit → `mutate({ transactionId, data: { description: null } })`; submit with no change → `mutate({ transactionId, data: {} })` is **not** called and the dialog closes.

`transaction-form-dialog.tsx` — a `Dialog` with a `<form>`; local form state with `useState` (form state, not list state). Fields: `DatePicker` from `@app/components/forms/date-picker` (required; default today in add mode, as a local ISO date — build it like `date-presets.ts`'s `iso`, never `toISOString()`), `Input` merchant (required, `maxLength={255}`), `Input` amount (`inputMode="decimal"`, placeholder `-9.99`, hint "Negative for money out"), category `Select` (or `FilterSelect`-style native select, options from `useCategories`), `Textarea` description (`maxLength={1000}`), `Switch` recurring. On submit:

```tsx
const amount = parseAmount(form.amount)
if (!amount) return setAmountError("Enter an amount like -4.50")
const description = form.description.trim() || null
if (mode === "add") {
  create.mutate(
    { data: { date: form.date, merchant: form.merchant, amount, category: form.category, description, is_recurring: form.recurring, allow_duplicate: allowDuplicate } },
    {
      onSuccess: async () => { await invalidate(); onOpenChange(false) },
      onError: (error) => { if (error instanceof ApiError && error.status === 409) setDuplicate(true) },
    },
  )
} else {
  const data = diff(transaction, { date: form.date, merchant: form.merchant.trim(), amount, description, category: form.category, is_recurring: form.recurring })
  if (Object.keys(data).length === 0) return onOpenChange(false)
  update.mutate({ transactionId: transaction.id, data }, { onSuccess: async () => { await invalidate(); onOpenChange(false) } })
}
```

with `diff` returning only keys whose value differs from the transaction's (`amount` compared via `parseAmount(transaction.amount)`), the create hook built as `useCreateTransaction({ mutation: { meta: { silentStatuses: [409] } } })`, and every `onChange` calling `setDuplicate(false)`. The duplicate notice (`role="alert"`) text is built as a template literal in the component body (testing skill trap: no JSX text around an expression):

```tsx
const duplicateText = `You already have a transaction on ${formatDate(form.date)} at ${form.merchant.trim()} for ${formatAmount(amount ?? "0")}.`
```

`use-invalidate-transactions.ts`:

```ts
"use client"

import { useQueryClient } from "@tanstack/react-query"
import { getListTransactionsQueryKey } from "@app/api-client/endpoints/transactions"

/** Refetch every page of the list after a write. The key without params is a prefix of each page's key. */
export function useInvalidateTransactions() {
  const queryClient = useQueryClient()
  return () => queryClient.invalidateQueries({ queryKey: getListTransactionsQueryKey() })
}
```

(Check the generated `getListTransactionsQueryKey()` with no argument returns `["/api/v1/transactions"]`; if it returns `[url, undefined]`, use `{ queryKey: [getListTransactionsQueryKey()[0]] }`.)

- [x] **Step 3: Delete confirm, category picker, row menu, wiring**

`delete-transactions-dialog.tsx`:

```tsx
"use client"

import { useBatchDeleteTransactions, useDeleteTransaction } from "@app/api-client/endpoints/transactions"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@app/ui/alert-dialog"
import { useInvalidateTransactions } from "./use-invalidate-transactions"

/** Confirms, then deletes one transaction or a batch (all or nothing). */
export function DeleteTransactionsDialog({
  ids, open, onOpenChange, onDeleted,
}: { ids: string[]; open: boolean; onOpenChange: (open: boolean) => void; onDeleted?: () => void }) {
  const one = useDeleteTransaction()
  const many = useBatchDeleteTransactions()
  const invalidate = useInvalidateTransactions()
  const done = async () => { await invalidate(); onDeleted?.(); onOpenChange(false) }
  const title = ids.length === 1 ? "Delete this transaction?" : `Delete ${ids.length} transactions?`
  const confirm = () =>
    ids.length === 1
      ? one.mutate({ transactionId: ids[0] }, { onSuccess: done })
      : many.mutate({ data: { ids } }, { onSuccess: done })
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>It disappears from your lists and analytics.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction variant="destructive" disabled={one.isPending || many.isPending} onClick={confirm}>Delete</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
```

(adapt `variant` to whatever the installed `AlertDialogAction` accepts.)

`category-picker.tsx`: a `DropdownMenu` whose trigger is a `Badge`-styled `<button>` showing the current label (pass `className={cn(badgeVariants({ variant: "outline" }))}` per `components.md`'s "trigger already a button" rule) and whose items are the categories; `onChange(value)`.

`use-transaction-columns.tsx`: the signature becomes `useTransactionColumns(label, { categories, onEdit, onDelete, onRecategorise })`; the category cell renders `<CategoryPicker value={row.original.category} categories={categories} label={label} onChange={(c) => onRecategorise(row.original, c)} />`; append a last column `{ id: "actions", header: "", enableSorting: false, enableHiding: false, meta: { width: "3rem" } }` rendering a `DropdownMenu` (trigger: ghost icon button `MoreHorizontal`, `aria-label="Row actions"`) with **Edit** and **Delete** items.

`transactions-table.tsx`: hold `const [editing, setEditing] = useState<TransactionResponse | "new" | null>(null)` and `const [deleting, setDeleting] = useState<string[] | null>(null)` (dialog state, not list state); `const update = useUpdateTransaction()`; `onRecategorise = (t, category) => update.mutate({ transactionId: t.id, data: { category } }, { onSuccess: invalidate })`; `headerActions={<Button size="sm" onClick={() => setEditing("new")}><Plus /> Add transaction</Button>}`; the "No transactions yet." empty state gains a **Add a transaction** button calling `setEditing("new")`; render `<TransactionFormDialog …>` and `<DeleteTransactionsDialog …>` beside the table.

Extend `transactions-table.test.tsx`: clicking **Add transaction** opens the dialog (its title "Add a transaction" shows); choosing **Delete** in a row's menu opens the confirm with "Delete this transaction?".

- [x] **Step 4: Run, check by hand, commit**

Run (repo root): `make check-web && make test-web` → PASS.
By hand: add a transaction; add the same one again → the duplicate notice, then **Add anyway**; edit it; recategorise from the chip; delete it.

```bash
git add web-app/apps/web/src/components/transactions
git commit -m "feat(transactions): add, edit, delete and recategorise one transaction"
```

---

## Task 13: Bulk recategorise and bulk delete

Spec §4.2 (bulk), §3.4.

**Files:**
- Create: `web-app/apps/web/src/components/transactions/bulk-category-dialog.tsx`
- Modify: `web-app/apps/web/src/components/transactions/transactions-table.tsx`, `transactions-table.test.tsx`

**Interfaces:**
- Consumes: `useBatchUpdateTransactionCategory` (generated), Task 9's `enableRowSelection` / `renderBulkActions`, Task 12's `DeleteTransactionsDialog`, `useInvalidateTransactions`, `useCategories`.
- Produces: `BulkCategoryDialog({ ids, open, onOpenChange, onDone })`.

- [x] **Step 1: Failing test** — in `transactions-table.test.tsx`, with two rows: select both checkboxes → "2 selected" and buttons **Recategorise** and **Delete** show; **Delete** opens "Delete 2 transactions?"; confirming calls the batch-delete `mutate` with `{ data: { ids: [id1, id2] } }`. **Recategorise** opens the dialog; choosing `shopping` and confirming calls the batch-update `mutate` with `{ data: { ids: [id1, id2], category: "shopping" } }`.
- [x] **Step 2: Implement** `bulk-category-dialog.tsx` — a `Dialog` titled `Recategorise ${ids.length} transactions` with a native category select (options from `useCategories`) and **Apply** → `mutate({ data: { ids, category } }, { onSuccess: async () => { await invalidate(); onDone(); onOpenChange(false) } })`. In `transactions-table.tsx`: `enableRowSelection` and

```tsx
renderBulkActions={(selected, clear) => (
  <>
    <Button size="sm" variant="outline" onClick={() => setBulk({ kind: "category", ids: selected.map((t) => t.id), clear })}>Recategorise</Button>
    <Button size="sm" variant="outline" onClick={() => setBulk({ kind: "delete", ids: selected.map((t) => t.id), clear })}>Delete</Button>
  </>
)}
```

with `bulk` dialog state rendering `BulkCategoryDialog` / `DeleteTransactionsDialog` and calling `clear` on success.
- [x] **Step 3: Run, by hand, commit**

Run (repo root): `make check-web && make test-web` → PASS. By hand: select three rows, recategorise; select two, delete; change page with a selection — it clears.

```bash
git add web-app/apps/web/src/components/transactions
git commit -m "feat(transactions): bulk recategorise and bulk delete"
```

---

## Task 14: Settings — Delete all transactions

Spec §4.5.

**Files:**
- Create: `web-app/apps/web/src/components/settings/data-settings.tsx`, `data-settings.test.tsx`
- Modify: `web-app/apps/web/src/app/(dashboard)/layout.tsx` (`SETTINGS_TABS` and one import only)

**Interfaces:**
- Consumes: `useDeleteAllTransactions`, `useListTransactions` (generated), `useInvalidateTransactions` (Task 12), `AlertDialog*`, `SettingSection`.
- Produces: `DataSettings`.

- [x] **Step 1: Failing test** `data-settings.test.tsx` — mock `useListTransactions` → `{ data: { total: 12, items: [] } }` and `useDeleteAllTransactions` → `{ mutate }`. Assert: the button **Delete all transactions** opens a dialog reading "Permanently deletes all 12 transactions. This cannot be undone."; confirming calls `mutate()`; with `total: 0` the button is disabled.
- [x] **Step 2: Implement**

```tsx
"use client"

import { useState } from "react"
import { useDeleteAllTransactions, useListTransactions } from "@app/api-client/endpoints/transactions"
import { SettingSection } from "@app/ui/setting-section"
import { Button } from "@app/ui/button"
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@app/ui/alert-dialog"
import { useInvalidateTransactions } from "@/components/transactions/use-invalidate-transactions"

export function DataSettings() {
  const [open, setOpen] = useState(false)
  const total = useListTransactions({ limit: 1 }).data?.total ?? 0
  const deleteAll = useDeleteAllTransactions()
  const invalidate = useInvalidateTransactions()
  const description = `Permanently deletes all ${total} transactions. This cannot be undone.`

  return (
    <div className="space-y-6">
      <SettingSection title="Transactions">
        <div className="flex items-center justify-between gap-4">
          <p className="text-sm text-muted-foreground">Remove every transaction you have.</p>
          <Button variant="destructive" size="sm" disabled={total === 0} onClick={() => setOpen(true)}>
            Delete all transactions
          </Button>
        </div>
      </SettingSection>
      <AlertDialog open={open} onOpenChange={setOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete all transactions?</AlertDialogTitle>
            <AlertDialogDescription>{description}</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={deleteAll.isPending}
              onClick={() => deleteAll.mutate(undefined, { onSuccess: async () => { await invalidate(); setOpen(false) } })}
            >
              Delete all
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
```

`layout.tsx`: `import { Database } from "lucide-react"` (add to the existing lucide import) and `import { DataSettings } from "@/components/settings/data-settings"`; append to `SETTINGS_TABS`:

```tsx
  {
    id: "data",
    label: "Data",
    icon: <Database className="w-5 h-5" />,
    content: <DataSettings />,
  },
```

- [x] **Step 3: Run, by hand, commit**

Run (repo root): `make check-web && make test-web` → PASS. By hand: Settings → Data → delete all → the list is empty and shows "No transactions yet.".

```bash
git add web-app/apps/web/src/components/settings web-app/apps/web/src/app/\(dashboard\)/layout.tsx
git commit -m "feat(settings): delete all transactions"
```

---

## Task 15: Docs

Spec §9. No code.

**Files:**
- Create: `docs/data-model/transaction.md`
- Modify: `docs/data-model/README.md`, `docs/product/features/transactions.md`, `docs/product/features/categorisation.md`, `docs/TODO.md`, `docs/architecture/server.md` (module tree §1, event table §8), `server/CLAUDE.md` (GDPR section only), `.claude/skills/web-app-patterns/references/data-tables.md`

- [ ] **Step 1: `docs/data-model/transaction.md`** — follow `docs/data-model/README.md` §2 and `account.md`'s shape. Status block: `shipped · Owner: Tiziano · Last updated: <today>`; **Describes:** `transactions.md`, `categorisation.md`; **Source of truth:** `server/app/modules/transaction/models.py`, `schemas.py` (`CATEGORIES`) and Task 2's revision id. Sections: §1 Approach (one row per movement; user-owned; the category list on the server, served by `GET /transactions/categories`); §2 the schema sketch from spec §2; §3 indexes and the query each serves (`ix_transaction_user_id_date` → the list; `ix_transaction_user_id_fingerprint` → the duplicate check and step 4's import); §4 decisions, numbered and dated 13 Oct 2026 — D1 date only; D2 slugs in `VARCHAR`, no DB constraint, labels by API (rejected: a Postgres enum, a CHECK, a `category` table) and how to add/rename/remove a category; D3 the fingerprint recipe verbatim and why `Decimal`; D4 soft delete one or a batch, hard delete for delete-all and erasure; D5 the manual duplicate check (409, `allow_duplicate`, soft-deleted rows don't count, edits don't check); §5 deferred (indexes on `category` / active rows; undo); §6 field map: each field of `transactions.md` §3 → its column.
- [ ] **Step 2: `docs/data-model/README.md`** map row: `| [transaction.md](./transaction.md) | [transactions](../product/features/transactions.md), [categorisation](../product/features/categorisation.md) | transaction | transaction | built |`.
- [ ] **Step 3: `docs/product/features/transactions.md`** — `Data model:` → `[transaction.md](../../data-model/transaction.md)`; §2 Filter: "by category (one or several)"; §2 Delete all: "permanently"; §2 Empty state: "a prompt to add a transaction (to upload a CSV once CSV import ships)"; §3 "a **date**" (not "date and time"); §4 replace the Duplicates bullet with: "Each transaction gets a fingerprint from its user, date, merchant, amount and description. The import skips a row whose fingerprint already exists; adding one by hand that matches an existing transaction asks before it is saved."; §6 delete the "Manual duplicates" question; `Last updated`.
- [ ] **Step 4: `docs/product/features/categorisation.md`** — `Data model:` link; §3 add: "The list is defined once on the server and the app reads it from there. Changing it is one server edit; renaming or removing a category also moves the transactions that carry it."; `Last updated`.
- [ ] **Step 5: `docs/TODO.md`** — add a section `## Web — the transactions empty state, with CSV import (roadmap step 4)`: "With no transactions the page offers **Add a transaction**. When CSV upload ships, the prompt becomes **Upload a CSV** (`transactions.md` §2). **Unblocks:** nothing; it lands with step 4."
- [ ] **Step 6: `docs/architecture/server.md`** — §1 tree: add `│   └── transaction/          # the user's transactions and the category list` (adjust the `└──`/`├──` of `conversation`); §8 event table, `USER_ERASING` subscribers: append "; `transaction` — hard-deletes every transaction the user owns".
- [ ] **Step 7: `server/CLAUDE.md`** GDPR list item 2 append: "; `transaction` hard-deletes every transaction the user owns, soft-deleted ones included". Rule "New models with PII must implement `AnonymizableMixin`…" becomes: "New models with PII implement `AnonymizableMixin` and an `anonymize_*()` method, or — when nothing references their rows — are hard-deleted by their module's `USER_ERASING` subscriber (`transaction`)". (Step 3 also edits this file — keep the edit to these two lines.)
- [ ] **Step 8: `data-tables.md`** (web-app-patterns reference) — a section "Selection, bulk actions and phone cards": `enableRowSelection` + `renderBulkActions(selected, clear)` (selection holds only rows on screen; desktop only), `renderCard(row)` below 768px, `DateFilterControl presets`, `FilterCheckboxGroup`; point at `apps/web/src/components/transactions/` as the worked example.
- [ ] **Step 9: Commit**

```bash
git add docs server/CLAUDE.md .claude/skills/web-app-patterns/references/data-tables.md
git commit -m "docs: the transaction data model, feature docs and patterns for step 2"
```

---

## Task 16: Finish (controller)

- [ ] Run everything: `make check`, `make test-web`, `make -C server test`, `make check-contract`. All green, output read.
- [ ] Whole-branch review (subagent-driven-development's final review).
- [ ] `superpowers:finishing-a-development-branch` up to an **open PR into `template-base`** (never a merge). In that PR: `docs/ROADMAP.md` row 2 → `complete — [PR #N](…) into template-base; reaches main at Cutover`, its "Where it is specified" cell names `data-model/transaction.md`; delete `.superpowers/specs/2026-10-13-transactions-design.md` and this plan.
- [ ] `SendMessage` to `orchestrator`: the PR URL, and the merge points (spec §7).
