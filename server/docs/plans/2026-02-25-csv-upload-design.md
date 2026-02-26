# CSV Transaction Import — Design

**Date:** 2026-02-25
**Branch:** upload-csv
**Status:** Approved

---

## Overview

Allow users to bulk-import transactions from a CSV file via two new endpoints. The flow is two-step: first the file is uploaded and a column mapping is proposed (via OpenAI), then the user confirms the mapping and the import runs. This handles arbitrary bank CSV formats without requiring a rigid column structure.

---

## End-to-End Flow

```
POST /transactions/upload
  │
  ├─ Validate file (extension, ≤3000 rows, not empty)
  ├─ Parse CSV headers only
  ├─ Look up CSVMappingProfile by (user_id, column_hash)
  │   ├─ HIT  → return cached mapping, skip OpenAI call
  │   └─ MISS → call OpenAI to propose column→field mapping
  └─ Persist CSVUploadSession (raw bytes + proposed mapping, TTL 30min)
     Return: mapping_id, proposed_mapping, sample_rows (first 3)

POST /transactions/upload/{mapping_id}/confirm
  │
  ├─ Retrieve CSVUploadSession (404 if expired/missing)
  ├─ Re-parse full CSV using confirmed mapping
  ├─ Validate rows → collect errors, skip bad rows
  ├─ Compute SHA-256 fingerprint per valid row
  ├─ Bulk-fetch all user fingerprints → filter duplicates → count skipped
  ├─ Run transaction labeler on remaining rows
  ├─ Bulk-insert labeled transactions (with fingerprints)
  ├─ Persist/update CSVMappingProfile (create or update last_used_at)
  └─ Return: CSVUploadResponse {imported, skipped, errors}
```

**OpenAI mapping call:** given CSV column names + a sample row, returns a JSON object mapping each column to one of: `date`, `merchant`, `amount`, `description`, `original_category`, `is_recurring`, or `ignore`. If `date`, `merchant`, or `amount` cannot be mapped, returns `422` before issuing a `mapping_id`.

---

## Data Models

### `Transaction` — one new field

```python
fingerprint: Optional[str] = Field(default=None, index=True)
```

- Nullable, indexed
- Computed for **all** new transactions (manual entry + CSV import) using SHA-256
- No DB uniqueness constraint — dedup logic lives only in the CSV import path
- Formula: `SHA-256("{user_id}|{date.isoformat()}|{merchant.strip().lower()}|{amount:.2f}|{(description or '').strip().lower()}")`
- Description included because merchants like PayPal use it to distinguish recipients

### `CSVMappingProfile` (new table)

```python
class CSVMappingProfile(BaseModel, table=True):
    id: Optional[int]
    user_id: str          # FK → User, indexed
    column_hash: str      # SHA-256 of sorted frozenset of CSV column names
    mapping: dict         # JSON: {"Betrag": "amount", "Name": "merchant", ...}
    last_used_at: datetime
```

Lookup key: `(user_id, column_hash)`. Supports multiple profiles per user (different banks).

### `CSVUploadSession` (new table)

```python
class CSVUploadSession(BaseModel, table=True):
    id: Optional[int]
    user_id: str
    mapping_id: str       # UUID, used in confirm URL
    proposed_mapping: dict
    csv_bytes: bytes      # Raw file cached for confirm step
    expires_at: datetime  # NOW + settings.UPLOAD_SESSION_TTL_MINUTES
```

Ephemeral. Cleaned up after confirm or expiry. Avoids requiring the client to re-upload the file.

### Alembic migration (new file)

- Add `fingerprint` column to `transaction` table (nullable VARCHAR, indexed)
- Create `csv_mapping_profile` table
- Create `csv_upload_session` table

---

## API

### `POST /api/v1/transactions/upload`

```
Content-Type: multipart/form-data
Rate limit: 10/minute
Auth: required

Request:  file (UploadFile, .csv)

Response 200:
{
  "mapping_id": "uuid",
  "proposed_mapping": {
    "Buchungsdatum":    "date",
    "Empfänger":        "merchant",
    "Betrag":           "amount",
    "Verwendungszweck": "description",
    "Kategorie":        "original_category"
  },
  "sample_rows": [...]   // first 3 rows for user to visually verify
}

Response 422: wrong file type | exceeds CSV_MAX_ROWS | required column unmappable
```

### `POST /api/v1/transactions/upload/{mapping_id}/confirm`

