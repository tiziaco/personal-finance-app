# CSV Transaction Import — Implementation Plan

**Date:** 2026-02-25
**Status:** Implemented  ✓

**Goal:** Implement two-step CSV transaction import (`POST /transactions/upload` + `POST /transactions/upload/{mapping_id}/confirm`) with flexible LLM-powered column mapping, SHA-256 dedup, and AI-powered transaction labeling.

**Architecture:** Upload step validates the file and proposes a column mapping via OpenAI (or returns a cached one); confirm step parses the full CSV, deduplicates via fingerprints, runs the refactored transaction labeler, and bulk-inserts the results. All existing transactions also get fingerprints computed on creation for future dedup coverage.

**Tech Stack:** FastAPI, SQLModel, SQLAlchemy async, Polars, LangGraph, LangChain OpenAI, Alembic, Langfuse, pytest-asyncio, httpx

---

### Task 1: New DB Models

**Files:**
- Modify: `app/models/transaction.py`
- Create: `app/models/csv_mapping_profile.py`
- Create: `app/models/csv_upload_session.py`
- Modify: `app/models/__init__.py`

**Step 1: Add `fingerprint` field to Transaction model**

In `app/models/transaction.py`, add after `is_recurring`:

```python
# Deduplication
fingerprint: Optional[str] = Field(default=None, index=True)
```

**Step 2: Create CSVMappingProfile model**

```python
# app/models/csv_mapping_profile.py
from datetime import UTC, datetime
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship

from app.models.base import BaseModel

if False:  # TYPE_CHECKING
    from app.models.user import User


class CSVMappingProfile(BaseModel, table=True):
    """Stores the column→field mapping for a user's CSV format.

    Keyed by (user_id, column_hash) so one profile is stored per unique
    set of CSV column names. Supports users importing from multiple banks.
    """

    __tablename__ = "csv_mapping_profile"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    column_hash: str = Field(index=True)      # SHA-256 of sorted frozenset of column names
    mapping: Dict[str, Any] = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    last_used_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )

    user: Optional["User"] = Relationship()
```

**Step 3: Create CSVUploadSession model**

```python
# app/models/csv_upload_session.py
from datetime import UTC, datetime
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship

from app.models.base import BaseModel

if False:  # TYPE_CHECKING
    from app.models.user import User


class CSVUploadSession(BaseModel, table=True):
    """Short-lived session linking mapping_id to raw CSV bytes.

    Created in step 1 (upload), consumed in step 2 (confirm).
    TTL is controlled by settings.UPLOAD_SESSION_TTL_MINUTES.
    """

    __tablename__ = "csv_upload_session"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    mapping_id: str = Field(index=True, unique=True)   # UUID
    proposed_mapping: Dict[str, Any] = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    csv_content: str = Field(sa_column=sa.Column(sa.Text, nullable=False))  # raw UTF-8 CSV
    expires_at: datetime = Field(sa_type=sa.DateTime(timezone=True))

    user: Optional["User"] = Relationship()
```

**Step 4: Export new models from `app/models/__init__.py`**

Add imports for `CSVMappingProfile` and `CSVUploadSession` alongside the existing model imports so SQLModel registers them in metadata before Alembic autogenerate runs.

**Step 5: Commit**

```bash
git add app/models/transaction.py app/models/csv_mapping_profile.py \
        app/models/csv_upload_session.py app/models/__init__.py
git commit -m "feat: add fingerprint to Transaction and new CSV upload models"
```

---

### Task 2: Alembic Migration

**Files:**
- Create: `alembic/versions/20260225_<time>_<hash>_add_csv_upload_tables.py`

**Step 1: Generate migration**

```bash
alembic revision --autogenerate -m "add_csv_upload_tables"
```

**Step 2: Review the generated file**

Verify it contains:
- `op.add_column('transaction', sa.Column('fingerprint', sa.String(), nullable=True))`
- `op.create_index(op.f('ix_transaction_fingerprint'), 'transaction', ['fingerprint'], unique=False)`
- `op.create_table('csv_mapping_profile', ...)`
- `op.create_table('csv_upload_session', ...)`

Fix anything that looks wrong. The `downgrade()` must drop the index before the column.

**Step 3: Apply migration**

```bash
alembic upgrade head
```

Expected output ends with: `Running upgrade ... -> <new_hash>, add_csv_upload_tables`

**Step 4: Commit**

```bash
git add alembic/versions/
git commit -m "feat: migration — add fingerprint, csv_mapping_profile, csv_upload_session"
```

---

### Task 3: Settings Update

**Files:**
- Modify: `app/core/config.py`

**Step 1: Add new settings to the main `Settings` class**

In `app/core/config.py`, inside the `Settings` class after `DEBUG`:

```python
# CSV Upload
CSV_MAX_ROWS: int = 3000
UPLOAD_SESSION_TTL_MINUTES: int = 30
```

These are plain fields (no env_prefix class), so they read from env vars `CSV_MAX_ROWS` and `UPLOAD_SESSION_TTL_MINUTES` directly.

**Step 2: Verify**

```bash
python -c "from app.core.config import settings; print(settings.CSV_MAX_ROWS, settings.UPLOAD_SESSION_TTL_MINUTES)"
```

Expected: `3000 30`

**Step 3: Commit**

```bash
git add app/core/config.py
git commit -m "feat: add CSV_MAX_ROWS and UPLOAD_SESSION_TTL_MINUTES settings"
```

---

### Task 4: `compute_fingerprint()` — TDD

**Files:**
- Create: `tests/unit/services/test_transaction_service_fingerprint.py`
- Modify: `app/services/transaction/service.py`

**Step 1: Write failing tests**

```python
# tests/unit/services/test_transaction_service_fingerprint.py
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.services.transaction.service import TransactionService


def make_fp(**overrides):
    base = dict(
        user_id="user_abc",
        date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        merchant="Netflix",
        amount=Decimal("12.99"),
        description=None,
    )
    return TransactionService.compute_fingerprint(**{**base, **overrides})


def test_fingerprint_is_deterministic():
    assert make_fp() == make_fp()


def test_fingerprint_changes_with_user_id():
    assert make_fp() != make_fp(user_id="user_xyz")


def test_fingerprint_changes_with_date():
    assert make_fp() != make_fp(date=datetime(2026, 2, 1, tzinfo=timezone.utc))


def test_fingerprint_changes_with_merchant():
    assert make_fp() != make_fp(merchant="Spotify")


def test_fingerprint_changes_with_amount():
    assert make_fp() != make_fp(amount=Decimal("9.99"))


def test_fingerprint_changes_with_description():
    assert make_fp() != make_fp(description="Payment to Alice")


def test_fingerprint_treats_none_description_as_empty_string():
    assert make_fp(description=None) == make_fp(description="")


def test_fingerprint_normalises_merchant_whitespace_and_case():
    assert make_fp(merchant="  NETFLIX  ") == make_fp(merchant="netflix")


def test_fingerprint_is_sha256_hex(monkeypatch):
    fp = make_fp()
    assert len(fp) == 64
    assert all(c in "0123456789abcdef" for c in fp)
```

**Step 2: Run to confirm FAIL**

```bash
pytest tests/unit/services/test_transaction_service_fingerprint.py -v
```

Expected: `AttributeError: type object 'TransactionService' has no attribute 'compute_fingerprint'`

