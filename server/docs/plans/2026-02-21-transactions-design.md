# Transactions Feature Design

**Date:** 2026-02-21
**Status:** Approved

---

## Overview

Full CRUD operations for financial transactions, exposed via a versioned REST API. Business logic is handled in a stateless service class consistent with existing codebase patterns. Includes paginated listing with filters, plus batch update and batch delete endpoints.

---

## Architecture

Four new files following existing project conventions:

```
app/
├── models/
│   └── transaction.py          # Transaction SQLModel + CategoryEnum
├── schemas/
│   └── transaction.py          # Request/response Pydantic schemas
├── services/
│   └── transaction_service.py  # TransactionService (stateless, @staticmethod)
└── api/v1/
    └── transactions.py         # FastAPI router, rate-limited
```

---

## Model

```python
class CategoryEnum(str, Enum):
    INCOME = "Income"
    TRANSPORTATION = "Transportation"
    SALARY = "Salary"
    HOUSEHOLD_UTILITIES = "Household & Utilities"
    TAX_FINES = "Tax & Fines"
    MISCELLANEOUS = "Miscellaneous"
    FOOD_GROCERIES = "Food & Groceries"
    FOOD_DELIVERY = "Food Delivery"
    ATM = "ATM"
    INSURANCE = "Insurances"
    SHOPPING = "Shopping"
    BARS_RESTAURANTS = "Bars & Restaurants"
    EDUCATION = "Education"
    FAMILY_FRIENDS = "Family & Friends"
    DONATIONS_CHARITY = "Donations & Charity"
    HEALTHCARE_DRUG_STORES = "Healthcare & Drug Stores"
    LEISURE_ENTERTAINMENT = "Leisure & Entertainment"
    MEDIA_ELECTRONICS = "Media & Electronics"
    SAVINGS_INVESTMENTS = "Savings & Investments"
    TRAVEL_HOLIDAYS = "Travel & Holidays"


class Transaction(SQLModel, table=True):
    # Primary & Foreign Keys
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)

    # Core Transaction Data
    date: datetime = Field(index=True)
    merchant: str
    amount: float
    description: Optional[str] = None
    original_category: Optional[str] = None

    # Categorization
    category: CategoryEnum = Field(index=True)
    confidence_score: float = Field(ge=0.0, le=1.0)

    # Recurring Detection
    is_recurring: bool = Field(default=False)

    # Soft Delete
    deleted_at: Optional[datetime] = None

    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    user: Optional["User"] = Relationship(back_populates="transactions")
```

**Key decisions:**
- `deleted_at` added for soft delete — consistent with existing `SoftDeleteMixin` pattern.
- `confidence_score` defaults to `1.0` for manually created transactions (human-verified).
- `user_id` is never accepted from the request body — always sourced from `request.state.clerk_id`.

---

## API Endpoints

All routes under `/api/v1/transactions`. Auth required. Rate-limited.

| Method   | Path       | Description                          |
|----------|------------|--------------------------------------|
| `POST`   | `/`        | Create a single transaction          |
| `GET`    | `/`        | List transactions (paginated + filtered) |
| `GET`    | `/{id}`    | Get a single transaction             |
| `PATCH`  | `/{id}`    | Partial update a single transaction  |
| `DELETE` | `/{id}`    | Soft delete a single transaction     |
| `PATCH`  | `/batch`   | Batch update multiple transactions   |
| `DELETE` | `/batch`   | Batch delete multiple transactions   |

---

## Schemas

### Request Schemas

```python
class TransactionCreate(SQLModel):
    date: datetime
    merchant: str
    amount: float
    category: CategoryEnum
    description: Optional[str] = None
    original_category: Optional[str] = None
    is_recurring: bool = False
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)

class TransactionUpdate(SQLModel):
    date: Optional[datetime] = None
    merchant: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    original_category: Optional[str] = None
    category: Optional[CategoryEnum] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_recurring: Optional[bool] = None

class BatchUpdateItem(SQLModel):
    id: int
    date: Optional[datetime] = None
    merchant: Optional[str] = None
    amount: Optional[float] = None
    description: Optional[str] = None
    original_category: Optional[str] = None
    category: Optional[CategoryEnum] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_recurring: Optional[bool] = None

class BatchUpdateRequest(SQLModel):
    items: list[BatchUpdateItem] = Field(min_length=1, max_length=100)

class BatchDeleteRequest(SQLModel):
    ids: list[int] = Field(min_length=1, max_length=100)
```

### Response Schemas

