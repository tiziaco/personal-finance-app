# CSV import, the labeller and recurring detection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import a bank's CSV into `transaction` — upload, mapping review, confirm — with every row categorised by an LLM labeller, duplicates count-matched, and `is_recurring` set by a deterministic rule on every write.

**Architecture:** A feature sub-package `app/modules/transaction/imports/` (router, service, repository, schemas, models, a pure `domain.py`) calls the transaction core, which gains a pure `domain/` package (fingerprint, merchant key, recurring rule, count-matching) and re-runs the recurring rule after every write. Two plain async agents under `app/agents/` (column mapping, labeller) go through a tool-less `LLMService`. The web adds one always-mounted import dialog to `/transactions`.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy (asyncpg), Alembic, LangChain over OpenRouter via `LLMService`, tenacity, Langfuse; Next.js 16, TanStack Query (orval-generated hooks), Base UI, Vitest + Testing Library.

**Spec:** `.superpowers/specs/2026-10-15-csv-import-design.md` — read it before your task. The wave's conditions are in `.superpowers/BRIEF.md` §3 (gitignored; ask the coordinator if you cannot see it).

## Global Constraints

- Work only in this worktree, on `feat/csv-import`. Never merge; never push without the gates below.
- `server/app/modules/transaction/service.py`, `repository.py` and `schemas.py` stay **files** (condition 2). Add to them; never turn them into packages.
- Never edit: `server/app/modules/transaction/` files other than those named in a task; anything under `web-app/apps/web/src/app/(dashboard)/home/`; `web-app/apps/web/src/lib/hub-nav.ts`; `web-app/apps/web/src/app/(dashboard)/layout.tsx`; `web-app/apps/web/src/components/transactions/use-invalidate-transactions.ts`; `web-app/packages/api-client/src/{query-provider.tsx,query-meta.ts,toast-for-error.ts,use-api-fetch.ts,errors.ts,index.ts}`; `web-app/packages/ui/src/index.ts`; any existing file in `web-app/packages/ui/src/primitives/`, `web-app/packages/data-table/`, `web-app/packages/components/`, `web-app/packages/core/src/constants/messages.ts`.
- Never hand-edit `server/openapi.json` or `web-app/packages/api-client/src/generated/`: run `make gen-contract` from the repo root after a route change and commit its output with the route.
- `server/scripts/seed_transactions.py` must keep working unchanged (condition 3).
- Server code: `async def`; type hints; imports at the top of the file; DB writes end in `flush()` — the single exception is `_release_connection` in `imports/service.py` (spec §5.3); services raise domain exceptions, routes never `try/except`; structlog events `lowercase_with_underscores` with kwargs, never f-strings; no merchant text or file content in logs or error details.
- Every route: explicit tag, camelCase `operation_id`, a `response_model` (or 204).
- Every LLM call is traced in Langfuse; every retry uses tenacity with exponential backoff.
- Tests mirror the tree (R5). Unit test files start `pytestmark = pytest.mark.unit`, integration files `pytestmark = pytest.mark.integration`. Integration tests need Docker running (testcontainers).
- Server commands run from `server/`: `APP_ENV=test uv run pytest <path> -v`. Web commands run from `web-app/`: `pnpm -s test <path>`.
- Copy and limits, verbatim: 3,000 rows; 5 MB; 30-minute hold; 10 uploads or confirms a minute per user; known-merchant confidence 0.95; fallback `miscellaneous` at 0.3; batches of 50, at most 5 at once; recurring band ±15 % with at least €1 of slack; 75 % of gaps; weekly 6–8 d / monthly 26–35 d / quarterly 84–98 d / yearly 350–380 d; minimum 3 rows for every cadence.
- Commit after each task with a message starting `CSV import:`. The pre-commit hook regenerates the contract when `server/app/` changes; if it blocks, run `make gen-contract`, add the output, commit again.

## Review Focus

1. **A bank preamble above the header, or a delimiter ending every line** (DKB, Sparkasse) — the header is found, the empty trailing column dropped, rejected-row numbers are file line numbers. Test: Task 8, `test_preamble_and_trailing_delimiter`.
2. **Importing the same file twice** — the second confirm imports nothing and reports every row as a skipped duplicate. Test: Task 10, `test_reimporting_the_same_file_imports_nothing`.
3. **A double-click on Import** (two confirms of one upload) — one imports, the other is a 404, nothing is written twice. Test: Task 10, `test_a_second_confirm_is_404`.
4. **Closing the dialog, then the import failing** — the user is still told: the error is not silenced once the dialog is closed. Test: Task 12, `"a failure after closing is left to QueryProvider's toast"`.
5. **Headers that differ only in case or spacing from a remembered profile** (`Betrag ` vs `betrag`) — the profile is reused, not dropped to Ignore. Test: Task 9, `test_a_remembered_mapping_matches_headers_by_case_and_spacing`.

## File Map

Server — create:
- `app/modules/transaction/domain/__init__.py`, `fingerprint.py`, `merchant.py`, `recurring.py`, `dedupe.py` — pure rules (R9).
- `app/modules/transaction/imports/__init__.py`, `router.py`, `service.py`, `repository.py`, `schemas.py`, `models.py`, `domain.py`, `exceptions.py`, `handlers.py`.
- `app/agents/shared/structured.py` — `structured_llm`, `ask_json`, `InvalidModelAnswer`.
- `app/agents/csv_mapping/__init__.py`, `mapper.py`, `prompts/v1.md`.
- `app/agents/transaction_labeler/__init__.py`, `labeler.py`, `known_merchants.py`, `prompts/v2.md`.
- `alembic/versions/20261015_1200_5b7e2c9d4f10_csv_import.py`.

Server — modify: `app/modules/transaction/{__init__,models,service,repository,schemas}.py`; `app/integrations/llm/service.py` (`config` on `call`); `app/agents/shared/observability/{langfuse,__init__}.py` (`create_trace_config`); `app/core/limiter.py` (`user_or_ip_key`); `app/core/config.py` (`TRANSACTION_IMPORTS`); `app/api/v1/api.py`; `alembic/env.py`; `pyproject.toml` (R9).

Web — create in `web-app/apps/web/src/components/transactions/`: `import-csv-dialog.tsx`, `import-drop-zone.tsx`, `import-mapping-review.tsx`, `import-result.tsx`, `import-mapping.ts`, `import-errors.ts`, and tests. Modify: `transactions-table.tsx`, `transactions-table.test.tsx`, `web-app/apps/web/package.json` (`sonner`).

Docs — Task 13.

---
### Task 1: The transaction `domain` package — fingerprint and merchant key — and the R9 contract

**Files:**
- Create: `server/app/modules/transaction/domain/__init__.py`, `server/app/modules/transaction/domain/fingerprint.py`, `server/app/modules/transaction/domain/merchant.py`
- Modify: `server/app/modules/transaction/service.py` (drop the `fingerprint` definition, import it), `server/pyproject.toml` (R9 contract), `docs/TODO.md` (delete the R9 entry)
- Move: `server/tests/unit/modules/transaction/test_service.py` → `server/tests/unit/modules/transaction/domain/test_fingerprint.py`
- Create: `server/tests/unit/modules/transaction/domain/__init__.py` (empty), `server/tests/unit/modules/transaction/domain/test_merchant.py`

**Interfaces:**
- Produces: `app.modules.transaction.domain.fingerprint(user_id: uuid.UUID, date: dt.date, merchant: str, amount: Decimal, description: Optional[str]) -> str` (unchanged recipe); `app.modules.transaction.domain.normalise_merchant(raw: str) -> str`. `app.modules.transaction.service.fingerprint` stays importable (the integration conftest and the seed use it).

- [ ] **Step 1: Move the fingerprint tests**

```bash
mkdir -p server/tests/unit/modules/transaction/domain
touch server/tests/unit/modules/transaction/domain/__init__.py
git mv server/tests/unit/modules/transaction/test_service.py server/tests/unit/modules/transaction/domain/test_fingerprint.py
```

In `test_fingerprint.py` change the import line to `from app.modules.transaction.domain import fingerprint`. Nothing else changes.

- [ ] **Step 2: Write the failing merchant-key test**

`server/tests/unit/modules/transaction/domain/test_merchant.py`:

```python
"""The merchant key (spec §4.2), pinned to fixed vectors."""

import pytest

from app.modules.transaction.domain import normalise_merchant

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("PAYPAL *NETFLIX 4029357733", "netflix"),
        ("NETFLIX.COM", "netflix"),
        ("Netflix", "netflix"),
        ("FEATHER - INSURANCE", "feather insurance"),
        ("REWE Markt GmbH 3112", "rewe markt"),
        ("REWE", "rewe"),
        ("Netflix International B.V.", "netflix international"),
        ("1&1 Telecom", "1&1 telecom"),
        ("Zettle_*Golda-delux", "golda delux"),
        ("SUMUP  *Café Kranzler", "café kranzler"),
        ("AMZNPrime DE*TX1FF8RV4", "amznprime"),
        ("Späti | Ref 99812", "späti"),
        ("  Bäckerei   Müller  ", "bäckerei müller"),
    ],
)
def test_vectors(raw, key):
    assert normalise_merchant(raw) == key


def test_different_businesses_stay_apart():
    assert normalise_merchant("REWE") != normalise_merchant("REWE Markt GmbH")
    assert normalise_merchant("Netflix") != normalise_merchant("Netflix International B.V.")


def test_only_a_reference_number_falls_back_to_the_folded_text():
    assert normalise_merchant("  123456 ") == "123456"


def test_ubr_prefix_becomes_uber():
    assert normalise_merchant("UBR* PENDING") == "uber pending"
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/transaction/domain -v`
Expected: collection error, `ModuleNotFoundError: No module named 'app.modules.transaction.domain'`.

- [ ] **Step 4: Create the domain package**

`server/app/modules/transaction/domain/fingerprint.py` — move the function out of `service.py` unchanged:

```python
"""The duplicate key (docs/data-model/transaction.md, D3)."""

import datetime as dt
import hashlib
import uuid
from decimal import Decimal
from typing import Optional

_CENT = Decimal("0.01")


def fingerprint(user_id: uuid.UUID, date: dt.date, merchant: str, amount: Decimal, description: Optional[str]) -> str:
    """sha256 of user|date|merchant|amount|description — the duplicate key (docs/data-model/transaction.md).

    Merchant and description are stripped and casefolded; the amount is the
    Decimal at two places, never a float, and -0.00 is 0.00. The import uses
    the same function, so the two can never disagree.
    """
    cents = amount.quantize(_CENT)
    if cents == 0:
        cents = Decimal("0.00")
    raw = (
        f"{user_id}|{date:%Y-%m-%d}|{merchant.strip().casefold()}|{cents:.2f}|{(description or '').strip().casefold()}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
```

`server/app/modules/transaction/domain/merchant.py`:

```python
"""The merchant key: the merchant text with a bank's noise removed (docs/data-model/transaction.md, D7)."""

import re
import unicodedata

_PROCESSOR_PREFIX = re.compile(r"^(?:paypal|sumup|lsp|spc|sq)\s*\*\s*|^zettle_\*?\s*")
_UBER_PREFIX = re.compile(r"^ubr\s*\*\s*")
_DOMAIN_SUFFIX = re.compile(r"\.(?:co\.uk|com|de|eu|it)$")
_LEGAL_FORMS = frozenset({"gmbh", "ag", "se", "kg", "bv", "b.v", "ltd", "inc", "srl", "spa"})
_PUNCTUATION = re.compile(r"[^\w&]|_")


def normalise_merchant(raw: str) -> str:
    """The key that groups one merchant's rows.

    Casefolded, with a payment processor's prefix, a web domain, a legal form and
    trailing reference numbers (a token with three or more digits) removed, and
    punctuation other than `&` turned into spaces. Conservative by design: it
    removes noise and never guesses that two names are one business. A change
    here changes stored keys, so it needs a backfill revision.
    """
    folded = unicodedata.normalize("NFKC", raw).casefold()
    text = folded.split("|", 1)[0].strip()
    text = _UBER_PREFIX.sub("uber ", text)
    text = _PROCESSOR_PREFIX.sub("", text)
    tokens = text.split()
    while tokens:
        last = _DOMAIN_SUFFIX.sub("", tokens[-1])
        if not last or sum(c.isdigit() for c in last) >= 3 or last.rstrip(".") in _LEGAL_FORMS:
            tokens.pop()
            continue
        tokens[-1] = last
        break
    key = " ".join(_PUNCTUATION.sub(" ", " ".join(tokens)).split())
    return key or " ".join(folded.split())
```

`server/app/modules/transaction/domain/__init__.py`:

```python
"""Transaction rules that need no database: pure functions over plain values (R9)."""

from app.modules.transaction.domain.fingerprint import fingerprint
from app.modules.transaction.domain.merchant import normalise_merchant

__all__ = ["fingerprint", "normalise_merchant"]
```

In `server/app/modules/transaction/service.py`: delete `import hashlib`, `_CENT` and the `fingerprint` function; add `from app.modules.transaction.domain import fingerprint` with the other `app.modules.transaction` imports. `uuid`, `dt` and `Decimal` stay if still used (ruff will tell you).

- [ ] **Step 5: Run the tests to see them pass**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/transaction -v`
Expected: all PASS.

- [ ] **Step 6: Add the R9 contract**

In `server/pyproject.toml`, under `[tool.importlinter]`, add `include_external_packages = true` (a `forbidden` contract may name third-party packages only with it), and after the R1 contracts add:

```toml
[[tool.importlinter.contracts]]
name = "R9: a domain slot imports neither the ORM nor the framework"
type = "forbidden"
source_modules = ["app.modules.*.domain"]
forbidden_modules = ["sqlmodel", "sqlalchemy", "fastapi"]
```

(Task 8 adds the second pattern, `app.modules.*.*.domain`, once a module matches it.)

Delete the section `## Server — the R9 import-linter contract` from `docs/TODO.md`.

- [ ] **Step 7: Prove the contract bites, then passes**

Temporarily add `import sqlalchemy  # noqa: F401` to `domain/merchant.py`, run `cd server && uv run lint-imports`, expect `R9 ... BROKEN`. Remove the line, run again, expect every contract `KEPT`. Then `make -C .. check-server` (from `server/`: `cd .. && make check-server`) passes.

- [ ] **Step 8: Commit**

```bash
git add server/app/modules/transaction/domain server/app/modules/transaction/service.py server/pyproject.toml docs/TODO.md server/tests/unit/modules/transaction
git commit -m "CSV import: transaction domain package (fingerprint, merchant key) and the R9 contract"
```

---

### Task 2: The recurring rule and count-matching

**Files:**
- Create: `server/app/modules/transaction/domain/recurring.py`, `server/app/modules/transaction/domain/dedupe.py`
- Modify: `server/app/modules/transaction/domain/__init__.py`
- Create: `server/tests/unit/modules/transaction/domain/test_recurring.py`, `server/tests/unit/modules/transaction/domain/test_dedupe.py`
- Create: `server/tests/unit/modules/transaction/domain/data/legacy_transactions_400.csv` — copy of `/Users/tizianoiacovelli/projects/pf-legacy/server/tests/data/test_transactions_400.csv`

**Interfaces:**
- Consumes: `normalise_merchant` (Task 1), only in the fixture test.
- Produces: `DETECTED = "detected"`, `USER = "user"`; `RecurringRow(id: uuid.UUID, date: dt.date, amount: Decimal, source: str)` (frozen dataclass); `detect_recurring(rows: list[RecurringRow]) -> dict[uuid.UUID, bool]` — a verdict for every `detected` row, none for `user` rows; `plan_count_matched(fingerprints: list[str], existing: dict[str, int]) -> list[bool]`. All exported from `app.modules.transaction.domain`.

- [ ] **Step 1: Write the failing tests**

`server/tests/unit/modules/transaction/domain/test_dedupe.py`:

```python
"""Count-matched duplicates (spec §4.4)."""

import pytest

from app.modules.transaction.domain import plan_count_matched

pytestmark = pytest.mark.unit


def test_nothing_held_keeps_every_copy():
    assert plan_count_matched(["a", "a", "b"], {}) == [True, True, True]


def test_held_copies_are_subtracted_from_the_first_ones():
    assert plan_count_matched(["a", "a", "b"], {"a": 1}) == [False, True, True]


def test_more_held_than_in_the_file_keeps_none():
    assert plan_count_matched(["a", "a", "b"], {"a": 5, "b": 1}) == [False, False, False]
```

`server/tests/unit/modules/transaction/domain/test_recurring.py`:

```python
"""The recurring rule (spec §4.3)."""

import csv
import datetime as dt
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest
from uuid_utils.compat import uuid7

from app.modules.transaction.domain import DETECTED, USER, RecurringRow, detect_recurring, normalise_merchant

pytestmark = pytest.mark.unit

START = dt.date(2025, 1, 5)


def series(gaps: list[int], amount: str = "-9.99", source: str = DETECTED) -> list[RecurringRow]:
    """Rows starting on START, each `gap` days after the previous one."""
    dates = [START]
    for gap in gaps:
        dates.append(dates[-1] + dt.timedelta(days=gap))
    return [RecurringRow(uuid7(), d, Decimal(amount), source) for d in dates]


def verdicts(rows: list[RecurringRow]) -> list[bool]:
    result = detect_recurring(rows)
    return [result[r.id] for r in rows if r.id in result]


@pytest.mark.parametrize(
    ("gaps", "expected"),
    [
        ([7, 7], True),  # weekly
        ([30, 31], True),  # monthly
        ([26, 35], True),  # monthly, both edges
        ([25, 25], False),  # under monthly, over weekly
        ([36, 36], False),  # over monthly
        ([91, 91], True),  # quarterly
        ([365, 366], True),  # yearly, three rows
        ([365], False),  # yearly needs three rows
        ([30], False),  # two rows are never a series
    ],
)
def test_cadences(gaps, expected):
    assert set(verdicts(series(gaps))) == {expected}


def test_one_skipped_period_still_fits():
    assert set(verdicts(series([30, 61, 30, 30]))) == {True}


def test_three_quarters_of_the_gaps_must_fit():
    assert set(verdicts(series([30, 30, 30, 10]))) == {True}
    assert set(verdicts(series([30, 30, 10, 10]))) == {False}


def test_an_amount_outside_the_band_is_judged_apart():
    subscription = series([31, 28, 31], amount="-10.00")
    one_off = RecurringRow(uuid7(), START + dt.timedelta(days=40), Decimal("-12.00"), DETECTED)
    result = detect_recurring([*subscription, one_off])
    assert [result[r.id] for r in subscription] == [True] * 4
    assert result[one_off.id] is False


def test_small_amounts_get_a_euro_of_slack():
    rows = [
        RecurringRow(uuid7(), START, Decimal("-2.00"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=30), Decimal("-2.80"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=60), Decimal("-2.00"), DETECTED),
    ]
    assert set(detect_recurring(rows).values()) == {True}


def test_user_rows_count_as_evidence_and_are_never_judged():
    pinned = series([30], source=USER)
    last = RecurringRow(uuid7(), pinned[-1].date + dt.timedelta(days=30), Decimal("-9.99"), DETECTED)
    result = detect_recurring([*pinned, last])
    assert result == {last.id: True}


def test_money_in_and_money_out_are_judged_apart():
    salary = series([30, 31], amount="2400.00")
    refund = RecurringRow(uuid7(), START + dt.timedelta(days=15), Decimal("-2400.00"), DETECTED)
    result = detect_recurring([*salary, refund])
    assert [result[r.id] for r in salary] == [True, True, True]
    assert result[refund.id] is False


def test_legacy_fixture_flags_only_the_real_series():
    """A sparse sample, so it proves no false positives — not recall (spec §8)."""
    path = Path(__file__).parent / "data" / "legacy_transactions_400.csv"
    groups: dict[str, list[RecurringRow]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        for line in csv.DictReader(f):
            row = RecurringRow(uuid7(), dt.date.fromisoformat(line["date"][:10]), Decimal(line["amount"]), DETECTED)
            groups[normalise_merchant(line["merchant"])].append(row)
    flagged = {key for key, rows in groups.items() if any(detect_recurring(rows).values())}
    assert flagged == {"amznprime", "berliner verkehrsbetriebe bvg"}
```

```bash
mkdir -p server/tests/unit/modules/transaction/domain/data
cp /Users/tizianoiacovelli/projects/pf-legacy/server/tests/data/test_transactions_400.csv server/tests/unit/modules/transaction/domain/data/legacy_transactions_400.csv
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/transaction/domain -v`
Expected: ImportError on `DETECTED` / `plan_count_matched`.

- [ ] **Step 3: Implement**

`server/app/modules/transaction/domain/dedupe.py`:

```python
"""Count-matched duplicates for an import (docs/data-model/transaction.md, D3)."""

from collections import Counter


def plan_count_matched(fingerprints: list[str], existing: dict[str, int]) -> list[bool]:
    """Which rows of a file to keep: a fingerprint held k times keeps all but its first k copies.

    Two identical coffees in a file import as two; re-importing the same file
    imports nothing. `existing` counts the user's active rows per fingerprint.
    """
    seen: Counter[str] = Counter()
    keep = []
    for fingerprint in fingerprints:
        seen[fingerprint] += 1
        keep.append(seen[fingerprint] > existing.get(fingerprint, 0))
    return keep
```

`server/app/modules/transaction/domain/recurring.py`:

```python
"""The recurring rule: one merchant's rows judged as a series (docs/data-model/transaction.md, D6)."""

import datetime as dt
import uuid
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

DETECTED = "detected"
USER = "user"

_BAND = Decimal("0.15")
_MIN_SLACK = Decimal("1")
_FIT_SHARE = 0.75


@dataclass(frozen=True)
class Cadence:
    """A period a series can follow: the days between two rows, and how many rows it needs."""

    name: str
    min_days: int
    max_days: int
    min_rows: int


CADENCES = (
    Cadence("weekly", 6, 8, 3),
    Cadence("monthly", 26, 35, 3),
    Cadence("quarterly", 84, 98, 3),
    Cadence("yearly", 350, 380, 3),
)


@dataclass(frozen=True)
class RecurringRow:
    """What the rule reads of one active transaction."""

    id: uuid.UUID
    date: dt.date
    amount: Decimal
    source: str


def detect_recurring(rows: list[RecurringRow]) -> dict[uuid.UUID, bool]:
    """is_recurring for every `detected` row among one merchant key's active rows.

    Money in and money out are judged apart; within each, rows are clustered by
    amount and a cluster is a series when it follows a cadence. `user` rows
    count as evidence and get no verdict, so they are never changed.
    """
    verdict: dict[uuid.UUID, bool] = {}
    for incoming in (True, False):
        side = [r for r in rows if (r.amount > 0) is incoming]
        for cluster in _clusters(side):
            recurring = _is_series(cluster)
            for row in cluster:
                if row.source == DETECTED:
                    verdict[row.id] = recurring
    return verdict


def _clusters(rows: list[RecurringRow]) -> list[list[RecurringRow]]:
    """Rows grouped around fixed seeds: the most frequent amounts first, then the smallest.

    A row joins the first cluster whose seed is within ±15 % of the seed (at
    least €1); otherwise it seeds a cluster. A fixed seed does not drift the way
    a running median does.
    """
    counts = Counter(abs(r.amount) for r in rows)
    clusters: list[tuple[Decimal, list[RecurringRow]]] = []
    for row in sorted(rows, key=lambda r: (-counts[abs(r.amount)], abs(r.amount), r.date)):
        size = abs(row.amount)
        for seed, members in clusters:
            if abs(size - seed) <= max(seed * _BAND, _MIN_SLACK):
                members.append(row)
                break
        else:
            clusters.append((size, [row]))
    return [members for _, members in clusters]


def _fits(gap: int, cadence: Cadence) -> bool:
    """A gap of one period, or of two (one skipped)."""
    return cadence.min_days <= gap <= cadence.max_days or 2 * cadence.min_days <= gap <= 2 * cadence.max_days


def _is_series(cluster: list[RecurringRow]) -> bool:
    dates = sorted(r.date for r in cluster)
    gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:])]
    if not gaps:
        return False
    return any(
        len(cluster) >= cadence.min_rows and sum(_fits(g, cadence) for g in gaps) >= _FIT_SHARE * len(gaps)
        for cadence in CADENCES
    )
```