**Step 3: Implement `compute_fingerprint()`**

Add to `TransactionService` in `app/services/transaction/service.py`:

```python
import hashlib

@staticmethod
def compute_fingerprint(
    user_id: str,
    date: datetime,
    merchant: str,
    amount: Decimal,
    description: Optional[str],
) -> str:
    """SHA-256 fingerprint for deduplication.

    Includes description because merchants like PayPal use it to
    distinguish recipients — same date/merchant/amount but different
    description = different transaction.
    """
    raw = (
        f"{user_id}|"
        f"{date.isoformat()}|"
        f"{merchant.strip().lower()}|"
        f"{float(amount):.2f}|"
        f"{(description or '').strip().lower()}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()
```

Add `import hashlib` at the top of the file.

**Step 4: Run tests — confirm PASS**

```bash
pytest tests/unit/services/test_transaction_service_fingerprint.py -v
```

Expected: `9 passed`

**Step 5: Commit**

```bash
git add app/services/transaction/service.py \
        tests/unit/services/test_transaction_service_fingerprint.py
git commit -m "feat: add TransactionService.compute_fingerprint() with tests"
```

---

### Task 5: `TransactionService.create()` Fingerprint — TDD

**Files:**
- Create: `tests/unit/services/test_transaction_service_create_fingerprint.py`
- Modify: `app/services/transaction/service.py`

**Step 1: Write failing test**

```python
# tests/unit/services/test_transaction_service_create_fingerprint.py
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.transaction import TransactionCreate
from app.models.transaction import CategoryEnum
from app.services.transaction.service import TransactionService


@pytest.mark.asyncio
async def test_create_stores_fingerprint():
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    data = TransactionCreate(
        date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        merchant="Netflix",
        amount=Decimal("12.99"),
        category=CategoryEnum.MEDIA_ELECTRONICS,
    )

    added_transaction = None

    def capture_add(obj):
        nonlocal added_transaction
        added_transaction = obj

    mock_db.add = capture_add

    await TransactionService.create(mock_db, "user_abc", data)

    assert added_transaction is not None
    assert added_transaction.fingerprint is not None
    assert len(added_transaction.fingerprint) == 64  # SHA-256 hex


@pytest.mark.asyncio
async def test_create_fingerprint_is_deterministic():
    """Same inputs produce same fingerprint across two calls."""
    data = TransactionCreate(
        date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        merchant="Netflix",
        amount=Decimal("12.99"),
        category=CategoryEnum.MEDIA_ELECTRONICS,
    )

    fingerprints = []
    for _ in range(2):
        mock_db = AsyncMock()
        added = None

        def capture(obj):
            nonlocal added
            added = obj

        mock_db.add = capture
        await TransactionService.create(mock_db, "user_abc", data)
        fingerprints.append(added.fingerprint)

    assert fingerprints[0] == fingerprints[1]
```

**Step 2: Run to confirm FAIL**

```bash
pytest tests/unit/services/test_transaction_service_create_fingerprint.py -v
```

Expected: `AssertionError: assert None is not None` (fingerprint not set yet)

**Step 3: Modify `TransactionService.create()` to compute and store fingerprint**

Replace the `create` method body:

```python
@staticmethod
async def create(
    db: AsyncSession,
    user_id: str,
    data: TransactionCreate,
) -> Transaction:
    fingerprint = TransactionService.compute_fingerprint(
        user_id=user_id,
        date=data.date,
        merchant=data.merchant,
        amount=data.amount,
        description=data.description,
    )
    transaction = Transaction(
        user_id=user_id,
        fingerprint=fingerprint,
        **data.model_dump(),
    )
    db.add(transaction)
    await db.flush()
    await db.refresh(transaction)

    logger.info("transaction_created", user_id=user_id, transaction_id=transaction.id)
    return transaction
```

**Step 4: Run tests — confirm PASS**

```bash
pytest tests/unit/services/test_transaction_service_create_fingerprint.py \
       tests/unit/services/test_transaction_service_fingerprint.py -v
```

Expected: `11 passed`

**Step 5: Commit**

```bash
git add app/services/transaction/service.py \
        tests/unit/services/test_transaction_service_create_fingerprint.py
git commit -m "feat: compute and store fingerprint on every TransactionService.create()"
```

---

### Task 6: `import_from_csv()` — TDD

**Files:**
- Create: `tests/unit/services/test_transaction_service_import.py`
- Modify: `app/services/transaction/service.py`

**Step 1: Write failing tests**

```python
# tests/unit/services/test_transaction_service_import.py
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.transaction import CategoryEnum
from app.schemas.transaction import TransactionCreate
from app.services.transaction.service import TransactionService


def make_row(**overrides) -> TransactionCreate:
    base = dict(
        date=datetime(2026, 1, 15, tzinfo=timezone.utc),
        merchant="Netflix",
        amount=Decimal("12.99"),
        category=CategoryEnum.MEDIA_ELECTRONICS,
        description=None,
    )
    return TransactionCreate(**{**base, **overrides})


def make_db(existing_fingerprints: list[str]):
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.add = MagicMock()

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = existing_fingerprints
    mock_db.execute = AsyncMock(return_value=mock_result)

    return mock_db


@pytest.mark.asyncio
async def test_import_inserts_all_rows_when_no_duplicates():
    rows = [make_row(merchant="Netflix"), make_row(merchant="Spotify")]
    db = make_db(existing_fingerprints=[])

    imported, skipped, errors = await TransactionService.import_from_csv(db, "user_abc", rows)

    assert imported == 2
    assert skipped == 0
    assert errors == []
    assert db.add.call_count == 2


@pytest.mark.asyncio
async def test_import_skips_rows_with_existing_fingerprints():
    row = make_row(merchant="Netflix")
    existing_fp = TransactionService.compute_fingerprint(
        "user_abc", row.date, row.merchant, row.amount, row.description
    )
    db = make_db(existing_fingerprints=[existing_fp])

    imported, skipped, errors = await TransactionService.import_from_csv(db, "user_abc", [row])

    assert imported == 0
    assert skipped == 1
    assert db.add.call_count == 0


@pytest.mark.asyncio
async def test_import_partial_overlap():
    row_a = make_row(merchant="Netflix")
    row_b = make_row(merchant="Spotify")
    existing_fp = TransactionService.compute_fingerprint(
        "user_abc", row_a.date, row_a.merchant, row_a.amount, row_a.description
    )
    db = make_db(existing_fingerprints=[existing_fp])

    imported, skipped, errors = await TransactionService.import_from_csv(
        db, "user_abc", [row_a, row_b]
    )

    assert imported == 1
    assert skipped == 1


@pytest.mark.asyncio
async def test_import_deduplicates_within_batch():
    """Two identical rows in the same CSV — only one inserted."""
    row = make_row(merchant="Netflix")
    db = make_db(existing_fingerprints=[])

    imported, skipped, errors = await TransactionService.import_from_csv(
        db, "user_abc", [row, row]
    )

    assert imported == 1
    assert skipped == 1
```

**Step 2: Run to confirm FAIL**

```bash
pytest tests/unit/services/test_transaction_service_import.py -v
```

Expected: `AttributeError: type object 'TransactionService' has no attribute 'import_from_csv'`

**Step 3: Implement `import_from_csv()`**

Add to `TransactionService` in `app/services/transaction/service.py`. Also add to imports at top: `from sqlmodel import select` (already there).