```python
class TransactionResponse(SQLModel):
    id: int
    user_id: str
    date: datetime
    merchant: str
    amount: float
    description: Optional[str]
    original_category: Optional[str]
    category: CategoryEnum
    confidence_score: float
    is_recurring: bool
    created_at: datetime
    updated_at: datetime

class TransactionListResponse(SQLModel):
    items: list[TransactionResponse]
    total: int
    offset: int
    limit: int

class BatchUpdateResponse(SQLModel):
    updated: int

class BatchDeleteResponse(SQLModel):
    deleted: int
```

**Batch response rationale:** The frontend uses optimistic updates, so the server only needs to confirm success with a count. Full item payloads would be ignored and waste bandwidth.

---

## Filtering & Pagination

```python
class TransactionFilters:
    def __init__(
        self,
        date_from: Optional[datetime] = Query(None),
        date_to: Optional[datetime] = Query(None),
        category: Optional[CategoryEnum] = Query(None),
        merchant: Optional[str] = Query(None),         # substring match
        amount_min: Optional[float] = Query(None),
        amount_max: Optional[float] = Query(None),
        is_recurring: Optional[bool] = Query(None),
        sort_by: Literal["date", "amount", "merchant"] = Query("date"),
        sort_order: Literal["asc", "desc"] = Query("desc"),
    ): ...
```

Router signature:

```python
async def list_transactions(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    filters: TransactionFilters = Depends(),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
): ...
```

`offset`/`limit` pagination supports both classic pagination and infinite scroll.

---

## Service

```python
class TransactionService:
    @staticmethod
    async def create(db, user_id: str, data: TransactionCreate) -> Transaction

    @staticmethod
    async def get(db, user_id: str, transaction_id: int) -> Transaction

    @staticmethod
    async def list(
        db, user_id: str, filters: TransactionFilters, offset: int, limit: int
    ) -> tuple[list[Transaction], int]

    @staticmethod
    async def update(
        db, user_id: str, transaction_id: int, data: TransactionUpdate
    ) -> Transaction

    @staticmethod
    async def delete(db, user_id: str, transaction_id: int) -> None

    @staticmethod
    async def batch_update(
        db, user_id: str, items: list[BatchUpdateItem]
    ) -> int  # returns count

    @staticmethod
    async def batch_delete(db, user_id: str, ids: list[int]) -> int  # returns count
```

---

## Error Handling

| Scenario | HTTP Response |
|----------|--------------|
| Transaction not found or belongs to another user | `404 Not Found` |
| Batch: any ID not found or belongs to another user | `404`, full rollback |
| Validation failure (bad amount, out-of-range score, unknown category) | `422 Unprocessable Entity` |
| Batch payload exceeds 100 items | `422 Unprocessable Entity` |
| Unauthenticated request | `401 Unauthorized` |

**Ownership:** Every query is scoped with `WHERE user_id = :user_id AND deleted_at IS NULL`. A transaction belonging to another user returns the same `404` as a missing one — no information leakage.

**`updated_at`:** Set explicitly to `datetime.utcnow()` in every update/delete service method.

**Batch atomicity:** Both batch operations are wrapped in a single DB transaction. Any failure rolls back all changes.

---

## Testing

### Unit Tests — `tests/unit/test_transaction_service.py`

No DB, no HTTP. Mock the `AsyncSession`.

| Test | Verified |
|------|----------|
| `create` with no `confidence_score` | Defaults to `1.0` |
| `update` with partial data | Unset fields unchanged; `updated_at` refreshed |
| `get` with wrong `user_id` | Raises `404` (no data leak) |
| `batch_update` with one invalid ID | Rolls back, raises `404` |
| `batch_delete` with one invalid ID | Rolls back, raises `404` |
| `list` filter logic | Correct conditions built per filter |

### Integration Tests — `tests/integration/test_transactions_api.py`

Real async DB + `AsyncClient`. Full stack: router → service → DB → response.

| Test | Verified |
|------|----------|
| `POST /` | Record exists in DB; response matches input |
| `GET /` with filters | Returns only matching records; pagination offsets correct |
| `GET /{id}` cross-user | User B cannot fetch User A's transaction (`404`) |
| `PATCH /{id}` | DB row updated; `updated_at` changed |
| `DELETE /{id}` | `deleted_at` set; record excluded from subsequent `GET /` |
| `PATCH /batch` partial failure | DB unchanged after rollback |
| `DELETE /batch` | Returns correct `deleted` count; records excluded from listing |
| No auth header | Returns `401` |
| `confidence_score` out of range | Returns `422` |
| Batch payload > 100 items | Returns `422` |