Update `server/app/modules/transaction/domain/__init__.py`:

```python
"""Transaction rules that need no database: pure functions over plain values (R9)."""

from app.modules.transaction.domain.dedupe import plan_count_matched
from app.modules.transaction.domain.fingerprint import fingerprint
from app.modules.transaction.domain.merchant import normalise_merchant
from app.modules.transaction.domain.recurring import DETECTED, USER, RecurringRow, detect_recurring

__all__ = [
    "DETECTED",
    "USER",
    "RecurringRow",
    "detect_recurring",
    "fingerprint",
    "normalise_merchant",
    "plan_count_matched",
]
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/transaction/domain -v`
Expected: all PASS. If `test_legacy_fixture_flags_only_the_real_series` fails, print `flagged` and stop: the rule or the normaliser differs from the spec — do not edit the expected set.

- [ ] **Step 5: Commit**

```bash
git add server/app/modules/transaction/domain server/tests/unit/modules/transaction/domain
git commit -m "CSV import: the recurring rule and count-matched duplicates"
```

---
### Task 3: The schema — two transaction columns, the import's two tables, erasure

**Files:**
- Modify: `server/app/modules/transaction/models.py`, `server/app/modules/transaction/__init__.py`, `server/alembic/env.py`, `server/tests/integration/modules/transaction/conftest.py`
- Create: `server/app/modules/transaction/imports/__init__.py`, `imports/models.py`, `imports/repository.py`, `imports/service.py`, `imports/handlers.py`
- Create: `server/alembic/versions/20261015_1200_5b7e2c9d4f10_csv_import.py`
- Create: `server/tests/unit/modules/transaction/imports/__init__.py` (empty), `server/tests/unit/modules/transaction/imports/test_handlers.py`, `server/tests/integration/modules/transaction/imports/__init__.py` (empty), `server/tests/integration/modules/transaction/imports/test_erasure.py`

**Interfaces:**
- Consumes: `normalise_merchant`, `DETECTED` (Tasks 1–2).
- Produces: `Transaction.merchant_key: str`, `Transaction.recurring_source: str`; `imports.models.MappingProfile` (table `csv_mapping_profile`: `user_id`, `column_key`, `mapping: dict[str, str]`), `imports.models.HeldUpload` (table `csv_upload`: `user_id` unique, `content: str`, `expires_at: datetime`); `import_repository.delete_all_for_user(session, user_id) -> None`; `import_service.delete_all_for_user(session, user_id) -> None`; subscriber `imports.handlers.erase_imports_on_user_erasing`.

- [ ] **Step 1: Write the failing tests**

`server/tests/unit/modules/transaction/imports/test_handlers.py`:

```python
"""The import's reaction to USER_ERASING."""

import pytest

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.transaction.imports import handlers

pytestmark = pytest.mark.unit


def test_subscribes_inline_to_user_erasing():
    matches = [s for s in events.subscriptions(USER_ERASING) if s.handler is handlers.erase_imports_on_user_erasing]
    assert matches, "erase_imports_on_user_erasing is not subscribed to USER_ERASING"
    assert matches[0].inline
```

`server/tests/integration/modules/transaction/imports/test_erasure.py`:

```python
"""Erasure removes the user's remembered mappings and held upload, and only theirs."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from app.modules.transaction.imports import handlers
from app.modules.transaction.imports.models import HeldUpload, MappingProfile

pytestmark = pytest.mark.integration


async def _seed(db_session, user):
    db_session.add(MappingProfile(user_id=user.id, column_key="a" * 64, mapping={"Betrag": "amount"}))
    db_session.add(HeldUpload(user_id=user.id, content="a,b\n1,2\n", expires_at=datetime.now(UTC) + timedelta(minutes=30)))
    await db_session.flush()


async def test_erasure_deletes_profiles_and_the_held_upload(db_session, test_user, other_user):
    await _seed(db_session, test_user)
    await _seed(db_session, other_user)

    await handlers.erase_imports_on_user_erasing(session=db_session, user_id=test_user.id)

    profiles = (await db_session.execute(select(MappingProfile.user_id))).scalars().all()
    uploads = (await db_session.execute(select(HeldUpload.user_id))).scalars().all()
    assert profiles == [other_user.id]
    assert uploads == [other_user.id]
```

`other_user` lives in `server/tests/integration/modules/transaction/conftest.py`; pytest finds it from the `imports/` subdirectory.

- [ ] **Step 2: Run them to see them fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/transaction/imports tests/integration/modules/transaction/imports -v`
Expected: `ModuleNotFoundError: No module named 'app.modules.transaction.imports'`.

- [ ] **Step 3: Add the transaction columns**

In `server/app/modules/transaction/models.py`, add the index to `__table_args__` and the two fields (no defaults: the app sets every value):

```python
    __table_args__ = (
        Index("ix_transaction_user_id_date", "user_id", "date"),
        Index("ix_transaction_user_id_fingerprint", "user_id", "fingerprint"),
        Index("ix_transaction_user_id_merchant_key", "user_id", "merchant_key"),
    )
    ...
    is_recurring: bool = Field(default=False)
    recurring_source: str = Field(max_length=16)
    fingerprint: str = Field(sa_column=Column(CHAR(64), nullable=False))
    merchant_key: str = Field(max_length=255)
```

Extend the class docstring with one sentence: "`merchant_key` is normalise_merchant(merchant), recomputed with the fingerprint; `recurring_source` says whether `is_recurring` was set by the rule (`detected`) or by the user (`user`), and the rule changes only `detected` rows (docs/data-model/transaction.md, D6–D7)."

- [ ] **Step 4: Add the import's models**

`server/app/modules/transaction/imports/models.py`:

```python
"""The import's tables: remembered mappings and the held upload (docs/data-model/transaction.md, D8–D9).

Both are user-owned and hard-deleted on erasure; nothing references them. Their
class names are two words, so they set `__tablename__` in snake_case — SQLModel's
default would be `mappingprofile`.
"""

from datetime import datetime

from sqlalchemy import CHAR, Column, DateTime, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models.base import BaseModel, UserOwnedMixin, UUIDPrimaryKeyMixin


class MappingProfile(BaseModel, UUIDPrimaryKeyMixin, UserOwnedMixin, table=True):
    """A confirmed column mapping, remembered for the next file with the same set of column names."""

    __tablename__ = "csv_mapping_profile"
    __table_args__ = (UniqueConstraint("user_id", "column_key", name="uq_csv_mapping_profile_user_id_column_key"),)

    column_key: str = Field(sa_column=Column(CHAR(64), nullable=False))
    mapping: dict[str, str] = Field(sa_column=Column(JSONB, nullable=False))


class HeldUpload(BaseModel, UUIDPrimaryKeyMixin, UserOwnedMixin, table=True):
    """An uploaded file waiting for its confirm: one per user, for 30 minutes."""

    __tablename__ = "csv_upload"
    __table_args__ = (UniqueConstraint("user_id", name="uq_csv_upload_user_id"),)

    content: str = Field(sa_column=Column(Text, nullable=False))
    expires_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
```

`server/app/modules/transaction/imports/repository.py` (Task 9 adds the rest):

```python
"""The import's repository: held uploads and remembered mappings, each query scoped by user_id."""

import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.modules.transaction.imports.models import HeldUpload, MappingProfile


class ImportRepository:
    """Repository for the import's tables."""

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Permanently remove the user's remembered mappings and held upload."""
        profiles = await session.execute(delete(MappingProfile).where(MappingProfile.user_id == user_id))
        uploads = await session.execute(delete(HeldUpload).where(HeldUpload.user_id == user_id))
        logger.info("csv_import_data_deleted", user_id=user_id, profiles=profiles.rowcount, uploads=uploads.rowcount)


import_repository = ImportRepository()
```

`server/app/modules/transaction/imports/service.py` (Tasks 9–10 add upload and confirm):

```python
"""The import: upload a bank's CSV, review its mapping, confirm (docs/product/features/csv-import.md)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transaction.imports.repository import import_repository


class ImportService:
    """Orchestrates the import."""

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Erasure: the user's remembered mappings and held upload."""
        await import_repository.delete_all_for_user(session, user_id)


import_service = ImportService()
```

`server/app/modules/transaction/imports/handlers.py`:

```python
"""The import's subscriptions to account events."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.transaction.imports.service import import_service


@events.on(USER_ERASING, inline=True)
async def erase_imports_on_user_erasing(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Permanently remove the user's remembered mappings and held upload.

    Inline, in the publishing transaction and before the user row is
    anonymised. A held upload is a bank statement; nothing references either
    table, so the rows go rather than being anonymised.
    """
    await import_service.delete_all_for_user(session, user_id)
```

`server/app/modules/transaction/imports/__init__.py`:

```python
"""CSV import, a feature sub-package of transaction (docs/architecture/server.md §2).

It calls the transaction core; the core never imports it.
"""

from app.modules.transaction.imports.service import import_service

__all__ = ["import_service"]

# @events.on is a module-level side effect: importing the package is what subscribes.
from app.modules.transaction.imports import handlers  # noqa: E402, F401
```

At the bottom of `server/app/modules/transaction/__init__.py`, after the existing handlers import:

```python
from app.modules.transaction import imports  # noqa: E402, F401  — importing it subscribes its handlers
```

In `server/alembic/env.py`, after `import app.modules.transaction.models`, add `import app.modules.transaction.imports.models`.

- [ ] **Step 5: Write the migration**

`server/alembic/versions/20261015_1200_5b7e2c9d4f10_csv_import.py`:

```python
"""csv import: merchant key, recurring source, mapping profiles, held uploads.

Revision ID: 5b7e2c9d4f10
Revises: 09aea922f9b1
Create Date: 2026-10-15 12:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

from alembic import op

# The live normaliser, not a frozen copy: changing it changes stored keys, which needs
# its own backfill revision whatever this one does (docs/data-model/transaction.md, D7).
from app.modules.transaction.domain import normalise_merchant

revision: str = "5b7e2c9d4f10"
down_revision: Union[str, Sequence[str], None] = "09aea922f9b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "transaction", sa.Column("merchant_key", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True)
    )
    # A server default only to fill existing rows; the app sets every value after this.
    op.add_column(
        "transaction",
        sa.Column(
            "recurring_source", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False, server_default="detected"
        ),
    )
    op.alter_column("transaction", "recurring_source", server_default=None)
    conn = op.get_bind()
    for merchant in conn.execute(sa.text('SELECT DISTINCT merchant FROM "transaction"')).scalars().all():
        conn.execute(
            sa.text('UPDATE "transaction" SET merchant_key = :key WHERE merchant = :merchant'),
            {"key": normalise_merchant(merchant), "merchant": merchant},
        )
    op.alter_column("transaction", "merchant_key", nullable=False)
    op.create_index("ix_transaction_user_id_merchant_key", "transaction", ["user_id", "merchant_key"], unique=False)

    op.create_table(
        "csv_mapping_profile",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("column_key", sa.CHAR(length=64), nullable=False),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "column_key", name="uq_csv_mapping_profile_user_id_column_key"),
    )
    op.create_index(op.f("ix_csv_mapping_profile_created_at"), "csv_mapping_profile", ["created_at"], unique=False)
    op.create_index(op.f("ix_csv_mapping_profile_user_id"), "csv_mapping_profile", ["user_id"], unique=False)

    op.create_table(
        "csv_upload",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_csv_upload_user_id"),
    )
    op.create_index(op.f("ix_csv_upload_created_at"), "csv_upload", ["created_at"], unique=False)
    op.create_index(op.f("ix_csv_upload_user_id"), "csv_upload", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_csv_upload_user_id"), table_name="csv_upload")
    op.drop_index(op.f("ix_csv_upload_created_at"), table_name="csv_upload")
    op.drop_table("csv_upload")
    op.drop_index(op.f("ix_csv_mapping_profile_user_id"), table_name="csv_mapping_profile")
    op.drop_index(op.f("ix_csv_mapping_profile_created_at"), table_name="csv_mapping_profile")
    op.drop_table("csv_mapping_profile")
    op.drop_index("ix_transaction_user_id_merchant_key", table_name="transaction")
    op.drop_column("transaction", "recurring_source")
    op.drop_column("transaction", "merchant_key")
```

- [ ] **Step 6: Give the test fixture the new columns**

In `server/tests/integration/modules/transaction/conftest.py`, `make_transaction`: add `"recurring_source": "detected"` to the default `fields`, and pass `merchant_key=normalise_merchant(fields["merchant"])` to `Transaction(...)` (import `normalise_merchant` from `app.modules.transaction.domain`; switch the `fingerprint` import to the same place).

- [ ] **Step 7: Run the tests**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/transaction tests/unit/models tests/unit/test_module_contracts.py tests/integration/modules/transaction tests/integration/database/test_migrations.py -v`
Expected: all PASS. `test_migrations_produce_the_models_schema` compares the migration with the models — if it reports a diff, fix the migration to match the models, not the reverse. `test_owned_tables.py` passes because both tables carry `UserOwnedMixin`.

Note that `TransactionService.create` and `import_many` do not set the new columns yet, so `tests/integration/modules/transaction/test_service.py` and the router tests fail on `NOT NULL` until Task 4; run only the paths above.

- [ ] **Step 8: Commit**

```bash
git add server/app/modules/transaction server/alembic server/tests
git commit -m "CSV import: merchant_key and recurring_source on transaction; mapping profile and held upload tables; erasure"
```

---

### Task 4: The recurring rule on every write

**Files:**
- Modify: `server/app/modules/transaction/service.py`, `server/app/modules/transaction/repository.py`, `server/app/modules/transaction/schemas.py`
- Modify: `server/tests/integration/modules/transaction/test_service.py`

**Interfaces:**
- Consumes: `normalise_merchant`, `detect_recurring`, `RecurringRow`, `DETECTED`, `USER` (Tasks 1–2); the columns (Task 3).
- Produces: `TransactionImport.is_recurring: Optional[bool] = None`; `transaction_service.count_active_by_fingerprints(session, user_id, fingerprints: list[str]) -> dict[str, int]`; `transaction_service.import_many(session, user_id, rows: list[TransactionImport]) -> int` (unchanged signature; now sets `merchant_key`, `recurring_source` and re-runs the rule). `create`, `update`, `soft_delete`, `batch_soft_delete` re-run the rule; `create` and `update` return the row as it stands after the rule.

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/integration/modules/transaction/test_service.py` (keep its existing imports; add any missing ones listed here):

```python
from sqlmodel import select

from app.modules.transaction.models import Transaction
from app.modules.transaction.schemas import TransactionCreate, TransactionImport, TransactionUpdate
from app.modules.transaction.service import transaction_service


async def _series(db_session, user_id, key: str) -> list[tuple[bool, str]]:
    """(is_recurring, recurring_source) of a merchant key's active rows, oldest first, read fresh."""
    statement = (
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.merchant_key == key, Transaction.deleted_at.is_(None))
        .order_by(Transaction.date)
        .execution_options(populate_existing=True)
    )
    return [(t.is_recurring, t.recurring_source) for t in (await db_session.execute(statement)).scalars()]


def _netflix(day: dt.date, **extra) -> TransactionCreate:
    return TransactionCreate(
        date=day, merchant="Netflix", amount=Decimal("-9.99"), category="leisure_entertainment", **extra
    )


class TestRecurringOnWrite:
    async def test_the_third_monthly_row_marks_the_series(self, db_session, test_user, make_transaction):
        await make_transaction(test_user, merchant="PAYPAL *NETFLIX 4029", amount=Decimal("-9.99"), date=dt.date(2026, 1, 5))
        await make_transaction(test_user, merchant="NETFLIX.COM", amount=Decimal("-9.99"), date=dt.date(2026, 2, 5))

        created = await transaction_service.create(db_session, test_user.id, _netflix(dt.date(2026, 3, 5)))

        assert (created.is_recurring, created.recurring_source, created.merchant_key) == (True, "detected", "netflix")
        assert await _series(db_session, test_user.id, "netflix") == [(True, "detected")] * 3

    async def test_a_ticked_box_is_the_users_and_an_unticked_one_is_not(self, db_session, test_user):
        ticked = await transaction_service.create(db_session, test_user.id, _netflix(dt.date(2026, 1, 5), is_recurring=True))
        unticked = await transaction_service.create(
            db_session, test_user.id, TransactionCreate(date=dt.date(2026, 1, 6), merchant="Kiosk", amount=Decimal("-2"), category="shopping")
        )
        assert (ticked.is_recurring, ticked.recurring_source) == (True, "user")
        assert (unticked.is_recurring, unticked.recurring_source) == (False, "detected")

    async def test_a_users_edit_survives_the_rule(self, db_session, test_user, make_transaction):
        rows = [
            await make_transaction(test_user, merchant="Netflix", amount=Decimal("-9.99"), date=dt.date(2026, m, 5))
            for m in (1, 2, 3)
        ]
        await transaction_service.update(db_session, rows[0], TransactionUpdate(category="shopping"))  # runs the rule
        edited = await transaction_service.update(db_session, rows[1], TransactionUpdate(is_recurring=False))
        assert (edited.is_recurring, edited.recurring_source) == (False, "user")
        assert await _series(db_session, test_user.id, "netflix") == [
            (True, "detected"),
            (False, "user"),
            (True, "detected"),
        ]

    async def test_renaming_a_merchant_rejudges_both_keys(self, db_session, test_user, make_transaction):
        rows = [
            await make_transaction(
                test_user, merchant="Netflix", amount=Decimal("-9.99"), date=dt.date(2026, m, 5), is_recurring=True
            )
            for m in (1, 2, 3)
        ]
        renamed = await transaction_service.update(db_session, rows[2], TransactionUpdate(merchant="Spotify"))
        assert renamed.merchant_key == "spotify"
        assert await _series(db_session, test_user.id, "netflix") == [(False, "detected")] * 2

    async def test_deleting_one_breaks_the_series(self, db_session, test_user, make_transaction):
        rows = [
            await make_transaction(
                test_user, merchant="Netflix", amount=Decimal("-9.99"), date=dt.date(2026, m, 5), is_recurring=True
            )
            for m in (1, 2, 3)
        ]
        await transaction_service.soft_delete(db_session, rows[1])
        assert await _series(db_session, test_user.id, "netflix") == [(False, "detected")] * 2

    async def test_batch_delete_rejudges_the_keys(self, db_session, test_user, make_transaction):
        rows = [
            await make_transaction(
                test_user, merchant="Netflix", amount=Decimal("-9.99"), date=dt.date(2026, m, 5), is_recurring=True
            )
            for m in (1, 2, 3)
        ]
        await transaction_service.batch_soft_delete(db_session, test_user.id, [rows[0].id])
        assert await _series(db_session, test_user.id, "netflix") == [(False, "detected")] * 2

    async def test_import_many_runs_the_rule_and_honours_a_users_value(self, db_session, test_user):
        rows = [
            TransactionImport(
                date=dt.date(2026, m, 5), merchant="Netflix", amount=Decimal("-9.99"),
                category="leisure_entertainment", confidence=0.9,
            )
            for m in (1, 2, 3)
        ]
        pinned = TransactionImport(
            date=dt.date(2026, 3, 9), merchant="Kiosk", amount=Decimal("-2"), category="shopping",
            confidence=0.9, is_recurring=True,
        )
        assert await transaction_service.import_many(db_session, test_user.id, [*rows, pinned]) == 4
        assert await _series(db_session, test_user.id, "netflix") == [(True, "detected")] * 3
        assert await _series(db_session, test_user.id, "kiosk") == [(True, "user")]


class TestCountActiveByFingerprints:
    async def test_counts_active_rows_only(self, db_session, test_user, other_user, make_transaction):
        a = await make_transaction(test_user)
        await make_transaction(test_user)
        gone = await make_transaction(test_user, merchant="Gone")
        await transaction_service.soft_delete(db_session, gone)
        await make_transaction(other_user)

        counts = await transaction_service.count_active_by_fingerprints(
            db_session, test_user.id, [a.fingerprint, gone.fingerprint, "f" * 64]
        )
        assert counts == {a.fingerprint: 2}
```

Run ruff format on the file afterwards; the long lines above are wrapped by it.

- [ ] **Step 2: Run them to see them fail**

Run: `cd server && APP_ENV=test uv run pytest tests/integration/modules/transaction/test_service.py -v`
Expected: FAIL — `NOT NULL` violations on `merchant_key`, and `count_active_by_fingerprints` missing.

- [ ] **Step 3: Make `TransactionImport.is_recurring` optional**

In `server/app/modules/transaction/schemas.py`, `TransactionImport`:

```python
    is_recurring: Optional[bool] = Field(
        None, description="The importer's own value, kept as the user's; None lets the recurring rule decide"
    )
```

and update its docstring to: `"""A row written by the import and the seed: confidence and original category are its own."""`

- [ ] **Step 4: Add the repository methods**

In `server/app/modules/transaction/repository.py` add `from sqlalchemy import Row` to the sqlalchemy import, `from app.modules.transaction.domain import DETECTED`, and these methods on `TransactionRepository`:

```python
    @staticmethod
    async def refresh(session: AsyncSession, transaction: Transaction) -> Transaction:
        """Reload a transaction's columns, after a statement that bypassed the ORM changed them."""
        await session.refresh(transaction)
        return transaction

    @staticmethod
    async def count_active_by_fingerprints(
        session: AsyncSession, user_id: uuid.UUID, fingerprints: list[str]
    ) -> dict[str, int]:
        """How many active rows this user holds per fingerprint, for those that occur at all."""
        if not fingerprints:
            return {}
        statement = (
            select(Transaction.fingerprint, func.count())
            .where(
                Transaction.user_id == user_id,
                Transaction.fingerprint.in_(set(fingerprints)),
                Transaction.deleted_at.is_(None),
            )
            .group_by(Transaction.fingerprint)
        )
        return {fingerprint: count for fingerprint, count in (await session.execute(statement)).all()}

    @staticmethod
    async def merchant_keys_for_ids(session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID]) -> set[str]:
        """The merchant keys of this user's active rows among `ids`."""
        statement = select(Transaction.merchant_key).where(
            Transaction.id.in_(ids), Transaction.user_id == user_id, Transaction.deleted_at.is_(None)
        )
        return set((await session.execute(statement)).scalars().all())

    @staticmethod
    async def recurring_rows_for_keys(session: AsyncSession, user_id: uuid.UUID, keys: set[str]) -> list[Row]:
        """id, date, amount, is_recurring and recurring_source of this user's active rows for these merchant keys."""
        statement = select(
            Transaction.id,
            Transaction.date,
            Transaction.amount,
            Transaction.is_recurring,
            Transaction.recurring_source,
        ).where(Transaction.user_id == user_id, Transaction.merchant_key.in_(keys), Transaction.deleted_at.is_(None))
        return list((await session.execute(statement)).all())

    @staticmethod
    async def set_recurring_for_ids(
        session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID], value: bool
    ) -> int:
        """Set is_recurring on this user's `detected` rows among `ids` in one UPDATE; a `user` row is never touched."""
        if not ids:
            return 0
        statement = (
            update(Transaction)
            .where(
                Transaction.id.in_(ids),
                Transaction.user_id == user_id,
                Transaction.recurring_source == DETECTED,
            )
            .values(is_recurring=value, updated_at=datetime.now(UTC))
        )
        result = await session.execute(statement)
        return result.rowcount