```python
@staticmethod
async def import_from_csv(
    db: AsyncSession,
    user_id: str,
    rows: List[TransactionCreate],
) -> tuple[int, int, list[str]]:
    """Bulk-import pre-labeled transactions, skipping fingerprint duplicates.

    Fetches all existing fingerprints for the user in a single query before
    inserting — no per-row DB lookups.

    Args:
        db: Database session.
        user_id: Authenticated user's ID.
        rows: Validated, labeled TransactionCreate objects.

    Returns:
        Tuple of (imported_count, skipped_count, errors).
        errors is always [] — row-level errors are handled upstream.
    """
    # 1. Compute fingerprint for each incoming row
    fingerprinted: list[tuple[TransactionCreate, str]] = [
        (
            row,
            TransactionService.compute_fingerprint(
                user_id=user_id,
                date=row.date,
                merchant=row.merchant,
                amount=row.amount,
                description=row.description,
            ),
        )
        for row in rows
    ]

    # 2. Fetch all existing fingerprints for this user in one query
    stmt = select(Transaction.fingerprint).where(
        Transaction.user_id == user_id,
        Transaction.fingerprint.isnot(None),
        Transaction.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    existing: set[str] = set(result.scalars().all())

    # 3. Filter duplicates (also catches within-batch duplicates)
    to_insert: list[tuple[TransactionCreate, str]] = []
    skipped = 0
    for row, fp in fingerprinted:
        if fp in existing:
            skipped += 1
        else:
            to_insert.append((row, fp))
            existing.add(fp)  # prevent within-batch duplicates

    # 4. Bulk insert
    for row, fp in to_insert:
        db.add(
            Transaction(
                user_id=user_id,
                fingerprint=fp,
                **row.model_dump(),
            )
        )
    await db.flush()

    logger.info(
        "csv_import_complete",
        user_id=user_id,
        imported=len(to_insert),
        skipped=skipped,
    )
    return len(to_insert), skipped, []
```

**Step 4: Run tests — confirm PASS**

```bash
pytest tests/unit/services/test_transaction_service_import.py -v
```

Expected: `4 passed`

**Step 5: Commit**

```bash
git add app/services/transaction/service.py \
        tests/unit/services/test_transaction_service_import.py
git commit -m "feat: add TransactionService.import_from_csv() with dedup logic"
```

---

### Task 7: `CSVMappingService` — TDD

**Files:**
- Create: `app/services/csv_mapping/__init__.py`
- Create: `app/services/csv_mapping/service.py`
- Create: `tests/unit/services/test_csv_mapping_service.py`

**Step 1: Write failing tests**

```python
# tests/unit/services/test_csv_mapping_service.py
import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.csv_mapping.service import CSVMappingService


def make_db_with_result(scalar_result):
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_result
    db.execute = AsyncMock(return_value=mock_result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: obj)
    return db


def column_hash(columns: list[str]) -> str:
    return hashlib.sha256("|".join(sorted(columns)).encode()).hexdigest()


@pytest.mark.asyncio
async def test_get_profile_returns_none_when_not_found():
    db = make_db_with_result(None)
    result = await CSVMappingService.get_profile(db, "user_abc", "somehash")
    assert result is None


@pytest.mark.asyncio
async def test_get_profile_returns_profile_when_found():
    from app.models.csv_mapping_profile import CSVMappingProfile

    fake = CSVMappingProfile(
        user_id="user_abc",
        column_hash="somehash",
        mapping={"Date": "date"},
        last_used_at=datetime.now(UTC),
    )
    db = make_db_with_result(fake)
    result = await CSVMappingService.get_profile(db, "user_abc", "somehash")
    assert result is fake


@pytest.mark.asyncio
async def test_save_profile_creates_new_when_not_found():
    db = make_db_with_result(None)
    await CSVMappingService.save_profile(
        db, "user_abc", "somehash", {"Date": "date"}
    )
    assert db.add.called


@pytest.mark.asyncio
async def test_compute_column_hash_is_order_independent():
    h1 = CSVMappingService.compute_column_hash(["Date", "Amount", "Merchant"])
    h2 = CSVMappingService.compute_column_hash(["Merchant", "Date", "Amount"])
    assert h1 == h2


@pytest.mark.asyncio
async def test_get_session_returns_none_for_expired():
    from app.models.csv_upload_session import CSVUploadSession

    expired = CSVUploadSession(
        user_id="user_abc",
        mapping_id="some-uuid",
        proposed_mapping={},
        csv_content="",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),  # already expired
    )
    db = make_db_with_result(expired)
    result = await CSVMappingService.get_session(db, "some-uuid", "user_abc")
    assert result is None
```

**Step 2: Run to confirm FAIL**

```bash
pytest tests/unit/services/test_csv_mapping_service.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.csv_mapping'`

**Step 3: Implement `CSVMappingService`**

```python
# app/services/csv_mapping/__init__.py
from app.services.csv_mapping.service import CSVMappingService

__all__ = ["CSVMappingService"]
```

```python
# app/services/csv_mapping/service.py
"""Service for CSV upload sessions and column mapping profiles."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.logging import logger
from app.models.csv_mapping_profile import CSVMappingProfile
from app.models.csv_upload_session import CSVUploadSession


class CSVMappingService:
    """Stateless service for CSV upload sessions and column mapping profiles."""

    @staticmethod
    def compute_column_hash(columns: list[str]) -> str:
        """SHA-256 of the sorted column names — order-independent fingerprint."""
        return hashlib.sha256("|".join(sorted(columns)).encode()).hexdigest()

    @staticmethod
    async def get_profile(
        db: AsyncSession,
        user_id: str,
        column_hash: str,
    ) -> Optional[CSVMappingProfile]:
        """Return the mapping profile for this user+column set, or None."""
        stmt = select(CSVMappingProfile).where(
            CSVMappingProfile.user_id == user_id,
            CSVMappingProfile.column_hash == column_hash,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def save_profile(
        db: AsyncSession,
        user_id: str,
        column_hash: str,
        mapping: Dict[str, Any],
    ) -> CSVMappingProfile:
        """Create or update a mapping profile for this user+column set."""
        stmt = select(CSVMappingProfile).where(
            CSVMappingProfile.user_id == user_id,
            CSVMappingProfile.column_hash == column_hash,
        )
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()

        if profile:
            profile.mapping = mapping
            profile.last_used_at = datetime.now(UTC)
        else:
            profile = CSVMappingProfile(
                user_id=user_id,
                column_hash=column_hash,
                mapping=mapping,
                last_used_at=datetime.now(UTC),
            )

        db.add(profile)
        await db.flush()
        await db.refresh(profile)

        logger.info("csv_mapping_profile_saved", user_id=user_id, column_hash=column_hash)
        return profile

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user_id: str,
        proposed_mapping: Dict[str, Any],
        csv_content: str,
    ) -> CSVUploadSession:
        """Create a new upload session with a fresh UUID mapping_id."""
        mapping_id = str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.UPLOAD_SESSION_TTL_MINUTES
        )
        session = CSVUploadSession(
            user_id=user_id,
            mapping_id=mapping_id,
            proposed_mapping=proposed_mapping,
            csv_content=csv_content,
            expires_at=expires_at,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)

        logger.info("csv_upload_session_created", user_id=user_id, mapping_id=mapping_id)
        return session

    @staticmethod
    async def get_session(
        db: AsyncSession,
        mapping_id: str,
        user_id: str,
    ) -> Optional[CSVUploadSession]:
        """Return the session if it exists, belongs to the user, and has not expired."""
        stmt = select(CSVUploadSession).where(
            CSVUploadSession.mapping_id == mapping_id,
            CSVUploadSession.user_id == user_id,
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            return None

        if session.expires_at < datetime.now(UTC):
            logger.info("csv_upload_session_expired", mapping_id=mapping_id)
            return None

        return session

    @staticmethod
    async def expire_session(db: AsyncSession, session: CSVUploadSession) -> None:
        """Immediately expire a session after it has been consumed."""
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.add(session)
        await db.flush()
```