```
Content-Type: application/json
Rate limit: 10/minute
Auth: required

Request:
{
  "confirmed_mapping": {
    "Buchungsdatum": "date",
    ...               // user may have corrected the proposal
  }
}

Response 200:
{
  "imported": 42,
  "skipped":  8,
  "errors":   ["Row 3: invalid date '99-99-99'"]
}

Response 404: mapping_id not found or expired
Response 422: confirmed_mapping missing required fields
```

### Error table

| Scenario | Response |
|---|---|
| File is not `.csv` | `422` |
| CSV exceeds `CSV_MAX_ROWS` | `422` |
| Required column can't be mapped | `422` |
| `mapping_id` expired or not found | `404` |
| Individual row has bad data | Row skipped, error collected, `200` |
| Duplicate fingerprint | Row skipped, counted in `skipped` |
| Unauthenticated | `401` |

---

## Settings

Two new configurable values in `app/core/config.py`:

```python
CSV_MAX_ROWS: int = 3000
UPLOAD_SESSION_TTL_MINUTES: int = 30
```

Both overridable per environment. Tests set `CSV_MAX_ROWS=10` to avoid large fixtures.

---

## Transaction Labeler Refactor

Current `app/agents/transactios_labeler/` is monolithic and needs splitting. Folder typo is fixed.

**New structure:**

```
app/agents/transactions_labeler/
├── agent.py          # LangGraph graph definition + public entry point
├── state.py          # CategorizationState, CategorizationConfig
├── nodes.py          # enrich_merchants, categorize_batch, validate, format_results
├── models.py         # RawTransaction, UserCategoryPreference
├── enums.py          # CategoryEnum (unchanged)
├── prompts/
│   └── categorization.py
└── __init__.py
```

**Public entry point:**

```python
async def run_labeler(
    transactions: list[dict],
    user_id: str,
    user_preferences: Optional[UserCategoryPreference] = None,
) -> list[TransactionCreate]
```

- No file I/O — receives plain dicts, returns `TransactionCreate` objects ready for `TransactionService.create()`
- `CategorizedTransaction` model eliminated — labeler output is `TransactionCreate` directly
- `UserCategoryPreference` kept as empty shell for future use; labeler runs on hardcoded common merchant mappings only (no user-level preferences in MVP)
- Langfuse observability added via `app/agents/shared/observability/` (same pattern as insights agent)

---

## Services

### Modified: `TransactionService`

```python
# Modified: compute and store fingerprint on every create
async def create(db, user_id, data: TransactionCreate) -> Transaction

# New static method
@staticmethod
def compute_fingerprint(user_id, date, merchant, amount, description) -> str

# New static method
@staticmethod
async def import_from_csv(
    db, user_id, rows: list[TransactionCreate]
) -> tuple[int, int, list[str]]   # imported, skipped, errors
```

### New: `CSVMappingService` (`app/services/csv_mapping/service.py`)

- `get_profile(db, user_id, column_hash)` → `Optional[CSVMappingProfile]`
- `save_profile(db, user_id, column_hash, mapping)` → `CSVMappingProfile`
- `create_session(db, user_id, mapping_id, mapping, csv_bytes)` → `CSVUploadSession`
- `get_session(db, mapping_id, user_id)` → `Optional[CSVUploadSession]`
- `expire_session(db, session)` → `None`

---

## Testing

### Unit (`tests/unit/services/test_transaction_service.py`)

- `compute_fingerprint` is deterministic
- `compute_fingerprint` changes when any individual field changes
- `import_from_csv` skips rows with existing fingerprints
- `import_from_csv` inserts all rows when no duplicates exist
- `import_from_csv` returns correct `imported/skipped/errors` counts

### Integration (`tests/integration/api/test_transactions_upload.py`)

- Valid CSV → correct `imported` count, rows in DB
- Upload same file twice → second: `imported=0`, `skipped=N`
- Partial overlap → correct counts on both sides
- Wrong file type → `422`
- CSV exceeds `CSV_MAX_ROWS` (set to 10 in test env) → `422`
- Missing mappable required column → `422`
- Rows with bad data → `200` with `errors[]`, valid rows imported
- Unauthenticated → `401`
- `mapping_id` expired → `404`
- User corrects proposed mapping before confirming → correct mapping used
- Same column set uploaded twice → second upload reuses cached mapping (no OpenAI call)

---

## Out of Scope (MVP)

- Post-import insights regeneration (manual refresh via existing endpoint)
- User-level category preferences and correction history
- Background job / async processing (synchronous with 3000-row cap is sufficient)
- Fingerprint backfill for legacy transactions (no existing data at time of implementation)