```

- [ ] **Step 5: Run the rule from the service**

In `server/app/modules/transaction/service.py`, import from the domain:

```python
from app.modules.transaction.domain import DETECTED, USER, RecurringRow, detect_recurring, fingerprint, normalise_merchant
```

Add the private helper on `TransactionService`:

```python
    @staticmethod
    async def _refresh_recurring(session: AsyncSession, user_id: uuid.UUID, keys: set[str]) -> None:
        """Re-judge every active row of these merchants; only `detected` rows change (docs/data-model/transaction.md, D6)."""
        if not keys:
            return
        rows = await transaction_repository.recurring_rows_for_keys(session, user_id, keys)
        current = {row.id: row.is_recurring for row in rows}
        verdict = detect_recurring([RecurringRow(r.id, r.date, r.amount, r.recurring_source) for r in rows])
        now_true = [i for i, recurring in verdict.items() if recurring and not current[i]]
        now_false = [i for i, recurring in verdict.items() if not recurring and current[i]]
        await transaction_repository.set_recurring_for_ids(session, user_id, now_true, True)
        await transaction_repository.set_recurring_for_ids(session, user_id, now_false, False)
```

Then change the writers:

```python
    @staticmethod
    async def create(session: AsyncSession, user_id: uuid.UUID, body: TransactionCreate) -> Transaction:
        """Add a transaction by hand. Raises DuplicateTransactionError on an active twin, unless allowed.

        A ticked Recurring box is the user's; an unticked one is left to the rule.
        """
        key = fingerprint(user_id, body.date, body.merchant, body.amount, body.description)
        if not body.allow_duplicate:
            ...  # unchanged duplicate check
        transaction = Transaction(
            user_id=user_id,
            date=body.date,
            merchant=body.merchant,
            amount=body.amount,
            description=body.description,
            category=body.category,
            confidence=MANUAL_CONFIDENCE,
            is_recurring=body.is_recurring,
            recurring_source=USER if body.is_recurring else DETECTED,
            fingerprint=key,
            merchant_key=normalise_merchant(body.merchant),
        )
        transaction = await transaction_repository.add(session, transaction)
        await TransactionService._refresh_recurring(session, user_id, {transaction.merchant_key})
        return await transaction_repository.refresh(session, transaction)

    @staticmethod
    async def update(session: AsyncSession, transaction: Transaction, body: TransactionUpdate) -> Transaction:
        """Apply a partial edit. An empty edit changes nothing; any edit sets confidence to 1.

        An edit that sends is_recurring makes it the user's. The rule re-runs for
        the merchant before and after the edit.
        """
        changes = body.model_dump(exclude_unset=True)
        if not changes:
            return transaction
        merged = {
            name: changes.get(name, getattr(transaction, name))
            for name in ("date", "merchant", "amount", "description")
        }
        old_key = transaction.merchant_key
        values = {
            **changes,
            "confidence": MANUAL_CONFIDENCE,
            "fingerprint": fingerprint(transaction.user_id, **merged),
            "merchant_key": normalise_merchant(merged["merchant"]),
        }
        if "is_recurring" in changes:
            values["recurring_source"] = USER
        updated = await transaction_repository.update(session, transaction, values)
        await TransactionService._refresh_recurring(session, updated.user_id, {old_key, updated.merchant_key})
        return await transaction_repository.refresh(session, updated)

    @staticmethod
    async def soft_delete(session: AsyncSession, transaction: Transaction) -> None:
        """Hide one transaction from every list; the row stays. Its merchant is re-judged."""
        await transaction_repository.soft_delete(session, transaction)
        await TransactionService._refresh_recurring(session, transaction.user_id, {transaction.merchant_key})

    @staticmethod
    async def count_active_by_fingerprints(
        session: AsyncSession, user_id: uuid.UUID, fingerprints: list[str]
    ) -> dict[str, int]:
        """The user's active rows per fingerprint: the import's duplicate check."""
        return await transaction_repository.count_active_by_fingerprints(session, user_id, fingerprints)

    @staticmethod
    async def import_many(session: AsyncSession, user_id: uuid.UUID, rows: list[TransactionImport]) -> int:
        """Insert rows that carry their own confidence and original category (the import; the seed).

        A row's own is_recurring is the user's; None leaves it to the rule, which re-runs for every merchant.
        """
        transactions = [
            Transaction(
                user_id=user_id,
                fingerprint=fingerprint(user_id, row.date, row.merchant, row.amount, row.description),
                merchant_key=normalise_merchant(row.merchant),
                recurring_source=DETECTED if row.is_recurring is None else USER,
                is_recurring=bool(row.is_recurring),
                **row.model_dump(exclude={"is_recurring"}),
            )
            for row in rows
        ]
        count = await transaction_repository.add_many(session, user_id, transactions)
        await TransactionService._refresh_recurring(session, user_id, {t.merchant_key for t in transactions})
        return count
```

And `batch_soft_delete`:

```python
    @staticmethod
    async def batch_soft_delete(session: AsyncSession, user_id: uuid.UUID, ids: list[uuid.UUID]) -> int:
        """Soft-delete up to 100 transactions, all or none. Their merchants are re-judged."""
        keys = await transaction_repository.merchant_keys_for_ids(session, user_id, ids)
        changed = await transaction_repository.soft_delete_ids(session, user_id, ids)
        TransactionService._require_all(ids, changed)
        await TransactionService._refresh_recurring(session, user_id, keys)
        return len(changed)
```

Keep the "unchanged duplicate check" block in `create` exactly as it is today.

- [ ] **Step 6: Run the transaction tests**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/transaction tests/integration/modules/transaction tests/integration/scripts tests/unit/scripts -v`
Expected: all PASS, including the router tests and the seed script tests, which now set the new columns through the service.

- [ ] **Step 7: Commit**

```bash
git add server/app/modules/transaction server/tests
git commit -m "CSV import: the recurring rule re-runs on every write; provenance on add, edit and import"
```

---
### Task 5: LLM plumbing for calls outside a graph

**Files:**
- Modify: `server/app/integrations/llm/service.py` (`config` through `call`), `server/app/agents/shared/observability/langfuse.py`, `server/app/agents/shared/observability/__init__.py`
- Create: `server/app/agents/shared/structured.py`
- Modify: `server/tests/unit/integrations/llm/test_service.py`, `server/tests/unit/agents/test_graph_config.py`
- Create: `server/tests/unit/agents/test_structured.py`

**Interfaces:**
- Produces: `LLMService.call(messages, model_name=None, config: Optional[RunnableConfig] = None, **model_kwargs)` — `config` reaches `llm.ainvoke(messages, config=config)`; `create_trace_config(user_id: uuid.UUID, session_id: uuid.UUID, name: str) -> dict`; in `app.agents.shared.structured`: `structured_llm: LLMService` (tool-less instance), `class InvalidModelAnswer(ValueError)`, `parse_answer(text: str, shape: type[T]) -> T`, `async ask_json(service: LLMService, system: str, user: str, shape: type[T], config: dict) -> T` (one retry on an invalid answer, through tenacity; model errors propagate).

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/unit/integrations/llm/test_service.py`:

```python
async def test_call_passes_the_config_to_the_model(messages):
    service = LLMService()
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="ok"))
    service._llm = llm
    config = {"callbacks": [], "metadata": {"langfuse_user_id": "u"}}

    await service.call(messages, config=config)

    llm.ainvoke.assert_awaited_once_with(messages, config=config)
```

(If the module already has a helper that builds a service with a stub client, use it instead of setting `_llm` directly.)

Append to `server/tests/unit/agents/test_graph_config.py`:

```python
from app.agents.shared.observability.langfuse import create_trace_config


def test_a_trace_config_groups_calls_by_session_and_names_the_run():
    user_id, session_id = uuid7(), uuid7()
    config = create_trace_config(user_id, session_id, "transaction_labeler")
    assert config["run_name"] == "transaction_labeler"
    assert config["metadata"]["langfuse_user_id"] == str(user_id)
    assert config["metadata"]["langfuse_session_id"] == str(session_id)
    assert "transaction_labeler" in config["metadata"]["langfuse_tags"]
    assert "configurable" not in config
```

`server/tests/unit/agents/test_structured.py`:

```python
"""A model call whose answer must be JSON of a known shape."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage
from pydantic import RootModel
from tenacity import wait_none

from app.agents.shared import structured
from app.agents.shared.structured import InvalidModelAnswer, ask_json, parse_answer
from app.integrations.llm import LLMAPIError

pytestmark = pytest.mark.unit


class Mapping(RootModel[dict[str, str]]):
    pass


@pytest.fixture(autouse=True)
def no_backoff():
    """The retry's real backoff would sleep a second; tenacity reads `wait` from the decorated function."""
    original = structured._ask_once.retry.wait
    structured._ask_once.retry.wait = wait_none()
    yield
    structured._ask_once.retry.wait = original


def test_parses_plain_and_fenced_json():
    assert parse_answer('{"a": "date"}', Mapping).root == {"a": "date"}
    assert parse_answer('```json\n{"a": "date"}\n```', Mapping).root == {"a": "date"}


def test_rejects_prose_and_the_wrong_shape():
    with pytest.raises(InvalidModelAnswer):
        parse_answer("Sure! Here it is", Mapping)
    with pytest.raises(InvalidModelAnswer):
        parse_answer('["a"]', Mapping)


async def test_asks_once_more_after_an_invalid_answer():
    service = MagicMock()
    service.call = AsyncMock(side_effect=[AIMessage(content="nope"), AIMessage(content='{"a": "date"}')])
    answer = await ask_json(service, "system", "user", Mapping, {"callbacks": []})
    assert answer.root == {"a": "date"}
    assert service.call.await_count == 2
    assert service.call.await_args.kwargs["config"] == {"callbacks": []}


async def test_gives_up_after_two_invalid_answers():
    service = MagicMock()
    service.call = AsyncMock(return_value=AIMessage(content="nope"))
    with pytest.raises(InvalidModelAnswer):
        await ask_json(service, "system", "user", Mapping, {})
    assert service.call.await_count == 2


async def test_a_model_error_propagates_without_a_second_ask():
    service = MagicMock()
    service.call = AsyncMock(side_effect=LLMAPIError("down"))
    with pytest.raises(LLMAPIError):
        await ask_json(service, "system", "user", Mapping, {})
    assert service.call.await_count == 1
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/integrations/llm/test_service.py tests/unit/agents/test_graph_config.py tests/unit/agents/test_structured.py -v`
Expected: FAIL — `call()` has no `config`; `create_trace_config` and `app.agents.shared.structured` missing.

- [ ] **Step 3: Thread `config` through `LLMService`**

In `server/app/integrations/llm/service.py` import `from langchain_core.runnables import RunnableConfig` and:
- `_call_llm_with_retry(self, messages: List[BaseMessage], config: Optional[RunnableConfig] = None)` → `response = await llm.ainvoke(messages, config=config)`.
- `_call_with_fallback(self, messages, config: Optional[RunnableConfig] = None)` → passes `config` to `_call_llm_with_retry`.
- `call(self, messages, model_name: Optional[str] = None, config: Optional[RunnableConfig] = None, **model_kwargs)` → passes `config` to both `_call_with_fallback` calls. Docstring gains: "`config` carries tracing callbacks for a call made outside a graph; inside one, LangChain propagates the graph's."

- [ ] **Step 4: Add `create_trace_config`**

In `server/app/agents/shared/observability/langfuse.py`:

```python
def create_trace_config(user_id: uuid.UUID, session_id: uuid.UUID, name: str) -> dict:
    """Langfuse config for a model call made outside a graph.

    Traced to the user, grouped by `session_id` (an import's upload id), named
    `name`. No thread id: nothing is checkpointed.
    """
    user, session = str(user_id), str(session_id)
    return {
        "callbacks": [CallbackHandler()],
        "run_name": name,
        "metadata": {
            "user_id": user,
            "environment": settings.ENVIRONMENT.value,
            "langfuse_user_id": user,
            "langfuse_session_id": session,
            "langfuse_tags": [settings.ENVIRONMENT.value, name],
        },
    }
```

Export it from `server/app/agents/shared/observability/__init__.py` beside `create_graph_config`.

- [ ] **Step 5: Add `structured.py`**

`server/app/agents/shared/structured.py`:

```python
"""A model call whose answer must be JSON of a known shape: the import's two agents use it."""

import json
import re
from typing import TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.integrations.llm import LLMService

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")

# Tool-less: the chatbot's `llm_service` has tools bound, and an answer here must never be a tool call.
# Built lazily by LLMService itself, so importing this needs no API key.
structured_llm = LLMService()


class InvalidModelAnswer(ValueError):
    """The model answered, but not with JSON of the expected shape."""


def parse_answer(text: str, shape: type[T]) -> T:
    """`text` as `shape`, tolerating a Markdown code fence. Raises InvalidModelAnswer."""
    cleaned = _FENCE.sub("", text.strip())
    try:
        return shape.model_validate(json.loads(cleaned))
    except (json.JSONDecodeError, ValidationError) as e:
        raise InvalidModelAnswer(type(e).__name__) from e


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type(InvalidModelAnswer),
    reraise=True,
)
async def _ask_once(service: LLMService, messages: list, shape: type[T], config: dict) -> T:
    response = await service.call(messages, config=config)
    return parse_answer(response.text, shape)


async def ask_json(service: LLMService, system: str, user: str, shape: type[T], config: dict) -> T:
    """Ask, parse and validate; an invalid answer is asked once more, then raises InvalidModelAnswer.

    A model error (LLMServiceError) propagates: the service has already retried
    and fallen back through its registry.
    """
    return await _ask_once(service, [SystemMessage(content=system), HumanMessage(content=user)], shape, config)
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/integrations tests/unit/agents -v`
Expected: all PASS (the chatbot's tests too: `call` without `config` behaves as before).

- [ ] **Step 7: Commit**

```bash
git add server/app/integrations/llm/service.py server/app/agents/shared server/tests/unit
git commit -m "CSV import: tracing config through LLMService.call; a structured JSON ask for agents"
```

---

### Task 6: The labeller agent

**Files:**
- Create: `server/app/agents/transaction_labeler/__init__.py`, `labeler.py`, `known_merchants.py`, `prompts/v2.md`
- Create: `server/tests/unit/agents/transaction_labeler/__init__.py` (empty), `test_labeler.py`, `test_known_merchants.py`

**Interfaces:**
- Consumes: `structured_llm`, `ask_json`, `create_trace_config` (Task 5); in the test only, `normalise_merchant` and `CATEGORIES`.
- Produces, from `app.agents.transaction_labeler`: `MerchantToLabel(key: str, merchant: str, description: Optional[str], original_category: Optional[str], amount: Decimal)`; `Label(category: str, confidence: float)`; `LabelResult(labels: dict[str, Label], fallback_keys: set[str], all_failed: bool)`; `async label(merchants: list[MerchantToLabel], categories: list[tuple[str, str]], *, user_id: uuid.UUID, upload_id: uuid.UUID) -> LabelResult` — `labels` has an entry for every key; `all_failed` is true when at least one LLM batch ran and none succeeded. Constants `KNOWN_CONFIDENCE = 0.95`, `FALLBACK_CATEGORY = "miscellaneous"`, `FALLBACK_CONFIDENCE = 0.3`, `BATCH_SIZE = 50`, `MAX_CONCURRENT_BATCHES = 5`.

- [ ] **Step 1: Generate the known-merchant table**

Legacy's 129 entries become `normalised key → slug`; the enum name lowercased is the slug, except `INSURANCE` → `insurances`. Run once from `server/` (it needs Task 1's normaliser):

```bash
cd server && uv run python - <<'EOF'
import re
from pathlib import Path
from app.modules.transaction.domain import normalise_merchant

src = Path("/Users/tizianoiacovelli/projects/pf-legacy/server/app/utils/merchant_mappings.py").read_text()
table = {}
for name, enum in re.findall(r'"([^"]+)":\s*CategoryEnum\.([A-Z_]+)', src):
    table.setdefault(normalise_merchant(name), "insurances" if enum == "INSURANCE" else enum.lower())
assert len(table) == 129, len(table)
lines = "\n".join(f'    "{k}": "{v}",' for k, v in table.items())
Path("app/agents/transaction_labeler").mkdir(exist_ok=True)
Path("app/agents/transaction_labeler/known_merchants.py").write_text(f'''"""Well-known merchants and their category, ported from legacy v1.0 (German/European).

Keys are merchant keys — already normalised, so they match the import's keys
exactly; tests/unit/agents/transaction_labeler/test_known_merchants.py holds
them to that. Values are category slugs.
"""

KNOWN_MERCHANTS: dict[str, str] = {{
{lines}
}}
''')
EOF
```

Then append the matcher to the generated file:

```python
# Longest names first, so "amazon prime" wins over a shorter name inside it.
_BY_LENGTH = sorted(KNOWN_MERCHANTS.items(), key=lambda item: -len(item[0].split()))


def match_known(key: str) -> str | None:
    """The slug of the first known merchant whose words appear whole and in order in `key`, or None.

    Whole words, not substrings: "dm" matches "dm drogerie" but not "dmitri".
    """
    tokens = key.split()
    for known, slug in _BY_LENGTH:
        words = known.split()
        if any(tokens[i : i + len(words)] == words for i in range(len(tokens) - len(words) + 1)):
            return slug
    return None
```

- [ ] **Step 2: Write the failing tests**

`server/tests/unit/agents/transaction_labeler/test_known_merchants.py`:

```python
"""The known-merchant table agrees with the transaction module it cannot import (R2)."""

import pytest

from app.agents.transaction_labeler.known_merchants import KNOWN_MERCHANTS, match_known
from app.modules.transaction import CATEGORIES
from app.modules.transaction.domain import normalise_merchant

pytestmark = pytest.mark.unit


def test_every_key_is_already_a_merchant_key():
    assert [k for k in KNOWN_MERCHANTS if normalise_merchant(k) != k] == []


def test_every_value_is_a_category_slug():
    slugs = {slug for slug, _ in CATEGORIES}
    assert {v for v in KNOWN_MERCHANTS.values()} <= slugs


@pytest.mark.parametrize(
    ("key", "slug"),
    [("netflix", "leisure_entertainment"), ("rewe markt", "food_groceries"), ("bvg", "transportation")],
)
def test_whole_words_match(key, slug):
    assert match_known(key) == slug


def test_a_word_inside_another_does_not_match():
    assert match_known("dmitri petrov") is None
    assert match_known("university of bologna") is None


def test_the_longest_name_wins():
    assert match_known("aldi süd filiale") == KNOWN_MERCHANTS["aldi süd"]
```

`server/tests/unit/agents/transaction_labeler/test_labeler.py`:

```python
"""The labeller: known merchants, batches, fallbacks (spec §6.3). The model is stubbed."""

import json
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from uuid_utils.compat import uuid7

from app.agents.shared.structured import InvalidModelAnswer
from app.agents.transaction_labeler import (
    BATCH_SIZE,
    FALLBACK_CATEGORY,
    FALLBACK_CONFIDENCE,
    KNOWN_CONFIDENCE,
    Label,
    MerchantToLabel,
    label,
)
from app.integrations.llm import LLMAPIError

pytestmark = pytest.mark.unit

CATEGORIES = [("shopping", "Shopping"), ("food_groceries", "Food & Groceries"), ("miscellaneous", "Miscellaneous")]
IDS = {"user_id": uuid7(), "upload_id": uuid7()}


def merchant(key: str) -> MerchantToLabel:
    return MerchantToLabel(key=key, merchant=key.upper(), description=None, original_category=None, amount=Decimal("-5.00"))


@pytest.fixture(autouse=True)
def no_langfuse():
    with patch("app.agents.transaction_labeler.labeler.create_trace_config", return_value={"metadata": {}}):
        yield


def answering(answer_for):
    """An ask_json stub: `answer_for(batch_items)` returns the parsed answer list for one batch."""

    async def fake(service, system, user, shape, config):
        return shape.model_validate(answer_for(json.loads(user)))

    return fake


async def test_a_known_merchant_skips_the_model():
    ask = AsyncMock()
    with patch("app.agents.transaction_labeler.labeler.ask_json", ask):
        result = await label([merchant("rewe")], CATEGORIES, **IDS)
    ask.assert_not_awaited()
    assert result.labels == {"rewe": Label("food_groceries", KNOWN_CONFIDENCE)}
    assert result.all_failed is False


async def test_the_model_labels_the_rest_by_slug_or_label():
    def answer(items):
        return [
            {"id": 0, "category": "shopping", "confidence": 0.9},
            {"id": 1, "category": "Food & Groceries", "confidence": 1.7},
        ]

    with patch("app.agents.transaction_labeler.labeler.ask_json", answering(answer)):
        result = await label([merchant("kiosk a"), merchant("kiosk b")], CATEGORIES, **IDS)
    assert result.labels == {"kiosk a": Label("shopping", 0.9), "kiosk b": Label("food_groceries", 1.0)}
    assert result.fallback_keys == set()


async def test_an_unknown_category_or_a_skipped_merchant_falls_back():
    def answer(items):
        return [{"id": 0, "category": "Groceries!", "confidence": 0.9}]

    with patch("app.agents.transaction_labeler.labeler.ask_json", answering(answer)):
        result = await label([merchant("kiosk a"), merchant("kiosk b")], CATEGORIES, **IDS)
    fallback = Label(FALLBACK_CATEGORY, FALLBACK_CONFIDENCE)
    assert result.labels == {"kiosk a": fallback, "kiosk b": fallback}
    assert result.fallback_keys == {"kiosk a", "kiosk b"}
    assert result.all_failed is False


async def test_merchants_go_in_batches_and_a_failed_batch_falls_back():
    merchants = [merchant(f"shop {i:03d}") for i in range(BATCH_SIZE + 1)]
    calls = []

    async def fake(service, system, user, shape, config):
        items = json.loads(user)
        calls.append(len(items))
        if len(items) == 1:
            raise LLMAPIError("down")
        return shape.model_validate([{"id": i, "category": "shopping", "confidence": 0.8} for i in range(len(items))])

    with patch("app.agents.transaction_labeler.labeler.ask_json", fake):
        result = await label(merchants, CATEGORIES, **IDS)
    assert sorted(calls) == [1, BATCH_SIZE]
    assert result.fallback_keys == {merchants[-1].key}
    assert result.all_failed is False


@pytest.mark.parametrize("error", [LLMAPIError("down"), InvalidModelAnswer("prose"), RuntimeError("no key")])
async def test_every_batch_failing_is_all_failed(error):
    with patch("app.agents.transaction_labeler.labeler.ask_json", AsyncMock(side_effect=error)):
        result = await label([merchant("kiosk a")], CATEGORIES, **IDS)
    assert result.all_failed is True
    assert result.labels["kiosk a"] == Label(FALLBACK_CATEGORY, FALLBACK_CONFIDENCE)


async def test_nothing_to_ask_is_not_a_failure():
    result = await label([], CATEGORIES, **IDS)
    assert (result.labels, result.all_failed) == ({}, False)