**Step 4: Run tests — confirm PASS**

```bash
pytest tests/unit/services/test_csv_mapping_service.py -v
```

Expected: `5 passed`

**Step 5: Commit**

```bash
git add app/services/csv_mapping/ tests/unit/services/test_csv_mapping_service.py
git commit -m "feat: add CSVMappingService with upload session and profile management"
```

---

### Task 8: New Upload Schemas

**Files:**
- Create: `app/schemas/csv_upload.py`

**Step 1: Create the schemas file**

```python
# app/schemas/csv_upload.py
"""Schemas for the two-step CSV transaction upload flow."""

from typing import Any, Dict, List, Optional

from sqlmodel import SQLModel


class CSVUploadProposalResponse(SQLModel):
    """Response from POST /transactions/upload (step 1).

    Returns the proposed column→field mapping and sample rows for the user
    to verify before confirming the import.
    """

    mapping_id: str
    proposed_mapping: Dict[str, str]  # {"Buchungsdatum": "date", "Betrag": "amount", ...}
    sample_rows: List[Dict[str, Any]]  # first 3 parsed rows for visual verification


class CSVConfirmRequest(SQLModel):
    """Request body for POST /transactions/upload/{mapping_id}/confirm (step 2).

    The client sends back the (possibly corrected) mapping.
    """

    confirmed_mapping: Dict[str, str]  # same shape as proposed_mapping


class CSVUploadResponse(SQLModel):
    """Response from POST /transactions/upload/{mapping_id}/confirm (step 2)."""

    imported: int
    skipped: int
    errors: List[str]
```

**Step 2: Commit**

```bash
git add app/schemas/csv_upload.py
git commit -m "feat: add CSV upload schemas (proposal, confirm request, upload response)"
```

---

### Task 9: Refactor `transactions_labeler` Agent

**Files:**
- Create: `app/agents/transactions_labeler/` (new folder — fixes the typo)
- Create: `app/agents/transactions_labeler/__init__.py`
- Create: `app/agents/transactions_labeler/models.py`
- Create: `app/agents/transactions_labeler/enums.py`
- Create: `app/agents/transactions_labeler/state.py`
- Create: `app/agents/transactions_labeler/prompts/__init__.py`
- Create: `app/agents/transactions_labeler/prompts/categorization.py`
- Create: `app/agents/transactions_labeler/nodes.py`
- Create: `app/agents/transactions_labeler/agent.py`
- Delete: `app/agents/transactios_labeler/` (old folder with typo)

**Step 1: Create `models.py`**

`CategorizedTransaction` is removed — the agent now outputs `TransactionCreate` directly.

```python
# app/agents/transactions_labeler/models.py
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.agents.transactions_labeler.enums import CategoryEnum


class RawTransaction(BaseModel):
    """A transaction row after CSV parsing, before AI categorization."""

    date: str            # ISO string, e.g. "2026-01-15T00:00:00+00:00"
    merchant: str
    amount: float
    description: Optional[str] = None
    original_category: Optional[str] = None


class UserCategoryPreference(BaseModel):
    """User-specific merchant mappings and keyword hints.

    For MVP all fields default to empty — the labeler runs on hardcoded
    common merchant mappings only. User-level preferences are a future feature.
    """

    user_id: str
    merchant_mappings: Dict[str, CategoryEnum] = Field(default_factory=dict)
    category_keywords: Dict[CategoryEnum, List[str]] = Field(default_factory=dict)
```

**Step 2: Create `enums.py`**

Copy `CategoryEnum` verbatim from `app/agents/transactios_labeler/enums.py` — it is identical to `app/models/transaction.CategoryEnum` and must stay in sync. Add a note in the file:

```python
# app/agents/transactions_labeler/enums.py
# NOTE: Keep in sync with app/models/transaction.CategoryEnum.
# This copy exists so the agent layer does not import from the DB model layer.
from enum import Enum


class CategoryEnum(str, Enum):
    INCOME = "Income"
    TRANSPORTATION = "Transportation"
    # ... (copy all 20 values verbatim from app/models/transaction.py)
```

**Step 3: Create `state.py`**

```python
# app/agents/transactions_labeler/state.py
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.agents.transactions_labeler.models import RawTransaction, UserCategoryPreference


class CategorizationState(BaseModel):
    """LangGraph state for the transaction categorization workflow."""

    # Input
    user_id: str
    raw_transactions: List[Dict[str, Any]]
    user_preferences: UserCategoryPreference

    # Processing
    enriched_transactions: List[Dict[str, Any]]

    # Output
    categorized_transactions: List[Dict[str, Any]]
    results: List[Dict[str, Any]]
    error: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
```

**Step 4: Create `prompts/categorization.py`**

```python
# app/agents/transactions_labeler/prompts/categorization.py
"""Prompt templates for transaction categorization."""

import json
from typing import Any, Dict, List

from app.agents.transactions_labeler.enums import CategoryEnum
from app.agents.transactions_labeler.models import UserCategoryPreference


def build_categorization_prompt(
    transactions: List[Dict[str, Any]],
    user_preferences: UserCategoryPreference,
) -> str:
    """Build the OpenAI prompt for batch transaction categorization."""
    categories_desc = "\n".join(
        f"- {cat.value}" for cat in CategoryEnum
    )

    keywords_section = ""
    if user_preferences.category_keywords:
        keywords_section = "\n\nUser's Category Keywords:\n"
        for category, keywords in user_preferences.category_keywords.items():
            keywords_section += f"- {category.value}: {', '.join(keywords)}\n"

    transactions_json = json.dumps(
        [
            {
                "id": i,
                "merchant": t["normalized_merchant"],
                "amount": int(t["transaction"].get("amount", 0)),
                "description": t["transaction"].get("description", ""),
            }
            for i, t in enumerate(transactions)
        ],
        separators=(",", ":"),
    )

    return f"""You are a transaction categorizer for a personal finance app.

Available Categories:
{categories_desc}
{keywords_section}

Transactions to categorize:
{transactions_json}

For EACH transaction return ONLY a valid JSON array:
[
  {{"id": 0, "category": "Food & Groceries", "confidence": 0.95, "is_recurring": false}},
  ...
]

Use the exact category names from the list above. No other text."""
```

**Step 5: Create `nodes.py`**

Move the four node functions and helpers from `transaction_labeler.py` into this file. Key changes:
- Fix import paths (`from app.utils.` not `from utils.`)
- `format_results` now produces `TransactionCreate`-compatible dicts (the agent.py entry point converts them)

