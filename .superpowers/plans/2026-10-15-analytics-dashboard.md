# Step 5a — Analytics Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The whole analytics computation library (a new `analytics` server module), its seven routes, and the home dashboard that reads them.

**Architecture:** `transaction` gains one read path returning plain `AnalysisRow`s. `analytics/domain/` holds pure functions over those rows (stdlib `statistics`, `Decimal` money, no ORM, no framework — R9); `analytics/service.py` loads rows, calls domain, and returns Pydantic responses that `router.py` serves under `/api/v1/analytics`. The web's home page is a client component on the generated hooks, drawing charts through a new `@app/ui/chart` primitive on Recharts.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy async, Pydantic v2, pytest + testcontainers, import-linter; Next.js 16, React 19, TanStack Query 5 via orval-generated hooks, Base UI, Tailwind 4, Recharts 3, Vitest + Testing Library.

**Spec:** `.superpowers/specs/2026-10-15-analytics-dashboard-design.md` — read it first. Ownership and the eleven merge conditions are in `.superpowers/BRIEF.md` §3.

## Global Constraints

- No file under `server/alembic/versions/`; no edit to `server/app/modules/transaction/models.py`.
- In `server/app/modules/transaction/`, only additions to `schemas.py`, `repository.py`, `service.py`, `__init__.py` and their tests.
- Do not edit: `web-app/apps/web/src/lib/hub-nav.ts`, `apps/web/src/app/(dashboard)/layout.tsx`, `packages/ui/src/index.ts`, any existing file in `packages/ui/src/primitives/`, anything under `apps/web/src/app/(dashboard)/transactions/` or `apps/web/src/components/transactions/` except `use-invalidate-transactions.ts`, the hand-written `packages/api-client/src/` files (`query-provider.tsx`, `query-meta.ts`, `toast-for-error.ts`, `use-api-fetch.ts`, `errors.ts`, `index.ts`), anything in `packages/data-table/`, `packages/components/`, `packages/core/src/constants/messages.ts`, `docs/data-model/transaction.md`, `docs/data-model/README.md` §1, `docs/architecture/server.md` §2 and §8, `docs/TODO.md`'s R9 entry.
- `web-app-patterns` `references/components.md` step 3 says to add a new primitive to `packages/ui/src/index.ts`. **Skip that step** — the brief forbids editing the barrel; the primitive is imported by subpath only.
- Money is `Decimal`, quantised to cents, serialised as a string. Every percent is on the 0–100 scale and rounded to 2 places; CV to 4.
- The sign decides: `amount < 0` expense (measured as `abs`), `> 0` income, `== 0` ignored by every sum, count and average.
- Never divide by zero: empty input gives zeros, `None` for an undefined ratio, and empty tuples.
- New dependency, exactly: `"recharts": "^3.10.1"` in `web-app/packages/ui/package.json` **and** `web-app/apps/web/package.json`. No polars, no numpy.
- Every route: an explicit tag (`analytics`), a camelCase `operation_id`, a `response_model`. Run `make gen-contract` from the repo root after any route change and commit its output in the same commit.
- Server tests run from `server/`: `APP_ENV=test uv run pytest <path> -v`. Unit test files carry `pytestmark = pytest.mark.unit`, integration ones `pytestmark = pytest.mark.integration` (an unmarked file never runs under `make test-unit`/`test-integration`). Docker must be running for integration tests.
- Web tests: `cd web-app && pnpm -s test -- <path>`; whole suite `make test-web` from the root.
- Gates before any push: `make check` and `make test-web` (root), plus `make test-unit` and `make test-integration` (from `server/`).
- Copy (exact strings): "Welcome back, {first name}" / "Welcome back"; "Your overview for {Month YYYY}" / "Your overview"; "No transactions yet"; "Add or import transactions to see your overview."; "Go to transactions"; "Couldn't load {what}."; "Retry"; "Recent transactions"; "View all"; "{n} recurring payment(s)"; "average of {n} month(s)"; "Spending by category"; "Income and expenses"; "Other".
- Ruff runs pydocstyle (`D`, google convention) on `server/app/`: every public module, class, function and method needs a docstring. Where the plan's code shows none (a dataclass, a response model, a route handler, a service method, a small helper), add a one-line docstring saying what it is; `ruff check` names each one (`D101`–`D103`). Bugbear is on too: every `zip()` takes `strict=True`.
- Commit messages follow the repo's style: a short sentence, sentence case, e.g. `Analytics: the spending and category analyses`. Never `git add -A`; add the files the task names.

## Review Focus

1. **A user whose only transactions are in one month** — the 3-month cashflow average must divide by 1, not 3 (`cashflow_months` 1). Pinned in Task 7.
2. **A month with no transactions inside the range** — it counts as zero in every per-month series and in every average "per month", and growth from it is `None`, never an error or `Infinity`. Pinned in Tasks 3 and 7.
3. **Two spellings of one merchant** ("Spotify", "spotify ") — one group, shown with the latest spelling; recurring and hidden-subscription grouping use the same key. Pinned in Task 4.
4. **A soft-deleted transaction or another user's transaction** — never counted by any route. Pinned in Tasks 1 and 8.
5. **A transaction edit or delete while the dashboard is cached** — the dashboard refetches immediately, not after the 2-minute stale time. Pinned in Task 10.

---

## File structure

**Server — create**
- `server/app/modules/analytics/__init__.py` — public surface: `router`, `analytics_service`, response schemas.
- `server/app/modules/analytics/exceptions.py` — `InvalidDateRangeError`.
- `server/app/modules/analytics/schemas.py` — `DateRange` and every response model.
- `server/app/modules/analytics/dependencies.py` — `get_date_range`, `AnalyticsRange`.
- `server/app/modules/analytics/service.py` — `AnalyticsService`.
- `server/app/modules/analytics/router.py` — the seven routes.
- `server/app/modules/analytics/domain/__init__.py` — package marker with a docstring only.
- `server/app/modules/analytics/domain/_aggregate.py` — `Row` protocol, money, months, grouping, safe ratios.
- `server/app/modules/analytics/domain/{spending,categories,merchants,recurring,behaviour,anomalies,dashboard}.py` — one analysis each.
- `server/tests/unit/modules/analytics/{__init__,rows,test_aggregate,test_spending,test_categories,test_merchants,test_recurring,test_behaviour,test_anomalies,test_dashboard}.py`
- `server/tests/integration/modules/analytics/{__init__,conftest,test_routes}.py`
- `server/tests/integration/modules/transaction/test_analysis_rows.py`

**Server — modify**
- `server/app/modules/transaction/{schemas,repository,service,__init__}.py` — the read path.
- `server/app/main.py` — `from app.modules import analytics as _analytics`.
- `server/app/api/v1/api.py` — include `analytics.router`.
- `server/pyproject.toml` — R1, R6, R9 contracts.
- `server/openapi.json`, `web-app/packages/api-client/src/generated/**` — regenerated.

**Web — create**
- `web-app/packages/ui/src/primitives/chart.tsx` — `ChartContainer`, `ChartTooltip`, `ChartTooltipContent`, `ChartConfig`.
- `web-app/apps/web/src/app/(dashboard)/home/loading.tsx`
- `web-app/apps/web/src/components/dashboard/`: `month.ts`, `category-slices.ts`, `trend-points.ts`, `welcome-header.tsx`, `summary-cards.tsx`, `category-chart.tsx`, `trend-chart.tsx`, `recent-transactions.tsx`, `section-error.tsx`, `empty-dashboard.tsx`, `dashboard-skeleton.tsx`, `home-dashboard.tsx`, and tests `month.test.ts`, `category-slices.test.ts`, `trend-points.test.ts`, `welcome-header.test.tsx`, `summary-cards.test.tsx`, `home-dashboard.test.tsx`.
- `web-app/apps/web/src/components/transactions/use-invalidate-transactions.test.tsx`

**Web — modify**
- `web-app/apps/web/src/app/(dashboard)/home/page.tsx` — render `<HomeDashboard />`.
- `web-app/apps/web/src/components/transactions/use-invalidate-transactions.ts` — also invalidate analytics.
- `web-app/packages/ui/src/styles/globals.css` — chart palette tokens.
- `web-app/packages/ui/package.json`, `web-app/apps/web/package.json`, `web-app/pnpm-lock.yaml` — recharts.

**Docs — modify (Task 13):** `docs/product/features/analytics.md`, `docs/architecture/server.md` §1, `docs/TODO.md`, `docs/ROADMAP.md`.

---

### Task 1: Transaction's read path for analysis

**Files:**
- Modify: `server/app/modules/transaction/schemas.py` (append after `TransactionResponse`)
- Modify: `server/app/modules/transaction/repository.py` (new method before `set_category_for_ids`)
- Modify: `server/app/modules/transaction/service.py` (new method after `list`)
- Modify: `server/app/modules/transaction/__init__.py`
- Test: `server/tests/integration/modules/transaction/test_analysis_rows.py`

**Interfaces:**
- Produces: `app.modules.transaction.AnalysisRow` — frozen Pydantic model with `date: dt.date`, `merchant: str`, `amount: Decimal`, `category: str`, `is_recurring: bool`.
- Produces: `transaction_service.list_for_analysis(session: AsyncSession, user_id: uuid.UUID, date_from: Optional[dt.date] = None, date_to: Optional[dt.date] = None) -> list[AnalysisRow]` — the user's active rows, inclusive bounds, ordered by `date, created_at, id`.

- [ ] **Step 1: Write the failing test**

Create `server/tests/integration/modules/transaction/test_analysis_rows.py`:

```python
"""The read path analytics loads: plain rows, this user's, active, in range, in date order."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.transaction import AnalysisRow, transaction_service

pytestmark = pytest.mark.integration


async def test_returns_plain_rows_in_date_order(db_session, test_user, make_transaction):
    await make_transaction(
        test_user, date=dt.date(2026, 2, 1), merchant="Landlord", amount=Decimal("-900.00"),
        category="household_utilities", is_recurring=True,
    )
    await make_transaction(test_user, date=dt.date(2026, 1, 5), merchant="REWE", amount=Decimal("-30.00"))

    rows = await transaction_service.list_for_analysis(db_session, test_user.id)

    assert rows == [
        AnalysisRow(
            date=dt.date(2026, 1, 5), merchant="REWE", amount=Decimal("-30.00"),
            category="food_groceries", is_recurring=False,
        ),
        AnalysisRow(
            date=dt.date(2026, 2, 1), merchant="Landlord", amount=Decimal("-900.00"),
            category="household_utilities", is_recurring=True,
        ),
    ]


async def test_excludes_deleted_rows_and_other_users(db_session, test_user, other_user, make_transaction):
    kept = await make_transaction(test_user, merchant="Kept")
    gone = await make_transaction(test_user, merchant="Gone")
    gone.soft_delete()
    db_session.add(gone)
    await db_session.flush()
    await make_transaction(other_user, merchant="Theirs")

    rows = await transaction_service.list_for_analysis(db_session, test_user.id)

    assert [r.merchant for r in rows] == [kept.merchant]


async def test_both_bounds_are_inclusive(db_session, test_user, make_transaction):
    for day in (1, 2, 3, 4):
        await make_transaction(test_user, date=dt.date(2026, 3, day), merchant=f"Day {day}")

    rows = await transaction_service.list_for_analysis(
        db_session, test_user.id, date_from=dt.date(2026, 3, 2), date_to=dt.date(2026, 3, 3)
    )

    assert [r.merchant for r in rows] == ["Day 2", "Day 3"]
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `server/`): `APP_ENV=test uv run pytest tests/integration/modules/transaction/test_analysis_rows.py -v`
Expected: collection error, `ImportError: cannot import name 'AnalysisRow'`.

- [ ] **Step 3: Implement**

In `schemas.py`, append after `TransactionResponse`:

```python
class AnalysisRow(BaseModel):
    """One active transaction as analytics reads it: the five fields every calculation uses."""

    date: dt.date
    merchant: str
    amount: Decimal
    category: str
    is_recurring: bool

    model_config = {"frozen": True}
```

In `repository.py`, import `AnalysisRow` alongside the existing schema imports (`from app.modules.transaction.schemas import AnalysisRow, TransactionFilters, TransactionOrdering`) and add `import datetime as dt` at the top. Add this method before `set_category_for_ids`:

```python
    @staticmethod
    async def list_active_rows_for_analysis(
        session: AsyncSession,
        user_id: uuid.UUID,
        date_from: Optional[dt.date],
        date_to: Optional[dt.date],
    ) -> list[AnalysisRow]:
        """This user's active rows within inclusive bounds, oldest first, as plain values."""
        conditions = [Transaction.user_id == user_id, Transaction.deleted_at.is_(None)]
        if date_from is not None:
            conditions.append(Transaction.date >= date_from)
        if date_to is not None:
            conditions.append(Transaction.date <= date_to)
        statement = (
            select(
                Transaction.date,
                Transaction.merchant,
                Transaction.amount,
                Transaction.category,
                Transaction.is_recurring,
            )
            .where(*conditions)
            .order_by(Transaction.date, Transaction.created_at, Transaction.id)
        )
        result = await session.execute(statement)
        return [
            AnalysisRow(date=date, merchant=merchant, amount=amount, category=category, is_recurring=is_recurring)
            for date, merchant, amount, category, is_recurring in result.all()
        ]
```

In `service.py`, import `AnalysisRow` in the schemas import block and add after `list`:

```python
    @staticmethod
    async def list_for_analysis(
        session: AsyncSession,
        user_id: uuid.UUID,
        date_from: Optional[dt.date] = None,
        date_to: Optional[dt.date] = None,
    ) -> list[AnalysisRow]:
        """A user's active transactions in a range, as plain rows: analytics' only read."""
        return await transaction_repository.list_active_rows_for_analysis(session, user_id, date_from, date_to)
```

In `__init__.py`, add `AnalysisRow` to the `from app.modules.transaction.schemas import (...)` block and to `__all__` (keep both alphabetical: it goes first).

- [ ] **Step 4: Run test to verify it passes**

Run: `APP_ENV=test uv run pytest tests/integration/modules/transaction/ -v`
Expected: all PASS (the three new tests and every existing transaction test).

- [ ] **Step 5: Lint and commit**

```bash
cd server && uv run ruff format app tests && uv run ruff check app tests && cd ..
git add server/app/modules/transaction/schemas.py server/app/modules/transaction/repository.py \
  server/app/modules/transaction/service.py server/app/modules/transaction/__init__.py \
  server/tests/integration/modules/transaction/test_analysis_rows.py
git commit -m "Transaction: a plain-row read path for analytics"
```

---

### Task 2: The analytics module, its contracts, and the domain helpers

**Files:**
- Create: `server/app/modules/analytics/__init__.py`
- Create: `server/app/modules/analytics/domain/__init__.py`
- Create: `server/app/modules/analytics/domain/_aggregate.py`
- Modify: `server/pyproject.toml` (`[tool.importlinter]` and its contracts)
- Modify: `server/app/main.py:44-46`
- Create: `server/tests/unit/modules/analytics/__init__.py` (empty), `server/tests/unit/modules/analytics/rows.py`
- Test: `server/tests/unit/modules/analytics/test_aggregate.py`

**Interfaces:**
- Produces (all in `app.modules.analytics.domain._aggregate`): `CENT`, `ZERO`, `Row` (Protocol), `money(Decimal) -> Decimal`, `expenses(rows) -> list`, `incomes(rows) -> list`, `spend(row) -> Decimal`, `total_spend(rows) -> Decimal`, `total_amount(rows) -> Decimal`, `month_start(dt.date) -> dt.date`, `month_key(dt.date) -> str`, `add_months(dt.date, int) -> dt.date`, `month_range(first, last) -> list[dt.date]`, `span(rows, date_from, date_to) -> Optional[tuple[dt.date, dt.date]]`, `group_by(rows, key) -> dict`, `monthly_totals(rows, months, value) -> list[Decimal]`, `pct_change(old, new) -> Optional[float]`, `share_pct(part, whole) -> float`, `average(total, count) -> Decimal`, `cv(values) -> Optional[float]`.
- Produces (tests): `tests.unit.modules.analytics.rows.row(day, amount, merchant="Shop", category="shopping", recurring=False)`.

- [ ] **Step 1: Write the test helper and the failing test**

`server/tests/unit/modules/analytics/rows.py`:

```python
"""Plain rows for the analytics domain tests: AnalysisRow's five fields, nothing else."""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Row:
    date: dt.date
    merchant: str
    amount: Decimal
    category: str
    is_recurring: bool


def row(day: str, amount: str, merchant: str = "Shop", category: str = "shopping", recurring: bool = False) -> Row:
    """`row("2026-03-01", "-12.50")` — a day in ISO form and a signed decimal string."""
    return Row(dt.date.fromisoformat(day), merchant, Decimal(amount), category, recurring)
```

`server/tests/unit/modules/analytics/test_aggregate.py`:

```python
"""The shared helpers every analysis stands on."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain._aggregate import (
    add_months,
    average,
    cv,
    expenses,
    group_by,
    incomes,
    money,
    month_key,
    month_range,
    monthly_totals,
    pct_change,
    share_pct,
    span,
    spend,
    total_spend,
)
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

D = dt.date


def test_money_quantises_and_drops_negative_zero():
    assert money(Decimal("1.005")) == Decimal("1.00")  # banker's rounding, as Decimal does
    assert money(Decimal("2.675")) == Decimal("2.68")
    assert str(money(Decimal("-0.001"))) == "0.00"


def test_the_sign_decides_and_zero_is_neither():
    rows = [row("2026-01-01", "-5.00"), row("2026-01-02", "0.00"), row("2026-01-03", "7.00")]
    assert [r.amount for r in expenses(rows)] == [Decimal("-5.00")]
    assert [r.amount for r in incomes(rows)] == [Decimal("7.00")]
    assert spend(rows[0]) == Decimal("5.00")
    assert total_spend(expenses(rows)) == Decimal("5.00")


def test_months():
    assert month_key(D(2026, 9, 17)) == "2026-09"
    assert add_months(D(2026, 11, 1), 3) == D(2027, 2, 1)
    assert add_months(D(2026, 1, 1), -1) == D(2025, 12, 1)
    assert month_range(D(2025, 11, 30), D(2026, 2, 1)) == [D(2025, 11, 1), D(2025, 12, 1), D(2026, 1, 1), D(2026, 2, 1)]
    assert month_range(D(2026, 3, 1), D(2026, 2, 1)) == []


def test_span_prefers_given_bounds_then_the_data():
    rows = [row("2026-01-05", "-1.00"), row("2026-03-28", "-1.00")]
    assert span(rows, None, None) == (D(2026, 1, 5), D(2026, 3, 28))
    assert span(rows, D(2025, 12, 1), None) == (D(2025, 12, 1), D(2026, 3, 28))
    assert span([], D(2026, 1, 1), D(2026, 1, 31)) == (D(2026, 1, 1), D(2026, 1, 31))
    assert span([], None, None) is None
    assert span([], D(2026, 1, 1), None) is None


def test_group_by_keeps_first_seen_order():
    rows = [row("2026-01-01", "-1", category="b"), row("2026-01-02", "-1", category="a"), row("2026-01-03", "-1", category="b")]
    groups = group_by(rows, lambda r: r.category)
    assert list(groups) == ["b", "a"]
    assert len(groups["b"]) == 2


def test_monthly_totals_zero_fill_missing_months():
    rows = [row("2026-01-05", "-10.00"), row("2026-03-01", "-4.50"), row("2026-03-02", "-0.50")]
    months = month_range(D(2026, 1, 1), D(2026, 3, 1))
    assert monthly_totals(rows, months, spend) == [Decimal("10.00"), Decimal("0.00"), Decimal("5.00")]


def test_ratios_never_divide_by_zero():
    assert pct_change(Decimal("0"), Decimal("10")) is None
    assert pct_change(Decimal("50"), Decimal("120")) == 140.0
    assert pct_change(Decimal("150"), Decimal("100")) == -33.33
    assert share_pct(Decimal("1"), Decimal("0")) == 0.0
    assert share_pct(Decimal("170"), Decimal("420")) == 40.48
    assert average(Decimal("10"), 0) == Decimal("0.00")
    assert average(Decimal("170"), 3) == Decimal("56.67")


def test_cv_is_population_stdev_over_mean():
    assert cv([Decimal("50"), Decimal("120")]) == 0.4118
    assert cv([Decimal("5")]) is None
    assert cv([Decimal("0"), Decimal("0")]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_aggregate.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'app.modules.analytics'`.

- [ ] **Step 3: Implement the module skeleton and helpers**

`server/app/modules/analytics/__init__.py` (grows in Task 8):

```python
"""Analytics — every calculation over the user's transactions. Stores nothing.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).
"""
```

`server/app/modules/analytics/domain/__init__.py`:

```python
"""The calculations: pure functions over plain rows. No ORM, no framework, no other module (R9).