async def test_the_model_sees_amounts_as_decimals_and_the_banks_category():
    seen = {}

    async def fake(service, system, user, shape, config):
        seen["system"], seen["items"] = system, json.loads(user)
        return shape.model_validate([])

    item = MerchantToLabel(key="kiosk", merchant="KIOSK 24", description="Snacks", original_category="Food", amount=Decimal("-4.50"))
    with patch("app.agents.transaction_labeler.labeler.ask_json", fake):
        await label([item], CATEGORIES, **IDS)
    assert seen["items"] == [
        {"id": 0, "merchant": "KIOSK 24", "amount": "-4.50", "description": "Snacks", "bank_category": "Food"}
    ]
    assert "- shopping: Shopping" in seen["system"]
```

- [ ] **Step 3: Run them to see them fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/transaction_labeler -v`
Expected: FAIL on `from app.agents.transaction_labeler import ...` (the package has no `__init__` exports yet).

- [ ] **Step 4: Implement**

`server/app/agents/transaction_labeler/prompts/v2.md`:

```markdown
You are a transaction categoriser for a personal finance app.

You MUST use ONLY the category slugs listed below. Do not invent, abbreviate or paraphrase them.

Categories (slug: label):
{categories}

The user message is a JSON array of merchants. Each has an id, the merchant as the bank wrote it, a typical signed amount in EUR (negative is money out), a sample description and the bank's own category when it gave one.

Return ONLY a JSON array with one object per merchant:
[
  {{"id": 0, "category": "shopping", "confidence": 0.95}},
  ...
]

Rules:
- "category" is a slug copied verbatim from the list above
- "confidence" is a float from 0.0 to 1.0: how sure you are
- No other text outside the JSON array
```

`server/app/agents/transaction_labeler/labeler.py`:

```python
"""The labeller: a category and a confidence for each merchant of an import (docs/product/features/categorisation.md).

Known merchants first, then the model in batches. It imports nothing from a
module (R2): the category list comes in as `(slug, label)` pairs.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, RootModel

from app.agents.shared.observability import create_trace_config
from app.agents.shared.structured import ask_json, structured_llm
from app.agents.transaction_labeler.known_merchants import match_known
from app.core.logging import logger

KNOWN_CONFIDENCE = 0.95
FALLBACK_CATEGORY = "miscellaneous"
FALLBACK_CONFIDENCE = 0.3
BATCH_SIZE = 50
MAX_CONCURRENT_BATCHES = 5
PROMPT_VERSION = "v2"

_PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")


@dataclass(frozen=True)
class MerchantToLabel:
    """One merchant of an import, as the model sees it."""

    key: str
    merchant: str
    description: Optional[str]
    original_category: Optional[str]
    amount: Decimal


@dataclass(frozen=True)
class Label:
    """A category slug and how sure the labeller is, 0 to 1."""

    category: str
    confidence: float


@dataclass(frozen=True)
class LabelResult:
    """A label for every merchant key, which keys fell back, and whether the model failed entirely."""

    labels: dict[str, Label]
    fallback_keys: set[str]
    all_failed: bool


class _Answer(BaseModel):
    id: int
    category: str
    confidence: float


class _Answers(RootModel[list[_Answer]]):
    pass


async def label(
    merchants: list[MerchantToLabel],
    categories: list[tuple[str, str]],
    *,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
) -> LabelResult:
    """Label every merchant. A merchant the model cannot place is filed under Miscellaneous at 0.3."""
    labels: dict[str, Label] = {}
    unknown = []
    for item in merchants:
        slug = match_known(item.key)
        if slug is not None:
            labels[item.key] = Label(slug, KNOWN_CONFIDENCE)
        else:
            unknown.append(item)

    batches = [unknown[i : i + BATCH_SIZE] for i in range(0, len(unknown), BATCH_SIZE)]
    config = create_trace_config(user_id, upload_id, "transaction_labeler")
    config["metadata"]["prompt_version"] = PROMPT_VERSION
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)

    async def run(batch: list[MerchantToLabel]) -> Optional[dict[str, Label]]:
        async with semaphore:
            try:
                return await _label_batch(batch, categories, config)
            except Exception as e:  # any failure of one batch is that batch's fallback, never the import's crash
                logger.warning("label_batch_failed", size=len(batch), error_type=type(e).__name__)
                return None

    answers = await asyncio.gather(*(run(batch) for batch in batches))
    fallback: set[str] = set()
    for batch, answer in zip(batches, answers):
        for item in batch:
            got = answer.get(item.key) if answer is not None else None
            if got is None:
                fallback.add(item.key)
                got = Label(FALLBACK_CATEGORY, FALLBACK_CONFIDENCE)
            labels[item.key] = got
    all_failed = bool(batches) and all(answer is None for answer in answers)
    logger.info(
        "merchants_labelled", known=len(merchants) - len(unknown), asked=len(unknown), fallback=len(fallback)
    )
    return LabelResult(labels=labels, fallback_keys=fallback, all_failed=all_failed)


async def _label_batch(
    batch: list[MerchantToLabel], categories: list[tuple[str, str]], config: dict
) -> dict[str, Label]:
    """One model call for up to BATCH_SIZE merchants: the labels it gave that name a real category."""
    slugs = {slug for slug, _ in categories}
    by_label = {label.casefold(): slug for slug, label in categories}
    system = _PROMPT.format(categories="\n".join(f"- {slug}: {label}" for slug, label in categories))
    user = json.dumps(
        [
            {
                "id": i,
                "merchant": item.merchant,
                "amount": str(item.amount),
                "description": item.description or "",
                "bank_category": item.original_category or "",
            }
            for i, item in enumerate(batch)
        ],
        ensure_ascii=False,
    )
    answers = await ask_json(structured_llm, system, user, _Answers, config)
    labelled: dict[str, Label] = {}
    for answer in answers.root:
        if not 0 <= answer.id < len(batch):
            continue
        slug = answer.category if answer.category in slugs else by_label.get(answer.category.casefold())
        if slug is not None:
            labelled[batch[answer.id].key] = Label(slug, min(max(answer.confidence, 0.0), 1.0))
    return labelled
```

`server/app/agents/transaction_labeler/__init__.py`:

```python
"""The transaction labeller (docs/product/features/categorisation.md)."""

from app.agents.transaction_labeler.labeler import (
    BATCH_SIZE,
    FALLBACK_CATEGORY,
    FALLBACK_CONFIDENCE,
    KNOWN_CONFIDENCE,
    MAX_CONCURRENT_BATCHES,
    Label,
    LabelResult,
    MerchantToLabel,
    label,
)

__all__ = [
    "BATCH_SIZE",
    "FALLBACK_CATEGORY",
    "FALLBACK_CONFIDENCE",
    "KNOWN_CONFIDENCE",
    "MAX_CONCURRENT_BATCHES",
    "Label",
    "LabelResult",
    "MerchantToLabel",
    "label",
]
```