```python
# app/agents/transactions_labeler/nodes.py
"""LangGraph node functions for the transaction categorization workflow."""

import asyncio
import json
import logging
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI

from app.agents.transactions_labeler.enums import CategoryEnum
from app.agents.transactions_labeler.models import UserCategoryPreference
from app.agents.transactions_labeler.prompts.categorization import build_categorization_prompt
from app.agents.transactions_labeler.state import CategorizationState
from app.utils.http_clients import TransactionLabelerHTTPClient
from app.utils.merchant_mappings import get_common_merchant_mappings

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


def normalize_merchant_name(merchant_name: str) -> str:
    """Remove payment processor noise and normalise to Title Case."""
    if not merchant_name:
        return ""
    merchant = merchant_name.strip().split("|")[0].strip()
    upper = merchant.upper()

    if upper.startswith("PAYPAL *"):
        merchant = merchant.split("*", 1)[1].strip()
    elif upper.startswith("SUMUP  *"):
        merchant = merchant.split("*", 1)[1].strip()
    elif upper.startswith("UBR*"):
        extracted = merchant.split("*", 1)[1].strip()
        merchant = "Uber" if "UBER" in extracted.upper() else extracted
    elif upper.startswith(("LSP*", "SPC*")):
        merchant = merchant.split("*", 1)[1].strip()
    elif upper.startswith("ZETTLE_"):
        merchant = merchant[7:].strip()
    else:
        merchant = merchant.split("*")[0].strip()

    if not merchant.startswith("Amazon"):
        merchant = merchant.split("-")[0].strip()

    return merchant.title()


def _build_merchant_lookup(
    merchant_mappings: Dict[str, CategoryEnum],
) -> tuple[dict, list]:
    exact = {k.lower(): v for k, v in merchant_mappings.items()}
    partial = [(k.lower(), v) for k, v in merchant_mappings.items()]
    return exact, partial


def enrich_merchants(state: CategorizationState) -> CategorizationState:
    """Normalise merchant names and check hardcoded + user merchant mappings."""
    # Merge common mappings (base) with user overrides
    common = get_common_merchant_mappings()
    merged = {**common, **state["user_preferences"].merchant_mappings}
    exact, partial = _build_merchant_lookup(merged)

    enriched = []
    for tx in state["raw_transactions"]:
        merchant = normalize_merchant_name(tx.get("merchant", ""))
        merchant_lower = merchant.lower()

        manual_category = exact.get(merchant_lower)
        if manual_category is None:
            for mapped, cat in partial:
                if mapped in merchant_lower or merchant_lower in mapped:
                    manual_category = cat
                    break

        enriched.append({
            "transaction": tx,
            "normalized_merchant": merchant,
            "manual_category": manual_category,
            "has_manual_mapping": manual_category is not None,
        })

    return {**state, "enriched_transactions": enriched}


async def categorize_batch(state: CategorizationState) -> CategorizationState:
    """Batch-categorize transactions via OpenAI, deduplicating by merchant."""
    need_categorization = [e for e in state["enriched_transactions"] if not e["has_manual_mapping"]]
    manually_mapped = [e for e in state["enriched_transactions"] if e["has_manual_mapping"]]

    # Deduplicate by merchant to reduce LLM calls
    merchant_to_txs: Dict[str, list] = {}
    unique_merchants = []
    for e in need_categorization:
        m = e["normalized_merchant"]
        if m not in merchant_to_txs:
            merchant_to_txs[m] = []
            unique_merchants.append(e)
        merchant_to_txs[m].append(e)

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
    semaphore = TransactionLabelerHTTPClient.get_semaphore()

    async def process_batch(idx: int, batch: list):
        try:
            prompt = build_categorization_prompt(batch, state["user_preferences"])
            async with semaphore:
                response = await llm.ainvoke(prompt)
            text = response.content
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            parsed = json.loads(text.strip())
            return {
                batch[r["id"]]["normalized_merchant"]: {
                    "category": r["category"],
                    "confidence_score": float(r["confidence"]),
                    "is_recurring": bool(r.get("is_recurring", False)),
                }
                for r in parsed
            }, None
        except Exception as exc:
            return None, f"Batch {idx}: {exc}"

    batches = [unique_merchants[i:i + BATCH_SIZE] for i in range(0, len(unique_merchants), BATCH_SIZE)]
    batch_results = await asyncio.gather(*[process_batch(i, b) for i, b in enumerate(batches)])

    merchant_categories: Dict[str, Any] = {}
    errors = []
    for res, err in batch_results:
        if err:
            errors.append(err)
        if res:
            merchant_categories.update(res)

    if errors:
        return {**state, "error": f"Categorization errors: {'; '.join(errors[:3])}", "categorized_transactions": [], "results": []}

    categorized = []
    for e in need_categorization:
        info = merchant_categories.get(e["normalized_merchant"])
        if info:
            categorized.append({"transaction": e["transaction"], **info})
        else:
            categorized.append({
                "transaction": e["transaction"],
                "category": CategoryEnum.MISCELLANEOUS.value,
                "confidence_score": 0.3,
                "is_recurring": False,
            })

    for e in manually_mapped:
        categorized.append({
            "transaction": e["transaction"],
            "category": e["manual_category"].value,
            "confidence_score": 1.0,
            "is_recurring": False,
        })

    return {**state, "categorized_transactions": categorized}


def validate_categorization(state: CategorizationState) -> CategorizationState:
    """Log confidence stats — no filtering, all rows pass through."""
    txs = state["categorized_transactions"]
    low = sum(1 for t in txs if t["confidence_score"] < 0.6)
    stats = {
        "total": len(txs),
        "high_confidence": len(txs) - low,
        "low_confidence": low,
        "recurring": sum(1 for t in txs if t["is_recurring"]),
        "avg_confidence": sum(t["confidence_score"] for t in txs) / len(txs) if txs else 0,
    }
    logger.info("categorization_stats: %s", stats)
    return {**state, "stats": stats}


def format_results(state: CategorizationState) -> CategorizationState:
    """Format categorized transactions as TransactionCreate-compatible dicts."""
    results = [
        {
            "date": tx["transaction"].get("date"),
            "merchant": tx["transaction"].get("merchant"),
            "amount": tx["transaction"].get("amount"),
            "description": tx["transaction"].get("description"),
            "original_category": tx["transaction"].get("original_category"),
            "category": tx["category"],
            "confidence_score": tx["confidence_score"],
            "is_recurring": tx["is_recurring"],
        }
        for tx in state["categorized_transactions"]
    ]
    return {**state, "results": results}
```

**Step 6: Create `agent.py`**