Every function takes rows already limited to the caller's range, in date order.
"""
```

`server/app/modules/analytics/domain/_aggregate.py`:

```python
"""Shared helpers: the row the library reads, money, months, grouping and safe ratios."""

import datetime as dt
from collections.abc import Callable, Hashable, Iterable, Sequence
from decimal import Decimal
from statistics import mean, pstdev
from typing import Optional, Protocol, TypeVar

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


class Row(Protocol):
    """One transaction as the library reads it. transaction's AnalysisRow satisfies it."""

    @property
    def date(self) -> dt.date: ...

    @property
    def merchant(self) -> str: ...

    @property
    def amount(self) -> Decimal: ...

    @property
    def category(self) -> str: ...

    @property
    def is_recurring(self) -> bool: ...


R = TypeVar("R", bound=Row)
K = TypeVar("K", bound=Hashable)


def money(value: Decimal) -> Decimal:
    """Quantise to cents; -0.00 becomes 0.00."""
    cents = value.quantize(CENT)
    return ZERO if cents == 0 else cents


def expenses(rows: Iterable[R]) -> list[R]:
    """Money out: a negative amount."""
    return [r for r in rows if r.amount < 0]


def incomes(rows: Iterable[R]) -> list[R]:
    """Money in: a positive amount. A zero amount is neither."""
    return [r for r in rows if r.amount > 0]


def spend(row: Row) -> Decimal:
    """An expense as a positive amount."""
    return -row.amount


def total_spend(rows: Iterable[Row]) -> Decimal:
    """The sum of expenses, positive."""
    return money(sum((spend(r) for r in rows), ZERO))


def total_amount(rows: Iterable[Row]) -> Decimal:
    """The sum of signed amounts."""
    return money(sum((r.amount for r in rows), ZERO))


def month_start(day: dt.date) -> dt.date:
    return day.replace(day=1)


def month_key(month: dt.date) -> str:
    """The month as YYYY-MM, its form on the wire."""
    return f"{month:%Y-%m}"