If ruff flags the broad `except Exception`, keep it and add `# noqa: BLE001` with the comment already on the line: a batch failing for any reason (no API key raises `openai.OpenAIError` outside the service's fallback) must fall back, not crash the import.

- [ ] **Step 5: Run the tests to see them pass**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/transaction_labeler -v && uv run lint-imports`
Expected: all PASS; every contract KEPT (the agent imports no module).

- [ ] **Step 6: Commit**

```bash
git add server/app/agents/transaction_labeler server/tests/unit/agents/transaction_labeler
git commit -m "CSV import: the labeller agent — known merchants, batched model calls, fallbacks"
```

---

### Task 7: The column-mapping agent

**Files:**
- Create: `server/app/agents/csv_mapping/__init__.py`, `mapper.py`, `prompts/v1.md`
- Create: `server/tests/unit/agents/csv_mapping/__init__.py` (empty), `test_mapper.py`

**Interfaces:**
- Consumes: `structured_llm`, `ask_json`, `create_trace_config` (Task 5).
- Produces, from `app.agents.csv_mapping`: `ColumnHint(name: str, empty_rate: float, date_format: Optional[str], amount_style: Optional[str])`; `async propose_mapping(columns: list[ColumnHint], samples: list[list[str]], *, user_id: uuid.UUID, upload_id: uuid.UUID) -> Optional[dict[str, str]]` — the model's raw `{column: field}` or `None` on any failure. The import validates it (Task 8's `clean_proposal`). `CELL_LIMIT = 100`.

- [ ] **Step 1: Write the failing test**

`server/tests/unit/agents/csv_mapping/test_mapper.py`:

```python
"""The column-mapping agent (spec §6.2). The model is stubbed."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from uuid_utils.compat import uuid7

from app.agents.csv_mapping import CELL_LIMIT, ColumnHint, propose_mapping
from app.integrations.llm import LLMAPIError

pytestmark = pytest.mark.unit

IDS = {"user_id": uuid7(), "upload_id": uuid7()}
COLUMNS = [ColumnHint("Buchungsdatum", 0.0, "dd.mm.yyyy", None), ColumnHint("Betrag", 0.0, None, "1.234,56")]


@pytest.fixture(autouse=True)
def no_langfuse():
    with patch("app.agents.csv_mapping.mapper.create_trace_config", return_value={}):
        yield


async def test_returns_the_models_mapping_and_sends_hints_and_capped_samples():
    seen = {}

    async def fake(service, system, user, shape, config):
        seen.update(json.loads(user))
        return shape.model_validate({"Buchungsdatum": "date", "Betrag": "amount"})

    with patch("app.agents.csv_mapping.mapper.ask_json", fake):
        mapping = await propose_mapping(COLUMNS, [["15.01.2026", "x" * 500]], **IDS)
    assert mapping == {"Buchungsdatum": "date", "Betrag": "amount"}
    assert seen["columns"][0] == {"name": "Buchungsdatum", "empty_rate": 0.0, "date_format": "dd.mm.yyyy", "amount_style": None}
    assert len(seen["sample_rows"][0][1]) == CELL_LIMIT


@pytest.mark.parametrize("error", [LLMAPIError("down"), ValueError("bad json"), RuntimeError("no key")])
async def test_any_failure_is_none(error):
    with patch("app.agents.csv_mapping.mapper.ask_json", AsyncMock(side_effect=error)):
        assert await propose_mapping(COLUMNS, [], **IDS) is None
```

- [ ] **Step 2: Run it to see it fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/csv_mapping -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`server/app/agents/csv_mapping/prompts/v1.md` (not passed through `str.format`, so braces are literal):

```markdown
You map the columns of a bank's CSV export to the fields of a personal finance app.

Fields:
- date: the day the transaction happened (the booking date over the value date when both exist)
- merchant: who was paid, or who paid (payee, recipient, counterparty)
- amount: the signed amount of money
- description: free text about the transaction (reference, purpose)
- original_category: the bank's own category for the transaction
- recurring: a column saying whether the transaction recurs
- ignore: anything else

date, merchant and amount should each be mapped to one column. Every field except ignore may be used at most once.

The user message is JSON: each column's name, how often it is empty, the date format or amount style detected in it (null when none), and up to three sample rows in column order.

Return ONLY a JSON object mapping every column name to one field, for example:
{"Buchungsdatum": "date", "Empfaenger": "merchant", "Betrag": "amount", "Notiz": "ignore"}
```

`server/app/agents/csv_mapping/mapper.py`:

```python
"""The column-mapping agent: proposes which CSV column is which field (docs/product/features/csv-import.md §3)."""

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pydantic import RootModel

from app.agents.shared.observability import create_trace_config
from app.agents.shared.structured import ask_json, structured_llm
from app.core.logging import logger

CELL_LIMIT = 100
_PROMPT = (Path(__file__).parent / "prompts" / "v1.md").read_text(encoding="utf-8")


@dataclass(frozen=True)
class ColumnHint:
    """What the model is told about a column besides its samples."""

    name: str
    empty_rate: float
    date_format: Optional[str]
    amount_style: Optional[str]


class _Mapping(RootModel[dict[str, str]]):
    pass


async def propose_mapping(
    columns: list[ColumnHint], samples: list[list[str]], *, user_id: uuid.UUID, upload_id: uuid.UUID
) -> Optional[dict[str, str]]:
    """The model's {column: field}, checked for shape only, or None when the call fails for any reason."""
    payload = {
        "columns": [
            {
                "name": c.name,
                "empty_rate": round(c.empty_rate, 2),
                "date_format": c.date_format,
                "amount_style": c.amount_style,
            }
            for c in columns
        ],
        "sample_rows": [[cell[:CELL_LIMIT] for cell in row] for row in samples],
    }
    try:
        answer = await ask_json(
            structured_llm,
            _PROMPT,
            json.dumps(payload, ensure_ascii=False),
            _Mapping,
            create_trace_config(user_id, upload_id, "csv_mapping"),
        )
    except Exception as e:  # the review then asks the user to map by hand; an upload never fails on this
        logger.warning("csv_mapping_failed", error_type=type(e).__name__)
        return None
    return answer.root
```

`server/app/agents/csv_mapping/__init__.py`:

```python
"""The CSV column-mapping agent."""

from app.agents.csv_mapping.mapper import CELL_LIMIT, ColumnHint, propose_mapping

__all__ = ["CELL_LIMIT", "ColumnHint", "propose_mapping"]
```

- [ ] **Step 4: Run it to see it pass**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/agents/csv_mapping -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server/app/agents/csv_mapping server/tests/unit/agents/csv_mapping
git commit -m "CSV import: the column-mapping agent"
```

---
### Task 8: The import's domain — reading a bank's CSV

**Files:**
- Create: `server/app/modules/transaction/imports/domain.py`
- Modify: `server/pyproject.toml` (R9's second pattern)
- Create: `server/tests/unit/modules/transaction/imports/test_domain.py`

**Interfaces:**
- Produces, in `app.modules.transaction.imports.domain`: constants `MAX_BYTES = 5 * 1024 * 1024`, `MAX_ROWS = 3000`, `IGNORE = "ignore"`, `FIELDS` (the seven field names), `REQUIRED`, `COMMA_DECIMAL = "1.234,56"`, `DOT_DECIMAL = "1,234.56"`; `class CsvFormatError(ValueError)` with `.reason: str` and `.message: str`; `class MappingProblem` (frozen dataclass `reason: str`, `message: str`); dataclasses `CsvRow(number: int, cells: list[str])`, `ParsedCsv(columns: list[str], rows: list[CsvRow])`, `ColumnProfile(name, empty_rate, date_format, amount_style)`, `ImportRow(number, date, merchant, amount, description, original_category, is_recurring: Optional[bool])`, `Rejection(number, reason)`; functions `decode(raw: bytes) -> str`, `sniff_delimiter(text) -> str`, `parse(text) -> ParsedCsv`, `column_key(columns) -> str`, `parse_date(value, date_format) -> Optional[dt.date]`, `parse_amount(value, style) -> Optional[Decimal]`, `parse_recurring(value) -> Optional[bool]`, `profile_columns(parsed) -> list[ColumnProfile]`, `pick_samples(parsed, size=3) -> list[CsvRow]`, `clean_proposal(columns, proposal) -> dict[str, str]`, `mapping_problem(columns, mapping) -> Optional[MappingProblem]`, `read_rows(parsed, mapping) -> tuple[list[ImportRow], list[Rejection]]`.

- [ ] **Step 1: Write the failing tests**

`server/tests/unit/modules/transaction/imports/test_domain.py`:

```python
"""Reading a bank's CSV (spec §5.2, §5.4). Pure: no database, no model."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.transaction.imports.domain import (
    COMMA_DECIMAL,
    DOT_DECIMAL,
    MAX_ROWS,
    CsvFormatError,
    clean_proposal,
    column_key,
    decode,
    mapping_problem,
    parse,
    parse_amount,
    parse_date,
    parse_recurring,
    pick_samples,
    profile_columns,
    read_rows,
    sniff_delimiter,
)

pytestmark = pytest.mark.unit

GERMAN = (
    "Buchungsdatum;Empfaenger;Verwendungszweck;Betrag\n"
    "15.01.2026;REWE Markt GmbH;Einkauf;-1.234,56\n"
    "16.01.2026;Arbeitgeber;Gehalt;2.450,00\n"
    "17.01.2026;Kiosk;;12,50-\n"
)
N26 = '"Date","Payee","Amount (EUR)"\n"2026-01-15","Spotify","-9.99"\n"2026-01-16","Employer","1,204.00"\n'
GERMAN_MAPPING = {"Buchungsdatum": "date", "Empfaenger": "merchant", "Verwendungszweck": "description", "Betrag": "amount"}


class TestDecode:
    def test_utf8_and_its_bom(self):
        assert decode("Späti".encode()) == "Späti"
        assert decode("\ufeffDate".encode()) == "Date"

    def test_windows_1252_when_not_utf8(self):
        assert decode("Empfänger".encode("cp1252")) == "Empfänger"


class TestParse:
    def test_semicolon_wins_over_a_decimal_comma(self):
        assert sniff_delimiter(GERMAN) == ";"

    @pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
    def test_each_delimiter(self, delimiter):
        assert sniff_delimiter(f"a{delimiter}b\n1{delimiter}2\n") == delimiter

    def test_header_and_stripped_cells(self):
        parsed = parse(N26)
        assert parsed.columns == ["Date", "Payee", "Amount (EUR)"]
        assert [r.cells for r in parsed.rows] == [["2026-01-15", "Spotify", "-9.99"], ["2026-01-16", "Employer", "1,204.00"]]
        assert [r.number for r in parsed.rows] == [2, 3]

    def test_preamble_and_trailing_delimiter(self):
        text = "Kontonummer:;DE12 3456;\nZeitraum:;Januar;\n\nDatum;Empfaenger;Betrag;\n15.01.2026;REWE;-3,00;\n\n16.01.2026;Lidl;-4,00;\n"
        parsed = parse(text)
        assert parsed.columns == ["Datum", "Empfaenger", "Betrag"]
        assert [r.number for r in parsed.rows] == [5, 7]
        assert parsed.rows[0].cells == ["15.01.2026", "REWE", "-3,00"]

    def test_short_rows_are_padded(self):
        assert parse("a,b,c\n1,2\n1,2,3\n").rows[0].cells == ["1", "2", ""]

    @pytest.mark.parametrize(
        ("text", "reason"),
        [
            ("", "empty"),
            ("\n\n", "empty"),
            ("justonecolumn\n1\n", "no_header"),
            ("a,,c\n1,2,3\n", "unnamed_column"),
            ("Betrag,betrag\n1,2\n", "duplicate_column"),
            ("a,b\n", "no_rows"),
        ],
    )
    def test_refusals(self, text, reason):
        with pytest.raises(CsvFormatError) as caught:
            parse(text)
        assert caught.value.reason == reason

    def test_too_many_rows(self):
        with pytest.raises(CsvFormatError) as caught:
            parse("a,b\n" + "1,2\n" * (MAX_ROWS + 1))
        assert caught.value.reason == "too_many_rows"
        parse("a,b\n" + "1,2\n" * MAX_ROWS)  # the limit itself is fine


class TestValues:
    @pytest.mark.parametrize(
        ("value", "style", "amount"),
        [
            ("-1.234,56", COMMA_DECIMAL, "-1234.56"),
            ("12,50-", COMMA_DECIMAL, "-12.50"),
            ("€ 1.204,00", COMMA_DECIMAL, "1204.00"),
            ("+3,5", COMMA_DECIMAL, "3.50"),
            ("1,234.56", DOT_DECIMAL, "1234.56"),
            ("-9.99 EUR", DOT_DECIMAL, "-9.99"),
            ("1,234", DOT_DECIMAL, "1234.00"),
            ("12.505", DOT_DECIMAL, "12.51"),
        ],
    )
    def test_amounts(self, value, style, amount):
        assert parse_amount(value, style) == Decimal(amount)

    @pytest.mark.parametrize(
        ("value", "style"),
        [("15.01.2026", COMMA_DECIMAL), ("12,50", DOT_DECIMAL), ("abc", DOT_DECIMAL), ("", DOT_DECIMAL), ("1e5", DOT_DECIMAL), ("99999999999", DOT_DECIMAL)],
    )
    def test_unreadable_amounts(self, value, style):
        assert parse_amount(value, style) is None

    @pytest.mark.parametrize(
        ("value", "fmt", "day"),
        [
            ("2026-01-15", "%Y-%m-%d", dt.date(2026, 1, 15)),
            ("2026-01-15T23:30:00+02:00", "iso", dt.date(2026, 1, 15)),
            ("15.01.2026", "%d.%m.%Y", dt.date(2026, 1, 15)),
            ("15.01.26", "%d.%m.%y", dt.date(2026, 1, 15)),
            ("01/15/2026", "%m/%d/%Y", dt.date(2026, 1, 15)),
        ],
    )
    def test_dates(self, value, fmt, day):
        assert parse_date(value, fmt) == day

    def test_an_impossible_date(self):
        assert parse_date("31.02.2026", "%d.%m.%Y") is None

    @pytest.mark.parametrize(
        ("value", "expected"),
        [("x", True), ("Ja", True), ("sì", True), ("1", True), ("nein", False), ("FALSE", False), ("", None), ("monthly", None)],
    )
    def test_recurring_cells(self, value, expected):
        assert parse_recurring(value) is expected


class TestProfiles:
    def test_formats_are_labelled(self):
        profiles = {p.name: p for p in profile_columns(parse(GERMAN))}
        assert profiles["Buchungsdatum"].date_format == "dd.mm.yyyy"
        assert profiles["Buchungsdatum"].amount_style is None
        assert profiles["Betrag"].amount_style == COMMA_DECIMAL
        assert profiles["Empfaenger"].date_format is None and profiles["Empfaenger"].amount_style is None
        assert profiles["Verwendungszweck"].empty_rate == pytest.approx(1 / 3)

    def test_an_ambiguous_date_goes_day_first(self):
        profiles = profile_columns(parse("d,m\n01/02/2026,x\n03/04/2026,y\n"))
        assert profiles[0].date_format == "dd/mm/yyyy"

    def test_samples_cover_the_most_columns_in_file_order(self):
        parsed = parse("a,b,c\n1,,\n2,,\n,5,\n,,6\n7,8,9\n")
        assert [r.number for r in pick_samples(parsed)] == [2, 3, 6]

    def test_column_key_ignores_order_case_and_spacing(self):
        assert column_key(["Betrag", " Datum"]) == column_key(["datum", "BETRAG "])
        assert column_key(["Betrag"]) != column_key(["Betrag", "Datum"])


class TestMapping:
    def test_a_proposal_is_made_valid(self):
        columns = ["A", "B", "C", "D"]
        cleaned = clean_proposal(columns, {"A": "date", "B": "date", "C": "nonsense", "Z": "amount"})
        assert cleaned == {"A": "date", "B": "ignore", "C": "ignore", "D": "ignore"}

    @pytest.mark.parametrize(
        ("mapping", "reason"),
        [
            ({"Nope": "date"}, "unknown_column"),
            ({"Buchungsdatum": "when"}, "unknown_field"),
            ({"Buchungsdatum": "date", "Empfaenger": "date"}, "field_twice"),
            ({"Buchungsdatum": "date", "Empfaenger": "merchant"}, "missing_required"),
        ],
    )
    def test_problems(self, mapping, reason):
        assert mapping_problem(parse(GERMAN).columns, mapping).reason == reason

    def test_a_good_mapping_has_no_problem(self):
        assert mapping_problem(parse(GERMAN).columns, GERMAN_MAPPING) is None


class TestReadRows:
    def test_rows_and_rejections_in_file_order(self):
        text = GERMAN + "31.02.2026;Bad;;-1,00\n18.01.2026;;;-3,00\n19.01.2026;Bar;;abc\n"
        rows, rejected = read_rows(parse(text), GERMAN_MAPPING)
        assert [(r.number, r.date, r.merchant, r.amount, r.description) for r in rows] == [
            (2, dt.date(2026, 1, 15), "REWE Markt GmbH", Decimal("-1234.56"), "Einkauf"),
            (3, dt.date(2026, 1, 16), "Arbeitgeber", Decimal("2450.00"), "Gehalt"),
            (4, dt.date(2026, 1, 17), "Kiosk", Decimal("-12.50"), None),
        ]
        assert [(r.number, r.reason) for r in rejected] == [
            (5, "unreadable date “31.02.2026”"),
            (6, "no merchant"),
            (7, "unreadable amount “abc”"),
        ]

    def test_recurring_is_none_unless_mapped(self):
        rows, _ = read_rows(parse(GERMAN), GERMAN_MAPPING)
        assert {r.is_recurring for r in rows} == {None}
        rows, _ = read_rows(parse("d,m,a,r\n2026-01-01,X,1,x\n2026-01-02,Y,1,\n"), {"d": "date", "m": "merchant", "a": "amount", "r": "recurring"})
        assert [r.is_recurring for r in rows] == [True, None]

    def test_long_text_is_cut_to_the_column_sizes(self):
        rows, _ = read_rows(parse(f"d,m,a\n2026-01-01,{'m' * 300},1\n"), {"d": "date", "m": "merchant", "a": "amount"})
        assert len(rows[0].merchant) == 255
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/transaction/imports/test_domain.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

`server/app/modules/transaction/imports/domain.py`:

```python
"""The import's rules: reading a bank's CSV and the values in it (spec §5.2, §5.4).

Pure: no ORM and no framework (R9). Messages on CsvFormatError and MappingProblem
are for logs and the API's message field; the web words each `reason` itself.
"""

import csv
import datetime as dt
import hashlib
import io
import re
from collections import Counter
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 3000
SAMPLE_SIZE = 3
# A column is labelled a date or an amount column when this share of its non-empty cells parse.
FORMAT_SHARE = 0.8

IGNORE = "ignore"
FIELDS = ("date", "merchant", "amount", "description", "original_category", "recurring", IGNORE)
REQUIRED = ("date", "merchant", "amount")

COMMA_DECIMAL = "1.234,56"
DOT_DECIMAL = "1,234.56"
ISO = "iso"
# strptime format (or ISO) → the label the review shows. Order breaks ties: day-first before month-first.
DATE_FORMATS: dict[str, str] = {
    "%Y-%m-%d": "yyyy-mm-dd",
    ISO: "yyyy-mm-dd hh:mm",
    "%d.%m.%Y": "dd.mm.yyyy",
    "%d.%m.%y": "dd.mm.yy",
    "%d/%m/%Y": "dd/mm/yyyy",
    "%m/%d/%Y": "mm/dd/yyyy",
    "%Y/%m/%d": "yyyy/mm/dd",
    "%d-%m-%Y": "dd-mm-yyyy",
}

_DELIMITERS = ",;\t|"
_CENT = Decimal("0.01")
_MAX_AMOUNT = Decimal("1e10")  # NUMERIC(12,2)
_CURRENCY = re.compile(r"€|(?i:\beur\b)")
_AMOUNT_PATTERNS = {
    COMMA_DECIMAL: (re.compile(r"^(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$"), ".", ","),
    DOT_DECIMAL: (re.compile(r"^(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$"), ",", "."),
}
_TRUE = frozenset({"true", "yes", "ja", "si", "sì", "1", "x"})
_FALSE = frozenset({"false", "no", "nein", "0"})
_SHOWN = 40


class CsvFormatError(ValueError):
    """The file cannot be read as a bank export."""

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class MappingProblem:
    """Why a confirmed mapping cannot be used."""

    reason: str
    message: str


@dataclass(frozen=True)
class CsvRow:
    """A data line: its line number in the file and its cells, stripped, one per column."""

    number: int
    cells: list[str]


@dataclass(frozen=True)
class ParsedCsv:
    """A file read into its header and data rows."""

    columns: list[str]
    rows: list[CsvRow]


@dataclass(frozen=True)
class ColumnProfile:
    """What the review shows about a column."""

    name: str
    empty_rate: float
    date_format: Optional[str]
    amount_style: Optional[str]


@dataclass(frozen=True)
class ImportRow:
    """A row to save, read through a confirmed mapping. is_recurring None leaves it to the rule."""

    number: int
    date: dt.date
    merchant: str
    amount: Decimal
    description: Optional[str]
    original_category: Optional[str]
    is_recurring: Optional[bool]


@dataclass(frozen=True)
class Rejection:
    """A row left out, and why — shown to the user."""

    number: int
    reason: str


def decode(raw: bytes) -> str:
    """UTF-8 (a BOM dropped), else Windows-1252, which reads any byte string."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _widths(lines: list[str], delimiter: str) -> list[int]:
    return [len(row) for row in csv.reader(lines, delimiter=delimiter) if any(c.strip() for c in row)]


def sniff_delimiter(text: str) -> str:
    """The delimiter that splits the most lines into one common number (at least two) of fields.

    Not csv.Sniffer: on `15.01.2026;REWE;-12,50` both `;` and `,` occur once a
    line, and the Sniffer then prefers the comma.
    """
    lines = text.splitlines()[:50]
    best, best_score = ",", (0.0, 0)
    for delimiter in _DELIMITERS:
        widths = _widths(lines, delimiter)
        if not widths:
            continue
        width, count = Counter(widths).most_common(1)[0]
        score = (count / len(widths), width)
        if width >= 2 and score > best_score:
            best, best_score = delimiter, score
    return best


def parse(text: str) -> ParsedCsv:
    """Read a file into a header and rows, or raise CsvFormatError.

    Lines above the header (a bank's account summary) are skipped: the header is
    the first line with as many fields as most lines have. Blank lines are
    skipped; short rows are padded. A trailing column with no name and no
    values — a delimiter ending every line — is dropped.
    """
    reader = csv.reader(io.StringIO(text), delimiter=sniff_delimiter(text))
    records = [(reader.line_num, row) for row in reader if any(c.strip() for c in row)]
    if not records:
        raise CsvFormatError("empty", "The file is empty.")
    width = Counter(len(row) for _, row in records).most_common(1)[0][0]
    if width < 2:
        raise CsvFormatError("no_header", "The file needs a header row and at least two columns.")
    start = next(i for i, (_, row) in enumerate(records) if len(row) == width)
    header = [c.strip() for c in records[start][1]]
    rows = [CsvRow(n, [c.strip() for c in (row + [""] * width)[:width]]) for n, row in records[start + 1 :]]
    if not header[-1] and all(not r.cells[-1] for r in rows):
        header.pop()
        rows = [CsvRow(r.number, r.cells[:-1]) for r in rows]
    if any(not name for name in header):
        raise CsvFormatError("unnamed_column", "Every column needs a name in the header row.")
    folded = [name.casefold() for name in header]
    if len(set(folded)) != len(folded):
        raise CsvFormatError("duplicate_column", "Two columns have the same name.")
    if not rows:
        raise CsvFormatError("no_rows", "The file has a header but no rows.")
    if len(rows) > MAX_ROWS:
        raise CsvFormatError("too_many_rows", f"The file has more than {MAX_ROWS} rows.")
    return ParsedCsv(columns=header, rows=rows)


def column_key(columns: list[str]) -> str:
    """A remembered mapping's key: sha256 of the names stripped, casefolded, sorted, joined by U+001F."""
    names = sorted(name.strip().casefold() for name in columns)
    return hashlib.sha256("\x1f".join(names).encode("utf-8")).hexdigest()


def parse_date(value: str, date_format: str) -> Optional[dt.date]:
    """The day `value` names in `date_format`, or None. A date-time keeps its date as written."""
    try:
        if date_format == ISO:
            return dt.datetime.fromisoformat(value).date()
        return dt.datetime.strptime(value, date_format).date()
    except ValueError:
        return None


def parse_amount(value: str, style: str) -> Optional[Decimal]:
    """`value` as a signed Decimal at two places in `style`, or None.

    Spaces, `€` and `EUR` are dropped; a trailing minus (`12,50-`) counts as a leading one.
    """
    text = _CURRENCY.sub("", value).replace("\u00a0", "").replace(" ", "")
    negative = False
    if text.endswith("-"):
        negative, text = True, text[:-1]
    elif text[:1] in ("+", "-"):
        negative, text = text[0] == "-", text[1:]
    pattern, thousands, decimal = _AMOUNT_PATTERNS[style]
    if not pattern.match(text):
        return None
    try:
        amount = Decimal(text.replace(thousands, "").replace(decimal, ".")).quantize(_CENT, ROUND_HALF_UP)
    except InvalidOperation:
        return None
    if amount >= _MAX_AMOUNT:
        return None
    return -amount if negative else amount


def parse_recurring(value: str) -> Optional[bool]:
    """A recurring cell as the user's assertion, or None — blank or unrecognised — to let the rule decide."""
    folded = value.strip().casefold()
    if folded in _TRUE:
        return True
    if folded in _FALSE:
        return False
    return None


def best_date_format(values: list[str]) -> tuple[str, float]:
    """The format that parses the most non-empty values, and the share it parses. Ties go day-first."""
    filled = [v for v in values if v]
    order = list(DATE_FORMATS)
    if not filled:
        return order[0], 0.0
    best = max(order, key=lambda f: (sum(parse_date(v, f) is not None for v in filled), -order.index(f)))
    return best, sum(parse_date(v, best) is not None for v in filled) / len(filled)


def best_amount_style(values: list[str]) -> tuple[str, float]:
    """The style that parses the most non-empty values, and the share. A tie is the comma style if any value has a comma."""
    filled = [v for v in values if v]
    if not filled:
        return DOT_DECIMAL, 0.0
    counts = {style: sum(parse_amount(v, style) is not None for v in filled) for style in (COMMA_DECIMAL, DOT_DECIMAL)}
    if counts[COMMA_DECIMAL] == counts[DOT_DECIMAL]:
        style = COMMA_DECIMAL if any("," in v for v in filled) else DOT_DECIMAL
    else:
        style = max(counts, key=counts.__getitem__)
    return style, counts[style] / len(filled)


def profile_columns(parsed: ParsedCsv) -> list[ColumnProfile]:
    """Each column's empty rate, and its date format or amount style when one fits most of its cells."""
    profiles = []
    for index, name in enumerate(parsed.columns):
        values = [row.cells[index] for row in parsed.rows]
        date_format, date_share = best_date_format(values)
        style, amount_share = best_amount_style(values)
        is_date = date_share >= FORMAT_SHARE
        profiles.append(
            ColumnProfile(
                name=name,
                empty_rate=sum(not v for v in values) / len(values),
                date_format=DATE_FORMATS[date_format] if is_date else None,
                amount_style=style if not is_date and amount_share >= FORMAT_SHARE else None,
            )
        )
    return profiles


def pick_samples(parsed: ParsedCsv, size: int = SAMPLE_SIZE) -> list[CsvRow]:
    """Up to `size` rows covering as many non-empty columns as possible, returned in file order.

    Greedy: each pick covers the most columns no earlier pick filled, ties to
    the earliest row; slots left over take the next rows in file order.
    """
    chosen: list[int] = []
    covered: set[int] = set()
    for _ in range(size):
        best, gain = None, 0
        for i, row in enumerate(parsed.rows):
            if i in chosen:
                continue
            new = len({j for j, cell in enumerate(row.cells) if cell} - covered)
            if new > gain:
                best, gain = i, new
        if best is None:
            break
        chosen.append(best)
        covered |= {j for j, cell in enumerate(parsed.rows[best].cells) if cell}
    for i in range(len(parsed.rows)):
        if len(chosen) >= size:
            break
        if i not in chosen:
            chosen.append(i)
    return [parsed.rows[i] for i in sorted(chosen)]


def clean_proposal(columns: list[str], proposal: dict[str, str]) -> dict[str, str]:
    """A proposal made valid: every column present, known fields only, each field once (the first column keeps it)."""
    taken: set[str] = set()
    cleaned = {}
    for column in columns:
        field = proposal.get(column, IGNORE)
        if field not in FIELDS or (field != IGNORE and field in taken):
            field = IGNORE
        taken.add(field)
        cleaned[column] = field
    return cleaned


def mapping_problem(columns: list[str], mapping: dict[str, str]) -> Optional[MappingProblem]:
    """Why a confirmed mapping cannot be used, or None."""
    if set(mapping) - set(columns):
        return MappingProblem("unknown_column", "The mapping names a column the file does not have.")
    if any(field not in FIELDS for field in mapping.values()):
        return MappingProblem("unknown_field", "The mapping uses an unknown field.")
    used = [field for field in mapping.values() if field != IGNORE]
    if len(used) != len(set(used)):
        return MappingProblem("field_twice", "Each field can be mapped to one column only.")
    if any(field not in used for field in REQUIRED):
        return MappingProblem("missing_required", "Map a date, a merchant and an amount.")
    return None


def _shown(value: str) -> str:
    return value if len(value) <= _SHOWN else value[: _SHOWN - 1] + "…"


def read_rows(parsed: ParsedCsv, mapping: dict[str, str]) -> tuple[list[ImportRow], list[Rejection]]:
    """Every row through a valid mapping: the rows to save and the rows rejected, in file order.

    The date format and amount style are the best for the mapped column. A row
    is rejected for an unreadable date, an unreadable amount or an empty
    merchant, checked in that order. Text is cut to the column sizes.
    """
    index = {field: parsed.columns.index(column) for column, field in mapping.items() if field != IGNORE}

    def cell(row: CsvRow, field: str) -> str:
        return row.cells[index[field]] if field in index else ""

    date_format, _ = best_date_format([cell(r, "date") for r in parsed.rows])
    style, _ = best_amount_style([cell(r, "amount") for r in parsed.rows])
    rows: list[ImportRow] = []
    rejected: list[Rejection] = []
    for row in parsed.rows:
        raw_date, raw_amount, merchant = cell(row, "date"), cell(row, "amount"), cell(row, "merchant")
        date = parse_date(raw_date, date_format)
        if date is None:
            rejected.append(Rejection(row.number, f"unreadable date “{_shown(raw_date)}”"))
            continue
        amount = parse_amount(raw_amount, style)
        if amount is None:
            rejected.append(Rejection(row.number, f"unreadable amount “{_shown(raw_amount)}”"))
            continue
        if not merchant:
            rejected.append(Rejection(row.number, "no merchant"))
            continue
        rows.append(
            ImportRow(
                number=row.number,
                date=date,
                merchant=merchant[:255],
                amount=amount,
                description=cell(row, "description")[:1000] or None,
                original_category=cell(row, "original_category")[:255] or None,
                is_recurring=parse_recurring(cell(row, "recurring")) if "recurring" in index else None,
            )
        )
    return rows, rejected
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/modules/transaction/imports/test_domain.py -v`
Expected: all PASS.

- [ ] **Step 5: Widen R9 and report it**

In `server/pyproject.toml`, the R9 contract's `source_modules` becomes `["app.modules.*.domain", "app.modules.*.*.domain"]`. Run `cd server && uv run lint-imports`: every contract KEPT.

The block must end up word for word as sent to the orchestrator on 15 Oct (5a uses the same, so the merge is a one-sided take): name `R9: a domain slot imports neither the ORM nor the framework`, type `forbidden`, `source_modules = ["app.modules.*.domain", "app.modules.*.*.domain"]`, `forbidden_modules = ["sqlmodel", "sqlalchemy", "fastapi"]`, plus `include_external_packages = true` under `[tool.importlinter]`.

- [ ] **Step 6: Commit**

```bash
git add server/app/modules/transaction/imports/domain.py server/pyproject.toml server/tests/unit/modules/transaction/imports/test_domain.py
git commit -m "CSV import: reading a bank's CSV — delimiter, encoding, formats, samples, mapping rules"
```

---
### Task 9: Upload — `POST /transactions/imports`

**Files:**
- Create: `server/app/modules/transaction/imports/exceptions.py`, `imports/schemas.py`, `imports/router.py`
- Modify: `imports/service.py`, `imports/repository.py`, `imports/__init__.py`, `server/app/modules/transaction/__init__.py`, `server/app/api/v1/api.py`, `server/app/core/limiter.py`, `server/app/core/config.py`
- Create: `server/tests/unit/core/test_limiter.py`, `server/tests/unit/modules/transaction/imports/test_schemas.py`, `server/tests/integration/modules/transaction/imports/test_router.py`
- Regenerate: `server/openapi.json`, `web-app/packages/api-client/src/generated/` (`make gen-contract`)

**Interfaces:**
- Consumes: Task 8's domain; `propose_mapping`, `ColumnHint` (Task 7); `HeldUpload`, `MappingProfile` (Task 3).
- Produces: route `POST /api/v1/transactions/imports` (`uploadTransactionsCsv`, tag `transaction-imports`, 201 `ImportPreview`); schemas `ImportField` (StrEnum of the seven fields), `MappingSource` (StrEnum `remembered|proposed|none`), `ImportColumn`, `ImportPreview`, `ImportConfirm`, `ImportRejection`, `ImportResult`; exceptions `InvalidImportFileError` (422 `INVALID_IMPORT_FILE`), `InvalidImportMappingError` (422 `INVALID_IMPORT_MAPPING`), `ImportUploadNotFoundError` (404 `IMPORT_UPLOAD_NOT_FOUND`), `CategorisationUnavailableError` (503 `CATEGORISATION_UNAVAILABLE`), each 422 with `reason=` in its context; `import_repository.replace_upload / get_live_upload / get_profile`; `_release_connection(session)`; `user_or_ip_key(request) -> str`; `transaction.imports_router`.

- [ ] **Step 1: Write the failing tests**

`server/tests/unit/core/test_limiter.py`:

```python
"""The per-user rate-limit key."""

from unittest.mock import MagicMock

import pytest

from app.core.limiter import user_or_ip_key

pytestmark = pytest.mark.unit


def test_a_signed_in_caller_is_keyed_by_clerk_id():
    request = MagicMock()
    request.state.clerk_id = "user_123"
    assert user_or_ip_key(request) == "user:user_123"


def test_no_caller_falls_back_to_the_address():
    request = MagicMock()
    request.state.clerk_id = None
    request.client.host = "203.0.113.9"
    assert user_or_ip_key(request) == "203.0.113.9"
```

`server/tests/unit/modules/transaction/imports/test_schemas.py`:

```python
"""The API's field list and the domain's are one list."""

import pytest

from app.modules.transaction.imports.domain import FIELDS
from app.modules.transaction.imports.schemas import ImportField

pytestmark = pytest.mark.unit


def test_fields_agree():
    assert set(FIELDS) == {f.value for f in ImportField}
```

`server/tests/integration/modules/transaction/imports/test_router.py`:

```python
"""Import routes against a real database. The two agents are stubbed."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel import select

from app.core.limiter import limiter
from app.modules.transaction.imports.domain import column_key
from app.modules.transaction.imports.models import HeldUpload, MappingProfile

pytestmark = pytest.mark.integration

BASE = "/api/v1/transactions/imports"
GERMAN = (
    "Buchungsdatum;Empfaenger;Verwendungszweck;Betrag\n"
    "15.01.2026;REWE Markt GmbH;Einkauf;-1.234,56\n"
    "16.01.2026;Arbeitgeber;Gehalt;2.450,00\n"
)
GERMAN_MAPPING = {"Buchungsdatum": "date", "Empfaenger": "merchant", "Verwendungszweck": "description", "Betrag": "amount"}


@pytest.fixture(autouse=True)
def fresh_limits():
    """The limiter's memory outlives a test; 10 uploads a minute would trip across the file."""
    limiter.reset()


@pytest.fixture
def propose():
    with patch(
        "app.modules.transaction.imports.service.propose_mapping", new=AsyncMock(return_value=GERMAN_MAPPING)
    ) as stub:
        yield stub


async def upload(client, content: str | bytes, name: str = "konto.csv"):
    body = content.encode("utf-8") if isinstance(content, str) else content
    return await client.post(BASE, files={"file": (name, body, "text/csv")})


class TestUpload:
    async def test_unauthenticated_is_401(self, client):
        assert (await upload(client, GERMAN)).status_code == 401

    async def test_returns_the_preview(self, authenticated_client, propose):
        response = await upload(authenticated_client, GERMAN)
        assert response.status_code == 201
        body = response.json()
        assert uuid.UUID(body["upload_id"])
        assert (body["filename"], body["row_count"], body["mapping_source"]) == ("konto.csv", 2, "proposed")
        assert [(c["name"], c["proposed_field"]) for c in body["columns"]] == list(GERMAN_MAPPING.items())
        assert body["columns"][0]["date_format"] == "dd.mm.yyyy"
        assert body["columns"][3]["amount_style"] == "1.234,56"
        assert body["sample_rows"][0] == ["15.01.2026", "REWE Markt GmbH", "Einkauf", "-1.234,56"]
        hints = propose.await_args.args[0]
        assert [h.name for h in hints] == list(GERMAN_MAPPING)

    async def test_reads_windows_1252(self, authenticated_client, propose):
        content = GERMAN.replace("Empfaenger", "Empfänger").encode("cp1252")
        response = await upload(authenticated_client, content)
        assert response.status_code == 201
        assert response.json()["columns"][1]["name"] == "Empfänger"

    async def test_the_agent_failing_leaves_every_column_to_the_user(self, authenticated_client, propose):
        propose.return_value = None
        body = (await upload(authenticated_client, GERMAN)).json()
        assert body["mapping_source"] == "none"
        assert {c["proposed_field"] for c in body["columns"]} == {"ignore"}

    @pytest.mark.parametrize(
        ("name", "content", "reason"),
        [
            ("notes.txt", GERMAN, "not_csv"),
            ("konto.csv", "", "empty"),
            ("konto.csv", "a;b\n", "no_rows"),
            ("konto.csv", "Betrag;betrag\n1;2\n", "duplicate_column"),
        ],
    )
    async def test_refusals_carry_a_reason(self, authenticated_client, propose, name, content, reason):
        response = await upload(authenticated_client, content, name)
        assert response.status_code == 422
        assert response.json()["error"] == "INVALID_IMPORT_FILE"
        assert response.json()["details"] == {"reason": reason}

    async def test_more_than_5_mb_is_refused(self, authenticated_client, propose):
        response = await upload(authenticated_client, b"a,b\n" + b"1,2\n" * (1_400_000))
        assert response.status_code == 422
        assert response.json()["details"] == {"reason": "too_large"}

    async def test_an_uppercase_extension_is_fine(self, authenticated_client, propose):
        assert (await upload(authenticated_client, GERMAN, "KONTO.CSV")).status_code == 201

    async def test_a_new_upload_replaces_the_held_one(self, authenticated_client, propose, db_session, test_user):
        await upload(authenticated_client, GERMAN)
        second = (await upload(authenticated_client, GERMAN)).json()
        held = (await db_session.execute(select(HeldUpload.id).where(HeldUpload.user_id == test_user.id))).scalars().all()
        assert held == [uuid.UUID(second["upload_id"])]

    async def test_a_remembered_mapping_matches_headers_by_case_and_spacing(
        self, authenticated_client, propose, db_session, test_user
    ):
        db_session.add(
            MappingProfile(user_id=test_user.id, column_key=column_key(list(GERMAN_MAPPING)), mapping=GERMAN_MAPPING)
        )
        await db_session.flush()
        shouted = GERMAN.replace("Buchungsdatum;Empfaenger;Verwendungszweck;Betrag", "BUCHUNGSDATUM; empfaenger;VERWENDUNGSZWECK;Betrag ")
        body = (await upload(authenticated_client, shouted)).json()
        assert body["mapping_source"] == "remembered"
        assert [c["proposed_field"] for c in body["columns"]] == ["date", "merchant", "description", "amount"]
        propose.assert_not_awaited()
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/core/test_limiter.py tests/unit/modules/transaction/imports/test_schemas.py tests/integration/modules/transaction/imports/test_router.py -v`
Expected: ImportErrors; then 404s for the route.

- [ ] **Step 3: The rate-limit key and setting**

In `server/app/core/limiter.py`, add (import `Request` from `starlette.requests`):

```python
def user_or_ip_key(request: Request) -> str:
    """The signed-in caller's Clerk id, else the remote address: a per-user limit on authenticated routes.

    AuthMiddleware sets request.state.clerk_id before any route runs.
    """
    clerk_id = getattr(request.state, "clerk_id", None)
    return f"user:{clerk_id}" if clerk_id else get_remote_address(request)
```

Update the module docstring's last sentence to: "Rate limits are keyed by remote IP address, or by the caller with `user_or_ip_key`."

In `server/app/core/config.py`, `RateLimitEndpointSettings`, after `TRANSACTIONS`:

```python
    TRANSACTION_IMPORTS: List[str] = Field(default_factory=lambda: ["10 per minute"])
```

- [ ] **Step 4: Exceptions and schemas**

`server/app/modules/transaction/imports/exceptions.py`:

```python
"""The import's exceptions. A 422's context carries `reason`, a code the web words itself."""

from app.exceptions.base import NotFoundError, ServiceError, ValidationError


class InvalidImportFileError(ValidationError):
    """The upload is not a CSV this app can read."""

    error_code = "INVALID_IMPORT_FILE"


class InvalidImportMappingError(ValidationError):
    """The confirmed mapping cannot be used with the held file."""

    error_code = "INVALID_IMPORT_MAPPING"


class ImportUploadNotFoundError(NotFoundError):
    """No held upload with this id: never uploaded, expired, confirmed, replaced, or another user's."""

    error_code = "IMPORT_UPLOAD_NOT_FOUND"


class CategorisationUnavailableError(ServiceError):
    """Every labelling call failed; nothing was saved and the upload is still held."""

    status_code = 503
    error_code = "CATEGORISATION_UNAVAILABLE"
```

`server/app/modules/transaction/imports/schemas.py`:

```python
"""The import's request and response schemas."""

import uuid
from enum import StrEnum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ImportField(StrEnum):
    """What a CSV column can be mapped to. `ignore` drops the column."""

    DATE = "date"
    MERCHANT = "merchant"
    AMOUNT = "amount"
    DESCRIPTION = "description"
    ORIGINAL_CATEGORY = "original_category"
    RECURRING = "recurring"
    IGNORE = "ignore"


class MappingSource(StrEnum):
    """Where a preview's mapping came from."""

    REMEMBERED = "remembered"
    PROPOSED = "proposed"
    NONE = "none"


class ImportColumn(BaseModel):
    """One column of an uploaded file, as the review shows it."""

    name: str = Field(..., description="The column's name in the file's header")
    proposed_field: ImportField = Field(..., description="The field the app proposes for it")
    empty_rate: float = Field(..., description="The share of rows where it is empty, 0 to 1")
    date_format: Optional[str] = Field(None, description="The date format detected in it, such as dd.mm.yyyy")
    amount_style: Optional[str] = Field(None, description="The amount style detected in it: 1.234,56 or 1,234.56")


class ImportPreview(BaseModel):
    """An uploaded file held for 30 minutes, and its proposed mapping."""

    upload_id: uuid.UUID = Field(..., description="The held upload; confirm takes it")
    filename: str = Field(..., description="The uploaded file's name")
    row_count: int = Field(..., description="Data rows in the file")
    mapping_source: MappingSource = Field(..., description="remembered, proposed by AI, or none")
    columns: List[ImportColumn] = Field(..., description="Every column, in file order")
    sample_rows: List[List[str]] = Field(..., description="Up to three rows, cells in column order")


class ImportConfirm(BaseModel):
    """The mapping the user confirmed. A column left out is ignored."""

    mapping: Dict[str, ImportField] = Field(..., description="Column name to field")


class ImportRejection(BaseModel):
    """A row that was not imported."""

    row: int = Field(..., description="The row's line number in the file")
    reason: str = Field(..., description="Why it was left out")


class ImportResult(BaseModel):
    """What a confirm did."""

    imported: int = Field(..., description="Rows saved")
    skipped_duplicates: int = Field(..., description="Rows already held, skipped")
    uncategorised: int = Field(..., description="Rows saved under Miscellaneous because the labeller could not place them")
    rejected: List[ImportRejection] = Field(..., description="Rows left out, in file order")
```

- [ ] **Step 5: Repository and service**

Add to `ImportRepository` in `imports/repository.py` (imports: `from datetime import datetime`, `from typing import Optional`, `from sqlmodel import select`):

```python
    @staticmethod
    async def replace_upload(
        session: AsyncSession, user_id: uuid.UUID, content: str, expires_at: datetime
    ) -> HeldUpload:
        """Hold a new upload for this user, replacing any held before: one per user (D9)."""
        await session.execute(delete(HeldUpload).where(HeldUpload.user_id == user_id))
        upload = HeldUpload(user_id=user_id, content=content, expires_at=expires_at)
        session.add(upload)
        await session.flush()
        logger.info("csv_upload_held", user_id=user_id, upload_id=upload.id)
        return upload

    @staticmethod
    async def get_live_upload(
        session: AsyncSession, user_id: uuid.UUID, upload_id: uuid.UUID, now: datetime
    ) -> Optional[HeldUpload]:
        """This user's held upload if it has not expired, else None."""
        statement = select(HeldUpload).where(
            HeldUpload.id == upload_id, HeldUpload.user_id == user_id, HeldUpload.expires_at > now
        )
        return (await session.execute(statement)).scalar_one_or_none()

    @staticmethod
    async def get_profile(session: AsyncSession, user_id: uuid.UUID, column_key: str) -> Optional[MappingProfile]:
        """This user's remembered mapping for a column set, or None."""
        statement = select(MappingProfile).where(
            MappingProfile.user_id == user_id, MappingProfile.column_key == column_key
        )
        return (await session.execute(statement)).scalar_one_or_none()
```

Replace `imports/service.py` with:

```python
"""The import: upload a bank's CSV, review its mapping, confirm (docs/product/features/csv-import.md)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.csv_mapping import ColumnHint, propose_mapping
from app.core.logging import logger
from app.modules.transaction.imports.domain import (
    IGNORE,
    MAX_BYTES,
    ColumnProfile,
    CsvFormatError,
    CsvRow,
    ParsedCsv,
    clean_proposal,
    column_key,
    decode,
    parse,
    pick_samples,
    profile_columns,
)
from app.modules.transaction.imports.exceptions import InvalidImportFileError
from app.modules.transaction.imports.repository import import_repository
from app.modules.transaction.imports.schemas import ImportColumn, ImportPreview, MappingSource

UPLOAD_TTL = timedelta(minutes=30)


async def _release_connection(session: AsyncSession) -> None:
    """Commit what the request has done so far, handing the connection back before a model call.

    The import's model calls take seconds, and DbSession would otherwise hold its
    pool connection idle in a transaction through them (docs/TODO.md, "a model
    call holds the request's DB connection"). Nothing written before this point
    depends on what follows: at most a held upload, which must survive a failed
    model call anyway. The session opens a new transaction on its next use, and
    DbSession commits that one after the route as usual. The only commits outside
    DbSession in this app; keep it that way.
    """
    await session.commit()


class ImportService:
    """Orchestrates the import."""

    @staticmethod
    async def upload(session: AsyncSession, user_id: uuid.UUID, filename: str, raw: bytes) -> ImportPreview:
        """Read a file, hold it for 30 minutes, and propose a mapping. Raises InvalidImportFileError."""
        if not filename.casefold().endswith(".csv"):
            raise InvalidImportFileError("Only .csv files can be imported", reason="not_csv")
        if len(raw) > MAX_BYTES:
            raise InvalidImportFileError("The file is larger than 5 MB", reason="too_large")
        text = decode(raw)
        try:
            parsed = parse(text)
        except CsvFormatError as e:
            raise InvalidImportFileError(e.message, reason=e.reason) from e
        held = await import_repository.replace_upload(session, user_id, text, datetime.now(UTC) + UPLOAD_TTL)
        profiles = profile_columns(parsed)
        samples = pick_samples(parsed)
        mapping, source = await ImportService._propose(session, user_id, held.id, parsed, profiles, samples)
        logger.info("csv_upload_previewed", user_id=user_id, rows=len(parsed.rows), mapping_source=source.value)
        return ImportPreview(
            upload_id=held.id,
            filename=filename,
            row_count=len(parsed.rows),
            mapping_source=source,
            columns=[
                ImportColumn(
                    name=p.name,
                    proposed_field=mapping[p.name],
                    empty_rate=p.empty_rate,
                    date_format=p.date_format,
                    amount_style=p.amount_style,
                )
                for p in profiles
            ],
            sample_rows=[row.cells for row in samples],
        )

    @staticmethod
    async def _propose(
        session: AsyncSession,
        user_id: uuid.UUID,
        upload_id: uuid.UUID,
        parsed: ParsedCsv,
        profiles: list[ColumnProfile],
        samples: list[CsvRow],
    ) -> tuple[dict[str, str], MappingSource]:
        """The remembered mapping for these columns, else the agent's, else every column ignored."""
        remembered = await import_repository.get_profile(session, user_id, column_key(parsed.columns))
        if remembered is not None:
            # The profile is keyed by names folded; the new file may differ in case or spacing.
            folded = {name.strip().casefold(): field for name, field in remembered.mapping.items()}
            mapping = {c: folded.get(c.strip().casefold(), IGNORE) for c in parsed.columns}
            return clean_proposal(parsed.columns, mapping), MappingSource.REMEMBERED
        await _release_connection(session)
        proposal = await propose_mapping(
            [ColumnHint(p.name, p.empty_rate, p.date_format, p.amount_style) for p in profiles],
            [row.cells for row in samples],
            user_id=user_id,
            upload_id=upload_id,
        )
        if proposal is None:
            return {c: IGNORE for c in parsed.columns}, MappingSource.NONE
        return clean_proposal(parsed.columns, proposal), MappingSource.PROPOSED

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Erasure: the user's remembered mappings and held upload."""
        await import_repository.delete_all_for_user(session, user_id)


import_service = ImportService()
```

- [ ] **Step 6: The route and its wiring**

`server/app/modules/transaction/imports/router.py`:

```python
"""Import routes under /transactions/imports, tag "transaction-imports"."""

from fastapi import APIRouter, File, Request, UploadFile

from app.core.config import settings
from app.core.limiter import limiter, user_or_ip_key
from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.transaction.imports.domain import MAX_BYTES
from app.modules.transaction.imports.schemas import ImportPreview
from app.modules.transaction.imports.service import import_service

router = APIRouter(prefix="/transactions/imports", tags=["transaction-imports"])


@router.post(
    "",
    operation_id="uploadTransactionsCsv",
    response_model=ImportPreview,
    status_code=201,
    summary="Upload a CSV",
    description="Hold a bank's CSV export for 30 minutes and propose which column is which. A file this app "
    "cannot read is 422 INVALID_IMPORT_FILE, with details.reason. A new upload replaces the one held before.",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTION_IMPORTS[0], key_func=user_or_ip_key)
async def upload_transactions_csv(
    request: Request,
    db_session: DbSession,
    user: CurrentUser,
    file: UploadFile = File(..., description="The bank's CSV export, at most 5 MB"),
) -> ImportPreview:
    """Upload a CSV and get its proposed mapping."""
    raw = await file.read(MAX_BYTES + 1)  # one byte over is enough to refuse it
    return await import_service.upload(db_session, user.id, file.filename or "", raw)
```

`imports/__init__.py` becomes:

```python
"""CSV import, a feature sub-package of transaction (docs/architecture/server.md §2).

It calls the transaction core; the core never imports it.
"""

from app.modules.transaction.imports.router import router
from app.modules.transaction.imports.service import import_service

__all__ = ["import_service", "router"]

# @events.on is a module-level side effect: importing the package is what subscribes.
from app.modules.transaction.imports import handlers  # noqa: E402, F401
```

In `server/app/modules/transaction/__init__.py`, replace the Task 3 line `from app.modules.transaction import imports  # noqa: ...` with:

```python
# After the core, which it imports. Importing it also subscribes its handlers.
from app.modules.transaction.imports import router as imports_router  # noqa: E402
```

and add `"imports_router"` to `__all__`. In `server/app/api/v1/api.py`, include it before the transaction router:

```python
api_router.include_router(transaction.imports_router)
api_router.include_router(transaction.router)
```

- [ ] **Step 7: Run the tests, regenerate the contract**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/core tests/unit/modules/transaction tests/unit/api tests/unit/test_module_contracts.py tests/integration/modules/transaction -v`
Expected: all PASS, `test_openapi_contract.py` included.

Then from the repo root: `make gen-contract`. Check `git status`: `server/openapi.json` and `web-app/packages/api-client/src/generated/endpoints/transaction-imports/` changed. Then `make check` passes.

- [ ] **Step 8: Commit**

```bash
git add server web-app/packages/api-client/src/generated
git commit -m "CSV import: upload — read, hold for 30 minutes, propose or recall the mapping"
```

---

### Task 10: Confirm — `POST /transactions/imports/{upload_id}/confirm`

**Files:**
- Modify: `imports/service.py`, `imports/repository.py`, `imports/router.py`
- Modify: `server/tests/integration/modules/transaction/imports/test_router.py`
- Regenerate: the contract

**Interfaces:**
- Consumes: Task 8's `mapping_problem`, `read_rows`, `column_key`; `fingerprint`, `normalise_merchant`, `plan_count_matched` (Tasks 1–2); `transaction_service.count_active_by_fingerprints`, `import_many`, `TransactionImport`, `CATEGORIES` (Task 4); `label`, `MerchantToLabel` (Task 6).
- Produces: route `POST /api/v1/transactions/imports/{upload_id}/confirm` (`confirmTransactionsImport`, 200 `ImportResult`); `import_service.confirm(session, user_id, upload_id, mapping: dict[str, str]) -> ImportResult`; `import_repository.take_upload(session, user_id, upload_id) -> bool`, `put_profile(session, user_id, column_key, mapping) -> None`.

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/integration/modules/transaction/imports/test_router.py`, and add to its imports `from datetime import UTC, datetime, timedelta`, `from sqlalchemy import update`, `from app.agents.transaction_labeler import Label, LabelResult`, `from app.modules.transaction.models import Transaction`:

```python
def labelling(slug: str = "shopping", confidence: float = 0.8, fail: frozenset = frozenset(), all_failed: bool = False):
    """A stand-in for the labeller: every merchant gets `slug`, except the keys in `fail`."""

    async def fake(merchants, categories, *, user_id, upload_id):
        labels = {m.key: Label("miscellaneous", 0.3) if m.key in fail else Label(slug, confidence) for m in merchants}
        fallback = {m.key for m in merchants if m.key in fail}
        return LabelResult(labels=labels, fallback_keys=fallback, all_failed=all_failed)

    return fake


@pytest.fixture
def labeller():
    with patch("app.modules.transaction.imports.service.label", new=labelling()) as stub:
        yield stub


async def confirm(client, upload_id: str, mapping=GERMAN_MAPPING):
    return await client.post(f"{BASE}/{upload_id}/confirm", json={"mapping": mapping})


async def upload_id(client, content: str = GERMAN) -> str:
    response = await upload(client, content)
    assert response.status_code == 201, response.text
    return response.json()["upload_id"]


async def rows(db_session, user_id) -> list[Transaction]:
    statement = (
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.date)
        .execution_options(populate_existing=True)
    )
    return list((await db_session.execute(statement)).scalars())


class TestConfirm:
    async def test_unauthenticated_is_401(self, client):
        assert (await confirm(client, str(uuid.uuid4()))).status_code == 401

    async def test_imports_and_categorises(self, authenticated_client, propose, labeller, db_session, test_user):
        response = await confirm(authenticated_client, await upload_id(authenticated_client))
        assert response.status_code == 200
        assert response.json() == {"imported": 2, "skipped_duplicates": 0, "uncategorised": 0, "rejected": []}
        saved = await rows(db_session, test_user.id)
        assert [(t.merchant, str(t.amount), t.description, t.category, t.confidence) for t in saved] == [
            ("REWE Markt GmbH", "-1234.56", "Einkauf", "shopping", 0.8),
            ("Arbeitgeber", "2450.00", "Gehalt", "shopping", 0.8),
        ]
        assert [t.recurring_source for t in saved] == ["detected", "detected"]
        held = (await db_session.execute(select(HeldUpload).where(HeldUpload.user_id == test_user.id))).scalars().all()
        assert held == []
        profile = (await db_session.execute(select(MappingProfile))).scalars().one()
        assert profile.mapping == GERMAN_MAPPING

    async def test_rejected_rows_are_reported(self, authenticated_client, propose, labeller):
        content = GERMAN + "31.02.2026;Bad;;-1,00\n"
        response = await confirm(authenticated_client, await upload_id(authenticated_client, content))
        assert response.json()["imported"] == 2
        assert response.json()["rejected"] == [{"row": 4, "reason": "unreadable date “31.02.2026”"}]

    async def test_reimporting_the_same_file_imports_nothing(self, authenticated_client, propose, labeller):
        await confirm(authenticated_client, await upload_id(authenticated_client))
        response = await confirm(authenticated_client, await upload_id(authenticated_client))
        assert response.json() == {"imported": 0, "skipped_duplicates": 2, "uncategorised": 0, "rejected": []}

    async def test_twin_rows_in_one_file_both_import(self, authenticated_client, propose, labeller):
        content = GERMAN + "15.01.2026;REWE Markt GmbH;Einkauf;-1.234,56\n"
        response = await confirm(authenticated_client, await upload_id(authenticated_client, content))
        assert response.json()["imported"] == 3

    async def test_a_second_confirm_is_404(self, authenticated_client, propose, labeller, db_session, test_user):
        held = await upload_id(authenticated_client)
        assert (await confirm(authenticated_client, held)).status_code == 200
        second = await confirm(authenticated_client, held)
        assert second.status_code == 404
        assert second.json()["error"] == "IMPORT_UPLOAD_NOT_FOUND"
        assert len(await rows(db_session, test_user.id)) == 2

    async def test_an_expired_upload_is_404(self, authenticated_client, propose, labeller, db_session):
        held = await upload_id(authenticated_client)
        await db_session.execute(update(HeldUpload).values(expires_at=datetime.now(UTC) - timedelta(minutes=1)))
        assert (await confirm(authenticated_client, held)).status_code == 404

    async def test_another_users_upload_is_404(self, authenticated_client, labeller, db_session, other_user):
        theirs = HeldUpload(user_id=other_user.id, content=GERMAN, expires_at=datetime.now(UTC) + timedelta(minutes=30))
        db_session.add(theirs)
        await db_session.flush()
        assert (await confirm(authenticated_client, str(theirs.id))).status_code == 404

    async def test_a_replaced_upload_is_404(self, authenticated_client, propose, labeller):
        first = await upload_id(authenticated_client)
        second = await upload_id(authenticated_client)
        assert (await confirm(authenticated_client, first)).status_code == 404
        assert (await confirm(authenticated_client, second)).status_code == 200

    async def test_a_bad_mapping_is_422(self, authenticated_client, propose, labeller):
        mapping = {**GERMAN_MAPPING, "Betrag": "ignore"}
        response = await confirm(authenticated_client, await upload_id(authenticated_client), mapping)
        assert response.status_code == 422
        assert response.json()["error"] == "INVALID_IMPORT_MAPPING"
        assert response.json()["details"] == {"reason": "missing_required"}

    async def test_categorisation_down_is_503_and_keeps_the_upload(self, authenticated_client, propose, db_session, test_user):
        held = await upload_id(authenticated_client)
        with patch("app.modules.transaction.imports.service.label", new=labelling(all_failed=True)):
            response = await confirm(authenticated_client, held)
        assert response.status_code == 503
        assert response.json()["error"] == "CATEGORISATION_UNAVAILABLE"
        assert await rows(db_session, test_user.id) == []
        with patch("app.modules.transaction.imports.service.label", new=labelling()):
            assert (await confirm(authenticated_client, held)).json()["imported"] == 2

    async def test_a_partial_failure_is_counted(self, authenticated_client, propose, db_session, test_user):
        held = await upload_id(authenticated_client)
        with patch("app.modules.transaction.imports.service.label", new=labelling(fail=frozenset({"rewe markt"}))):
            response = await confirm(authenticated_client, held)
        assert response.json()["uncategorised"] == 1
        rewe = [t for t in await rows(db_session, test_user.id) if t.merchant_key == "rewe markt"][0]
        assert (rewe.category, rewe.confidence) == ("miscellaneous", 0.3)

    async def test_a_mapped_recurring_column_is_the_users(self, authenticated_client, propose, labeller, db_session, test_user):
        content = "Datum;Empfaenger;Betrag;Abo\n15.01.2026;Gym;-20,00;x\n16.01.2026;Kiosk;-2,00;\n"
        mapping = {"Datum": "date", "Empfaenger": "merchant", "Betrag": "amount", "Abo": "recurring"}
        await confirm(authenticated_client, await upload_id(authenticated_client, content), mapping)
        saved = {t.merchant: (t.is_recurring, t.recurring_source) for t in await rows(db_session, test_user.id)}
        assert saved == {"Gym": (True, "user"), "Kiosk": (False, "detected")}
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd server && APP_ENV=test uv run pytest tests/integration/modules/transaction/imports/test_router.py -v -k TestConfirm`
Expected: 404/405 from the missing route.

- [ ] **Step 3: Repository**

Add to `ImportRepository` (imports: `from sqlalchemy.dialects.postgresql import insert as pg_insert`, `from uuid_utils.compat import uuid7`, `from datetime import UTC`):

```python
    @staticmethod
    async def take_upload(session: AsyncSession, user_id: uuid.UUID, upload_id: uuid.UUID) -> bool:
        """Delete this user's held upload; False when it is already gone.

        The row lock is the double-confirm guard: a second confirm's DELETE waits
        for the first to commit, then finds nothing.
        """
        statement = (
            delete(HeldUpload)
            .where(HeldUpload.id == upload_id, HeldUpload.user_id == user_id)
            .returning(HeldUpload.id)
        )
        return (await session.execute(statement)).scalar_one_or_none() is not None

    @staticmethod
    async def put_profile(session: AsyncSession, user_id: uuid.UUID, column_key: str, mapping: dict[str, str]) -> None:
        """Remember a confirmed mapping for this column set, replacing the one remembered before."""
        now = datetime.now(UTC)
        statement = (
            pg_insert(MappingProfile)
            .values(id=uuid7(), user_id=user_id, column_key=column_key, mapping=mapping, created_at=now, updated_at=now)
            .on_conflict_do_update(
                constraint="uq_csv_mapping_profile_user_id_column_key", set_={"mapping": mapping, "updated_at": now}
            )
        )
        await session.execute(statement)
```

- [ ] **Step 4: Service**

Add to `imports/service.py` — imports:

```python
import statistics

from app.agents.transaction_labeler import MerchantToLabel, label
from app.modules.transaction.domain import fingerprint, normalise_merchant, plan_count_matched
from app.modules.transaction.imports.domain import ImportRow, mapping_problem, read_rows
from app.modules.transaction.imports.exceptions import (
    CategorisationUnavailableError,
    ImportUploadNotFoundError,
    InvalidImportMappingError,
)
from app.modules.transaction.imports.schemas import ImportRejection, ImportResult
from app.modules.transaction.schemas import CATEGORIES, TransactionImport
from app.modules.transaction.service import transaction_service
```

A module-level helper:

```python
def _merchants_to_label(rows: list[ImportRow]) -> list[MerchantToLabel]:
    """One item per merchant key: its first spelling, a description and bank category if any row has one, the median amount."""
    by_key: dict[str, list[ImportRow]] = {}
    for row in rows:
        by_key.setdefault(normalise_merchant(row.merchant), []).append(row)
    return [
        MerchantToLabel(
            key=key,
            merchant=group[0].merchant,
            description=next((r.description for r in group if r.description), None),
            original_category=next((r.original_category for r in group if r.original_category), None),
            amount=statistics.median_low([r.amount for r in group]),
        )
        for key, group in by_key.items()
    ]
```

And the method on `ImportService`:

```python
    @staticmethod
    async def confirm(
        session: AsyncSession, user_id: uuid.UUID, upload_id: uuid.UUID, mapping: dict[str, str]
    ) -> ImportResult:
        """Read the held file through the mapping, skip duplicates, label, save (spec §5.3).

        Raises ImportUploadNotFoundError, InvalidImportMappingError, or
        CategorisationUnavailableError — after which nothing is saved and the
        upload is still held.
        """
        held = await import_repository.get_live_upload(session, user_id, upload_id, datetime.now(UTC))
        if held is None:
            raise ImportUploadNotFoundError("Upload not found or expired", upload_id=str(upload_id))
        parsed = parse(held.content)
        problem = mapping_problem(parsed.columns, mapping)
        if problem is not None:
            raise InvalidImportMappingError(problem.message, reason=problem.reason)
        rows, rejected = read_rows(parsed, mapping)

        prints = [fingerprint(user_id, r.date, r.merchant, r.amount, r.description) for r in rows]
        existing = await transaction_service.count_active_by_fingerprints(session, user_id, prints)
        fresh = [row for row, keep in zip(rows, plan_count_matched(prints, existing)) if keep]

        await _release_connection(session)
        labelled = await label(_merchants_to_label(fresh), CATEGORIES, user_id=user_id, upload_id=upload_id)
        if labelled.all_failed:
            raise CategorisationUnavailableError("Categorisation is unavailable", upload_id=str(upload_id))

        if not await import_repository.take_upload(session, user_id, upload_id):
            raise ImportUploadNotFoundError("Upload already confirmed", upload_id=str(upload_id))
        keys = [normalise_merchant(row.merchant) for row in fresh]
        imported = await transaction_service.import_many(
            session,
            user_id,
            [
                TransactionImport(
                    date=row.date,
                    merchant=row.merchant,
                    amount=row.amount,
                    description=row.description,
                    original_category=row.original_category,
                    category=labelled.labels[key].category,
                    confidence=labelled.labels[key].confidence,
                    is_recurring=row.is_recurring,
                )
                for row, key in zip(fresh, keys)
            ],
        )
        await import_repository.put_profile(session, user_id, column_key(parsed.columns), mapping)
        result = ImportResult(
            imported=imported,
            skipped_duplicates=len(rows) - len(fresh),
            uncategorised=sum(key in labelled.fallback_keys for key in keys),
            rejected=[ImportRejection(row=r.number, reason=r.reason) for r in rejected],
        )
        logger.info(
            "transactions_import_confirmed",
            user_id=user_id,
            imported=result.imported,
            skipped=result.skipped_duplicates,
            uncategorised=result.uncategorised,
            rejected=len(result.rejected),
        )
        return result
```

The route passes `{column: field.value}`; `mapping_problem` and `read_rows` take plain strings.

- [ ] **Step 5: Route**

Add to `imports/router.py` (imports: `import uuid`; `ImportConfirm`, `ImportResult` from schemas):

```python
@router.post(
    "/{upload_id}/confirm",
    operation_id="confirmTransactionsImport",
    response_model=ImportResult,
    summary="Confirm an import",
    description="Read the held file through the confirmed mapping, skip duplicates, categorise every row and save. "
    "404 IMPORT_UPLOAD_NOT_FOUND for an expired, confirmed, replaced or another user's upload; 422 "
    "INVALID_IMPORT_MAPPING with details.reason; 503 CATEGORISATION_UNAVAILABLE keeps the upload for a retry.",
)
@limiter.limit(settings.rate_limits.endpoints.TRANSACTION_IMPORTS[0], key_func=user_or_ip_key)
async def confirm_transactions_import(
    request: Request, upload_id: uuid.UUID, body: ImportConfirm, db_session: DbSession, user: CurrentUser
) -> ImportResult:
    """Confirm a held upload's mapping and import it."""
    mapping = {column: field.value for column, field in body.mapping.items()}
    return await import_service.confirm(db_session, user.id, upload_id, mapping)
```

- [ ] **Step 6: Run the server suite and regenerate**

Run: `cd server && APP_ENV=test uv run pytest tests/ -v` — everything PASSES (unit and integration).
Then from the repo root: `make gen-contract`, then `make check`.

- [ ] **Step 7: Commit**

```bash
git add server web-app/packages/api-client/src/generated
git commit -m "CSV import: confirm — count-matched duplicates, labelling, save, remember the mapping"
```

---
### Task 11: Web — the mapping helpers, the error copy, the drop zone and the review

Load the `web-app-patterns` skill (`references/components.md`, `references/data-access.md`) and the `web-app-testing` skill before writing code.

**Files:**
- Create in `web-app/apps/web/src/components/transactions/`: `import-mapping.ts`, `import-mapping.test.ts`, `import-errors.ts`, `import-errors.test.ts`, `import-drop-zone.tsx`, `import-mapping-review.tsx`, `import-mapping-review.test.tsx`

**Interfaces:**
- Consumes: generated types `ImportPreview`, `ImportColumn`, `ImportField`, `MappingSource`, `ImportResult` from `@app/api-client/types` (Task 9–10's `make gen-contract`). Check the generated names in `web-app/packages/api-client/src/generated/types/` first; if orval named the enum differently, use its name throughout.
- Produces:
  - `import-mapping.ts`: `type Mapping = Record<string, ImportField>`; `FIELD_LABELS: Record<ImportField, string>`; `FIELD_ORDER: ImportField[]`; `initialMapping(preview) -> Mapping`; `assignField(mapping, column, field) -> Mapping`; `hasRequired(mapping) -> boolean`; `examples(preview, columnIndex) -> string[]`.
  - `import-errors.ts`: `MAX_FILE_BYTES`, `EXPIRED`, `UNAVAILABLE`, `checkFile(file: File) -> string | undefined`, `fileErrorMessage(error) -> string | undefined`, `confirmErrorMessage(error) -> string | undefined`, `isUploadInlineError(error) -> boolean`, `isConfirmInlineError(error) -> boolean`, `isExpired(error) -> boolean`.
  - `<ImportDropZone onFile pending error />`, `<ImportMappingReview preview mapping error retry onChange onBack onImport />`.

- [ ] **Step 1: Write the failing tests**

`import-mapping.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import type { ImportPreview } from "@app/api-client/types"
import { assignField, examples, hasRequired, initialMapping } from "./import-mapping"

const preview = {
  upload_id: "u",
  filename: "konto.csv",
  row_count: 2,
  mapping_source: "proposed",
  columns: [
    { name: "Datum", proposed_field: "date", empty_rate: 0, date_format: "dd.mm.yyyy", amount_style: null },
    { name: "Empfaenger", proposed_field: "merchant", empty_rate: 0, date_format: null, amount_style: null },
    { name: "Betrag", proposed_field: "amount", empty_rate: 0, date_format: null, amount_style: "1.234,56" },
    { name: "Notiz", proposed_field: "ignore", empty_rate: 0.5, date_format: null, amount_style: null },
  ],
  sample_rows: [
    ["15.01.2026", "REWE", "-3,00", ""],
    ["16.01.2026", "Lidl", "-4,00", "Snacks"],
  ],
} as ImportPreview

describe("import mapping", () => {
  it("starts from the proposal", () => {
    expect(initialMapping(preview)).toEqual({ Datum: "date", Empfaenger: "merchant", Betrag: "amount", Notiz: "ignore" })
  })

  it("moves a taken field, leaving the old column ignored", () => {
    const next = assignField(initialMapping(preview), "Notiz", "merchant")
    expect(next).toEqual({ Datum: "date", Empfaenger: "ignore", Betrag: "amount", Notiz: "merchant" })
  })

  it("lets several columns be ignored", () => {
    const next = assignField(initialMapping(preview), "Datum", "ignore")
    expect(next.Notiz).toBe("ignore")
    expect(next.Datum).toBe("ignore")
  })

  it("needs a date, a merchant and an amount", () => {
    expect(hasRequired(initialMapping(preview))).toBe(true)
    expect(hasRequired(assignField(initialMapping(preview), "Betrag", "ignore"))).toBe(false)
  })

  it("takes up to two non-empty examples", () => {
    expect(examples(preview, 3)).toEqual(["Snacks"])
    expect(examples(preview, 1)).toEqual(["REWE", "Lidl"])
  })
})
```

`import-errors.test.ts`:

```ts
import { describe, expect, it } from "vitest"
import { ApiError } from "@app/api-client"
import {
  EXPIRED,
  UNAVAILABLE,
  checkFile,
  confirmErrorMessage,
  fileErrorMessage,
  isConfirmInlineError,
  isExpired,
  isUploadInlineError,
} from "./import-errors"

const apiError = (status: number, reason?: string) =>
  new ApiError(`HTTP ${status}`, status, { error: "X", details: reason ? { reason } : {} }, null)

describe("import errors", () => {
  it("refuses a non-csv name or a file over 5 MB before sending", () => {
    expect(checkFile(new File(["a"], "notes.txt"))).toBe("Choose a .csv file.")
    expect(checkFile(new File(["a"], "KONTO.CSV"))).toBeUndefined()
    const big = new File(["a"], "big.csv")
    Object.defineProperty(big, "size", { value: 5 * 1024 * 1024 + 1 })
    expect(checkFile(big)).toBe("The file is larger than 5 MB.")
  })

  it("words a refused file by its reason, never the server's text", () => {
    expect(fileErrorMessage(apiError(422, "too_many_rows"))).toBe(
      "The file has more than 3,000 rows. Split it and import each part.",
    )
    expect(fileErrorMessage(apiError(422, "something_new"))).toBe("This file can't be read as a bank export.")
    expect(fileErrorMessage(apiError(500))).toBeUndefined()
    expect(isUploadInlineError(apiError(422))).toBe(true)
    expect(isUploadInlineError(apiError(429))).toBe(false)
  })

  it("words a failed confirm", () => {
    expect(confirmErrorMessage(apiError(503))).toBe(UNAVAILABLE)
    expect(confirmErrorMessage(apiError(422, "missing_required"))).toBe(
      "This mapping can't be used. Check the columns and try again.",
    )
    expect(confirmErrorMessage(apiError(500))).toBeUndefined()
    expect(isExpired(apiError(404))).toBe(true)
    expect(EXPIRED).toBe("This upload has expired. Choose the file again.")
    expect([404, 422, 503].map((s) => isConfirmInlineError(apiError(s)))).toEqual([true, true, true])
    expect(isConfirmInlineError(apiError(500))).toBe(false)
  })
})
```

`import-mapping-review.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import type { ImportPreview } from "@app/api-client/types"
import { ImportMappingReview } from "./import-mapping-review"
import { initialMapping, type Mapping } from "./import-mapping"

const preview = {
  upload_id: "u",
  filename: "konto.csv",
  row_count: 1204,
  mapping_source: "proposed",
  columns: [
    { name: "Datum", proposed_field: "date", empty_rate: 0, date_format: "dd.mm.yyyy", amount_style: null },
    { name: "Empfaenger", proposed_field: "merchant", empty_rate: 0, date_format: null, amount_style: null },
    { name: "Betrag", proposed_field: "amount", empty_rate: 0, date_format: null, amount_style: "1.234,56" },
    { name: "Notiz", proposed_field: "ignore", empty_rate: 0.92, date_format: null, amount_style: null },
  ],
  sample_rows: [["15.01.2026", "REWE", "-1.234,56", ""]],
} as ImportPreview

function renderReview(mapping: Mapping = initialMapping(preview), extra = {}) {
  const props = { onChange: vi.fn(), onBack: vi.fn(), onImport: vi.fn() }
  render(<ImportMappingReview preview={preview} mapping={mapping} {...props} {...extra} />)
  return props
}

describe("ImportMappingReview", () => {
  it("shows every column with its examples, format and emptiness", () => {
    renderReview()
    expect(screen.getByText("konto.csv")).toBeInTheDocument()
    expect(screen.getByText("Suggested by AI. Please check it.")).toBeInTheDocument()
    for (const name of ["Datum", "Empfaenger", "Betrag", "Notiz"]) expect(screen.getByText(name)).toBeInTheDocument()
    expect(screen.getByText("dd.mm.yyyy")).toBeInTheDocument()
    expect(screen.getByText("1.234,56")).toBeInTheDocument()
    expect(screen.getByText("92% empty")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Import 1,204 rows" })).toBeEnabled()
  })

  it("moves a taken field when another column picks it", async () => {
    const { onChange } = renderReview()
    await userEvent.click(screen.getByRole("combobox", { name: "Notiz maps to" }))
    await userEvent.click(within(await screen.findByRole("listbox")).getByRole("option", { name: "Merchant" }))
    expect(onChange).toHaveBeenCalledWith({ Datum: "date", Empfaenger: "ignore", Betrag: "amount", Notiz: "merchant" })
  })

  it("holds Import until a date, a merchant and an amount are mapped", () => {
    renderReview({ ...initialMapping(preview), Betrag: "ignore" })
    expect(screen.getByRole("button", { name: "Import 1,204 rows" })).toBeDisabled()
    expect(screen.getByText("Map a date, a merchant and an amount.")).toBeInTheDocument()
  })

  it("shows an error and offers to try again", () => {
    renderReview(undefined, { error: "Categorisation isn't available right now.", retry: true })
    expect(screen.getByRole("alert")).toHaveTextContent("Categorisation isn't available right now.")
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled()
  })
})
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd web-app && pnpm -s test apps/web/src/components/transactions/import-`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement the helpers and the copy**

`import-mapping.ts`:

```ts
import type { ImportField, ImportPreview } from "@app/api-client/types"

/** Column name to field, for every column of the file. */
export type Mapping = Record<string, ImportField>

export const FIELD_LABELS: Record<ImportField, string> = {
  date: "Date",
  merchant: "Merchant",
  amount: "Amount",
  description: "Description",
  original_category: "Bank's category",
  recurring: "Recurring",
  ignore: "Ignore",
}

export const FIELD_ORDER = Object.keys(FIELD_LABELS) as ImportField[]

const REQUIRED: ImportField[] = ["date", "merchant", "amount"]

export function initialMapping(preview: ImportPreview): Mapping {
  return Object.fromEntries(preview.columns.map((c) => [c.name, c.proposed_field]))
}

/** Give `column` the field `field`. A field maps to one column, so the column that held it becomes Ignore. */
export function assignField(mapping: Mapping, column: string, field: ImportField): Mapping {
  return Object.fromEntries(
    Object.entries(mapping).map(([name, current]) => {
      if (name === column) return [name, field]
      return [name, field !== "ignore" && current === field ? "ignore" : current]
    }),
  )
}

export function hasRequired(mapping: Mapping): boolean {
  const used = new Set(Object.values(mapping))
  return REQUIRED.every((f) => used.has(f))
}

/** Up to two non-empty sample values of the column at `index`. */
export function examples(preview: ImportPreview, index: number): string[] {
  return preview.sample_rows
    .map((row) => row[index])
    .filter((value): value is string => Boolean(value))
    .slice(0, 2)
}
```

`import-errors.ts`:

```ts
import { ApiError } from "@app/api-client"

export const MAX_FILE_BYTES = 5 * 1024 * 1024
export const EXPIRED = "This upload has expired. Choose the file again."
export const UNAVAILABLE =
  "Categorisation isn't available right now. Your file is kept for 30 minutes, so try again."
const BAD_MAPPING = "This mapping can't be used. Check the columns and try again."
const UNREADABLE = "This file can't be read as a bank export."

/** The server's refusal reasons, worded here: the web never shows server text. */
const FILE_REASONS: Record<string, string> = {
  not_csv: "Choose a .csv file.",
  too_large: "The file is larger than 5 MB.",
  empty: "The file is empty.",
  no_header: "The file needs a header row and at least two columns.",
  unnamed_column: "Every column needs a name in the header row.",
  duplicate_column: "Two columns have the same name.",
  no_rows: "The file has a header but no rows.",
  too_many_rows: "The file has more than 3,000 rows. Split it and import each part.",
}

const status = (error: unknown) => (error instanceof ApiError ? error.status : undefined)

function reason(error: unknown): string | undefined {
  if (!(error instanceof ApiError)) return undefined
  const details = (error.body as { details?: { reason?: unknown } } | null)?.details
  return typeof details?.reason === "string" ? details.reason : undefined
}

/** Why a file is refused before it is sent, or undefined. */
export function checkFile(file: File): string | undefined {
  if (!file.name.toLowerCase().endsWith(".csv")) return FILE_REASONS.not_csv
  if (file.size > MAX_FILE_BYTES) return FILE_REASONS.too_large
  return undefined
}

export const isUploadInlineError = (error: unknown) => status(error) === 422
export const isConfirmInlineError = (error: unknown) => [404, 422, 503].includes(status(error) ?? 0)
export const isExpired = (error: unknown) => status(error) === 404

/** The inline message for a failed upload; undefined when QueryProvider's toast covers it. */
export function fileErrorMessage(error: unknown): string | undefined {
  if (!isUploadInlineError(error)) return undefined
  return FILE_REASONS[reason(error) ?? ""] ?? UNREADABLE
}

/** The inline message for a failed confirm (a 404 goes back to choosing a file instead). */
export function confirmErrorMessage(error: unknown): string | undefined {
  if (status(error) === 503) return UNAVAILABLE
  if (status(error) === 422) return BAD_MAPPING
  return undefined
}
```

- [ ] **Step 4: Implement the drop zone and the review**

`import-drop-zone.tsx`:

```tsx
"use client"

import { useRef, useState, type DragEvent } from "react"
import { Loader2Icon, UploadIcon } from "lucide-react"
import { Button } from "@app/ui/button"

/** Step 1: drop a file or browse for one. */
export function ImportDropZone({
  onFile,
  pending,
  error,
}: {
  onFile: (file: File) => void
  pending: boolean
  error?: string
}) {
  const input = useRef<HTMLInputElement>(null)
  const [over, setOver] = useState(false)

  const drop = (event: DragEvent) => {
    event.preventDefault()
    setOver(false)
    const file = event.dataTransfer.files[0]
    if (file && !pending) onFile(file)
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={(event) => {
          event.preventDefault()
          setOver(true)
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
        className={`flex flex-col items-center gap-3 rounded-lg border border-dashed p-8 text-center ${over ? "border-primary bg-muted" : ""}`}
      >
        {pending ? (
          <>
            <Loader2Icon className="size-6 animate-spin" aria-hidden />
            <p>Reading your file…</p>
          </>
        ) : (
          <>
            <UploadIcon className="size-6 text-muted-foreground" aria-hidden />
            <p>Drop a CSV here, or</p>
            <Button type="button" variant="outline" onClick={() => input.current?.click()}>
              Browse
            </Button>
          </>
        )}
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          aria-label="CSV file"
          className="sr-only"
          onChange={(event) => {
            const file = event.target.files?.[0]
            event.target.value = ""
            if (file) onFile(file)
          }}
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
```

`import-mapping-review.tsx`:

```tsx
"use client"

import type { ImportField, ImportPreview, MappingSource } from "@app/api-client/types"
import { Button } from "@app/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@app/ui/select"
import { FIELD_LABELS, FIELD_ORDER, assignField, examples, hasRequired, type Mapping } from "./import-mapping"

const SOURCE_NOTE: Record<MappingSource, string> = {
  remembered: "Using your saved mapping for these columns.",
  proposed: "Suggested by AI. Please check it.",
  none: "Couldn't suggest a mapping: pick the columns yourself.",
}

const FIELD_ITEMS = FIELD_ORDER.map((value) => ({ value, label: FIELD_LABELS[value] }))

/** Step 2: every column of the file, what it holds, and the field it maps to. */
export function ImportMappingReview({
  preview,
  mapping,
  error,
  retry = false,
  onChange,
  onBack,
  onImport,
}: {
  preview: ImportPreview
  mapping: Mapping
  error?: string
  retry?: boolean
  onChange: (mapping: Mapping) => void
  onBack: () => void
  onImport: () => void
}) {
  const ready = hasRequired(mapping)
  const rows = preview.row_count.toLocaleString("en-GB")
  return (
    <div className="space-y-4">
      <div className="space-y-1 text-sm">
        <p>
          <span className="font-medium">{preview.filename}</span> · {rows} rows
        </p>
        <p className="text-muted-foreground">{SOURCE_NOTE[preview.mapping_source]}</p>
      </div>
      <ul className="max-h-[50vh] divide-y overflow-y-auto rounded-md border">
        {preview.columns.map((column, index) => {
          const format = column.date_format ?? column.amount_style
          return (
            <li key={column.name} className="grid gap-2 p-3 sm:grid-cols-[1fr_1fr_11rem] sm:items-center">
              <div className="min-w-0">
                <p className="truncate font-mono text-sm">{column.name}</p>
                {column.empty_rate > 0 && (
                  <p className="text-xs text-muted-foreground">{Math.round(column.empty_rate * 100)}% empty</p>
                )}
              </div>
              <div className="min-w-0 text-sm text-muted-foreground">
                <p className="truncate">{examples(preview, index).join(", ") || "—"}</p>
                {format && <p className="text-xs italic">{format}</p>}
              </div>
              <Select
                items={FIELD_ITEMS}
                value={mapping[column.name]}
                onValueChange={(next) => next && onChange(assignField(mapping, column.name, next as ImportField))}
              >
                <SelectTrigger aria-label={`${column.name} maps to`} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {FIELD_ITEMS.map((item) => (
                    <SelectItem key={item.value} value={item.value}>
                      {item.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </li>
          )
        })}
      </ul>
      {!ready && <p className="text-sm text-muted-foreground">Map a date, a merchant and an amount.</p>}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
        <Button variant="outline" onClick={onBack}>
          Choose another file
        </Button>
        <Button disabled={!ready} onClick={onImport}>
          {retry ? "Try again" : `Import ${rows} rows`}
        </Button>
      </div>
    </div>
  )
}
```

If the generated client names the enum types differently (`ImportColumnProposedField`, say), adjust the imports; never hand-write the union.

- [ ] **Step 5: Run the tests to see them pass**

Run: `cd web-app && pnpm -s test apps/web/src/components/transactions/import-`
Expected: PASS. Then `make check-web` from the repo root (ESLint, Prettier, `tsc`); run `pnpm -s format` in `web-app/` if Prettier complains.

- [ ] **Step 6: Commit**

```bash
git add web-app/apps/web/src/components/transactions
git commit -m "CSV import: the mapping review, the drop zone and their copy"
```

---

### Task 12: Web — the dialog, the result, and the entry points on `/transactions`

**Files:**
- Create in `web-app/apps/web/src/components/transactions/`: `import-csv-dialog.tsx`, `import-csv-dialog.test.tsx`, `import-result.tsx`
- Modify: `transactions-table.tsx`, `transactions-table.test.tsx`, `web-app/apps/web/package.json`
- Regenerate: `web-app/pnpm-lock.yaml` (`pnpm install`)

**Interfaces:**
- Consumes: Task 11's components and helpers; generated hooks `useUploadTransactionsCsv`, `useConfirmTransactionsImport` from `@app/api-client/endpoints/transaction-imports`; `useInvalidateTransactions` (condition 4: called, not edited).
- Produces: `<ImportCsvDialog open onOpenChange />` — mounted for as long as the table is; `<ImportResultView result onDone />`.

- [ ] **Step 1: Add `sonner` to the app**

In `web-app/apps/web/package.json` dependencies add `"sonner": "^2.0.7"` (the specifier `@app/ui` uses — condition 8; the orchestrator has been told). Run `cd web-app && pnpm install` and commit the lockfile change with this task.

- [ ] **Step 2: Write the failing tests**

`import-csv-dialog.test.tsx`:

```tsx
import { beforeEach, describe, expect, it, vi } from "vitest"
import { act, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { toast } from "sonner"
import { ApiError } from "@app/api-client"
import {
  useConfirmTransactionsImport,
  useUploadTransactionsCsv,
} from "@app/api-client/endpoints/transaction-imports"
import type { ImportPreview, ImportResult } from "@app/api-client/types"
import { ImportCsvDialog } from "./import-csv-dialog"

vi.mock("sonner", () => ({ toast: { success: vi.fn() } }))
vi.mock("@app/api-client/endpoints/transaction-imports", () => ({
  useUploadTransactionsCsv: vi.fn(),
  useConfirmTransactionsImport: vi.fn(),
}))

const uploadMutate = vi.fn()
const confirmMutate = vi.fn()
const user = userEvent.setup({ applyAccept: false })
let queryClient = new QueryClient()
const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
)

const preview = {
  upload_id: "u1",
  filename: "konto.csv",
  row_count: 2,
  mapping_source: "proposed",
  columns: [
    { name: "Datum", proposed_field: "date", empty_rate: 0, date_format: "dd.mm.yyyy", amount_style: null },
    { name: "Empfaenger", proposed_field: "merchant", empty_rate: 0, date_format: null, amount_style: null },
    { name: "Betrag", proposed_field: "amount", empty_rate: 0, date_format: null, amount_style: "1.234,56" },
  ],
  sample_rows: [["15.01.2026", "REWE", "-3,00"]],
} as ImportPreview

const result: ImportResult = {
  imported: 412,
  skipped_duplicates: 3,
  uncategorised: 1,
  rejected: [{ row: 14, reason: "unreadable date “31.02.2026”" }],
}

/** The hook-level options the dialog passed to the confirm hook (onSuccess, meta). */
const confirmOptions = () => vi.mocked(useConfirmTransactionsImport).mock.calls.at(-1)![0]!.mutation!
/** Run the hook-level onSuccess as TanStack would once the confirm resolves. */
const succeed = (r: ImportResult) =>
  (confirmOptions().onSuccess as unknown as (data: ImportResult) => Promise<void>)(r)

function renderDialog(open = true) {
  const onOpenChange = vi.fn()
  const view = render(<ImportCsvDialog open={open} onOpenChange={onOpenChange} />, { wrapper })
  return { onOpenChange, rerender: (next: boolean) => view.rerender(<ImportCsvDialog open={next} onOpenChange={onOpenChange} />) }
}

async function reachReview() {
  await user.upload(screen.getByLabelText("CSV file"), new File(["x"], "konto.csv", { type: "text/csv" }))
  act(() => uploadMutate.mock.calls[0][1].onSuccess(preview))
}

describe("ImportCsvDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient()
    vi.mocked(useUploadTransactionsCsv).mockReturnValue({ mutate: uploadMutate, isPending: false } as never)
    vi.mocked(useConfirmTransactionsImport).mockReturnValue({ mutate: confirmMutate, isPending: false } as never)
  })

  it("refuses a file that is not a CSV without sending it", async () => {
    renderDialog()
    await user.upload(screen.getByLabelText("CSV file"), new File(["x"], "notes.txt"))
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a .csv file.")
    expect(uploadMutate).not.toHaveBeenCalled()
  })

  it("uploads a CSV and shows its review", async () => {
    renderDialog()
    await reachReview()
    expect(uploadMutate.mock.calls[0][0]).toEqual({ data: { file: expect.any(File) } })
    expect(screen.getByText("Empfaenger")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Import 2 rows" })).toBeEnabled()
  })

  it("shows a refused upload inline", async () => {
    renderDialog()
    await user.upload(screen.getByLabelText("CSV file"), new File(["x"], "konto.csv"))
    act(() =>
      uploadMutate.mock.calls[0][1].onError(new ApiError("HTTP 422", 422, { details: { reason: "no_rows" } }, null)),
    )
    expect(screen.getByRole("alert")).toHaveTextContent("The file has a header but no rows.")
  })

  it("imports and shows the result", async () => {
    renderDialog()
    await reachReview()
    await user.click(screen.getByRole("button", { name: "Import 2 rows" }))
    expect(confirmMutate.mock.calls[0][0]).toEqual({
      uploadId: "u1",
      data: { mapping: { Datum: "date", Empfaenger: "merchant", Betrag: "amount" } },
    })
    expect(screen.getByText(/Importing and categorising 2 rows/)).toBeInTheDocument()
    await act(() => succeed(result))
    expect(screen.getByText("412")).toBeInTheDocument()
    expect(screen.getByText("Row 14: unreadable date “31.02.2026”")).toBeInTheDocument()
    expect(toast.success).not.toHaveBeenCalled()
  })

  it("refreshes the list from the hook, so a closed dialog still refreshes", async () => {
    renderDialog()
    const invalidate = vi.spyOn(queryClient, "invalidateQueries")
    await act(() => succeed(result))
    expect(invalidate).toHaveBeenCalled()
  })

  it("toasts the counts when the dialog was closed mid-import, and View details reopens it", async () => {
    const { onOpenChange, rerender } = renderDialog()
    await reachReview()
    await user.click(screen.getByRole("button", { name: "Import 2 rows" }))
    rerender(false)
    await act(() => succeed(result))
    const [message, options] = vi.mocked(toast.success).mock.calls[0]
    expect(message).toBe("Imported 412 · 3 duplicates skipped · 1 rejected")
    ;(options as { action: { onClick: () => void } }).action.onClick()
    expect(onOpenChange).toHaveBeenCalledWith(true)
  })

  it("a failure after closing is left to QueryProvider's toast", async () => {
    const { rerender } = renderDialog()
    const silent = confirmOptions().meta!.silentError as (e: unknown) => boolean
    const unavailable = new ApiError("HTTP 503", 503, {}, null)
    expect(silent(unavailable)).toBe(true)
    rerender(false)
    expect((confirmOptions().meta!.silentError as (e: unknown) => boolean)(unavailable)).toBe(false)
  })

  it("goes back to choosing a file when the upload expired", async () => {
    renderDialog()
    await reachReview()
    await user.click(screen.getByRole("button", { name: "Import 2 rows" }))
    act(() => confirmMutate.mock.calls[0][1].onError(new ApiError("HTTP 404", 404, {}, null)))
    expect(screen.getByRole("alert")).toHaveTextContent("This upload has expired. Choose the file again.")
    expect(screen.getByLabelText("CSV file")).toBeInTheDocument()
  })

  it("offers to try again when categorisation is down", async () => {
    renderDialog()
    await reachReview()
    await user.click(screen.getByRole("button", { name: "Import 2 rows" }))
    act(() => confirmMutate.mock.calls[0][1].onError(new ApiError("HTTP 503", 503, {}, null)))
    expect(screen.getByRole("alert")).toHaveTextContent("Categorisation isn't available right now.")
    await user.click(screen.getByRole("button", { name: "Try again" }))
    expect(confirmMutate).toHaveBeenCalledTimes(2)
  })
})
```

In `transactions-table.test.tsx`:
- add `vi.mock("@app/api-client/endpoints/transaction-imports", () => ({ useUploadTransactionsCsv: vi.fn(() => ({ mutate: vi.fn(), isPending: false })), useConfirmTransactionsImport: vi.fn(() => ({ mutate: vi.fn(), isPending: false })) }))` beside the existing mock;
- in `"opens the add dialog from the first-run empty state"`, the button's name becomes `"add a transaction"`;
- add:

```tsx
  it("offers Upload a CSV first in the first-run empty state", async () => {
    result([])
    renderAt()
    await userEvent.click(screen.getByRole("button", { name: "Upload a CSV" }))
    expect(await screen.findByRole("heading", { name: "Import a CSV" })).toBeInTheDocument()
  })

  it("opens the import dialog from the header", async () => {
    result([row])
    renderAt()
    await userEvent.click(screen.getByRole("button", { name: "Import CSV" }))
    expect(await screen.findByRole("heading", { name: "Import a CSV" })).toBeInTheDocument()
  })
```

- [ ] **Step 3: Run them to see them fail**

Run: `cd web-app && pnpm -s test apps/web/src/components/transactions/import-csv-dialog apps/web/src/components/transactions/transactions-table`
Expected: FAIL — module not found; buttons missing.

- [ ] **Step 4: Implement the result view**

`import-result.tsx`:

```tsx
"use client"

import type { ImportResult } from "@app/api-client/types"
import { Button } from "@app/ui/button"

const SHOWN = 100
const count = (n: number) => n.toLocaleString("en-GB")

/** Step 4: what the import did, and the rows it left out. */
export function ImportResultView({ result, onDone }: { result: ImportResult; onDone: () => void }) {
  const counts: [string, number][] = [
    ["Imported", result.imported],
    ["Skipped as duplicates", result.skipped_duplicates],
    ["Filed under Miscellaneous", result.uncategorised],
    ["Rejected", result.rejected.length],
  ]
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {counts.map(([label, n]) => (
          <div key={label} className="rounded-md border p-3">
            <dt className="text-xs text-muted-foreground">{label}</dt>
            <dd className="text-xl font-semibold tabular-nums">{count(n)}</dd>
          </div>
        ))}
      </dl>
      {result.rejected.length > 0 && (
        <div className="space-y-1">
          <p className="text-sm font-medium">Rejected rows</p>
          <ul className="max-h-48 space-y-0.5 overflow-y-auto text-sm">
            {result.rejected.slice(0, SHOWN).map((r) => (
              <li key={r.row}>
                Row {r.row}: {r.reason}
              </li>
            ))}
          </ul>
          {result.rejected.length > SHOWN && (
            <p className="text-sm text-muted-foreground">+{count(result.rejected.length - SHOWN)} more</p>
          )}
        </div>
      )}
      <div className="flex justify-end">
        <Button onClick={onDone}>Done</Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Implement the dialog**

`import-csv-dialog.tsx`:

```tsx
"use client"

import { useEffect, useRef, useState } from "react"
import { Loader2Icon } from "lucide-react"
import { toast } from "sonner"
import {
  useConfirmTransactionsImport,
  useUploadTransactionsCsv,
} from "@app/api-client/endpoints/transaction-imports"
import type { ImportPreview, ImportResult } from "@app/api-client/types"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@app/ui/dialog"
import { ImportDropZone } from "./import-drop-zone"
import {
  EXPIRED,
  UNAVAILABLE,
  checkFile,
  confirmErrorMessage,
  fileErrorMessage,
  isConfirmInlineError,
  isExpired,
  isUploadInlineError,
} from "./import-errors"
import { initialMapping, type Mapping } from "./import-mapping"
import { ImportMappingReview } from "./import-mapping-review"
import { ImportResultView } from "./import-result"
import { useInvalidateTransactions } from "./use-invalidate-transactions"

type Step =
  | { name: "choose"; error?: string }
  | { name: "review"; preview: ImportPreview; mapping: Mapping; error?: string }
  | { name: "importing"; preview: ImportPreview; mapping: Mapping }
  | { name: "result"; result: ImportResult }

const DESCRIPTIONS: Record<Step["name"], string> = {
  choose: "Upload your bank's CSV export. Nothing is saved until you confirm.",
  review: "Check which column is which, then import.",
  importing: "Every row is categorised as it is imported.",
  result: "Your import is done.",
}

const summary = (r: ImportResult) =>
  `Imported ${r.imported.toLocaleString("en-GB")} · ${r.skipped_duplicates} duplicates skipped · ${r.rejected.length} rejected`

/**
 * Upload → review → import → result. Mounted for as long as the table is, so
 * closing it mid-import loses nothing: the import carries on, the step moves to
 * the result, and a toast offers to reopen it.
 */
export function ImportCsvDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const [step, setStep] = useState<Step>({ name: "choose" })
  // Read by hook-level callbacks, which outlive a render and run after unmount.
  const openRef = useRef(open)
  const mountedRef = useRef(false)
  useEffect(() => {
    openRef.current = open
  }, [open])
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])
  const invalidate = useInvalidateTransactions()

  const upload = useUploadTransactionsCsv({ mutation: { meta: { silentError: isUploadInlineError } } })
  const confirm = useConfirmTransactionsImport({
    mutation: {
      // Inline while the dialog is open; once it is closed, QueryProvider's toast tells the user.
      meta: { silentError: (error: unknown) => openRef.current && isConfirmInlineError(error) },
      onSuccess: async (result) => {
        await invalidate()
        setStep({ name: "result", result })
        if (!openRef.current) {
          toast.success(
            summary(result),
            mountedRef.current
              ? { action: { label: "View details", onClick: () => onOpenChange(true) } }
              : undefined,
          )
        }
      },
    },
  })

  const choose = (file: File) => {
    const problem = checkFile(file)
    if (problem) return setStep({ name: "choose", error: problem })
    setStep({ name: "choose" })
    upload.mutate(
      { data: { file } },
      {
        onSuccess: (preview) => setStep({ name: "review", preview, mapping: initialMapping(preview) }),
        onError: (error) => setStep({ name: "choose", error: fileErrorMessage(error) }),
      },
    )
  }

  const start = (preview: ImportPreview, mapping: Mapping) => {
    setStep({ name: "importing", preview, mapping })
    confirm.mutate(
      { uploadId: preview.upload_id, data: { mapping } },
      {
        onError: (error) =>
          setStep(
            isExpired(error)
              ? { name: "choose", error: EXPIRED }
              : { name: "review", preview, mapping, error: confirmErrorMessage(error) },
          ),
      },
    )
  }

  const changeOpen = (next: boolean) => {
    // An import in flight keeps its step; anything else starts over next time.
    if (!next && step.name !== "importing") setStep({ name: "choose" })
    onOpenChange(next)
  }

  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import a CSV</DialogTitle>
          <DialogDescription>{DESCRIPTIONS[step.name]}</DialogDescription>
        </DialogHeader>
        {step.name === "choose" && <ImportDropZone onFile={choose} pending={upload.isPending} error={step.error} />}
        {step.name === "review" && (
          <ImportMappingReview
            preview={step.preview}
            mapping={step.mapping}
            error={step.error}
            retry={step.error === UNAVAILABLE}
            onChange={(mapping) => setStep({ ...step, mapping, error: undefined })}
            onBack={() => setStep({ name: "choose" })}
            onImport={() => start(step.preview, step.mapping)}
          />
        )}
        {step.name === "importing" && (
          <div className="flex flex-col items-center gap-3 py-8 text-center">
            <Loader2Icon className="size-6 animate-spin" aria-hidden />
            <p>Importing and categorising {step.preview.row_count.toLocaleString("en-GB")} rows…</p>
            <p className="text-sm text-muted-foreground">You can close this window; the import carries on.</p>
          </div>
        )}
        {step.name === "result" && <ImportResultView result={step.result} onDone={() => changeOpen(false)} />}
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 6: The entry points**

In `transactions-table.tsx`:
- import `UploadIcon` beside `PlusIcon`, and `ImportCsvDialog` from `./import-csv-dialog`;
- add `const [importing, setImporting] = useState(false)` beside `dialog` (the import dialog is not in the `OpenDialog` union: it stays mounted);
- the first-run empty state becomes:

```tsx
    <div className="space-y-2">
      <p>No transactions yet.</p>
      <Button size="sm" onClick={() => setImporting(true)}>
        <UploadIcon />
        Upload a CSV
      </Button>
      <p className="text-sm">
        or{" "}
        <Button variant="link" size="sm" className="h-auto p-0" onClick={() => setDialog({ kind: "add" })}>
          add a transaction
        </Button>
      </p>
    </div>
```

- the header's button becomes a pair:

```tsx
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setImporting(true)}>
            <UploadIcon />
            Import CSV
          </Button>
          <Button onClick={() => setDialog({ kind: "add" })}>
            <PlusIcon />
            Add transaction
          </Button>
        </div>
```

- render `<ImportCsvDialog open={importing} onOpenChange={setImporting} />` once, beside the other dialogs, unconditionally.

- [ ] **Step 7: Run the web gates**

Run: `cd web-app && pnpm -s test` (the whole suite), then from the repo root `make check-web`.
Expected: all PASS. If `toLocaleString("en-GB")` renders a thin space in jsdom, the counts `"412"` and `"1,204"` still match; check before changing a test.

- [ ] **Step 8: Commit**

```bash
git add web-app/apps/web web-app/pnpm-lock.yaml
git commit -m "CSV import: the import dialog on /transactions, its result, and Upload a CSV in the empty state"
```

---

### Task 13: Docs, the hand check, and the roadmap

No code. The controller runs this task itself or gives it to one subagent with this section and the spec.

**Files:**
- Modify: `docs/data-model/transaction.md`, `docs/data-model/README.md` (§1 row; §3 one line), `docs/product/features/csv-import.md`, `docs/product/features/categorisation.md`, `docs/architecture/server.md` (§2 paragraph, §8 table row), `docs/TODO.md`, `docs/ROADMAP.md` (row 4, after the PR exists)

- [ ] **Step 1: `docs/data-model/transaction.md`**

- Status block: **Last updated** 15 Oct 2026; **Describes** adds `csv-import.md`; **Scope** adds "the import's two tables"; **Source of truth** adds `imports/models.py` and revision `5b7e2c9d4f10`.
- §2 sketch: add `merchant_key VARCHAR(255) NOT NULL` and `recurring_source VARCHAR(16) NOT NULL` to `transaction`; add `csv_mapping_profile` and `csv_upload` exactly as in spec §2.2–§2.3.
- §3 indexes: `ix_transaction_user_id_merchant_key` (serves re-running the recurring rule for a merchant); the two unique constraints.
- §4 decisions, each dated 15 Oct 2026, with the reasoning from the spec: **D3** gains "an import count-matches: a fingerprint held k times keeps all but the file's first k copies"; **D6** `recurring_source` and the rule — its thresholds table, `user` rows as evidence never changed, which writes set which provenance (spec §4.5 table), the yearly minimum of 3 and why; **D7** `merchant_key` — the normaliser's steps, conservative by design, a change needs a backfill revision; **D8** mapping profiles — keyed per user and folded column set, upserted on confirm, matched by case and spacing; **D9** held uploads — one per user, 30 minutes, hard-deleted on confirm or erasure, text only.
- §5 deferred: "**A sweep of abandoned uploads.** An unconfirmed upload's text stays until the user's next upload or erasure; a sweep across users needs the worker in `../TODO.md` (Server — events beyond the request)."
- §6 field map: original category "set by the import and the seed"; recurring → `is_recurring`, with `recurring_source`.

- [ ] **Step 2: The rest of the docs**

- `docs/data-model/README.md` §1: the `transaction` row's Tables cell becomes `transaction`, `csv_mapping_profile`, `csv_upload`, and Describes adds `csv-import`. §3, after "Singular table names": "A model whose class name is two words sets `__tablename__` in snake_case (`csv_upload`), since SQLModel's default runs the words together."
- `docs/product/features/csv-import.md`: **Data model** → `transaction.md`; **Last updated** 15 Oct 2026; §2 step 3 lists the four result counts and that the dialog can be closed while the import carries on; §4: UTF-8 or Windows-1252, the delimiter and each column's date format and decimal style inferred and shown in the review, lines above the header skipped; duplicates count-matched (two identical rows in a file are two; a re-import adds nothing); required fields checked at confirm, not upload; a mapped recurring column is the user's assertion; 10 a minute **per user**; §5 adds "selecting several files at once"; §6 drops the European-amounts question.
- `docs/product/features/categorisation.md` §4: known merchants at 0.95 (1 stays "you chose it"); one prompt version (v2); a partial failure files those rows under Miscellaneous at 0.3 and says how many, a total failure saves nothing and keeps the upload; the labeller no longer sets recurring — the rule does (link `transaction.md` D6). **Last updated** 15 Oct 2026.
- `docs/architecture/server.md` §2, after the "A module on both rungs" example, add:

  > **A feature sub-package** is the third way a module grows: one concept with its own small tables and routes, kept together instead of spread across slot packages. `transaction/imports/` holds its own `router`, `service`, `repository`, `schemas`, `models`, `domain` and `handlers`. It calls the module's core — rows are written only through `transaction_service` — and the core never imports it. The module root re-exports what the outside needs (`imports_router`), so R1 is unchanged; the R9 contract covers `app.modules.*.*.domain` for it.

  §8's events table: the `USER_ERASING` row's Subscribers cell adds "`transaction.imports` — hard-deletes the user's mapping profiles and held upload".
- `docs/TODO.md`: delete the sections **Web — the transactions empty state, with CSV import (roadmap step 4)**, and the two step-4 bullets under **Port — carry into backend modules** ("Services returning `None` on a miss", "Direct `ChatOpenAI` use"). The R9 section went in Task 1. Leave **Server — a model call holds the request's DB connection** in place, and add one sentence to it: "The import routes already release it (`_release_connection` in `transaction/imports/service.py`)."

- [ ] **Step 3: The hand check**

Use the `run-stack` and `worktrees` skills to bring up this worktree's stack on its own ports, with `OPENROUTER_API_KEY` set. Then, signed in, on `/transactions`:
1. Import a German-format file — `;`, `dd.mm.yyyy`, `1.234,56`, saved as Windows-1252, with two preamble lines. The review shows the formats; confirm; the result's counts match the file.
2. Import an N26-style file (`"Date","Payee","Amount (EUR)"`, ISO dates, dot decimals).
3. Import the N26 file again: every row is skipped as a duplicate, and the review said "Using your saved mapping".
4. Close the dialog during an import: a toast with **View details** appears and reopens the result.
5. Three monthly rows of one merchant are marked recurring in the table.

Record anything that fails as a bug and fix it before the PR; do not open the PR with a known failure.

- [ ] **Step 4: Gates, then finish**

From the repo root: `make check`, `make test-web`, `make -C server test`, `make check-contract` — all PASS.
Then follow `superpowers:finishing-a-development-branch`: push `feat/csv-import`, open a PR into **`template-base`** (never merge). In the PR's own branch, set `docs/ROADMAP.md` row 4 to `complete — [PR #N](url) into template-base; reaches main at Cutover` (as rows 2 and 3 read), delete `.superpowers/specs/2026-10-15-csv-import-design.md` and `.superpowers/plans/2026-10-15-csv-import.md`, commit, push. Then `SendMessage` to `orchestrator`: first line `csv-import: PR open — <url>`.