```python
# app/agents/transactions_labeler/agent.py
"""Public entry point for the transaction labeler workflow."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.shared.observability.langfuse import create_graph_config
from app.agents.transactions_labeler.models import UserCategoryPreference
from app.agents.transactions_labeler.nodes import (
    categorize_batch,
    enrich_merchants,
    format_results,
    validate_categorization,
)
from app.agents.transactions_labeler.state import CategorizationState
from app.schemas.transaction import TransactionCreate
from app.models.transaction import CategoryEnum


def _build_graph():
    workflow = StateGraph(CategorizationState)
    workflow.add_node("enrich", enrich_merchants)
    workflow.add_node("categorize", categorize_batch)
    workflow.add_node("validate", validate_categorization)
    workflow.add_node("format", format_results)
    workflow.add_edge(START, "enrich")
    workflow.add_edge("enrich", "categorize")
    workflow.add_edge("categorize", "validate")
    workflow.add_edge("validate", "format")
    workflow.add_edge("format", END)
    return workflow.compile()


_graph = _build_graph()


async def run_labeler(
    transactions: List[Dict[str, Any]],
    user_id: str,
    user_preferences: Optional[UserCategoryPreference] = None,
) -> List[TransactionCreate]:
    """Run the transaction categorization workflow.

    Args:
        transactions: List of dicts with keys: date, merchant, amount,
                      description (optional), original_category (optional).
                      Date must be an ISO string or datetime.
        user_id: Authenticated user's ID (used for Langfuse tracing).
        user_preferences: Optional user preferences. Defaults to empty
                          (common merchant mappings still apply).

    Returns:
        List of TransactionCreate objects ready for TransactionService.import_from_csv().
    """
    if not transactions:
        return []

    if user_preferences is None:
        user_preferences = UserCategoryPreference(user_id=user_id)

    initial_state = {
        "user_id": user_id,
        "raw_transactions": transactions,
        "user_preferences": user_preferences,
        "enriched_transactions": [],
        "categorized_transactions": [],
        "results": [],
        "error": None,
        "stats": None,
    }

    trace_id = str(uuid.uuid4())
    config = create_graph_config(conversation_id=trace_id, user_id=user_id)

    final_state = await _graph.ainvoke(initial_state, config=config)

    if final_state.get("error"):
        raise RuntimeError(f"Labeler failed: {final_state['error']}")

    labeled: List[TransactionCreate] = []
    for r in final_state["results"]:
        # Normalise date to datetime
        date_val = r["date"]
        if isinstance(date_val, str):
            date_val = datetime.fromisoformat(date_val)
        if date_val.tzinfo is None:
            date_val = date_val.replace(tzinfo=timezone.utc)

        labeled.append(
            TransactionCreate(
                date=date_val,
                merchant=r["merchant"],
                amount=Decimal(str(r["amount"])),
                category=CategoryEnum(r["category"]),
                description=r.get("description"),
                original_category=r.get("original_category"),
                is_recurring=r.get("is_recurring", False),
                confidence_score=float(r.get("confidence_score", 0.5)),
            )
        )

    return labeled
```

**Step 7: Create `__init__.py`**

```python
# app/agents/transactions_labeler/__init__.py
from app.agents.transactions_labeler.agent import run_labeler

__all__ = ["run_labeler"]
```

**Step 8: Delete old folder**

```bash
rm -rf app/agents/transactios_labeler/
```

Verify no remaining imports of the old path:

```bash
grep -r "transactios_labeler" app/
```

Expected: no output.

**Step 9: Smoke test**

```bash
python -c "from app.agents.transactions_labeler import run_labeler; print('OK')"
```

Expected: `OK`

**Step 10: Commit**

```bash
git add app/agents/transactions_labeler/
git rm -r app/agents/transactios_labeler/
git commit -m "refactor: split transactions_labeler agent into multi-file structure, fix typo, add Langfuse"
```

---

### Task 10: Upload Endpoint (`POST /transactions/upload`)

**Files:**
- Modify: `app/api/v1/transactions.py`
- Create: `tests/integration/api/test_transactions_upload.py`

**Step 1: Write failing integration tests for the upload endpoint**

```python
# tests/integration/api/test_transactions_upload.py
import io
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

CSV_VALID = b"Buchungsdatum,Empfaenger,Betrag,Verwendungszweck\n2026-01-15,Netflix,12.99,Subscription\n"
CSV_MISSING_COL = b"OnlyOneColumn\nValue\n"
CSV_WRONG_TYPE = b"not a csv"


@pytest.fixture
def mock_mapping_proposal():
    return {
        "Buchungsdatum": "date",
        "Empfaenger": "merchant",
        "Betrag": "amount",
        "Verwendungszweck": "description",
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upload_valid_csv_returns_proposal(client, auth_headers, mock_mapping_proposal):
    with patch(
        "app.api.v1.transactions.CSVMappingService.get_profile",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.api.v1.transactions._propose_column_mapping",
        new_callable=AsyncMock,
        return_value=mock_mapping_proposal,
    ):
        response = await client.post(
            "/api/v1/transactions/upload",
            headers=auth_headers,
            files={"file": ("transactions.csv", io.BytesIO(CSV_VALID), "text/csv")},
        )

    assert response.status_code == 200
    body = response.json()
    assert "mapping_id" in body
    assert body["proposed_mapping"] == mock_mapping_proposal
    assert len(body["sample_rows"]) <= 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upload_wrong_file_type_returns_422(client, auth_headers):
    response = await client.post(
        "/api/v1/transactions/upload",
        headers=auth_headers,
        files={"file": ("data.xlsx", io.BytesIO(CSV_WRONG_TYPE), "application/octet-stream")},
    )
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upload_exceeds_row_cap_returns_422(client, auth_headers, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CSV_MAX_ROWS", 1)

    big_csv = b"Date,Merchant,Amount\n" + b"2026-01-01,Shop,10.00\n" * 2  # 2 rows, cap is 1

    with patch(
        "app.api.v1.transactions.CSVMappingService.get_profile",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = await client.post(
            "/api/v1/transactions/upload",
            headers=auth_headers,
            files={"file": ("big.csv", io.BytesIO(big_csv), "text/csv")},
        )

    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upload_uses_cached_mapping_when_available(client, auth_headers, mock_mapping_proposal):
    from app.models.csv_mapping_profile import CSVMappingProfile
    from datetime import UTC, datetime

    cached_profile = CSVMappingProfile(
        user_id="user_test_123456789",
        column_hash="somehash",
        mapping=mock_mapping_proposal,
        last_used_at=datetime.now(UTC),
    )

    with patch(
        "app.api.v1.transactions.CSVMappingService.get_profile",
        new_callable=AsyncMock,
        return_value=cached_profile,
    ), patch(
        "app.api.v1.transactions._propose_column_mapping",
        new_callable=AsyncMock,
    ) as mock_openai:
        response = await client.post(
            "/api/v1/transactions/upload",
            headers=auth_headers,
            files={"file": ("transactions.csv", io.BytesIO(CSV_VALID), "text/csv")},
        )

    assert response.status_code == 200
    mock_openai.assert_not_called()  # OpenAI was NOT called — cached mapping used


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upload_unauthenticated_returns_401(unauthenticated_client):
    response = await unauthenticated_client.post(
        "/api/v1/transactions/upload",
        files={"file": ("transactions.csv", io.BytesIO(CSV_VALID), "text/csv")},
    )
    assert response.status_code == 401
```

**Step 2: Run to confirm FAIL**

```bash
pytest tests/integration/api/test_transactions_upload.py::test_upload_unauthenticated_returns_401 -v
```

Expected: `404 Not Found` (endpoint does not exist yet)

**Step 3: Implement the upload endpoint**

In `app/api/v1/transactions.py`, add these imports at the top:

```python
import io
from fastapi import HTTPException, UploadFile, File

import polars as pl
from langchain_openai import ChatOpenAI

from app.schemas.csv_upload import CSVUploadProposalResponse
from app.services.csv_mapping.service import CSVMappingService
from app.core.config import settings
```

Add the private helper function (outside the router):