def add_months(month: dt.date, n: int) -> dt.date:
    """The first day of the month n months from month's (n may be negative)."""
    index = month.year * 12 + month.month - 1 + n
    return dt.date(index // 12, index % 12 + 1, 1)


def month_range(first: dt.date, last: dt.date) -> list[dt.date]:
    """Every month start from first's month to last's, inclusive; empty if last precedes first."""
    months: list[dt.date] = []
    current, end = month_start(first), month_start(last)
    while current <= end:
        months.append(current)
        current = add_months(current, 1)
    return months


def span(rows: Sequence[Row], date_from: Optional[dt.date], date_to: Optional[dt.date]) -> Optional[tuple[dt.date, dt.date]]:
    """The days a result covers: the given bounds, else the data's first and last day; None when unknown."""
    start = date_from or min((r.date for r in rows), default=None)
    end = date_to or max((r.date for r in rows), default=None)
    if start is None or end is None or end < start:
        return None
    return start, end


def group_by(rows: Iterable[R], key: Callable[[R], K]) -> dict[K, list[R]]:
    """Rows grouped by key, groups in first-seen order."""
    groups: dict[K, list[R]] = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    return groups


def monthly_totals(rows: Iterable[R], months: Sequence[dt.date], value: Callable[[R], Decimal]) -> list[Decimal]:
    """The sum of value(row) for each month in months; zero for a month without rows."""
    by_month = group_by(rows, lambda r: month_start(r.date))
    return [money(sum((value(r) for r in by_month.get(m, [])), ZERO)) for m in months]


def pct_change(old: Decimal, new: Decimal) -> Optional[float]:
    """Percent change from old to new; None when old is zero."""
    if old == 0:
        return None
    return round(float((new - old) / old * 100), 2)


def share_pct(part: Decimal, whole: Decimal) -> float:
    """part as a percent of whole; 0 when whole is zero."""
    if whole == 0:
        return 0.0
    return round(float(part / whole * 100), 2)


def average(total: Decimal, count: int) -> Decimal:
    """total ÷ count in cents; zero for no items."""
    return money(total / count) if count else ZERO


def cv(values: Sequence[Decimal]) -> Optional[float]:
    """Coefficient of variation, population stdev ÷ mean; None for fewer than two values or a zero mean."""
    if len(values) < 2:
        return None
    centre = mean(values)
    if centre == 0:
        return None
    return round(float(pstdev(values) / centre), 4)
```

- [ ] **Step 4: Wire the module into main.py and the contracts**

In `server/app/main.py`, after `from app.modules import account as _account`, add (alphabetical order):

```python
from app.modules import analytics as _analytics
```

In `server/pyproject.toml`:

1. Under `[tool.importlinter]`, add `include_external_packages = true` (R9 forbids external packages; import-linter only sees them with this on):

```toml
[tool.importlinter]
root_package = "app"
# R4 lets a module type-hint another's model under TYPE_CHECKING.
exclude_type_checking_imports = true
# R9 forbids third-party packages; import-linter only graphs them with this on.
include_external_packages = true
```

2. Replace the R6 `layers` list:

```toml
layers = [
    "app.modules.conversation | app.modules.analytics",
    "app.modules.transaction",
    "app.modules.account",
]
```

3. Add `"app.modules.analytics.*"` to the `forbidden_modules` of the three existing R1 contracts (account, conversation, transaction), and add analytics' own R1 contract after the account one:

```toml
[[tool.importlinter.contracts]]
name = "R1: analytics reaches other modules only through their package roots"
type = "forbidden"
source_modules = ["app.modules.analytics"]
forbidden_modules = ["app.modules.account.*", "app.modules.conversation.*", "app.modules.transaction.*"]
allow_indirect_imports = true
```

4. Append the R9 contract (both patterns, exactly as relayed from step 4 by the orchestrator; at merge step 4's block wins, and step 4 deletes the `docs/TODO.md` entry — do not touch it here):

```toml
[[tool.importlinter.contracts]]
name = "R9: a domain slot imports neither the ORM nor the framework"
type = "forbidden"
source_modules = ["app.modules.*.domain", "app.modules.*.*.domain"]
forbidden_modules = ["sqlmodel", "sqlalchemy", "fastapi"]
```

- [ ] **Step 5: Run the tests and the import linter**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_aggregate.py tests/unit/test_module_contracts.py -v`
Expected: all PASS.

Run: `uv run lint-imports`
Expected: every contract KEPT. If import-linter rejects `app.modules.*.*.domain` because nothing matches it yet, do **not** drop the pattern: stop and report to the coordinator (the pattern is step 4's, relayed by `orchestrator`).

Prove R9 bites: temporarily add `import sqlalchemy` to `domain/_aggregate.py`, run `uv run lint-imports`, expect the R9 contract BROKEN, then remove the line.

- [ ] **Step 6: Lint and commit**

```bash
cd server && uv run ruff format app tests && uv run ruff check app tests && cd ..
git add server/app/modules/analytics server/app/main.py server/pyproject.toml server/tests/unit/modules/analytics
git commit -m "Analytics: the module, its R1/R6/R9 contracts and the domain helpers"
```

---

### Task 3: Spending and categories

**Files:**
- Create: `server/app/modules/analytics/domain/spending.py`
- Create: `server/app/modules/analytics/domain/categories.py`
- Test: `server/tests/unit/modules/analytics/test_spending.py`, `server/tests/unit/modules/analytics/test_categories.py`

**Interfaces:**
- Consumes: Task 2's `_aggregate` helpers.
- Produces: `spending_summary(rows, date_from=None, date_to=None) -> SpendingSummary`; dataclasses `MonthFlow(month: str, income: Decimal, expenses: Decimal, net: Decimal, expense_change_pct: Optional[float])`, `SpendingSummary(date_from: Optional[dt.date], date_to: Optional[dt.date], total_income, total_expenses, net: Decimal, transaction_count: int, average_income, average_expense, average_monthly_income, average_monthly_expenses, burn_rate: Decimal, months: tuple[MonthFlow, ...])`.
- Produces: `category_breakdown(rows, top_n=10, date_from=None, date_to=None) -> CategoryBreakdown`; dataclasses `CategorySpend(category: str, total: Decimal, count: int, average: Decimal, share_pct: float)`, `CategoryTrend(category: str, first_month_total: Decimal, last_month_total: Decimal, growth_pct: float, cv: Optional[float])`, `CategoryBreakdown(total_expenses: Decimal, top_categories: tuple[CategorySpend, ...], by_frequency: tuple[CategorySpend, ...], top_growing: tuple[CategoryTrend, ...], top_declining: tuple[CategoryTrend, ...])`.

- [ ] **Step 1: Write the failing tests**

`test_spending.py`:

```python
"""Spending: per-month flows, totals and averages over a zero-filled range."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.spending import MonthFlow, spending_summary
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

# January and March have money; February has none; a zero amount on 15 March is ignored.
ROWS = [
    row("2026-01-05", "-100.00"),
    row("2026-01-20", "2000.00", category="salary"),
    row("2026-03-10", "-300.00"),
    row("2026-03-15", "0.00"),
    row("2026-03-28", "1000.00", category="salary"),
]


def test_months_are_zero_filled_and_growth_after_zero_is_none():
    result = spending_summary(ROWS)
    assert result.months == (
        MonthFlow("2026-01", Decimal("2000.00"), Decimal("100.00"), Decimal("1900.00"), None),
        MonthFlow("2026-02", Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), -100.0),
        MonthFlow("2026-03", Decimal("1000.00"), Decimal("300.00"), Decimal("700.00"), None),
    )


def test_totals_and_averages():
    result = spending_summary(ROWS)
    assert (result.date_from, result.date_to) == (dt.date(2026, 1, 5), dt.date(2026, 3, 28))
    assert result.total_income == Decimal("3000.00")
    assert result.total_expenses == Decimal("400.00")
    assert result.net == Decimal("2600.00")
    assert result.transaction_count == 4  # the zero amount is not a transaction of either kind
    assert result.average_income == Decimal("1500.00")
    assert result.average_expense == Decimal("200.00")
    assert result.average_monthly_income == Decimal("1000.00")
    assert result.average_monthly_expenses == Decimal("133.33")
    assert result.burn_rate == Decimal("-866.67")


def test_given_bounds_widen_the_month_range():
    result = spending_summary(ROWS, date_from=dt.date(2025, 12, 1), date_to=dt.date(2026, 3, 31))
    assert [m.month for m in result.months] == ["2025-12", "2026-01", "2026-02", "2026-03"]
    assert result.average_monthly_income == Decimal("750.00")
    assert result.months[1].expense_change_pct is None  # December spent nothing


def test_empty_input_is_all_zero():
    result = spending_summary([])
    assert result.months == ()
    assert result.date_from is None and result.date_to is None
    assert result.total_expenses == Decimal("0.00")
    assert result.burn_rate == Decimal("0.00")
    assert result.transaction_count == 0
```

`test_categories.py`:

```python
"""Categories: ranked spend, frequency, and per-category growth across months."""

from decimal import Decimal

import pytest

from app.modules.analytics.domain.categories import CategorySpend, CategoryTrend, category_breakdown
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

ROWS = [
    row("2026-01-03", "-50.00", category="food_groceries"),
    row("2026-01-10", "-150.00", category="household_utilities"),
    row("2026-02-03", "-100.00", category="food_groceries"),
    row("2026-02-10", "-100.00", category="household_utilities"),
    row("2026-02-12", "-20.00", category="food_groceries"),
    row("2026-02-20", "500.00", category="salary"),  # income: never a category's spend
]

FOOD = CategorySpend("food_groceries", Decimal("170.00"), 3, Decimal("56.67"), 40.48)
HOUSE = CategorySpend("household_utilities", Decimal("250.00"), 2, Decimal("125.00"), 59.52)


def test_ranked_by_spend_and_by_frequency():
    result = category_breakdown(ROWS)
    assert result.total_expenses == Decimal("420.00")
    assert result.top_categories == (HOUSE, FOOD)
    assert result.by_frequency == (FOOD, HOUSE)


def test_top_n_cuts_both_rankings():
    result = category_breakdown(ROWS, top_n=1)
    assert result.top_categories == (HOUSE,)
    assert result.by_frequency == (FOOD,)


def test_growth_from_first_to_last_month_with_spend():
    result = category_breakdown(ROWS)
    assert result.top_growing == (CategoryTrend("food_groceries", Decimal("50.00"), Decimal("120.00"), 140.0, 0.4118),)
    assert result.top_declining == (
        CategoryTrend("household_utilities", Decimal("150.00"), Decimal("100.00"), -33.33, 0.2),
    )


def test_a_category_with_one_month_has_no_trend():
    result = category_breakdown([row("2026-01-03", "-50.00", category="food_groceries")])
    assert result.top_growing == () and result.top_declining == ()


def test_empty_input():
    result = category_breakdown([])
    assert result.total_expenses == Decimal("0.00")
    assert result.top_categories == ()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_spending.py tests/unit/modules/analytics/test_categories.py -v`
Expected: collection errors, `ModuleNotFoundError` for `spending` and `categories`.

- [ ] **Step 3: Implement `spending.py`**

```python
"""Spending: income, expenses and net per month and over the range."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.modules.analytics.domain._aggregate import (
    ZERO,
    Row,
    average,
    expenses,
    incomes,
    money,
    month_key,
    month_range,
    monthly_totals,
    pct_change,
    span,
    spend,
    total_amount,
    total_spend,
)


@dataclass(frozen=True)
class MonthFlow:
    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    expense_change_pct: Optional[float]


@dataclass(frozen=True)
class SpendingSummary:
    date_from: Optional[dt.date]
    date_to: Optional[dt.date]
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal
    transaction_count: int
    average_income: Decimal
    average_expense: Decimal
    average_monthly_income: Decimal
    average_monthly_expenses: Decimal
    burn_rate: Decimal
    months: tuple[MonthFlow, ...]


def monthly_flows(rows: Sequence[Row], months: Sequence[dt.date]) -> tuple[MonthFlow, ...]:
    """Income, expenses and net for each month, zero-filled; expense change against the month before."""
    income = monthly_totals(incomes(rows), months, lambda r: r.amount)
    spent = monthly_totals(expenses(rows), months, spend)
    flows: list[MonthFlow] = []
    for i, month in enumerate(months):
        change = pct_change(spent[i - 1], spent[i]) if i > 0 else None
        flows.append(MonthFlow(month_key(month), income[i], spent[i], money(income[i] - spent[i]), change))
    return tuple(flows)


def spending_summary(
    rows: Sequence[Row], date_from: Optional[dt.date] = None, date_to: Optional[dt.date] = None
) -> SpendingSummary:
    """Totals, averages and the per-month series over the range (the bounds, else the data's span)."""
    covered = span(rows, date_from, date_to)
    months = month_range(*covered) if covered else []
    money_in, money_out = incomes(rows), expenses(rows)
    total_in, total_out = total_amount(money_in), total_spend(money_out)
    monthly_in = average(total_in, len(months))
    monthly_out = average(total_out, len(months))
    return SpendingSummary(
        date_from=covered[0] if covered else None,
        date_to=covered[1] if covered else None,
        total_income=total_in,
        total_expenses=total_out,
        net=money(total_in - total_out),
        transaction_count=len(money_in) + len(money_out),
        average_income=average(total_in, len(money_in)),
        average_expense=average(total_out, len(money_out)),
        average_monthly_income=monthly_in,
        average_monthly_expenses=monthly_out,
        burn_rate=money(monthly_out - monthly_in) if months else ZERO,
        months=monthly_flows(rows, months),
    )
```

- [ ] **Step 4: Implement `categories.py`**

```python
"""Categories: where the money goes, how often, and which categories grow."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.modules.analytics.domain._aggregate import (
    Row,
    average,
    cv,
    expenses,
    group_by,
    month_range,
    monthly_totals,
    pct_change,
    share_pct,
    span,
    spend,
    total_spend,
)

TREND_SIZE = 5


@dataclass(frozen=True)
class CategorySpend:
    category: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float


@dataclass(frozen=True)
class CategoryTrend:
    category: str
    first_month_total: Decimal
    last_month_total: Decimal
    growth_pct: float
    cv: Optional[float]


@dataclass(frozen=True)
class CategoryBreakdown:
    total_expenses: Decimal
    top_categories: tuple[CategorySpend, ...]
    by_frequency: tuple[CategorySpend, ...]
    top_growing: tuple[CategoryTrend, ...]
    top_declining: tuple[CategoryTrend, ...]


def category_spend(rows: Sequence[Row]) -> list[CategorySpend]:
    """Expenses per category, ranked by total (ties by slug)."""
    spent = expenses(rows)
    whole = total_spend(spent)
    items = []
    for category, group in group_by(spent, lambda r: r.category).items():
        total = total_spend(group)
        items.append(CategorySpend(category, total, len(group), average(total, len(group)), share_pct(total, whole)))
    return sorted(items, key=lambda i: (-i.total, i.category))


def _trends(rows: Sequence[Row], months: Sequence[dt.date]) -> list[CategoryTrend]:
    """Growth from each category's first to last month with spend; needs two such months."""
    trends: list[CategoryTrend] = []
    for category, group in group_by(expenses(rows), lambda r: r.category).items():
        series = monthly_totals(group, months, spend)
        with_spend = [total for total in series if total > 0]
        if len(with_spend) < 2:
            continue
        growth = pct_change(with_spend[0], with_spend[-1])
        if growth is None:
            continue
        trends.append(CategoryTrend(category, with_spend[0], with_spend[-1], growth, cv(series)))
    return trends


def category_breakdown(
    rows: Sequence[Row], top_n: int = 10, date_from: Optional[dt.date] = None, date_to: Optional[dt.date] = None
) -> CategoryBreakdown:
    """Ranked category spend, the same ranked by count, and the fastest growing and declining categories."""
    ranked = category_spend(rows)
    covered = span(rows, date_from, date_to)
    trends = _trends(rows, month_range(*covered)) if covered else []
    growing = sorted((t for t in trends if t.growth_pct > 0), key=lambda t: (-t.growth_pct, t.category))
    declining = sorted((t for t in trends if t.growth_pct < 0), key=lambda t: (t.growth_pct, t.category))
    return CategoryBreakdown(
        total_expenses=total_spend(expenses(rows)),
        top_categories=tuple(ranked[:top_n]),
        by_frequency=tuple(sorted(ranked, key=lambda i: (-i.count, -i.total, i.category))[:top_n]),
        top_growing=tuple(growing[:TREND_SIZE]),
        top_declining=tuple(declining[:TREND_SIZE]),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/ -v`
Expected: all PASS.

- [ ] **Step 6: Lint and commit**

```bash
cd server && uv run ruff format app tests && uv run ruff check app tests && uv run lint-imports && cd ..
git add server/app/modules/analytics/domain/spending.py server/app/modules/analytics/domain/categories.py \
  server/tests/unit/modules/analytics/test_spending.py server/tests/unit/modules/analytics/test_categories.py
git commit -m "Analytics: the spending and category analyses"
```

---

### Task 4: Merchants and recurring

**Files:**
- Create: `server/app/modules/analytics/domain/merchants.py`, `server/app/modules/analytics/domain/recurring.py`
- Test: `server/tests/unit/modules/analytics/test_merchants.py`, `server/tests/unit/modules/analytics/test_recurring.py`

**Interfaces:**
- Consumes: `_aggregate` helpers.
- Produces: `merchant_key(name: str) -> str` (stripped, casefolded), `display_names(rows) -> dict[str, str]` (key → latest spelling, stripped), `merchant_breakdown(rows, top_n=15) -> MerchantBreakdown`; dataclasses `MerchantSpend(merchant: str, total: Decimal, count: int, average: Decimal, first_date: dt.date, last_date: dt.date, share_pct: float)`, `MerchantConcentration(top_5_share_pct: float, top_10_share_pct: float, herfindahl_index: float, risk: Literal["low", "medium", "high"], unique_merchants: int)`, `MerchantBreakdown(total_expenses: Decimal, top_by_spend: tuple[MerchantSpend, ...], top_by_frequency: tuple[MerchantSpend, ...], concentration: MerchantConcentration)`.
- Produces: `recurring_analysis(rows) -> RecurringAnalysis`; dataclasses `RecurringMerchant(merchant: str, charges: int, months_charged: int, median_charge: Decimal, monthly_cost: Decimal)`, `HiddenSubscription(merchant: str, charges: int, months_active: int, average_charge: Decimal, charges_per_month: float)`, `RecurringAnalysis(total_expenses: Decimal, recurring_total: Decimal, recurring_count: int, amount_share_pct: float, count_share_pct: float, monthly_recurring_cost: Decimal, merchants: tuple[RecurringMerchant, ...], hidden_subscriptions: tuple[HiddenSubscription, ...])`.

- [ ] **Step 1: Write the failing tests**

`test_merchants.py`:

```python
"""Merchants: spend and frequency per merchant, and how concentrated spending is."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.merchants import MerchantSpend, merchant_breakdown
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

ROWS = [
    row("2026-01-01", "-10.00", merchant="Spotify"),
    row("2026-01-05", "-60.00", merchant="REWE"),
    row("2026-01-20", "-30.00", merchant="REWE"),
    row("2026-01-25", "-90.00", merchant="Landlord"),
    row("2026-01-31", "100.00", merchant="Employer"),  # income: not a merchant's spend
    row("2026-02-01", "-10.00", merchant="spotify "),  # same merchant, latest spelling
]

SPOTIFY = MerchantSpend("spotify", Decimal("20.00"), 2, Decimal("10.00"), dt.date(2026, 1, 1), dt.date(2026, 2, 1), 10.0)
REWE = MerchantSpend("REWE", Decimal("90.00"), 2, Decimal("45.00"), dt.date(2026, 1, 5), dt.date(2026, 1, 20), 45.0)
LANDLORD = MerchantSpend("Landlord", Decimal("90.00"), 1, Decimal("90.00"), dt.date(2026, 1, 25), dt.date(2026, 1, 25), 45.0)


def test_spellings_group_and_show_the_latest():
    result = merchant_breakdown(ROWS)
    assert result.total_expenses == Decimal("200.00")
    assert result.top_by_spend == (LANDLORD, REWE, SPOTIFY)  # a tie at 90 breaks by name
    assert result.top_by_frequency == (REWE, SPOTIFY, LANDLORD)


def test_concentration_is_over_all_spending():
    c = merchant_breakdown(ROWS).concentration
    assert (c.top_5_share_pct, c.top_10_share_pct) == (100.0, 100.0)
    assert c.herfindahl_index == 4150.0  # 10² + 45² + 45²
    assert c.risk == "high"
    assert c.unique_merchants == 3


def test_herfindahl_bounds():
    one = merchant_breakdown([row("2026-01-01", "-5.00", merchant="Only")]).concentration
    assert one.herfindahl_index == 10000.0
    ten = merchant_breakdown([row("2026-01-01", "-5.00", merchant=f"M{i}") for i in range(10)]).concentration
    assert ten.herfindahl_index == 1000.0
    assert ten.risk == "low"
    assert merchant_breakdown([]).concentration.herfindahl_index == 0.0


def test_top_n():
    assert len(merchant_breakdown(ROWS, top_n=1).top_by_spend) == 1
```

`test_recurring.py`:

```python
"""Recurring: what the stored flag marks, its monthly cost, and unflagged small regulars."""

from decimal import Decimal

import pytest

from app.modules.analytics.domain.recurring import HiddenSubscription, RecurringMerchant, recurring_analysis
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

ROWS = [
    row("2026-01-01", "-10.00", merchant="Netflix", recurring=True),
    row("2026-01-02", "-3.00", merchant="Coffee"),
    row("2026-01-09", "-3.00", merchant="Coffee"),
    row("2026-01-15", "-900.00", merchant="Landlord", recurring=True),
    row("2026-01-16", "-3.00", merchant="coffee"),
    row("2026-01-20", "-100.00", merchant="IKEA"),
    row("2026-01-27", "2000.00", merchant="Employer", recurring=True),  # income: ignored
    row("2026-02-01", "-10.00", merchant="Netflix", recurring=True),
    row("2026-02-02", "-3.50", merchant="Coffee"),
    row("2026-02-09", "-3.50", merchant="Coffee"),
    row("2026-02-15", "-900.00", merchant="Landlord", recurring=True),
    row("2026-02-16", "-3.50", merchant="Coffee"),
    row("2026-03-01", "-12.00", merchant="Netflix", recurring=True),
]


def test_flagged_spend_and_its_share():
    result = recurring_analysis(ROWS)
    assert result.total_expenses == Decimal("1951.50")
    assert result.recurring_total == Decimal("1832.00")
    assert result.recurring_count == 5
    assert result.amount_share_pct == 93.88
    assert result.count_share_pct == 41.67  # 5 of 12 expenses


def test_monthly_recurring_cost_is_a_run_rate():
    result = recurring_analysis(ROWS)
    assert result.merchants == (
        RecurringMerchant("Landlord", 2, 2, Decimal("900.00"), Decimal("900.00")),
        RecurringMerchant("Netflix", 3, 3, Decimal("10.00"), Decimal("10.00")),  # median, not mean
    )
    assert result.monthly_recurring_cost == Decimal("910.00")


def test_hidden_subscriptions_are_unflagged_small_and_frequent():
    result = recurring_analysis(ROWS)
    assert result.hidden_subscriptions == (HiddenSubscription("Coffee", 6, 2, Decimal("3.25"), 3.0),)


def test_empty_input():
    result = recurring_analysis([])
    assert result.recurring_total == Decimal("0.00")
    assert result.amount_share_pct == 0.0
    assert result.merchants == () and result.hidden_subscriptions == ()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_merchants.py tests/unit/modules/analytics/test_recurring.py -v`
Expected: `ModuleNotFoundError` for `merchants` and `recurring`.

- [ ] **Step 3: Implement `merchants.py`**

```python
"""Merchants: who gets the money, how often, and how concentrated spending is."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.modules.analytics.domain._aggregate import Row, average, expenses, group_by, share_pct, total_spend

HIGH_CONCENTRATION = 2500
MEDIUM_CONCENTRATION = 1500


@dataclass(frozen=True)
class MerchantSpend:
    merchant: str
    total: Decimal
    count: int
    average: Decimal
    first_date: dt.date
    last_date: dt.date
    share_pct: float


@dataclass(frozen=True)
class MerchantConcentration:
    top_5_share_pct: float
    top_10_share_pct: float
    herfindahl_index: float
    risk: Literal["low", "medium", "high"]
    unique_merchants: int


@dataclass(frozen=True)
class MerchantBreakdown:
    total_expenses: Decimal
    top_by_spend: tuple[MerchantSpend, ...]
    top_by_frequency: tuple[MerchantSpend, ...]
    concentration: MerchantConcentration


def merchant_key(name: str) -> str:
    """Spellings that differ only in case or padding are one merchant."""
    return name.strip().casefold()


def display_names(rows: Sequence[Row]) -> dict[str, str]:
    """Each merchant key's latest spelling (rows are in date order, so the last one wins)."""
    return {merchant_key(r.merchant): r.merchant.strip() for r in rows}


def _concentration(ranked: Sequence[MerchantSpend], whole: Decimal) -> MerchantConcentration:
    shares = [float(m.total / whole * 100) for m in ranked] if whole else []
    hhi = round(sum(s * s for s in shares), 2)
    risk: Literal["low", "medium", "high"] = (
        "high" if hhi > HIGH_CONCENTRATION else "medium" if hhi > MEDIUM_CONCENTRATION else "low"
    )
    return MerchantConcentration(
        top_5_share_pct=round(sum(shares[:5]), 2),
        top_10_share_pct=round(sum(shares[:10]), 2),
        herfindahl_index=hhi,
        risk=risk,
        unique_merchants=len(ranked),
    )


def merchant_breakdown(rows: Sequence[Row], top_n: int = 15) -> MerchantBreakdown:
    """Merchants ranked by spend and by count; concentration over every merchant's share of all spending."""
    spent = expenses(rows)
    whole = total_spend(spent)
    names = display_names(spent)
    items = [
        MerchantSpend(
            merchant=names[key],
            total=total_spend(group),
            count=len(group),
            average=average(total_spend(group), len(group)),
            first_date=min(r.date for r in group),
            last_date=max(r.date for r in group),
            share_pct=share_pct(total_spend(group), whole),
        )
        for key, group in group_by(spent, lambda r: merchant_key(r.merchant)).items()
    ]
    by_spend = sorted(items, key=lambda m: (-m.total, m.merchant.casefold()))
    by_count = sorted(items, key=lambda m: (-m.count, -m.total, m.merchant.casefold()))
    return MerchantBreakdown(
        total_expenses=whole,
        top_by_spend=tuple(by_spend[:top_n]),
        top_by_frequency=tuple(by_count[:top_n]),
        concentration=_concentration(by_spend, whole),
    )
```

- [ ] **Step 4: Implement `recurring.py`**

```python
"""Recurring: spend the stored is_recurring flag marks, its run-rate, and unflagged small regulars.

No detection here: the flag is the one source of truth (docs/ROADMAP.md, decision of 15 Oct 2026).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from app.modules.analytics.domain._aggregate import (
    Row,
    average,
    expenses,
    group_by,
    money,
    month_start,
    share_pct,
    spend,
    total_spend,
)
from app.modules.analytics.domain.merchants import display_names, merchant_key

HIDDEN_MAX_AVERAGE = Decimal("50.00")
HIDDEN_MIN_PER_MONTH = 3


@dataclass(frozen=True)
class RecurringMerchant:
    merchant: str
    charges: int
    months_charged: int
    median_charge: Decimal
    monthly_cost: Decimal


@dataclass(frozen=True)
class HiddenSubscription:
    merchant: str
    charges: int
    months_active: int
    average_charge: Decimal
    charges_per_month: float


@dataclass(frozen=True)
class RecurringAnalysis:
    total_expenses: Decimal
    recurring_total: Decimal
    recurring_count: int
    amount_share_pct: float
    count_share_pct: float
    monthly_recurring_cost: Decimal
    merchants: tuple[RecurringMerchant, ...]
    hidden_subscriptions: tuple[HiddenSubscription, ...]


def _months(group: Sequence[Row]) -> int:
    return len({month_start(r.date) for r in group})


def recurring_analysis(rows: Sequence[Row]) -> RecurringAnalysis:
    """Flagged spend and share; per flagged merchant, median charge × charges per month; hidden candidates."""
    spent = expenses(rows)
    flagged = [r for r in spent if r.is_recurring]
    unflagged = [r for r in spent if not r.is_recurring]
    names = display_names(spent)

    merchants: list[RecurringMerchant] = []
    for key, group in group_by(flagged, lambda r: merchant_key(r.merchant)).items():
        charge = money(median(spend(r) for r in group))
        months = _months(group)
        merchants.append(RecurringMerchant(names[key], len(group), months, charge, money(charge * len(group) / months)))
    merchants.sort(key=lambda m: (-m.monthly_cost, m.merchant.casefold()))

    hidden: list[HiddenSubscription] = []
    for key, group in group_by(unflagged, lambda r: merchant_key(r.merchant)).items():
        months = _months(group)
        mean_charge = average(total_spend(group), len(group))
        per_month = round(len(group) / months, 2)
        if mean_charge <= HIDDEN_MAX_AVERAGE and per_month >= HIDDEN_MIN_PER_MONTH:
            hidden.append(HiddenSubscription(names[key], len(group), months, mean_charge, per_month))
    hidden.sort(key=lambda h: (-h.charges_per_month, h.merchant.casefold()))

    whole, recurring_total = total_spend(spent), total_spend(flagged)
    return RecurringAnalysis(
        total_expenses=whole,
        recurring_total=recurring_total,
        recurring_count=len(flagged),
        amount_share_pct=share_pct(recurring_total, whole),
        count_share_pct=share_pct(Decimal(len(flagged)), Decimal(len(spent))),
        monthly_recurring_cost=money(sum((m.monthly_cost for m in merchants), Decimal(0))),
        merchants=tuple(merchants),
        hidden_subscriptions=tuple(hidden),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/ -v`
Expected: all PASS.

- [ ] **Step 6: Lint and commit**

```bash
cd server && uv run ruff format app tests && uv run ruff check app tests && uv run lint-imports && cd ..
git add server/app/modules/analytics/domain/merchants.py server/app/modules/analytics/domain/recurring.py \
  server/tests/unit/modules/analytics/test_merchants.py server/tests/unit/modules/analytics/test_recurring.py
git commit -m "Analytics: the merchant and recurring analyses"
```

---

### Task 5: Behaviour

**Files:**
- Create: `server/app/modules/analytics/domain/behaviour.py`
- Test: `server/tests/unit/modules/analytics/test_behaviour.py`

**Interfaces:**
- Consumes: `_aggregate` helpers.
- Produces: `behaviour_analysis(rows, date_from=None, date_to=None) -> Behaviour`; dataclasses `WeekdaySpend(weekday: int, name: str, total: Decimal, count: int, average: Decimal, share_pct: float)` (weekday 0 = Monday), `WeekPart(days: int, total: Decimal, per_day: Decimal)`, `MonthOfYear(month: int, average_spend: Decimal, index: Optional[float])`, `CategoryStability(category: str, count: int, cv: float, stability: Literal["stable", "moderate", "volatile"])`, `Behaviour(by_weekday: tuple[WeekdaySpend, ...], weekday: WeekPart, weekend: WeekPart, weekend_bias_pct: Optional[float], seasonality: tuple[MonthOfYear, ...], stability: tuple[CategoryStability, ...], stable_share_pct: float, moderate_share_pct: float, volatile_share_pct: float, expense_change_pct: Optional[float])`.

- [ ] **Step 1: Write the failing test**

```python
"""Behaviour: weekdays, weekends, seasons, and which categories are steady."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.behaviour import MonthOfYear, WeekPart, WeekdaySpend, behaviour_analysis
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

# 2 March 2026 is a Monday; 2–15 March is 10 weekdays and 4 weekend days.
WEEK = [
    row("2026-03-02", "-20.00"),
    row("2026-03-03", "-10.00"),
    row("2026-03-07", "-40.00"),
    row("2026-03-08", "-20.00"),
    row("2026-03-09", "-10.00"),
    row("2026-03-14", "100.00", category="income"),
]
START, END = dt.date(2026, 3, 2), dt.date(2026, 3, 15)


def test_by_weekday_has_seven_days_from_monday():
    days = behaviour_analysis(WEEK, START, END).by_weekday
    assert [d.name for d in days] == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert days[0] == WeekdaySpend(0, "Monday", Decimal("30.00"), 2, Decimal("15.00"), 30.0)
    assert days[2] == WeekdaySpend(2, "Wednesday", Decimal("0.00"), 0, Decimal("0.00"), 0.0)
    assert days[5].share_pct == 40.0


def test_weekend_per_day_divides_by_real_calendar_days():
    result = behaviour_analysis(WEEK, START, END)
    assert result.weekday == WeekPart(10, Decimal("40.00"), Decimal("4.00"))
    assert result.weekend == WeekPart(4, Decimal("60.00"), Decimal("15.00"))
    assert result.weekend_bias_pct == 275.0


def test_stability_classes_need_five_expenses():
    rows = [row(f"2026-03-0{d}", "-10.00", category="food_groceries") for d in range(1, 6)]
    rows += [row(f"2026-03-0{d}", a, category="bars_restaurants") for d, a in zip(range(1, 6), ["-10", "-50", "-10", "-50", "-10"], strict=True)]
    rows += [row(f"2026-03-0{d}", "-99.00", category="shopping") for d in range(1, 5)]  # four: unclassified
    result = behaviour_analysis(sorted(rows, key=lambda r: r.date))
    assert [(s.category, s.cv, s.stability) for s in result.stability] == [
        ("food_groceries", 0.0, "stable"),
        ("bars_restaurants", 0.7537, "volatile"),
    ]
    assert (result.stable_share_pct, result.moderate_share_pct, result.volatile_share_pct) == (27.78, 0.0, 72.22)


def test_seasonality_averages_each_calendar_month_across_years():
    rows = [row("2025-01-10", "-100.00"), row("2026-01-10", "-300.00")]
    season = behaviour_analysis(rows).seasonality
    assert len(season) == 12
    assert season[0] == MonthOfYear(1, Decimal("200.00"), 650.0)  # 400 over 13 months → mean 30.77
    assert season[1] == MonthOfYear(2, Decimal("0.00"), 0.0)


def test_month_over_month_expense_change():
    rows = [row("2026-02-10", "-100.00"), row("2026-03-10", "-150.00")]
    assert behaviour_analysis(rows).expense_change_pct == 50.0
    assert behaviour_analysis(WEEK, START, END).expense_change_pct is None  # one month


def test_empty_input():
    result = behaviour_analysis([])
    assert result.weekday == WeekPart(0, Decimal("0.00"), Decimal("0.00"))
    assert result.weekend_bias_pct is None
    assert all(m.index is None for m in result.seasonality)
    assert result.stability == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_behaviour.py -v`
Expected: `ModuleNotFoundError` for `behaviour`.

- [ ] **Step 3: Implement `behaviour.py`**

```python
"""Behaviour: spending by weekday and season, and how steady each category is."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import mean
from typing import Literal, Optional

from app.modules.analytics.domain._aggregate import (
    ZERO,
    Row,
    average,
    cv,
    expenses,
    group_by,
    money,
    month_range,
    monthly_totals,
    pct_change,
    share_pct,
    span,
    spend,
    total_spend,
)

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
WEEKEND = (5, 6)
STABILITY_MIN_EXPENSES = 5
STABLE_BELOW = 0.3
MODERATE_BELOW = 0.7

Stability = Literal["stable", "moderate", "volatile"]


@dataclass(frozen=True)
class WeekdaySpend:
    weekday: int
    name: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float


@dataclass(frozen=True)
class WeekPart:
    days: int
    total: Decimal
    per_day: Decimal


@dataclass(frozen=True)
class MonthOfYear:
    month: int
    average_spend: Decimal
    index: Optional[float]


@dataclass(frozen=True)
class CategoryStability:
    category: str
    count: int
    cv: float
    stability: Stability


@dataclass(frozen=True)
class Behaviour:
    by_weekday: tuple[WeekdaySpend, ...]
    weekday: WeekPart
    weekend: WeekPart
    weekend_bias_pct: Optional[float]
    seasonality: tuple[MonthOfYear, ...]
    stability: tuple[CategoryStability, ...]
    stable_share_pct: float
    moderate_share_pct: float
    volatile_share_pct: float
    expense_change_pct: Optional[float]


def _week_part(spent: Sequence[Row], covered: Optional[tuple[dt.date, dt.date]], weekend: bool) -> WeekPart:
    rows = [r for r in spent if (r.date.weekday() in WEEKEND) == weekend]
    days = 0
    if covered:
        length = (covered[1] - covered[0]).days + 1
        days = sum(1 for i in range(length) if ((covered[0] + dt.timedelta(days=i)).weekday() in WEEKEND) == weekend)
    total = total_spend(rows)
    return WeekPart(days, total, average(total, days))


def _seasonality(spent: Sequence[Row], months: Sequence[dt.date]) -> tuple[MonthOfYear, ...]:
    totals = monthly_totals(spent, months, spend)
    overall = mean(totals) if totals else ZERO
    result: list[MonthOfYear] = []
    for calendar_month in range(1, 13):
        present = [t for m, t in zip(months, totals, strict=True) if m.month == calendar_month]
        if not present:
            result.append(MonthOfYear(calendar_month, ZERO, None))
            continue
        avg = money(sum(present, ZERO) / len(present))
        index = round(float(sum(present, ZERO) / len(present) / overall * 100), 2) if overall else None
        result.append(MonthOfYear(calendar_month, avg, index))
    return tuple(result)


def _stability(spent: Sequence[Row]) -> list[CategoryStability]:
    classified: list[CategoryStability] = []
    for category, group in group_by(spent, lambda r: r.category).items():
        if len(group) < STABILITY_MIN_EXPENSES:
            continue
        value = cv([spend(r) for r in group]) or 0.0
        label: Stability = "stable" if value < STABLE_BELOW else "moderate" if value < MODERATE_BELOW else "volatile"
        classified.append(CategoryStability(category, len(group), value, label))
    return sorted(classified, key=lambda s: (s.cv, s.category))


def behaviour_analysis(
    rows: Sequence[Row], date_from: Optional[dt.date] = None, date_to: Optional[dt.date] = None
) -> Behaviour:
    """Weekday and weekend spend, seasonality, category stability and the last month-over-month change."""
    spent = expenses(rows)
    whole = total_spend(spent)
    covered = span(rows, date_from, date_to)
    months = month_range(*covered) if covered else []

    by_day = group_by(spent, lambda r: r.date.weekday())
    weekdays = tuple(
        WeekdaySpend(
            day,
            WEEKDAY_NAMES[day],
            total_spend(by_day.get(day, [])),
            len(by_day.get(day, [])),
            average(total_spend(by_day.get(day, [])), len(by_day.get(day, []))),
            share_pct(total_spend(by_day.get(day, [])), whole),
        )
        for day in range(7)
    )
    weekday, weekend = _week_part(spent, covered, False), _week_part(spent, covered, True)
    bias = pct_change(weekday.per_day, weekend.per_day)

    stability = _stability(spent)
    by_class = {
        label: total_spend(r for s in stability if s.stability == label for r in spent if r.category == s.category)
        for label in ("stable", "moderate", "volatile")
    }
    classified = sum(by_class.values(), ZERO)

    totals = monthly_totals(spent, months, spend)
    change = pct_change(totals[-2], totals[-1]) if len(totals) >= 2 else None

    return Behaviour(
        by_weekday=weekdays,
        weekday=weekday,
        weekend=weekend,
        weekend_bias_pct=bias,
        seasonality=_seasonality(spent, months),
        stability=tuple(stability),
        stable_share_pct=share_pct(by_class["stable"], classified),
        moderate_share_pct=share_pct(by_class["moderate"], classified),
        volatile_share_pct=share_pct(by_class["volatile"], classified),
        expense_change_pct=change,
    )
```

Note on `weekend_bias_pct`: `pct_change(weekday.per_day, weekend.per_day)` is `(weekend ÷ weekday − 1) × 100`, and `None` when weekdays spent nothing.

- [ ] **Step 4: Run test to verify it passes**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_behaviour.py -v`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
cd server && uv run ruff format app tests && uv run ruff check app tests && uv run lint-imports && cd ..
git add server/app/modules/analytics/domain/behaviour.py server/tests/unit/modules/analytics/test_behaviour.py
git commit -m "Analytics: the behaviour analysis"
```

---

### Task 6: Anomalies

**Files:**
- Create: `server/app/modules/analytics/domain/anomalies.py`
- Test: `server/tests/unit/modules/analytics/test_anomalies.py`

**Interfaces:**
- Consumes: `_aggregate` helpers.
- Produces: `find_anomalies(rows, std_threshold=2.5, window_days=30, date_from=None, date_to=None) -> Anomalies`; dataclasses `Outlier(date: dt.date, merchant: str, category: str, amount: Decimal, z_score: float, window_mean: Decimal)` (`amount` positive), `CategorySpike(category: str, recent_total: Decimal, baseline_30d: Decimal, spike_pct: float)`, `Anomalies(std_threshold: float, window_days: int, outliers: tuple[Outlier, ...], spikes: tuple[CategorySpike, ...], spike_window_start: Optional[dt.date], spike_window_end: Optional[dt.date])`.
- Constants: `MIN_WINDOW_EXPENSES = 5`, `MAX_OUTLIERS = 20`, `SPIKE_DAYS = 30`, `SPIKE_MIN_PCT = 50.0`.

- [ ] **Step 1: Write the failing test**

```python
"""Anomalies: single expenses far above their trailing window, and categories spiking lately."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.anomalies import CategorySpike, Outlier, find_anomalies
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

BASE = [row(f"2026-03-0{d}", a) for d, a in zip(range(1, 6), ["-10.00", "-12.00", "-10.00", "-12.00", "-10.00"], strict=True)]


def test_flags_an_expense_far_above_its_trailing_window():
    rows = BASE + [row("2026-03-06", "-100.00", merchant="Big"), row("2026-03-06", "-11.00", merchant="Small")]
    result = find_anomalies(rows)
    assert result.outliers == (
        Outlier(dt.date(2026, 3, 6), "Big", "shopping", Decimal("100.00"), 91.04, Decimal("10.80")),
    )


def test_fewer_than_five_prior_expenses_never_flag():
    rows = BASE[:4] + [row("2026-03-05", "-1000.00")]
    assert find_anomalies(rows).outliers == ()


def test_the_window_ends_window_days_back():
    rows = [row(f"2026-02-0{d}", a) for d, a in zip(range(1, 6), ["-10.00", "-12.00", "-10.00", "-12.00", "-10.00"], strict=True)]
    rows.append(row("2026-03-07", "-100.00"))  # 30 days back is 5 Feb: only one prior expense in the window
    assert find_anomalies(rows).outliers == ()
    assert len(find_anomalies(rows, window_days=35).outliers) == 1


def test_identical_prior_expenses_have_no_spread_and_never_flag():
    rows = [row(f"2026-03-0{d}", "-10.00") for d in range(1, 6)] + [row("2026-03-06", "-500.00")]
    assert find_anomalies(rows).outliers == ()


def test_category_spikes_against_the_rest_of_the_range():
    rows = [
        row("2026-01-10", "-150.00", category="food_groceries"),
        row("2026-01-20", "-100.00", category="bars_restaurants"),
        row("2026-02-10", "-150.00", category="food_groceries"),
        row("2026-02-20", "-100.00", category="bars_restaurants"),
        row("2026-03-10", "-400.00", category="food_groceries"),
        row("2026-03-12", "-120.00", category="bars_restaurants"),
        row("2026-03-15", "-500.00", category="travel_holidays"),  # no history: no baseline, no spike
    ]
    result = find_anomalies(rows, date_from=dt.date(2026, 1, 1), date_to=dt.date(2026, 3, 31))
    assert (result.spike_window_start, result.spike_window_end) == (dt.date(2026, 3, 2), dt.date(2026, 3, 31))
    assert result.spikes == (CategorySpike("food_groceries", Decimal("400.00"), Decimal("150.00"), 166.67),)


def test_less_than_thirty_days_of_history_has_no_spikes():
    rows = [row("2026-02-20", "-10.00"), row("2026-03-10", "-400.00")]
    result = find_anomalies(rows, date_from=dt.date(2026, 2, 15), date_to=dt.date(2026, 3, 31))
    assert result.spikes == ()


def test_empty_input():
    result = find_anomalies([])
    assert result.outliers == () and result.spikes == ()
    assert result.spike_window_start is None
```

Hand check for the first test: prior window 10, 12, 10, 12, 10 → mean 10.8, population stdev √0.96 = 0.97980; z = (100 − 10.8) ÷ 0.97980 = 91.04. "Small" scores 0.20. For the spikes: the recent window is 2–31 March; baseline days are 1 Jan–1 Mar = 60; food's earlier 300 → 150 per 30 days; 400 ÷ 150 − 1 = 166.67 %. Bars: 200 → 100; 120 is +20 %, under the 50 % bar.

- [ ] **Step 2: Run test to verify it fails**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_anomalies.py -v`
Expected: `ModuleNotFoundError` for `anomalies`.

- [ ] **Step 3: Implement `anomalies.py`**

```python
"""Anomalies: expenses far above their trailing window, and categories spending more than usual lately."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import mean, pstdev
from typing import Optional

from app.modules.analytics.domain._aggregate import Row, expenses, group_by, money, span, spend, total_spend

MIN_WINDOW_EXPENSES = 5
MAX_OUTLIERS = 20
SPIKE_DAYS = 30
SPIKE_MIN_PCT = 50.0


@dataclass(frozen=True)
class Outlier:
    date: dt.date
    merchant: str
    category: str
    amount: Decimal
    z_score: float
    window_mean: Decimal


@dataclass(frozen=True)
class CategorySpike:
    category: str
    recent_total: Decimal
    baseline_30d: Decimal
    spike_pct: float


@dataclass(frozen=True)
class Anomalies:
    std_threshold: float
    window_days: int
    outliers: tuple[Outlier, ...]
    spikes: tuple[CategorySpike, ...]
    spike_window_start: Optional[dt.date]
    spike_window_end: Optional[dt.date]


def _outliers(spent: Sequence[Row], std_threshold: float, window_days: int) -> list[Outlier]:
    """Each expense against the expenses of the window_days days before its own day."""
    ordered = sorted(spent, key=lambda r: r.date)
    found: list[Outlier] = []
    for current in ordered:
        start = current.date - dt.timedelta(days=window_days)
        window = [spend(r) for r in ordered if start <= r.date < current.date]
        if len(window) < MIN_WINDOW_EXPENSES:
            continue
        spread = pstdev(window)
        if spread == 0:
            continue
        centre = mean(window)
        z = float((spend(current) - centre) / spread)
        if z > std_threshold:
            found.append(
                Outlier(current.date, current.merchant, current.category, money(spend(current)), round(z, 2), money(centre))
            )
    found.sort(key=lambda o: (-o.z_score, o.date))
    return found[:MAX_OUTLIERS]


def _spikes(spent: Sequence[Row], start: dt.date, end: dt.date) -> list[CategorySpike]:
    """The last 30 days per category against its average 30 days over the rest of the range."""
    recent_start = end - dt.timedelta(days=SPIKE_DAYS - 1)
    baseline_days = (recent_start - start).days
    if baseline_days < SPIKE_DAYS:
        return []
    spikes: list[CategorySpike] = []
    for category, group in group_by(spent, lambda r: r.category).items():
        recent = total_spend(r for r in group if recent_start <= r.date <= end)
        before = total_spend(r for r in group if r.date < recent_start)
        if before == 0 or recent == 0:
            continue
        baseline = before * SPIKE_DAYS / baseline_days
        pct = round(float((recent / baseline - 1) * 100), 2)
        if pct > SPIKE_MIN_PCT:
            spikes.append(CategorySpike(category, recent, money(baseline), pct))
    return sorted(spikes, key=lambda s: (-s.spike_pct, s.category))


def find_anomalies(
    rows: Sequence[Row],
    std_threshold: float = 2.5,
    window_days: int = 30,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
) -> Anomalies:
    """Outliers by trailing z-score, and category spikes in the range's last 30 days."""
    spent = expenses(rows)
    covered = span(spent, date_from, date_to)
    spikes = _spikes(spent, *covered) if covered else []
    return Anomalies(
        std_threshold=std_threshold,
        window_days=window_days,
        outliers=tuple(_outliers(spent, std_threshold, window_days)),
        spikes=tuple(spikes),
        spike_window_start=covered[1] - dt.timedelta(days=SPIKE_DAYS - 1) if covered else None,
        spike_window_end=covered[1] if covered else None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_anomalies.py -v`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
cd server && uv run ruff format app tests && uv run ruff check app tests && uv run lint-imports && cd ..
git add server/app/modules/analytics/domain/anomalies.py server/tests/unit/modules/analytics/test_anomalies.py
git commit -m "Analytics: outliers and category spikes"
```

---

### Task 7: The dashboard figures

**Files:**
- Create: `server/app/modules/analytics/domain/dashboard.py`
- Test: `server/tests/unit/modules/analytics/test_dashboard.py`

**Interfaces:**
- Consumes: `_aggregate`, `spending.monthly_flows`, `categories.category_spend`.
- Produces: `build_dashboard(rows) -> Dashboard`; dataclasses `CategorySlice(category: Optional[str], amount: Decimal, share_pct: float)` (`None` is "Other"), `TrendPoint(month: str, income: Decimal, expenses: Decimal)`, `Dashboard(reference_month: Optional[str], total_spent: Decimal, recurring_spent: Decimal, recurring_count: int, net_balance: Decimal, average_cashflow: Decimal, cashflow_months: int, spending_by_category: tuple[CategorySlice, ...], monthly_trend: tuple[TrendPoint, ...])`.
- Constants: `TOP_SLICES = 5`, `CASHFLOW_MONTHS = 3`, `TREND_MONTHS = 6`.

- [ ] **Step 1: Write the failing test**

```python
"""The home page's figures, all anchored to the latest month with data (spec D1, D2)."""

from decimal import Decimal

import pytest

from app.modules.analytics.domain.dashboard import CategorySlice, TrendPoint, build_dashboard
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

ROWS = [
    row("2026-07-10", "-100.00", category="food_groceries"),
    row("2026-07-25", "2000.00", category="salary"),
    row("2026-08-05", "-900.00", merchant="Landlord", category="household_utilities", recurring=True),
    row("2026-08-10", "2000.00", category="salary"),
    row("2026-09-01", "-900.00", merchant="Landlord", category="household_utilities", recurring=True),
    row("2026-09-03", "-15.00", merchant="Netflix", category="leisure_entertainment", recurring=True),
    row("2026-09-05", "-200.00", category="food_groceries"),
    row("2026-09-06", "-100.00", category="bars_restaurants"),
    row("2026-09-07", "-80.00", category="transportation"),
    row("2026-09-08", "-60.00", category="shopping"),
    row("2026-09-09", "-40.00", category="healthcare_drug_stores"),
    row("2026-09-25", "2100.00", category="salary"),
]


def test_cards_read_the_latest_month_with_data():
    d = build_dashboard(ROWS)
    assert d.reference_month == "2026-09"
    assert d.total_spent == Decimal("1395.00")
    assert (d.recurring_spent, d.recurring_count) == (Decimal("915.00"), 2)
    assert d.net_balance == Decimal("705.00")
    assert (d.average_cashflow, d.cashflow_months) == (Decimal("1235.00"), 3)  # (1900 + 1100 + 705) ÷ 3


def test_top_five_categories_and_other_sum_to_total_spent():
    d = build_dashboard(ROWS)
    assert d.spending_by_category == (
        CategorySlice("household_utilities", Decimal("900.00"), 64.52),
        CategorySlice("food_groceries", Decimal("200.00"), 14.34),
        CategorySlice("bars_restaurants", Decimal("100.00"), 7.17),
        CategorySlice("transportation", Decimal("80.00"), 5.73),
        CategorySlice("shopping", Decimal("60.00"), 4.3),
        CategorySlice(None, Decimal("55.00"), 3.94),
    )
    assert sum(s.amount for s in d.spending_by_category) == d.total_spent


def test_trend_is_six_zero_filled_months_ending_at_the_reference_month():
    assert build_dashboard(ROWS).monthly_trend == (
        TrendPoint("2026-04", Decimal("0.00"), Decimal("0.00")),
        TrendPoint("2026-05", Decimal("0.00"), Decimal("0.00")),
        TrendPoint("2026-06", Decimal("0.00"), Decimal("0.00")),
        TrendPoint("2026-07", Decimal("2000.00"), Decimal("100.00")),
        TrendPoint("2026-08", Decimal("2000.00"), Decimal("900.00")),
        TrendPoint("2026-09", Decimal("2100.00"), Decimal("1395.00")),
    )


def test_one_month_of_data_averages_over_one_month():
    d = build_dashboard([row("2026-09-01", "-40.00"), row("2026-09-02", "100.00", category="salary")])
    assert (d.average_cashflow, d.cashflow_months) == (Decimal("60.00"), 1)


def test_a_gap_month_inside_the_window_counts_as_zero():
    d = build_dashboard([row("2026-06-15", "500.00", category="salary"), row("2026-09-01", "-30.00")])
    assert d.cashflow_months == 3  # July, August (empty) and September; June is outside the window
    assert d.average_cashflow == Decimal("-10.00")


def test_five_or_fewer_categories_have_no_other_slice():
    d = build_dashboard([row("2026-09-01", "-40.00", category="shopping")])
    assert d.spending_by_category == (CategorySlice("shopping", Decimal("40.00"), 100.0),)


def test_no_transactions():
    d = build_dashboard([])
    assert d.reference_month is None
    assert d.total_spent == Decimal("0.00") and d.average_cashflow == Decimal("0.00")
    assert d.cashflow_months == 0
    assert d.spending_by_category == () and d.monthly_trend == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_dashboard.py -v`
Expected: `ModuleNotFoundError` for `dashboard`.

- [ ] **Step 3: Implement `dashboard.py`**

```python
"""The home page's figures: the latest month with data, its cards, its categories, and the trend to it."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.modules.analytics.domain._aggregate import (
    ZERO,
    Row,
    add_months,
    expenses,
    money,
    month_key,
    month_range,
    month_start,
    share_pct,
    total_spend,
)
from app.modules.analytics.domain.categories import category_spend
from app.modules.analytics.domain.spending import monthly_flows

TOP_SLICES = 5
CASHFLOW_MONTHS = 3
TREND_MONTHS = 6


@dataclass(frozen=True)
class CategorySlice:
    category: Optional[str]
    amount: Decimal
    share_pct: float


@dataclass(frozen=True)
class TrendPoint:
    month: str
    income: Decimal
    expenses: Decimal


@dataclass(frozen=True)
class Dashboard:
    reference_month: Optional[str]
    total_spent: Decimal
    recurring_spent: Decimal
    recurring_count: int
    net_balance: Decimal
    average_cashflow: Decimal
    cashflow_months: int
    spending_by_category: tuple[CategorySlice, ...]
    monthly_trend: tuple[TrendPoint, ...]


EMPTY = Dashboard(None, ZERO, ZERO, 0, ZERO, ZERO, 0, (), ())


def _slices(month_rows: Sequence[Row], total: Decimal) -> tuple[CategorySlice, ...]:
    ranked = category_spend(month_rows)
    slices = [CategorySlice(c.category, c.total, share_pct(c.total, total)) for c in ranked[:TOP_SLICES]]
    rest = ranked[TOP_SLICES:]
    if rest:
        other = money(sum((c.total for c in rest), ZERO))
        slices.append(CategorySlice(None, other, share_pct(other, total)))
    return tuple(slices)


def build_dashboard(rows: Sequence[Row]) -> Dashboard:
    """Everything the home page draws. The reference month is the latest month holding a transaction."""
    if not rows:
        return EMPTY
    reference = month_start(max(r.date for r in rows))
    first = month_start(min(r.date for r in rows))
    month_rows = [r for r in rows if month_start(r.date) == reference]
    spent = expenses(month_rows)
    flagged = [r for r in spent if r.is_recurring]
    total = total_spend(spent)

    cashflow_window = month_range(max(first, add_months(reference, -(CASHFLOW_MONTHS - 1))), reference)
    cashflow = monthly_flows(rows, cashflow_window)
    trend = monthly_flows(rows, month_range(add_months(reference, -(TREND_MONTHS - 1)), reference))

    return Dashboard(
        reference_month=month_key(reference),
        total_spent=total,
        recurring_spent=total_spend(flagged),
        recurring_count=len(flagged),
        net_balance=cashflow[-1].net,
        average_cashflow=money(sum((m.net for m in cashflow), ZERO) / len(cashflow)),
        cashflow_months=len(cashflow),
        spending_by_category=_slices(month_rows, total),
        monthly_trend=tuple(TrendPoint(m.month, m.income, m.expenses) for m in trend),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `APP_ENV=test uv run pytest tests/unit/modules/analytics/ -v`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
cd server && uv run ruff format app tests && uv run ruff check app tests && uv run lint-imports && cd ..
git add server/app/modules/analytics/domain/dashboard.py server/tests/unit/modules/analytics/test_dashboard.py
git commit -m "Analytics: the dashboard figures for the latest month with data"
```

---

### Task 8: Schemas, service, routes and the contract

**Files:**
- Create: `server/app/modules/analytics/{exceptions,schemas,dependencies,service,router}.py`
- Modify: `server/app/modules/analytics/__init__.py`, `server/app/api/v1/api.py`
- Create: `server/tests/integration/modules/analytics/__init__.py` (empty), `conftest.py`, `test_routes.py`
- Regenerate: `server/openapi.json`, `web-app/packages/api-client/src/generated/**`

**Interfaces:**
- Consumes: `transaction_service.list_for_analysis`, `AnalysisRow` (Task 1); every domain function (Tasks 3–7).
- Produces: routes `GET /api/v1/analytics/{dashboard,spending,categories,merchants,recurring,behaviour,anomalies}` with operation ids `getDashboard`, `getSpending`, `getCategoryBreakdown`, `getMerchantBreakdown`, `getRecurring`, `getBehaviour`, `getAnomalies`.
- Produces (web, generated): `useGetDashboard`, `getGetDashboardQueryKey` in `@app/api-client/endpoints/analytics`; type `DashboardResponse` in `@app/api-client/types` with fields `reference_month: string | null`, `total_spent: string`, `recurring_spent: string`, `recurring_count: number`, `net_balance: string`, `average_cashflow: string`, `cashflow_months: number`, `spending_by_category: CategorySliceResponse[]` (`{ category: string | null; amount: string; share_pct: number }`), `monthly_trend: TrendPointResponse[]` (`{ month: string; income: string; expenses: string }`).
- Produces (Python, for steps 6 and 7): `analytics_service` with async methods `dashboard(session, user_id)`, `spending(session, user_id, date_range)`, `categories(session, user_id, date_range, top_n)`, `merchants(session, user_id, date_range, top_n)`, `recurring(session, user_id, date_range)`, `behaviour(session, user_id, date_range)`, `anomalies(session, user_id, date_range, std_threshold, window_days)`, each returning its response model.

- [ ] **Step 1: Write the failing integration tests**

`server/tests/integration/modules/analytics/conftest.py`:

```python
"""Fixtures for the analytics routes: transactions written straight to the table."""

import datetime as dt
from decimal import Decimal

import pytest
import pytest_asyncio

from app.modules.account.models import User
from app.modules.transaction.models import Transaction
from app.modules.transaction.service import fingerprint


@pytest_asyncio.fixture
async def other_user(db_session):
    user = User(clerk_id="user_other_analytics", email="other_analytics@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def add(db_session):
    """add(user, "2026-09-05", "-200.00", category=..., merchant=..., recurring=..., deleted=...)"""

    async def _add(user, day, amount, category="food_groceries", merchant="Shop", recurring=False, deleted=False):
        date, value = dt.date.fromisoformat(day), Decimal(amount)
        txn = Transaction(
            user_id=user.id,
            date=date,
            merchant=merchant,
            amount=value,
            description=None,
            category=category,
            confidence=1.0,
            is_recurring=recurring,
            original_category=None,
            fingerprint=fingerprint(user.id, date, merchant, value, None),
        )
        if deleted:
            txn.soft_delete()
        db_session.add(txn)
        await db_session.flush()
        return txn

    return _add
```

`server/tests/integration/modules/analytics/test_routes.py`:

```python
"""The analytics routes against a real database: auth, ownership, ranges, and one end-to-end dashboard."""

import pytest

pytestmark = pytest.mark.integration

BASE = "/api/v1/analytics"
ROUTES = ["dashboard", "spending", "categories", "merchants", "recurring", "behaviour", "anomalies"]


@pytest.mark.parametrize("route", ROUTES)
async def test_signed_out_is_401(client, route):
    assert (await client.get(f"{BASE}/{route}")).status_code == 401


@pytest.mark.parametrize("route", ROUTES)
async def test_a_user_with_no_transactions_gets_200(authenticated_client, route):
    assert (await authenticated_client.get(f"{BASE}/{route}")).status_code == 200


@pytest.mark.parametrize("route", ROUTES[1:])
async def test_an_inverted_range_is_422(authenticated_client, route):
    response = await authenticated_client.get(f"{BASE}/{route}", params={"date_from": "2026-03-02", "date_to": "2026-03-01"})
    assert response.status_code == 422
    assert response.json()["error"] == "INVALID_DATE_RANGE"


async def test_empty_dashboard(authenticated_client):
    body = (await authenticated_client.get(f"{BASE}/dashboard")).json()
    assert body == {
        "reference_month": None,
        "total_spent": "0.00",
        "recurring_spent": "0.00",
        "recurring_count": 0,
        "net_balance": "0.00",
        "average_cashflow": "0.00",
        "cashflow_months": 0,
        "spending_by_category": [],
        "monthly_trend": [],
    }


async def test_dashboard_counts_only_this_users_active_rows(authenticated_client, test_user, other_user, add):
    await add(test_user, "2026-08-10", "2000.00", category="salary")
    await add(test_user, "2026-09-01", "-900.00", category="household_utilities", merchant="Landlord", recurring=True)
    await add(test_user, "2026-09-05", "-200.00")
    await add(test_user, "2026-09-25", "2100.00", category="salary")
    await add(test_user, "2026-09-26", "-5000.00", deleted=True)  # soft-deleted: invisible
    await add(test_user, "2026-10-02", "-1.00", deleted=True)  # would move the reference month if counted
    await add(other_user, "2026-10-01", "-9999.00")  # another user's: invisible

    body = (await authenticated_client.get(f"{BASE}/dashboard")).json()

    assert body["reference_month"] == "2026-09"
    assert body["total_spent"] == "1100.00"
    assert (body["recurring_spent"], body["recurring_count"]) == ("900.00", 1)
    assert body["net_balance"] == "1000.00"
    assert (body["average_cashflow"], body["cashflow_months"]) == ("1500.00", 2)  # (2000 + 1000) ÷ 2
    assert body["spending_by_category"] == [
        {"category": "household_utilities", "amount": "900.00", "share_pct": 81.82},
        {"category": "food_groceries", "amount": "200.00", "share_pct": 18.18},
    ]
    assert [p["month"] for p in body["monthly_trend"]] == ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]


async def test_spending_respects_the_range(authenticated_client, test_user, add):
    await add(test_user, "2026-01-15", "-10.00")
    await add(test_user, "2026-02-15", "-20.00")
    await add(test_user, "2026-03-15", "-40.00")

    body = (
        await authenticated_client.get(f"{BASE}/spending", params={"date_from": "2026-02-01", "date_to": "2026-02-28"})
    ).json()

    assert body["total_expenses"] == "20.00"
    assert [m["month"] for m in body["months"]] == ["2026-02"]


async def test_categories_top_n_and_bounds(authenticated_client, test_user, add):
    for category in ("food_groceries", "shopping", "transportation"):
        await add(test_user, "2026-03-01", "-10.00", category=category)
    body = (await authenticated_client.get(f"{BASE}/categories", params={"top_n": 2})).json()
    assert len(body["top_categories"]) == 2
    assert (await authenticated_client.get(f"{BASE}/categories", params={"top_n": 51})).status_code == 422


async def test_anomalies_echo_their_parameters(authenticated_client):
    body = (await authenticated_client.get(f"{BASE}/anomalies", params={"std_threshold": 3, "window_days": 14})).json()
    assert (body["std_threshold"], body["window_days"]) == (3.0, 14)
    assert (await authenticated_client.get(f"{BASE}/anomalies", params={"window_days": 6})).status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `APP_ENV=test uv run pytest tests/integration/modules/analytics/ -v`
Expected: FAIL — every route answers 404 (not registered).

- [ ] **Step 3: Implement `exceptions.py`, `schemas.py`, `dependencies.py`**

`exceptions.py`:

```python
"""Analytics module domain exceptions."""

from app.exceptions.base import ValidationError


class InvalidDateRangeError(ValidationError):
    """date_from falls after date_to."""

    error_code = "INVALID_DATE_RANGE"
```

`schemas.py` — the response models mirror the domain dataclasses field for field, so the service validates a dataclass straight into its model with `from_attributes`:

```python
"""Analytics request and response schemas. Money is a decimal string; percents are 0–100."""

import datetime as dt
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DateRange(BaseModel):
    """Inclusive, optional bounds; omitted means all time."""

    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None


# Dashboard


class CategorySliceResponse(_Out):
    category: Optional[str] = Field(..., description="The category slug; null is every category past the top five")
    amount: Decimal = Field(..., description="Spend in the reference month")
    share_pct: float = Field(..., description="Share of the month's spend, 0–100")


class TrendPointResponse(_Out):
    month: str = Field(..., description="YYYY-MM")
    income: Decimal
    expenses: Decimal


class DashboardResponse(_Out):
    """The home page's figures for the latest month with an active transaction."""

    reference_month: Optional[str] = Field(..., description="YYYY-MM; null for a user with no transactions")
    total_spent: Decimal
    recurring_spent: Decimal = Field(..., description="Expenses flagged recurring in the reference month")
    recurring_count: int
    net_balance: Decimal = Field(..., description="Income minus expenses in the reference month")
    average_cashflow: Decimal = Field(..., description="Mean monthly net over cashflow_months")
    cashflow_months: int = Field(..., description="1–3 months ending at the reference month; 0 with no data")
    spending_by_category: List[CategorySliceResponse]
    monthly_trend: List[TrendPointResponse] = Field(..., description="The six months ending at the reference month")


# Spending


class MonthFlowResponse(_Out):
    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    expense_change_pct: Optional[float] = Field(..., description="Against the month before; null after a zero month")


class SpendingResponse(_Out):
    date_from: Optional[dt.date] = Field(..., description="The first day covered")
    date_to: Optional[dt.date] = Field(..., description="The last day covered")
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal
    transaction_count: int
    average_income: Decimal
    average_expense: Decimal
    average_monthly_income: Decimal
    average_monthly_expenses: Decimal
    burn_rate: Decimal = Field(..., description="Average monthly expenses minus average monthly income")
    months: List[MonthFlowResponse]


# Categories


class CategorySpendResponse(_Out):
    category: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float


class CategoryTrendResponse(_Out):
    category: str
    first_month_total: Decimal
    last_month_total: Decimal
    growth_pct: float
    cv: Optional[float] = Field(..., description="Coefficient of variation of the monthly totals")


class CategoryBreakdownResponse(_Out):
    total_expenses: Decimal
    top_categories: List[CategorySpendResponse]
    by_frequency: List[CategorySpendResponse]
    top_growing: List[CategoryTrendResponse]
    top_declining: List[CategoryTrendResponse]


# Merchants


class MerchantSpendResponse(_Out):
    merchant: str
    total: Decimal
    count: int
    average: Decimal
    first_date: dt.date
    last_date: dt.date
    share_pct: float


class MerchantConcentrationResponse(_Out):
    top_5_share_pct: float
    top_10_share_pct: float
    herfindahl_index: float = Field(..., description="Σ(share %)² over every merchant, 0–10000")
    risk: Literal["low", "medium", "high"]
    unique_merchants: int


class MerchantBreakdownResponse(_Out):
    total_expenses: Decimal
    top_by_spend: List[MerchantSpendResponse]
    top_by_frequency: List[MerchantSpendResponse]
    concentration: MerchantConcentrationResponse


# Recurring


class RecurringMerchantResponse(_Out):
    merchant: str
    charges: int
    months_charged: int
    median_charge: Decimal
    monthly_cost: Decimal = Field(..., description="Median charge × charges per month charged")


class HiddenSubscriptionResponse(_Out):
    merchant: str
    charges: int
    months_active: int
    average_charge: Decimal
    charges_per_month: float


class RecurringResponse(_Out):
    total_expenses: Decimal
    recurring_total: Decimal
    recurring_count: int
    amount_share_pct: float
    count_share_pct: float
    monthly_recurring_cost: Decimal
    merchants: List[RecurringMerchantResponse]
    hidden_subscriptions: List[HiddenSubscriptionResponse]


# Behaviour


class WeekdaySpendResponse(_Out):
    weekday: int = Field(..., description="0 is Monday")
    name: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float


class WeekPartResponse(_Out):
    days: int = Field(..., description="Calendar days of this kind in the range")
    total: Decimal
    per_day: Decimal


class MonthOfYearResponse(_Out):
    month: int = Field(..., description="1 is January")
    average_spend: Decimal
    index: Optional[float] = Field(..., description="100 is the average month; null when the month is not in range")


class CategoryStabilityResponse(_Out):
    category: str
    count: int
    cv: float
    stability: Literal["stable", "moderate", "volatile"]


class BehaviourResponse(_Out):
    by_weekday: List[WeekdaySpendResponse]
    weekday: WeekPartResponse
    weekend: WeekPartResponse
    weekend_bias_pct: Optional[float]
    seasonality: List[MonthOfYearResponse]
    stability: List[CategoryStabilityResponse]
    stable_share_pct: float
    moderate_share_pct: float
    volatile_share_pct: float
    expense_change_pct: Optional[float] = Field(..., description="Between the range's last two months")


# Anomalies


class OutlierResponse(_Out):
    date: dt.date
    merchant: str
    category: str
    amount: Decimal = Field(..., description="The expense, positive")
    z_score: float
    window_mean: Decimal


class CategorySpikeResponse(_Out):
    category: str
    recent_total: Decimal
    baseline_30d: Decimal
    spike_pct: float


class AnomaliesResponse(_Out):
    std_threshold: float
    window_days: int
    outliers: List[OutlierResponse]
    spikes: List[CategorySpikeResponse]
    spike_window_start: Optional[dt.date]
    spike_window_end: Optional[dt.date]
```

`dependencies.py`:

```python
"""Analytics dependencies: the date range read from the query string."""

import datetime as dt
from typing import Annotated, Optional

from fastapi import Depends, Query

from app.modules.analytics.exceptions import InvalidDateRangeError
from app.modules.analytics.schemas import DateRange


def get_date_range(
    date_from: Optional[dt.date] = Query(None, description="On or after this day"),
    date_to: Optional[dt.date] = Query(None, description="On or before this day"),
) -> DateRange:
    """Inclusive, optional bounds. A start after the end is a 422."""
    if date_from and date_to and date_from > date_to:
        raise InvalidDateRangeError("date_from is after date_to", date_from=str(date_from), date_to=str(date_to))
    return DateRange(date_from=date_from, date_to=date_to)


AnalyticsRange = Annotated[DateRange, Depends(get_date_range)]
```

- [ ] **Step 4: Implement `service.py`**

```python
"""Analytics service: load the user's rows, run a calculation, shape the response."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.domain.anomalies import find_anomalies
from app.modules.analytics.domain.behaviour import behaviour_analysis
from app.modules.analytics.domain.categories import category_breakdown
from app.modules.analytics.domain.dashboard import build_dashboard
from app.modules.analytics.domain.merchants import merchant_breakdown
from app.modules.analytics.domain.recurring import recurring_analysis
from app.modules.analytics.domain.spending import spending_summary
from app.modules.analytics.schemas import (
    AnomaliesResponse,
    BehaviourResponse,
    CategoryBreakdownResponse,
    DashboardResponse,
    DateRange,
    MerchantBreakdownResponse,
    RecurringResponse,
    SpendingResponse,
)
from app.modules.transaction import AnalysisRow, transaction_service


async def _rows(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> list[AnalysisRow]:
    return await transaction_service.list_for_analysis(session, user_id, date_range.date_from, date_range.date_to)


class AnalyticsService:
    """Every analysis over one user's active transactions. Steps 6 and 7 call these directly."""

    @staticmethod
    async def dashboard(session: AsyncSession, user_id: uuid.UUID) -> DashboardResponse:
        rows = await _rows(session, user_id, DateRange())
        return DashboardResponse.model_validate(build_dashboard(rows), from_attributes=True)

    @staticmethod
    async def spending(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> SpendingResponse:
        rows = await _rows(session, user_id, date_range)
        result = spending_summary(rows, date_range.date_from, date_range.date_to)
        return SpendingResponse.model_validate(result, from_attributes=True)

    @staticmethod
    async def categories(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, top_n: int
    ) -> CategoryBreakdownResponse:
        rows = await _rows(session, user_id, date_range)
        result = category_breakdown(rows, top_n, date_range.date_from, date_range.date_to)
        return CategoryBreakdownResponse.model_validate(result, from_attributes=True)

    @staticmethod
    async def merchants(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, top_n: int
    ) -> MerchantBreakdownResponse:
        rows = await _rows(session, user_id, date_range)
        return MerchantBreakdownResponse.model_validate(merchant_breakdown(rows, top_n), from_attributes=True)

    @staticmethod
    async def recurring(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> RecurringResponse:
        rows = await _rows(session, user_id, date_range)
        return RecurringResponse.model_validate(recurring_analysis(rows), from_attributes=True)

    @staticmethod
    async def behaviour(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> BehaviourResponse:
        rows = await _rows(session, user_id, date_range)
        result = behaviour_analysis(rows, date_range.date_from, date_range.date_to)
        return BehaviourResponse.model_validate(result, from_attributes=True)

    @staticmethod
    async def anomalies(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, std_threshold: float, window_days: int
    ) -> AnomaliesResponse:
        rows = await _rows(session, user_id, date_range)
        result = find_anomalies(rows, std_threshold, window_days, date_range.date_from, date_range.date_to)
        return AnomaliesResponse.model_validate(result, from_attributes=True)


analytics_service = AnalyticsService()
```

- [ ] **Step 5: Implement `router.py`, the public surface, and register the router**

`router.py`:

```python
"""Analytics routes under /analytics. Every one reads; none writes."""

from fastapi import APIRouter, Query, Request

from app.core.config import settings
from app.core.limiter import limiter
from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.analytics.dependencies import AnalyticsRange
from app.modules.analytics.schemas import (
    AnomaliesResponse,
    BehaviourResponse,
    CategoryBreakdownResponse,
    DashboardResponse,
    MerchantBreakdownResponse,
    RecurringResponse,
    SpendingResponse,
)
from app.modules.analytics.service import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])

LIMIT = settings.rate_limits.endpoints.TRANSACTIONS[0]


@router.get(
    "/dashboard",
    operation_id="getDashboard",
    response_model=DashboardResponse,
    summary="The home dashboard",
    description="Figures for the latest month holding an active transaction, and the six months up to it.",
)
@limiter.limit(LIMIT)
async def get_dashboard(request: Request, db_session: DbSession, user: CurrentUser) -> DashboardResponse:
    return await analytics_service.dashboard(db_session, user.id)


@router.get(
    "/spending",
    operation_id="getSpending",
    response_model=SpendingResponse,
    summary="Income, expenses and net",
    description="Totals, averages and a zero-filled per-month series. Bounds are inclusive and optional.",
)
@limiter.limit(LIMIT)
async def get_spending(
    request: Request, db_session: DbSession, user: CurrentUser, date_range: AnalyticsRange
) -> SpendingResponse:
    return await analytics_service.spending(db_session, user.id, date_range)


@router.get(
    "/categories",
    operation_id="getCategoryBreakdown",
    response_model=CategoryBreakdownResponse,
    summary="Spend by category",
    description="Categories ranked by spend and by count, and the fastest growing and declining.",
)
@limiter.limit(LIMIT)
async def get_categories(
    request: Request,
    db_session: DbSession,
    user: CurrentUser,
    date_range: AnalyticsRange,
    top_n: int = Query(10, ge=1, le=50, description="How many categories each ranking keeps"),
) -> CategoryBreakdownResponse:
    return await analytics_service.categories(db_session, user.id, date_range, top_n)


@router.get(
    "/merchants",
    operation_id="getMerchantBreakdown",
    response_model=MerchantBreakdownResponse,
    summary="Spend by merchant",
    description="Merchants ranked by spend and by count, and how concentrated spending is.",
)
@limiter.limit(LIMIT)
async def get_merchants(
    request: Request,
    db_session: DbSession,
    user: CurrentUser,
    date_range: AnalyticsRange,
    top_n: int = Query(15, ge=1, le=50, description="How many merchants each ranking keeps"),
) -> MerchantBreakdownResponse:
    return await analytics_service.merchants(db_session, user.id, date_range, top_n)


@router.get(
    "/recurring",
    operation_id="getRecurring",
    response_model=RecurringResponse,
    summary="Recurring spend",
    description="Spend flagged recurring, its monthly cost per merchant, and unflagged small regular charges.",
)
@limiter.limit(LIMIT)
async def get_recurring(
    request: Request, db_session: DbSession, user: CurrentUser, date_range: AnalyticsRange
) -> RecurringResponse:
    return await analytics_service.recurring(db_session, user.id, date_range)


@router.get(
    "/behaviour",
    operation_id="getBehaviour",
    response_model=BehaviourResponse,
    summary="Spending patterns",
    description="By weekday, weekday against weekend, by calendar month, and how steady each category is.",
)
@limiter.limit(LIMIT)
async def get_behaviour(
    request: Request, db_session: DbSession, user: CurrentUser, date_range: AnalyticsRange
) -> BehaviourResponse:
    return await analytics_service.behaviour(db_session, user.id, date_range)


@router.get(
    "/anomalies",
    operation_id="getAnomalies",
    response_model=AnomaliesResponse,
    summary="Unusual spending",
    description="Expenses far above their trailing window, and categories spending more than usual lately.",
)
@limiter.limit(LIMIT)
async def get_anomalies(
    request: Request,
    db_session: DbSession,
    user: CurrentUser,
    date_range: AnalyticsRange,
    std_threshold: float = Query(2.5, ge=1.0, le=5.0, description="Standard deviations above the window mean"),
    window_days: int = Query(30, ge=7, le=90, description="Days before an expense that it is compared with"),
) -> AnomaliesResponse:
    return await analytics_service.anomalies(db_session, user.id, date_range, std_threshold, window_days)
```

`__init__.py` — replace with:

```python
"""Analytics — every calculation over the user's transactions. Stores nothing.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).
"""

from app.modules.analytics.router import router
from app.modules.analytics.schemas import (
    AnomaliesResponse,
    BehaviourResponse,
    CategoryBreakdownResponse,
    DashboardResponse,
    DateRange,
    MerchantBreakdownResponse,
    RecurringResponse,
    SpendingResponse,
)
from app.modules.analytics.service import analytics_service

__all__ = [
    "AnomaliesResponse",
    "BehaviourResponse",
    "CategoryBreakdownResponse",
    "DashboardResponse",
    "DateRange",
    "MerchantBreakdownResponse",
    "RecurringResponse",
    "SpendingResponse",
    "analytics_service",
    "router",
]
```

`server/app/api/v1/api.py`:

```python
from app.modules import account, analytics, conversation, transaction

api_router = APIRouter()
api_router.include_router(account.router)
api_router.include_router(analytics.router)
api_router.include_router(conversation.router)
api_router.include_router(transaction.router)
```

- [ ] **Step 6: Run the tests**

Run: `APP_ENV=test uv run pytest tests/integration/modules/analytics/ tests/unit/api/test_openapi_contract.py tests/unit/test_module_contracts.py -v`
Expected: all PASS. Then `uv run lint-imports` — every contract KEPT.

- [ ] **Step 7: Regenerate the contract**

Run (repo root): `make gen-contract`
Expected: `server/openapi.json` gains the seven paths; `web-app/packages/api-client/src/generated/endpoints/analytics/` appears with `useGetDashboard` and `getGetDashboardQueryKey`; `generated/types/` gains `dashboardResponse.ts` and friends. Check: `grep -n "reference_month" web-app/packages/api-client/src/generated/types/dashboardResponse.ts` shows `reference_month: string | null`, and `grep -n "total_spent" …` shows `string`. If a money field generates as `number | string` instead, stop and report it — the web code in Tasks 11–12 assumes `string`, as `TransactionResponse.amount` already is.

- [ ] **Step 8: Lint and commit**

```bash
cd server && uv run ruff format app tests && uv run ruff check app tests && cd ..
git add server/app/modules/analytics server/app/api/v1/api.py server/tests/integration/modules/analytics \
  server/openapi.json web-app/packages/api-client/src/generated
git commit -m "Analytics: the seven routes, their schemas and the regenerated client"
```

---

### Task 9: The chart primitive, Recharts and the palette

**Files:**
- Create: `web-app/packages/ui/src/primitives/chart.tsx`
- Modify: `web-app/packages/ui/package.json`, `web-app/apps/web/package.json`, `web-app/pnpm-lock.yaml`
- Modify: `web-app/packages/ui/src/styles/globals.css` (the `--chart-*` lines in `:root`, `.dark`, and `@theme inline`)

**Interfaces:**
- Produces: `@app/ui/chart` exporting `ChartConfig` (`Record<string, { label: React.ReactNode; color: string }>`), `ChartContainer` (props: div props + `config: ChartConfig` + Recharts children), `ChartTooltip` (Recharts `Tooltip`), `ChartTooltipContent` (props: `active?`, `payload?`, `label?`, `formatter?: (value: unknown, key: string) => React.ReactNode`, `labelFormatter?: (label: unknown) => React.ReactNode`, `hideLabel?`, `className?`). `ChartContainer` sets `--color-<key>` for each config key.
- Produces: CSS tokens `--chart-1` … `--chart-6` (6 is the neutral "Other") and Tailwind colours `chart-1` … `chart-6`.

- [ ] **Step 1: Add the dependency**

```bash
cd web-app
pnpm --filter @app/ui add recharts@^3.10.1
pnpm --filter @app/web add recharts@^3.10.1
cd ..
```

Expected: both `package.json` files list `"recharts": "^3.10.1"`; `pnpm-lock.yaml` resolves `recharts@3.10.1`. (Recharts' `react-is` peer is auto-installed by pnpm.)

- [ ] **Step 2: Write `chart.tsx`**

```tsx
"use client"

import * as React from "react"
import * as RechartsPrimitive from "recharts"
import { cn } from "@app/core/lib/utils"

/** Per-series label and colour, keyed by data key (a line) or by name (a pie slice). */
export type ChartConfig = Record<
  string,
  { label: React.ReactNode; color: string }
>

const ChartContext = React.createContext<{ config: ChartConfig } | null>(null)

function useChart() {
  const context = React.useContext(ChartContext)
  if (!context) {
    throw new Error("useChart must be used within a <ChartContainer />")
  }
  return context
}

/** Sizes a Recharts chart to its box and exposes each series colour as --color-<key>. */
function ChartContainer({
  config,
  className,
  style,
  children,
  ...props
}: React.ComponentProps<"div"> & {
  config: ChartConfig
  children: React.ComponentProps<
    typeof RechartsPrimitive.ResponsiveContainer
  >["children"]
}) {
  const colors = Object.fromEntries(
    Object.entries(config).map(([key, item]) => [`--color-${key}`, item.color]),
  )
  return (
    <ChartContext.Provider value={{ config }}>
      <div
        data-slot="chart"
        style={{ ...colors, ...style } as React.CSSProperties}
        className={cn(
          "flex justify-center text-xs [&_.recharts-cartesian-axis-tick_text]:fill-muted-foreground [&_.recharts-cartesian-grid_line]:stroke-border [&_.recharts-layer]:outline-hidden [&_.recharts-sector]:outline-hidden [&_.recharts-surface]:outline-hidden",
          className,
        )}
        {...props}
      >
        <RechartsPrimitive.ResponsiveContainer>
          {children}
        </RechartsPrimitive.ResponsiveContainer>
      </div>
    </ChartContext.Provider>
  )
}

const ChartTooltip = RechartsPrimitive.Tooltip

type TooltipItem = {
  name?: string | number
  dataKey?: unknown
  value?: unknown
  color?: string
}

/** Tooltip body: one row per series, labelled and coloured from the config; text in text tokens. */
function ChartTooltipContent({
  active,
  payload,
  label,
  formatter,
  labelFormatter,
  hideLabel = false,
  className,
}: {
  active?: boolean
  payload?: ReadonlyArray<TooltipItem>
  label?: unknown
  formatter?: (value: unknown, key: string) => React.ReactNode
  labelFormatter?: (label: unknown) => React.ReactNode
  hideLabel?: boolean
  className?: string
}) {
  const { config } = useChart()
  if (!active || !payload?.length) return null
  return (
    <div
      className={cn(
        "grid min-w-36 gap-1.5 rounded-lg border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-md",
        className,
      )}
    >
      {!hideLabel && label != null && (
        <div className="font-medium">
          {labelFormatter ? labelFormatter(label) : String(label)}
        </div>
      )}
      {payload.map((item) => {
        const key = String(
          typeof item.dataKey === "string" && config[item.dataKey]
            ? item.dataKey
            : (item.name ?? ""),
        )
        const entry = config[key]
        return (
          <div key={key} className="flex items-center gap-2">
            <span
              aria-hidden
              className="size-2.5 shrink-0 rounded-[2px]"
              style={{ backgroundColor: entry?.color ?? item.color }}
            />
            <span className="text-muted-foreground">{entry?.label ?? key}</span>
            <span className="ml-auto font-medium tabular-nums">
              {formatter ? formatter(item.value, key) : String(item.value)}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export { ChartContainer, ChartTooltip, ChartTooltipContent }
```

Do **not** add these to `packages/ui/src/index.ts` (brief condition 6); `@app/ui/chart` resolves through the `./*` export wildcard.

- [ ] **Step 3: Set the palette in `globals.css`**

The values are the `dataviz` skill's reference categorical slots 1–5, validated by its script against this app's card surfaces (light `#ffffff`, dark `#161b1d`): every hard check passes in both modes; light mode warns that slots 3–5 are under 3:1 contrast, which the category legend's visible labels and amounts relieve (Task 11). Slot 6 is the neutral for "Other".

In `:root`, replace the five `--chart-*` lines with:

```css
  --chart-1: #2a78d6;
  --chart-2: #eb6834;
  --chart-3: #1baf7a;
  --chart-4: #eda100;
  --chart-5: #e87ba4;
  --chart-6: #898781;
```

In `.dark`, replace the five `--chart-*` lines with:

```css
  --chart-1: #3987e5;
  --chart-2: #d95926;
  --chart-3: #199e70;
  --chart-4: #c98500;
  --chart-5: #d55181;
  --chart-6: #898781;
```

In the `@theme inline` block, add after `--color-chart-1: var(--chart-1);` … the line:

```css
  --color-chart-6: var(--chart-6);
```

Re-run the validator to confirm (path is the dataviz skill's `scripts/validate_palette.js`; load the `dataviz` skill to find its base directory):

```bash
node <dataviz>/scripts/validate_palette.js "#2a78d6,#eb6834,#1baf7a,#eda100,#e87ba4" --mode light --surface "#ffffff"
node <dataviz>/scripts/validate_palette.js "#3987e5,#d95926,#199e70,#c98500,#d55181" --mode dark --surface "#161b1d"
```

Expected: `ALL CHECKS PASS` for both (light with the contrast WARN described above).

- [ ] **Step 4: Type-check, format and commit**

```bash
cd web-app && pnpm exec prettier --write packages/ui/src/primitives/chart.tsx && pnpm -s type-check && cd ..
git add web-app/packages/ui/src/primitives/chart.tsx web-app/packages/ui/package.json web-app/apps/web/package.json \
  web-app/pnpm-lock.yaml web-app/packages/ui/src/styles/globals.css
git commit -m "UI: a chart primitive on Recharts, and a validated chart palette"
```

Expected: `type-check` exits 0.

---

### Task 10: Every transaction write refetches analytics

**Files:**
- Modify: `web-app/apps/web/src/components/transactions/use-invalidate-transactions.ts`
- Test: `web-app/apps/web/src/components/transactions/use-invalidate-transactions.test.tsx`

**Interfaces:**
- Consumes: `getListTransactionsQueryKey` (existing), the generated analytics keys' shape `[\`/api/v1/analytics/...\`, params?]` (Task 8).
- Produces: `useInvalidateTransactions()` and `useRefreshTransactionsOnSuccess()` keep their signatures; the invalidation now also covers every analytics query. Exported `ANALYTICS_KEY_PREFIX = "/api/v1/analytics/"`.

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect } from "vitest"
import { renderHook, act } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { getListTransactionsQueryKey } from "@app/api-client/endpoints/transactions"
import { getGetDashboardQueryKey } from "@app/api-client/endpoints/analytics"
import { useInvalidateTransactions } from "./use-invalidate-transactions"

const setup = () => {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity } },
  })
  const list = getListTransactionsQueryKey({ limit: 10 })
  const dashboard = getGetDashboardQueryKey()
  const spending = ["/api/v1/analytics/spending", { date_from: "2026-01-01" }]
  const unrelated = ["/api/v1/conversation"]
  for (const key of [list, dashboard, spending, unrelated]) {
    client.setQueryData(key, {})
  }
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(() => useInvalidateTransactions(), {
    wrapper,
  })
  const stale = (key: readonly unknown[]) =>
    client.getQueryState(key)?.isInvalidated
  return { invalidate: result.current, stale, list, dashboard, spending, unrelated }
}

describe("useInvalidateTransactions", () => {
  it("marks the list and every analytics query stale, and nothing else", async () => {
    const { invalidate, stale, list, dashboard, spending, unrelated } = setup()
    await act(() => invalidate())
    expect(stale(list)).toBe(true)
    expect(stale(dashboard)).toBe(true)
    expect(stale(spending)).toBe(true)
    expect(stale(unrelated)).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-app && pnpm -s test -- apps/web/src/components/transactions/use-invalidate-transactions.test.tsx`
Expected: FAIL — `stale(dashboard)` is `false`.

- [ ] **Step 3: Implement**

```ts
"use client"

import { useCallback, useMemo } from "react"
import { useQueryClient, type Query } from "@tanstack/react-query"
import { getListTransactionsQueryKey } from "@app/api-client/endpoints/transactions"

/**
 * Generated query keys are `[url, params?]`, so no key is a prefix of every
 * analytics query's; a predicate on the url catches them all.
 */
export const ANALYTICS_KEY_PREFIX = "/api/v1/analytics/"

const isAnalyticsQuery = (query: Query) => {
  const [url] = query.queryKey
  return typeof url === "string" && url.startsWith(ANALYTICS_KEY_PREFIX)
}

/**
 * Refetch every page of the list, and every analytics figure, after a write.
 * The list key without params is a prefix of each page's key.
 */
export function useInvalidateTransactions() {
  const queryClient = useQueryClient()
  return useCallback(
    () =>
      Promise.all([
        queryClient.invalidateQueries({
          queryKey: getListTransactionsQueryKey(),
        }),
        queryClient.invalidateQueries({ predicate: isAnalyticsQuery }),
      ]),
    [queryClient],
  )
}

/**
 * Hook-level mutation options that refetch the list on success. Hook-level
 * callbacks run even after the component unmounts — a per-call
 * `mutate(…, { onSuccess })` is skipped then — and the mutation stays
 * pending while the refetch runs.
 */
export function useRefreshTransactionsOnSuccess() {
  const invalidate = useInvalidateTransactions()
  return useMemo(
    () => ({ mutation: { onSuccess: () => invalidate() } }),
    [invalidate],
  )
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd web-app && pnpm -s test -- apps/web/src/components/transactions/`
Expected: all PASS (the new test and every existing transactions test).

- [ ] **Step 5: Format, type-check and commit**

```bash
cd web-app && pnpm exec prettier --write apps/web/src/components/transactions/use-invalidate-transactions.ts \
  apps/web/src/components/transactions/use-invalidate-transactions.test.tsx && pnpm -s type-check && cd ..
git add web-app/apps/web/src/components/transactions/use-invalidate-transactions.ts \
  web-app/apps/web/src/components/transactions/use-invalidate-transactions.test.tsx
git commit -m "Transactions: every write also refetches analytics"
```

---

### Task 11: Dashboard pieces — header, cards, charts

**Files (all under `web-app/apps/web/src/components/dashboard/`):**
- Create: `month.ts`, `category-slices.ts`, `trend-points.ts`, `welcome-header.tsx`, `summary-cards.tsx`, `category-chart.tsx`, `trend-chart.tsx`
- Test: `month.test.ts`, `category-slices.test.ts`, `trend-points.test.ts`, `welcome-header.test.tsx`, `summary-cards.test.tsx`

**Interfaces:**
- Consumes: `DashboardResponse`, `CategorySliceResponse`, `TrendPointResponse` from `@app/api-client/types` (Task 8); `formatAmount`, `amountClass` from `@/components/transactions/format`; `useCategories` from `@/components/transactions/use-categories`; `useAppAuth` from `@app/auth`; `@app/ui/chart` (Task 9).
- Produces: `formatMonth(key: string, month: "long" | "short" = "long"): string`; `toCategorySlices(slices: CategorySliceResponse[], label: (slug: string) => string): CategorySlice[]` where `CategorySlice = { key: string; name: string; amount: number; display: string; share: number; fill: string }`; `toTrendPoints(points: TrendPointResponse[]): TrendPoint[]` where `TrendPoint = { month: string; label: string; income: number; expenses: number; incomeText: string; expensesText: string }`; components `WelcomeHeader({ referenceMonth }: { referenceMonth?: string | null })`, `SummaryCards({ dashboard }: { dashboard: DashboardResponse })`, `CategoryChart({ slices }: { slices: CategorySliceResponse[] })`, `TrendChart({ points }: { points: TrendPointResponse[] })`.

- [ ] **Step 1: Write the failing tests**

`month.test.ts`:

```ts
import { describe, it, expect } from "vitest"
import { formatMonth } from "./month"

const expected = (month: "long" | "short") =>
  new Intl.DateTimeFormat(undefined, { month, year: month === "long" ? "numeric" : undefined }).format(
    new Date(2026, 8, 1),
  )

describe("formatMonth", () => {
  it("names a YYYY-MM month in the user's locale", () => {
    expect(formatMonth("2026-09")).toBe(expected("long"))
    expect(formatMonth("2026-09", "short")).toBe(expected("short"))
  })

  it("returns the key unchanged when it is not a month", () => {
    expect(formatMonth("nope")).toBe("nope")
  })
})
```

`category-slices.test.ts`:

```ts
import { describe, it, expect } from "vitest"
import { toCategorySlices } from "./category-slices"
import { formatAmount } from "@/components/transactions/format"

const label = (slug: string) =>
  ({ household_utilities: "Household & Utilities", food_groceries: "Food & Groceries" })[slug] ?? slug

describe("toCategorySlices", () => {
  it("labels categories, names the null slice Other and colours slices in order", () => {
    const slices = toCategorySlices(
      [
        { category: "household_utilities", amount: "900.00", share_pct: 81.82 },
        { category: "food_groceries", amount: "150.00", share_pct: 13.64 },
        { category: null, amount: "50.00", share_pct: 4.55 },
      ],
      label,
    )
    expect(slices).toEqual([
      { key: "household_utilities", name: "Household & Utilities", amount: 900, display: formatAmount("900.00"), share: 81.82, fill: "var(--chart-1)" },
      { key: "food_groceries", name: "Food & Groceries", amount: 150, display: formatAmount("150.00"), share: 13.64, fill: "var(--chart-2)" },
      { key: "other", name: "Other", amount: 50, display: formatAmount("50.00"), share: 4.55, fill: "var(--chart-6)" },
    ])
  })
})
```

`trend-points.test.ts`:

```ts
import { describe, it, expect } from "vitest"
import { toTrendPoints } from "./trend-points"
import { formatMonth } from "./month"
import { formatAmount } from "@/components/transactions/format"

describe("toTrendPoints", () => {
  it("turns decimal strings into plottable numbers and keeps the exact text for the tooltip", () => {
    expect(toTrendPoints([{ month: "2026-09", income: "2100.00", expenses: "1395.50" }])).toEqual([
      {
        month: "2026-09",
        label: formatMonth("2026-09", "short"),
        income: 2100,
        expenses: 1395.5,
        incomeText: formatAmount("2100.00"),
        expensesText: formatAmount("1395.50"),
      },
    ])
  })
})
```

`welcome-header.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import { useAppAuth } from "@app/auth"
import { WelcomeHeader } from "./welcome-header"
import { formatMonth } from "./month"

vi.mock("@app/auth", () => ({ useAppAuth: vi.fn() }))

const signedIn = (name: string | null) =>
  vi.mocked(useAppAuth).mockReturnValue({
    user: { name, email: null, imageUrl: null },
    isLoaded: true,
  } as unknown as ReturnType<typeof useAppAuth>)

describe("WelcomeHeader", () => {
  it("greets by first name and names the reference month", () => {
    signedIn("Ada Lovelace")
    render(<WelcomeHeader referenceMonth="2026-09" />)
    expect(screen.getByRole("heading", { name: "Welcome back, Ada" })).toBeInTheDocument()
    expect(screen.getByText(`Your overview for ${formatMonth("2026-09")}`)).toBeInTheDocument()
  })

  it("falls back without a name or a month", () => {
    signedIn(null)
    render(<WelcomeHeader referenceMonth={null} />)
    expect(screen.getByRole("heading", { name: "Welcome back" })).toBeInTheDocument()
    expect(screen.getByText("Your overview")).toBeInTheDocument()
  })
})
```

`summary-cards.test.tsx`:

```tsx
import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import type { DashboardResponse } from "@app/api-client/types"
import { SummaryCards } from "./summary-cards"
import { formatMonth } from "./month"
import { formatAmount } from "@/components/transactions/format"

const dashboard = (over: Partial<DashboardResponse> = {}): DashboardResponse => ({
  reference_month: "2026-09",
  total_spent: "1395.00",
  recurring_spent: "915.00",
  recurring_count: 2,
  net_balance: "705.00",
  average_cashflow: "1235.00",
  cashflow_months: 3,
  spending_by_category: [],
  monthly_trend: [],
  ...over,
})

const card = (title: string) => screen.getByRole("group", { name: title })

describe("SummaryCards", () => {
  it("shows each figure with its subtitle", () => {
    render(<SummaryCards dashboard={dashboard()} />)
    expect(card("Total Spent")).toHaveTextContent(formatAmount("1395.00"))
    expect(card("Total Spent")).toHaveTextContent(formatMonth("2026-09"))
    expect(card("Recurring Costs")).toHaveTextContent("2 recurring payments")
    expect(card("Net Balance")).toHaveTextContent(formatAmount("705.00"))
    expect(card("Average Cashflow")).toHaveTextContent("average of 3 months")
  })

  it("uses the singular for one", () => {
    render(<SummaryCards dashboard={dashboard({ recurring_count: 1, cashflow_months: 1 })} />)
    expect(card("Recurring Costs")).toHaveTextContent("1 recurring payment")
    expect(card("Recurring Costs")).not.toHaveTextContent("payments")
    expect(card("Average Cashflow")).toHaveTextContent("average of 1 month")
  })

  it("marks a negative net and cashflow as destructive", () => {
    render(<SummaryCards dashboard={dashboard({ net_balance: "-40.00", average_cashflow: "-10.00" })} />)
    expect(screen.getByText(formatAmount("-40.00"))).toHaveClass("text-destructive")
    expect(screen.getByText(formatAmount("-10.00"))).toHaveClass("text-destructive")
    expect(screen.getByText(formatAmount("1395.00"))).not.toHaveClass("text-destructive")
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd web-app && pnpm -s test -- apps/web/src/components/dashboard/`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement the mapping helpers**

`month.ts`:

```ts
/** "2026-09" → "September 2026" (long) or "Sep" (short), in the user's locale; anything else unchanged. */
export function formatMonth(key: string, month: "long" | "short" = "long") {
  const match = /^(\d{4})-(\d{2})$/.exec(key)
  if (!match) return key
  const date = new Date(Number(match[1]), Number(match[2]) - 1, 1)
  return new Intl.DateTimeFormat(undefined, {
    month,
    year: month === "long" ? "numeric" : undefined,
  }).format(date)
}
```

`category-slices.ts`:

```ts
import type { CategorySliceResponse } from "@app/api-client/types"
import { formatAmount } from "@/components/transactions/format"

export type CategorySlice = {
  key: string
  name: string
  amount: number
  display: string
  share: number
  fill: string
}

/** The server's top five plus Other, ready to draw: numbers for geometry, exact text for labels. */
export function toCategorySlices(
  slices: CategorySliceResponse[],
  label: (slug: string) => string,
): CategorySlice[] {
  return slices.map((slice, i) => {
    const other = slice.category === null
    return {
      key: other ? "other" : slice.category!,
      name: other ? "Other" : label(slice.category!),
      amount: Number(slice.amount),
      display: formatAmount(slice.amount),
      share: slice.share_pct,
      fill: other ? "var(--chart-6)" : `var(--chart-${i + 1})`,
    }
  })
}
```

`trend-points.ts`:

```ts
import type { TrendPointResponse } from "@app/api-client/types"
import { formatAmount } from "@/components/transactions/format"
import { formatMonth } from "./month"

export type TrendPoint = {
  month: string
  label: string
  income: number
  expenses: number
  incomeText: string
  expensesText: string
}

export function toTrendPoints(points: TrendPointResponse[]): TrendPoint[] {
  return points.map((p) => ({
    month: p.month,
    label: formatMonth(p.month, "short"),
    income: Number(p.income),
    expenses: Number(p.expenses),
    incomeText: formatAmount(p.income),
    expensesText: formatAmount(p.expenses),
  }))
}
```

- [ ] **Step 4: Implement the header and the cards**

`welcome-header.tsx`:

```tsx
"use client"

import { useAppAuth } from "@app/auth"
import { formatMonth } from "./month"

export function WelcomeHeader({
  referenceMonth,
}: {
  referenceMonth?: string | null
}) {
  const { user } = useAppAuth()
  const firstName = user?.name?.trim().split(/\s+/)[0]
  return (
    <div className="space-y-1">
      <h1 className="text-2xl font-semibold tracking-tight">
        {firstName ? `Welcome back, ${firstName}` : "Welcome back"}
      </h1>
      <p className="text-sm text-muted-foreground">
        {referenceMonth
          ? `Your overview for ${formatMonth(referenceMonth)}`
          : "Your overview"}
      </p>
    </div>
  )
}
```

`summary-cards.tsx` (each card is a labelled `group` so tests and screen readers find it by title):

```tsx
import { useId, type ComponentType } from "react"
import {
  CreditCard,
  PiggyBank,
  RefreshCw,
  TrendingDown,
  TrendingUp,
} from "lucide-react"
import type { DashboardResponse } from "@app/api-client/types"
import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"
import { cn } from "@app/core/lib/utils"
import { formatAmount, isExpense } from "@/components/transactions/format"
import { formatMonth } from "./month"

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`

function SummaryCard({
  title,
  value,
  subtitle,
  icon: Icon,
  negative = false,
}: {
  title: string
  value: string
  subtitle: string
  icon: ComponentType<{ className?: string }>
  negative?: boolean
}) {
  const id = useId()
  return (
    <Card role="group" aria-labelledby={id} size="sm">
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle id={id} className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent className="space-y-1">
        <p
          className={cn(
            "text-2xl font-semibold tabular-nums",
            negative && "text-destructive",
          )}
        >
          {formatAmount(value)}
        </p>
        <p className="text-xs text-muted-foreground">{subtitle}</p>
      </CardContent>
    </Card>
  )
}

/** The four cards for the reference month: two by two on a phone, one row from md up. */
export function SummaryCards({ dashboard }: { dashboard: DashboardResponse }) {
  const month = dashboard.reference_month
    ? formatMonth(dashboard.reference_month)
    : ""
  const netNegative = isExpense(dashboard.net_balance)
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
      <SummaryCard
        title="Total Spent"
        value={dashboard.total_spent}
        subtitle={month}
        icon={CreditCard}
      />
      <SummaryCard
        title="Recurring Costs"
        value={dashboard.recurring_spent}
        subtitle={plural(dashboard.recurring_count, "recurring payment")}
        icon={RefreshCw}
      />
      <SummaryCard
        title="Net Balance"
        value={dashboard.net_balance}
        subtitle={month}
        icon={netNegative ? TrendingDown : TrendingUp}
        negative={netNegative}
      />
      <SummaryCard
        title="Average Cashflow"
        value={dashboard.average_cashflow}
        subtitle={`average of ${plural(dashboard.cashflow_months, "month")}`}
        icon={PiggyBank}
        negative={isExpense(dashboard.average_cashflow)}
      />
    </div>
  )
}
```

- [ ] **Step 5: Implement the two charts**

Before writing them, load the `dataviz` skill and read `references/marks-and-anatomy.md` and `references/interaction.md`; the specs below follow them (2px surface gap between donut segments, 2px lines, recessive grid, a hover tooltip on both, a legend for ≥ 2 series, text in text tokens never series colours).

`category-chart.tsx`:

```tsx
"use client"

import { Pie, PieChart } from "recharts"
import type { CategorySliceResponse } from "@app/api-client/types"
import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@app/ui/chart"
import { useCategories } from "@/components/transactions/use-categories"
import { toCategorySlices } from "./category-slices"

/** A donut of the month's top five categories plus Other, with a labelled legend beside it. */
export function CategoryChart({ slices }: { slices: CategorySliceResponse[] }) {
  const { label } = useCategories()
  const data = toCategorySlices(slices, label)
  const config: ChartConfig = Object.fromEntries(
    data.map((s) => [s.key, { label: s.name, color: s.fill }]),
  )
  const display = new Map(data.map((s) => [s.key, s.display]))
  return (
    <Card>
      <CardHeader>
        <CardTitle>Spending by category</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-center gap-6 sm:flex-row">
        <ChartContainer config={config} className="aspect-square w-44 shrink-0">
          <PieChart>
            <ChartTooltip
              content={
                <ChartTooltipContent
                  hideLabel
                  formatter={(_, key) => display.get(key)}
                />
              }
            />
            <Pie
              data={data}
              dataKey="amount"
              nameKey="key"
              innerRadius="58%"
              outerRadius="100%"
              stroke="var(--card)"
              strokeWidth={2}
              isAnimationActive={false}
            />
          </PieChart>
        </ChartContainer>
        <ul className="w-full space-y-2 text-sm">
          {data.map((s) => (
            <li key={s.key} className="flex items-center gap-2">
              <span
                aria-hidden
                className="size-2.5 shrink-0 rounded-[2px]"
                style={{ backgroundColor: s.fill }}
              />
              <span className="min-w-0 flex-1 truncate">{s.name}</span>
              <span className="tabular-nums">{s.display}</span>
              <span className="w-14 text-right text-muted-foreground tabular-nums">
                {s.share.toFixed(1)}%
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}
```

`trend-chart.tsx`:

```tsx
"use client"

import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts"
import type { TrendPointResponse } from "@app/api-client/types"
import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@app/ui/chart"
import { formatMonth } from "./month"
import { toTrendPoints, type TrendPoint } from "./trend-points"

const config: ChartConfig = {
  income: { label: "Income", color: "var(--chart-1)" },
  expenses: { label: "Expenses", color: "var(--chart-2)" },
}

const compact = new Intl.NumberFormat(undefined, {
  notation: "compact",
  maximumFractionDigits: 1,
})

/** Income and expenses over the six months to the reference month. */
export function TrendChart({ points }: { points: TrendPointResponse[] }) {
  const data = toTrendPoints(points)
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>Income and expenses</CardTitle>
        <ul className="flex gap-4 text-xs text-muted-foreground">
          {Object.entries(config).map(([key, item]) => (
            <li key={key} className="flex items-center gap-1.5">
              <span
                aria-hidden
                className="h-0.5 w-3 rounded-full"
                style={{ backgroundColor: item.color }}
              />
              {item.label}
            </li>
          ))}
        </ul>
      </CardHeader>
      <CardContent>
        <ChartContainer config={config} className="aspect-[2/1] w-full">
          <LineChart data={data} margin={{ left: 4, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v: number) => compact.format(v)}
            />
            <ChartTooltip
              content={({ active, payload }) => {
                // payload[i].payload is the hovered row: show its exact text, not the plotted float.
                const point = payload?.[0]?.payload as TrendPoint | undefined
                return (
                  <ChartTooltipContent
                    active={active}
                    payload={payload}
                    label={point ? formatMonth(point.month) : undefined}
                    formatter={(_, key) =>
                      key === "income" ? point?.incomeText : point?.expensesText
                    }
                  />
                )
              }}
            />
            <Line
              dataKey="income"
              type="monotone"
              stroke="var(--color-income)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="expenses"
              type="monotone"
              stroke="var(--color-expenses)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}
```

If `tsc` rejects passing Recharts' `payload` to `ChartTooltipContent`, widen `TooltipItem` in `chart.tsx` (Task 9) to accept Recharts' `Payload` fields rather than casting at the call site.

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd web-app && pnpm -s test -- apps/web/src/components/dashboard/`
Expected: all PASS.

- [ ] **Step 7: Format, lint, type-check and commit**

```bash
cd web-app && pnpm exec prettier --write apps/web/src/components/dashboard && pnpm -s lint && pnpm -s type-check && cd ..
git add web-app/apps/web/src/components/dashboard
git commit -m "Dashboard: the header, the four cards, and the category and trend charts"
```

---

### Task 12: The home page — recent transactions, states, assembly

**Files:**
- Create (under `web-app/apps/web/src/components/dashboard/`): `section-error.tsx`, `empty-dashboard.tsx`, `dashboard-skeleton.tsx`, `recent-transactions.tsx`, `home-dashboard.tsx`
- Test: `web-app/apps/web/src/components/dashboard/home-dashboard.test.tsx`
- Modify: `web-app/apps/web/src/app/(dashboard)/home/page.tsx`
- Create: `web-app/apps/web/src/app/(dashboard)/home/loading.tsx`

**Interfaces:**
- Consumes: Task 11's components; `useGetDashboard` (`@app/api-client/endpoints/analytics`), `useListTransactions` (`@app/api-client/endpoints/transactions`); `TransactionResponse` type; `formatAmount`, `amountClass`, `formatDate` from `@/components/transactions/format`; `useCategories`.
- Produces: `HomeDashboard()` (client), `ANALYTICS_STALE_TIME = 120_000` exported from `home-dashboard.tsx`.

- [ ] **Step 1: Write the failing test**

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useGetDashboard } from "@app/api-client/endpoints/analytics"
import {
  useListTransactions,
  useListTransactionCategories,
} from "@app/api-client/endpoints/transactions"
import { useAppAuth } from "@app/auth"
import { HomeDashboard } from "./home-dashboard"

vi.mock("@app/api-client/endpoints/analytics", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/analytics")>()),
  useGetDashboard: vi.fn(),
}))
vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useListTransactions: vi.fn(),
  useListTransactionCategories: vi.fn(),
}))
vi.mock("@app/auth", () => ({ useAppAuth: vi.fn() }))
// jsdom cannot lay out SVG; the charts' mapping is tested on its own.
vi.mock("./category-chart", () => ({ CategoryChart: () => <div>category chart</div> }))
vi.mock("./trend-chart", () => ({ TrendChart: () => <div>trend chart</div> }))

const dashboardRefetch = vi.fn()
const recentRefetch = vi.fn()

const DATA = {
  reference_month: "2026-09",
  total_spent: "1395.00",
  recurring_spent: "915.00",
  recurring_count: 2,
  net_balance: "705.00",
  average_cashflow: "1235.00",
  cashflow_months: 3,
  spending_by_category: [],
  monthly_trend: [],
}

const dashboard = (state: object) =>
  vi.mocked(useGetDashboard).mockReturnValue({
    isPending: false,
    isError: false,
    data: undefined,
    refetch: dashboardRefetch,
    ...state,
  } as unknown as ReturnType<typeof useGetDashboard>)

const recent = (state: object) =>
  vi.mocked(useListTransactions).mockReturnValue({
    isPending: false,
    isError: false,
    data: undefined,
    refetch: recentRefetch,
    ...state,
  } as unknown as ReturnType<typeof useListTransactions>)

const TXN = {
  id: "1",
  date: "2026-09-05",
  merchant: "REWE",
  amount: "-200.00",
  category: "food_groceries",
  confidence: 1,
  description: null,
  original_category: null,
  is_recurring: false,
  created_at: "2026-09-05T10:00:00Z",
  updated_at: "2026-09-05T10:00:00Z",
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useAppAuth).mockReturnValue({
    user: { name: "Ada", email: null, imageUrl: null },
    isLoaded: true,
  } as unknown as ReturnType<typeof useAppAuth>)
  vi.mocked(useListTransactionCategories).mockReturnValue({
    data: [{ value: "food_groceries", label: "Food & Groceries" }],
  } as unknown as ReturnType<typeof useListTransactionCategories>)
  recent({ data: { items: [TXN], total: 1, offset: 0, limit: 10 } })
})

describe("HomeDashboard", () => {
  it("asks for the dashboard silently, with a two-minute stale time, and ten recent rows", () => {
    dashboard({ data: DATA })
    render(<HomeDashboard />)
    const options = vi.mocked(useGetDashboard).mock.calls[0][0]
    expect(options?.query?.staleTime).toBe(120_000)
    expect(options?.query?.meta?.silentError).toBe(true)
    expect(vi.mocked(useListTransactions).mock.calls[0][0]).toEqual({ limit: 10 })
  })

  it("draws the cards, the charts and the recent transactions", () => {
    dashboard({ data: DATA })
    render(<HomeDashboard />)
    expect(screen.getByRole("group", { name: "Total Spent" })).toBeInTheDocument()
    expect(screen.getByText("category chart")).toBeInTheDocument()
    expect(screen.getByText("trend chart")).toBeInTheDocument()
    expect(screen.getAllByText("REWE").length).toBeGreaterThan(0)
    expect(screen.getByRole("link", { name: "View all" })).toHaveAttribute("href", "/transactions")
  })

  it("shows the empty state, linking to /transactions, for a user with no data", () => {
    dashboard({ data: { ...DATA, reference_month: null } })
    render(<HomeDashboard />)
    expect(screen.getByText("No transactions yet")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "Go to transactions" })).toHaveAttribute("href", "/transactions")
    expect(screen.queryByRole("group", { name: "Total Spent" })).not.toBeInTheDocument()
    expect(screen.queryByText("Recent transactions")).not.toBeInTheDocument()
  })

  it("a failed dashboard offers a retry and the recent list still renders", async () => {
    dashboard({ isError: true })
    render(<HomeDashboard />)
    expect(screen.getByText("Couldn't load your overview.")).toBeInTheDocument()
    expect(screen.getAllByText("REWE").length).toBeGreaterThan(0)
    await userEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(dashboardRefetch).toHaveBeenCalled()
  })

  it("a failed recent list offers its own retry and the cards still render", async () => {
    dashboard({ data: DATA })
    recent({ isError: true })
    render(<HomeDashboard />)
    expect(screen.getByRole("group", { name: "Total Spent" })).toBeInTheDocument()
    expect(screen.getByText("Couldn't load recent transactions.")).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(recentRefetch).toHaveBeenCalled()
  })

  it("shows skeletons, never nothing, while loading", () => {
    dashboard({ isPending: true })
    recent({ isPending: true })
    const { container } = render(<HomeDashboard />)
    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0)
  })
})
```

Before running, confirm the skeleton primitive's marker: `grep -n "data-slot" web-app/packages/ui/src/primitives/skeleton.tsx`. If it is not `data-slot="skeleton"`, change the selector in the last test to whatever it renders.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web-app && pnpm -s test -- apps/web/src/components/dashboard/home-dashboard.test.tsx`
Expected: FAIL — `./home-dashboard` not found.

- [ ] **Step 3: Implement the small pieces**

`section-error.tsx`:

```tsx
import { Button } from "@app/ui/button"
import { Card, CardContent } from "@app/ui/card"

/** A section that failed on its own: say so, offer a retry, leave the rest of the page alone. */
export function SectionError({
  what,
  onRetry,
}: {
  what: string
  onRetry: () => void
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">Couldn&apos;t load {what}.</p>
        <Button variant="outline" size="sm" onClick={onRetry}>
          Retry
        </Button>
      </CardContent>
    </Card>
  )
}
```

`empty-dashboard.tsx`:

```tsx
import Link from "next/link"
import { buttonVariants } from "@app/ui/button"
import { Card, CardContent } from "@app/ui/card"

export function EmptyDashboard() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
        <p className="font-medium">No transactions yet</p>
        <p className="text-sm text-muted-foreground">
          Add or import transactions to see your overview.
        </p>
        <Link href="/transactions" className={buttonVariants()}>
          Go to transactions
        </Link>
      </CardContent>
    </Card>
  )
}
```

`dashboard-skeleton.tsx`:

```tsx
import { Skeleton } from "@app/ui/skeleton"

/** The cards and charts while the dashboard loads. */
export function DashboardSkeleton() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-28 w-full" />
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Skeleton className="h-72 w-full" />
        <Skeleton className="h-72 w-full" />
      </div>
    </div>
  )
}

/** Rows while the recent list loads. */
export function RecentSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }, (_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Implement `recent-transactions.tsx`**

```tsx
"use client"

import Link from "next/link"
import { useListTransactions } from "@app/api-client/endpoints/transactions"
import type { TransactionResponse } from "@app/api-client/types"
import { buttonVariants } from "@app/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"
import { cn } from "@app/core/lib/utils"
import {
  amountClass,
  formatAmount,
  formatDate,
} from "@/components/transactions/format"
import { useCategories } from "@/components/transactions/use-categories"
import { RecentSkeleton } from "./dashboard-skeleton"
import { SectionError } from "./section-error"

const RECENT = { limit: 10 } as const

function Amount({ value }: { value: string }) {
  return (
    <span className={cn("tabular-nums", amountClass(value))}>
      {formatAmount(value)}
    </span>
  )
}

/** The ten newest transactions: a table from md up, a list on a phone. */
export function RecentTransactions() {
  const query = useListTransactions(RECENT, {
    query: { meta: { silentError: true } },
  })
  const { label } = useCategories()

  if (query.isError) {
    return (
      <SectionError
        what="recent transactions"
        onRetry={() => void query.refetch()}
      />
    )
  }

  const items: TransactionResponse[] = query.data?.items ?? []
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>Recent transactions</CardTitle>
        <Link
          href="/transactions"
          className={buttonVariants({ variant: "ghost", size: "sm" })}
        >
          View all
        </Link>
      </CardHeader>
      <CardContent>
        {query.isPending ? (
          <RecentSkeleton />
        ) : (
          <>
            <table className="hidden w-full text-sm md:table">
              <tbody>
                {items.map((t) => (
                  <tr key={t.id} className="border-b last:border-0">
                    <td className="py-2 pr-3 font-medium">{t.merchant}</td>
                    <td className="py-2 pr-3 text-muted-foreground">
                      {formatDate(t.date)}
                    </td>
                    <td className="py-2 pr-3 text-muted-foreground">
                      {label(t.category)}
                    </td>
                    <td className="py-2 text-right">
                      <Amount value={t.amount} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ul className="space-y-3 md:hidden">
              {items.map((t) => (
                <li key={t.id} className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-medium">{t.merchant}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(t.date)} · {label(t.category)}
                    </p>
                  </div>
                  <Amount value={t.amount} />
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  )
}
```

- [ ] **Step 5: Implement `home-dashboard.tsx`, the page and its loading state**

`home-dashboard.tsx`:

```tsx
"use client"

import { useGetDashboard } from "@app/api-client/endpoints/analytics"
import { CategoryChart } from "./category-chart"
import { DashboardSkeleton } from "./dashboard-skeleton"
import { EmptyDashboard } from "./empty-dashboard"
import { RecentTransactions } from "./recent-transactions"
import { SectionError } from "./section-error"
import { SummaryCards } from "./summary-cards"
import { TrendChart } from "./trend-chart"
import { WelcomeHeader } from "./welcome-header"

/** Analytics are costlier than a list; any transaction write invalidates them sooner (use-invalidate-transactions). */
export const ANALYTICS_STALE_TIME = 2 * 60 * 1000

export function HomeDashboard() {
  const query = useGetDashboard({
    query: { staleTime: ANALYTICS_STALE_TIME, meta: { silentError: true } },
  })
  const data = query.data

  if (data && data.reference_month === null) {
    return (
      <div className="space-y-6">
        <WelcomeHeader referenceMonth={null} />
        <EmptyDashboard />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <WelcomeHeader referenceMonth={data?.reference_month} />
      {query.isError ? (
        <SectionError what="your overview" onRetry={() => void query.refetch()} />
      ) : !data ? (
        <DashboardSkeleton />
      ) : (
        <>
          <SummaryCards dashboard={data} />
          <div className="grid gap-4 lg:grid-cols-2">
            <CategoryChart slices={data.spending_by_category} />
            <TrendChart points={data.monthly_trend} />
          </div>
        </>
      )}
      {/* Step 6 puts the insights callout here, full width. */}
      <RecentTransactions />
    </div>
  )
}
```

`web-app/apps/web/src/app/(dashboard)/home/page.tsx`:

```tsx
import { HomeDashboard } from "@/components/dashboard/home-dashboard"

export default function HomePage() {
  return <HomeDashboard />
}
```

`web-app/apps/web/src/app/(dashboard)/home/loading.tsx`:

```tsx
import { Skeleton } from "@app/ui/skeleton"
import { DashboardSkeleton } from "@/components/dashboard/dashboard-skeleton"

export default function HomeLoading() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-64" />
      <DashboardSkeleton />
    </div>
  )
}
```

- [ ] **Step 6: Run the web suite**

Run: `make test-web` (root)
Expected: all PASS.

- [ ] **Step 7: Format, lint, type-check and commit**

```bash
make check-web
git add web-app/apps/web/src/components/dashboard "web-app/apps/web/src/app/(dashboard)/home"
git commit -m "Dashboard: the home page, recent transactions, and its empty, loading and error states"
```

Expected: `make check-web` exits 0.

- [ ] **Step 8: Look at it in the browser**

The `dataviz` procedure's last step is to render the charts and look. Start this worktree's stack (the `run-stack` and `worktrees` skills give the commands and this worktree's ports), sign in as a dev user, seed with `make seed-transactions CLERK_ID=<that user's id>`, and open `/home` with the Playwright tools at desktop width and at 390px. Check, in light and dark mode: the donut's segments are separated by a 2px gap and the legend lists names, amounts and shares; the trend lines are 2px, the grid recessive, the tooltip shows exact amounts; the cards sit two by two on the phone; nothing overflows. Then delete every transaction for that user (Settings → delete all) and confirm the empty state links to `/transactions`. Fix anything wrong and commit it with the task's files.

---

### Task 13: Docs, and the hand-off to the PR

**Files:**
- Modify: `docs/product/features/analytics.md`, `docs/architecture/server.md` (§1 only), `docs/TODO.md`

- [ ] **Step 1: `analytics.md`**

1. In the header, replace `**Data model:** pending — written with step 5a. Analytics stores nothing of its own: it reads [`transactions.md`](./transactions.md).` with:

   `**Data model:** none — analytics stores nothing. It reads the transaction table through one read path ([`../../data-model/transaction.md`](../../data-model/transaction.md)).`

2. In §2, replace the bullet `- four summary cards: **Total Spent**, **Recurring Costs**, **Net Balance** and **Average Cashflow**;` with:

   ```markdown
   - four summary cards for the **reference month** — the latest calendar month holding a
     transaction, named on the page ("September 2026"): **Total Spent**, that month's
     expenses; **Recurring Costs**, the expenses flagged recurring in that month and how many
     there were; **Net Balance**, income minus expenses; **Average Cashflow**, the mean
     monthly net over the three months to it (fewer when the data starts later; an empty
     month counts as zero);
   ```

   and replace `- a pie chart of spending by category and a line chart of the monthly trend;` with:

   ```markdown
   - a donut of the reference month's top five categories plus Other, and a line chart of
     income and expenses over the six months to it;
   ```

   and add after the recent-transactions bullet: `With no transactions, the page shows an empty state linking to the transactions page.`

3. In §6, replace the bullet `- **Date range on the dashboard.** …` with:

   ```markdown
   - **Date range on the dashboard** — decided 15 Oct 2026: the latest month with data,
     labelled by name, not the calendar month (imports lag the calendar). A month picker is
     in [`TODO.md`](../../TODO.md).
   ```

- [ ] **Step 2: `architecture/server.md` §1**

In the module tree, add between `account/` and `conversation/`:

```
│   ├── analytics/            # every calculation over the user's transactions; stores nothing.
│   │                         #   domain/ holds the pure functions (R9)
```

Do not edit §2 (step 4 owns it this wave) or §8.

- [ ] **Step 3: `docs/TODO.md`**

Append three entries in the file's style (heading, what it unblocks, where the reasoning lives). Do **not** touch the R9 entry (step 4 deletes it).

```markdown
## Web — the currency symbol

Money shows in EUR everywhere: `formatAmount` in
`apps/web/src/components/transactions/format.ts` hard-codes it. `analytics.md` §4 promises the
symbol the user picks in Settings. The setting is display only — amounts are stored without a
currency. **Unblocks:** a user outside the euro area. **Decide first:** where the preference
lives (the user row, or the browser).

## Web — a month picker on the dashboard

The home dashboard shows the latest month with data (decision of 15 Oct 2026). A picker would let
the user look back; every analytics route already takes `date_from`/`date_to`, but
`GET /analytics/dashboard` picks its own month, so it gains a `month` parameter. **Unblocks:**
looking at a past month without the analytics page. Reasoning: `analytics.md` §6.

## Chat — free-form questions over the user's data

The chat tools (step 7) call the analytics library's fixed functions. A question they do not
cover could be answered by generated code run in an isolated sandbox with its own environment
(polars or similar); the server only hands it the user's rows from
`transaction_service.list_for_analysis`, as CSV or JSON, so no dataframe library enters
`server/pyproject.toml`. **Unblocks:** open-ended questions in chat. Decided with step 5a
(15 Oct 2026): the server library stays plain Python.
```

- [ ] **Step 4: Commit**

```bash
git add docs/product/features/analytics.md docs/architecture/server.md docs/TODO.md
git commit -m "Docs: analytics' data model, the dashboard's month, and three TODO entries"
```

- [ ] **Step 5: Hand-off (done by the coordinator session in `superpowers:finishing-a-development-branch`, not by a task subagent)**

Listed so nothing is forgotten: run the full gates (`make check`, `make test-web`, and from `server/` `make test-unit` and `make test-integration`); delete `.superpowers/specs/2026-10-15-analytics-dashboard-design.md` and this plan; open the PR into `template-base`; then set `docs/ROADMAP.md` row 5a to `complete — [PR #N](url) into template-base; reaches main at Cutover` and push that commit; message `orchestrator` with the PR URL and the `recharts` specifier `^3.10.1`.