```python
async def _propose_column_mapping(columns: list[str], sample_row: dict) -> dict[str, str]:
    """Call OpenAI to map CSV column names to transaction schema fields."""
    schema_fields = ["date", "merchant", "amount", "description", "original_category", "is_recurring", "ignore"]
    prompt = f"""You are a column mapping assistant for a personal finance app.

Map each CSV column to one of these schema fields: {schema_fields}

Use "ignore" for columns that don't map to any field.
Required fields that MUST be mapped: date, merchant, amount.

CSV columns: {columns}
Sample row values: {sample_row}

Return ONLY a JSON object like:
{{"Buchungsdatum": "date", "Empfaenger": "merchant", "Betrag": "amount", "Notiz": "ignore"}}"""

    llm = ChatOpenAI(model=settings.llm.DEFAULT_LLM_MODEL, temperature=0)
    response = await llm.ainvoke(prompt)
    text = response.content.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    import json
    return json.loads(text)
```

Add the endpoint **before** the `POST ""` (create transaction) route — insert after the batch routes section comment, before `# ── Collection routes`:

```python
@router.post(
    "/upload",
    response_model=CSVUploadProposalResponse,
    summary="Upload CSV — step 1: propose column mapping",
    description="Validate the file and return a proposed column→field mapping "
                "for user review. Uses a cached mapping if the same column set "
                "was uploaded before.",
)
@limiter.limit("10/minute")
async def upload_csv(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    file: UploadFile = File(...),
) -> CSVUploadProposalResponse:
    # 1. Validate file type
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=422, detail="Only .csv files are accepted.")

    raw_bytes = await file.read()
    csv_text = raw_bytes.decode("utf-8", errors="replace")

    # 2. Parse with Polars to get columns + row count
    try:
        df = pl.read_csv(io.StringIO(csv_text))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse CSV: {exc}")

    columns = df.columns

    # 3. Check row cap
    if len(df) > settings.CSV_MAX_ROWS:
        raise HTTPException(
            status_code=422,
            detail=f"CSV exceeds the {settings.CSV_MAX_ROWS}-row limit ({len(df)} rows).",
        )

    # 4. Check for cached mapping
    column_hash = CSVMappingService.compute_column_hash(columns)
    cached_profile = await CSVMappingService.get_profile(db, user.id, column_hash)

    if cached_profile:
        proposed_mapping = cached_profile.mapping
    else:
        # 5. Call OpenAI to propose mapping
        sample_row = df.head(1).to_dicts()[0] if len(df) > 0 else {}
        proposed_mapping = await _propose_column_mapping(columns, sample_row)

        # 6. Validate required fields are mapped
        mapped_fields = set(proposed_mapping.values())
        required = {"date", "merchant", "amount"}
        missing = required - mapped_fields
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Required columns could not be mapped: {missing}. "
                       f"Please ensure your CSV contains date, merchant, and amount columns.",
            )

    # 7. Create upload session (stores raw CSV for confirm step)
    session = await CSVMappingService.create_session(
        db=db,
        user_id=user.id,
        proposed_mapping=proposed_mapping,
        csv_content=csv_text,
    )

    # 8. Sample rows for display
    sample_rows = df.head(3).to_dicts()

    return CSVUploadProposalResponse(
        mapping_id=session.mapping_id,
        proposed_mapping=proposed_mapping,
        sample_rows=sample_rows,
    )
```

**Step 4: Run tests — confirm key ones PASS**

```bash
pytest tests/integration/api/test_transactions_upload.py \
       -k "not confirm" -v
```

Expected: at minimum `test_upload_unauthenticated_returns_401` passes (others may need auth mock setup — verify against existing transaction integration tests for the auth pattern).

**Step 5: Commit**

```bash
git add app/api/v1/transactions.py app/schemas/csv_upload.py \
        tests/integration/api/test_transactions_upload.py
git commit -m "feat: add POST /transactions/upload endpoint (step 1)"
```

---

### Task 11: Confirm Endpoint (`POST /transactions/upload/{mapping_id}/confirm`)

**Files:**
- Modify: `app/api/v1/transactions.py`
- Modify: `tests/integration/api/test_transactions_upload.py`

**Step 1: Write failing integration tests**

Add to `tests/integration/api/test_transactions_upload.py`:

```python
CSV_TWO_ROWS = (
    b"Buchungsdatum,Empfaenger,Betrag,Verwendungszweck\n"
    b"2026-01-15,Netflix,12.99,Subscription\n"
    b"2026-01-16,Spotify,9.99,Music\n"
)

MAPPING = {
    "Buchungsdatum": "date",
    "Empfaenger": "merchant",
    "Betrag": "amount",
    "Verwendungszweck": "description",
}

LABELED_ROWS_MOCK = []  # filled in fixture below


@pytest.fixture
def labeled_rows():
    from datetime import datetime, timezone
    from decimal import Decimal
    from app.schemas.transaction import TransactionCreate
    from app.models.transaction import CategoryEnum

    return [
        TransactionCreate(
            date=datetime(2026, 1, 15, tzinfo=timezone.utc),
            merchant="Netflix",
            amount=Decimal("12.99"),
            category=CategoryEnum.MEDIA_ELECTRONICS,
            confidence_score=0.95,
        ),
        TransactionCreate(
            date=datetime(2026, 1, 16, tzinfo=timezone.utc),
            merchant="Spotify",
            amount=Decimal("9.99"),
            category=CategoryEnum.MEDIA_ELECTRONICS,
            confidence_score=0.95,
        ),
    ]


def make_session(csv_content: bytes, mapping: dict):
    from datetime import UTC, datetime, timedelta
    from app.models.csv_upload_session import CSVUploadSession

    return CSVUploadSession(
        user_id="user_test_123456789",
        mapping_id="test-mapping-uuid",
        proposed_mapping=mapping,
        csv_content=csv_content.decode(),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_confirm_valid_csv_imports_rows(client, auth_headers, labeled_rows):
    session = make_session(CSV_TWO_ROWS, MAPPING)

    with patch(
        "app.api.v1.transactions.CSVMappingService.get_session",
        new_callable=AsyncMock,
        return_value=session,
    ), patch(
        "app.api.v1.transactions.run_labeler",
        new_callable=AsyncMock,
        return_value=labeled_rows,
    ), patch(
        "app.api.v1.transactions.CSVMappingService.save_profile",
        new_callable=AsyncMock,
    ), patch(
        "app.api.v1.transactions.CSVMappingService.expire_session",
        new_callable=AsyncMock,
    ):
        response = await client.post(
            "/api/v1/transactions/upload/test-mapping-uuid/confirm",
            headers=auth_headers,
            json={"confirmed_mapping": MAPPING},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 2
    assert body["skipped"] == 0
    assert body["errors"] == []


@pytest.mark.integration
@pytest.mark.asyncio
async def test_confirm_second_upload_skips_duplicates(client, auth_headers, labeled_rows, db_session):
    """Uploading the same file twice → second upload: imported=0, skipped=2."""
    from app.services.transaction.service import TransactionService

    # Pre-insert the transactions so their fingerprints exist in DB
    for row in labeled_rows:
        await TransactionService.create(db_session, "user_test_123456789", row)
    await db_session.flush()

    session = make_session(CSV_TWO_ROWS, MAPPING)

    with patch(
        "app.api.v1.transactions.CSVMappingService.get_session",
        new_callable=AsyncMock,
        return_value=session,
    ), patch(
        "app.api.v1.transactions.run_labeler",
        new_callable=AsyncMock,
        return_value=labeled_rows,
    ), patch(
        "app.api.v1.transactions.CSVMappingService.save_profile",
        new_callable=AsyncMock,
    ), patch(
        "app.api.v1.transactions.CSVMappingService.expire_session",
        new_callable=AsyncMock,
    ):
        response = await client.post(
            "/api/v1/transactions/upload/test-mapping-uuid/confirm",
            headers=auth_headers,
            json={"confirmed_mapping": MAPPING},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 0
    assert body["skipped"] == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_confirm_expired_session_returns_404(client, auth_headers):
    with patch(
        "app.api.v1.transactions.CSVMappingService.get_session",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = await client.post(
            "/api/v1/transactions/upload/nonexistent-uuid/confirm",
            headers=auth_headers,
            json={"confirmed_mapping": MAPPING},
        )

    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_confirm_bad_rows_collected_in_errors(client, auth_headers):
    csv_with_bad_row = (
        b"Date,Merchant,Amount\n"
        b"2026-01-15,Netflix,12.99\n"
        b"not-a-date,Spotify,bad-amount\n"  # bad row
    )
    mapping = {"Date": "date", "Merchant": "merchant", "Amount": "amount"}
    session = make_session(csv_with_bad_row, mapping)

    with patch(
        "app.api.v1.transactions.CSVMappingService.get_session",
        new_callable=AsyncMock,
        return_value=session,
    ), patch(
        "app.api.v1.transactions.run_labeler",
        new_callable=AsyncMock,
        return_value=[],  # labeler returns empty (only bad row skipped)
    ), patch(
        "app.api.v1.transactions.CSVMappingService.save_profile",
        new_callable=AsyncMock,
    ), patch(
        "app.api.v1.transactions.CSVMappingService.expire_session",
        new_callable=AsyncMock,
    ):
        response = await client.post(
            "/api/v1/transactions/upload/test-mapping-uuid/confirm",
            headers=auth_headers,
            json={"confirmed_mapping": mapping},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["errors"]) >= 1
```

**Step 2: Run to confirm FAIL**

```bash
pytest tests/integration/api/test_transactions_upload.py::test_confirm_expired_session_returns_404 -v
```

Expected: `404 Not Found` (endpoint does not exist)

**Step 3: Implement the confirm endpoint**

Add these imports to `app/api/v1/transactions.py`:

```python
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone

from app.agents.transactions_labeler import run_labeler
from app.schemas.csv_upload import CSVConfirmRequest, CSVUploadResponse
from app.services.transaction.service import transaction_service
```

Add the confirm endpoint — place it immediately after the upload endpoint:

```python
@router.post(
    "/upload/{mapping_id}/confirm",
    response_model=CSVUploadResponse,
    summary="Upload CSV — step 2: confirm mapping and import",
    description="Re-parse the cached CSV using the confirmed column mapping, "
                "run AI categorization, deduplicate, and bulk-insert.",
)
@limiter.limit("10/minute")
async def confirm_csv_upload(
    request: Request,
    mapping_id: str,
    body: CSVConfirmRequest,
    db: DbSession,
    user: CurrentUser,
) -> CSVUploadResponse:
    # 1. Retrieve session
    session = await CSVMappingService.get_session(db, mapping_id, user.id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Upload session not found or expired. Please re-upload the file.",
        )

    confirmed_mapping = body.confirmed_mapping

    # 2. Validate required fields present in confirmed mapping
    mapped_fields = set(confirmed_mapping.values())
    required = {"date", "merchant", "amount"}
    missing = required - mapped_fields
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Confirmed mapping is missing required fields: {missing}",
        )

    # 3. Re-parse full CSV using confirmed mapping
    df = pl.read_csv(io.StringIO(session.csv_content))
    rows_raw = df.to_dicts()

    # 4. Validate and transform rows — collect errors, skip bad rows
    valid_rows: list[dict] = []
    errors: list[str] = []

    for i, row in enumerate(rows_raw, start=2):  # row 1 is header
        # Map CSV column names to schema field names
        mapped: dict = {}
        for csv_col, field in confirmed_mapping.items():
            if field != "ignore" and csv_col in row:
                mapped[field] = row[csv_col]

        # Validate date
        try:
            raw_date = mapped.get("date", "")
            if isinstance(raw_date, str):
                date_val = datetime.fromisoformat(raw_date)
            elif isinstance(raw_date, datetime):
                date_val = raw_date
            else:
                raise ValueError(f"unrecognised date type: {type(raw_date)}")
            if date_val.tzinfo is None:
                date_val = date_val.replace(tzinfo=timezone.utc)
            mapped["date"] = date_val.isoformat()
        except (ValueError, TypeError) as exc:
            errors.append(f"Row {i}: invalid date {repr(mapped.get('date'))} — {exc}")
            continue

        # Validate amount
        try:
            mapped["amount"] = float(Decimal(str(mapped.get("amount", ""))))
        except (InvalidOperation, ValueError, TypeError):
            errors.append(f"Row {i}: invalid amount {repr(mapped.get('amount'))}")
            continue

        # Validate merchant
        if not mapped.get("merchant"):
            errors.append(f"Row {i}: merchant is empty")
            continue

        valid_rows.append(mapped)

    # 5. Run labeler on valid rows
    labeled = await run_labeler(transactions=valid_rows, user_id=user.id)

    # 6. Bulk import with fingerprint dedup
    imported, skipped, _ = await transaction_service.import_from_csv(db, user.id, labeled)

    # 7. Persist/update the mapping profile
    column_hash = CSVMappingService.compute_column_hash(list(confirmed_mapping.keys()))
    await CSVMappingService.save_profile(db, user.id, column_hash, confirmed_mapping)

    # 8. Expire the session
    await CSVMappingService.expire_session(db, session)

    return CSVUploadResponse(imported=imported, skipped=skipped, errors=errors)
```

**Step 4: Run all upload tests**

```bash
pytest tests/integration/api/test_transactions_upload.py -v
```

Expected: all tests pass (some may require auth fixture setup matching the existing integration tests — mirror the pattern from `tests/integration/api/test_transactions.py` if tests fail due to auth).

**Step 5: Run the full test suite to confirm no regressions**

```bash
pytest tests/ -v --ignore=tests/integration/api/test_transactions_upload.py -x
```

Expected: all existing tests still pass.

**Step 6: Commit**

```bash
git add app/api/v1/transactions.py tests/integration/api/test_transactions_upload.py
git commit -m "feat: add POST /transactions/upload/{mapping_id}/confirm endpoint (step 2)"
```

---

## Summary

| Task | Scope |
|------|-------|
| 1 | DB models: fingerprint on Transaction, CSVMappingProfile, CSVUploadSession |
| 2 | Alembic migration |
| 3 | Settings: CSV_MAX_ROWS, UPLOAD_SESSION_TTL_MINUTES |
| 4 | compute_fingerprint() — TDD |
| 5 | TransactionService.create() fingerprint — TDD |
| 6 | import_from_csv() — TDD |
| 7 | CSVMappingService — TDD |
| 8 | New schemas |
| 9 | Refactor transactions_labeler (typo fix, multi-file, Langfuse) |
| 10 | Upload endpoint + integration tests |
| 11 | Confirm endpoint + integration tests |
