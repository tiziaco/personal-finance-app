# CSV Upload Improvements — Smarter Sampling + Manual Mapping Support

**Date:** 2026-02-25
**Branch:** upload-csv
**Status:** Approved

**Goal:** Fix column mapping quality by selecting representative rows for the LLM prompt, and expose the metadata the frontend needs to render an editable mapping UI.

**Architecture:** Two independent improvements applied at the `POST /api/v1/transactions/upload` endpoint.
(1) A greedy row-selection algorithm replaces `df.head(1)` with rows that maximise non-null column coverage — so sparse columns like `Payment Reference` appear in the LLM prompt.
(2) `CSVUploadProposalResponse` gains two new fields (`available_fields`, `column_null_rates`) that give the frontend everything it needs to render per-column dropdowns with null-rate warnings.
The confirm step is already correct — `confirmed_mapping` in `CSVConfirmRequest` can be any mapping the client sends, so no backend changes are needed there.

**Tech Stack:** Polars (DataFrame ops), FastAPI, Pydantic/SQLModel, pytest-asyncio

---

### Task 1: `pick_representative_sample()` — TDD

**Files:**
- Create: `app/utils/csv_utils.py`
- Test: `tests/unit/utils/test_csv_utils.py`

**Step 1: Write the failing tests**

```python
# tests/unit/utils/test_csv_utils.py
import polars as pl
import pytest

from app.utils.csv_utils import pick_representative_sample


def test_empty_dataframe_returns_empty():
    df = pl.DataFrame({"date": [], "amount": []})
    assert pick_representative_sample(df, n=3) == []


def test_fewer_rows_than_n_returns_all():
    df = pl.DataFrame({"date": ["2024-01-01"], "amount": [1.0]})
    rows = pick_representative_sample(df, n=3)
    assert len(rows) == 1


def test_all_non_null_returns_first_n_rows():
    df = pl.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "merchant": ["A", "B", "C", "D"],
        "amount": [1.0, 2.0, 3.0, 4.0],
    })
    rows = pick_representative_sample(df, n=3)
    assert len(rows) == 3


def test_sparse_column_row_is_included():
    """Row 4 is the only one with a non-null description — it must be selected."""
    df = pl.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "description": [None, None, None, "Payment ref 123"],
        "amount": [1.0, 2.0, 3.0, 4.0],
    })
    rows = pick_representative_sample(df, n=3)
    descriptions = [r["description"] for r in rows]
    assert "Payment ref 123" in descriptions


def test_all_null_column_still_returns_n_rows():
    """A permanently-null column should not prevent n rows from being returned."""
    df = pl.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "reference": [None, None, None, None],
        "amount": [1.0, 2.0, 3.0, 4.0],
    })
    rows = pick_representative_sample(df, n=3)
    assert len(rows) == 3
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/utils/test_csv_utils.py -v
```

Expected: `ERROR` — `ImportError: cannot import name 'pick_representative_sample'`

**Step 3: Implement**

```python
# app/utils/csv_utils.py
"""Utility functions for CSV parsing and sampling."""

import polars as pl


def pick_representative_sample(df: pl.DataFrame, n: int = 3) -> list[dict]:
    """Return up to n rows that maximise non-null column coverage.

    Uses a greedy algorithm: repeatedly selects the row that adds the most
    newly-covered (non-null) columns, stopping when n rows are selected or
    all columns are covered.  Remaining slots are filled with sequential
    rows not yet selected.

    Args:
        df: Parsed Polars DataFrame.
        n:  Maximum number of rows to return.

    Returns:
        List of row dicts, sorted by original row index.
    """
    if df.is_empty():
        return []

    all_rows = df.to_dicts()
    n = min(n, len(all_rows))
    selected: list[int] = []
    uncovered = set(df.columns)

    while len(selected) < n and uncovered:
        best_idx, best_score = -1, -1
        for i, row in enumerate(all_rows):
            if i in selected:
                continue
            score = sum(1 for col in uncovered if row.get(col) is not None)
            if score > best_score:
                best_score, best_idx = score, i
        if best_idx == -1:
            break
        selected.append(best_idx)
        uncovered -= {col for col in uncovered if all_rows[best_idx].get(col) is not None}

    # Fill remaining slots with sequential rows not yet selected
    for i in range(len(all_rows)):
        if len(selected) >= n:
            break
        if i not in selected:
            selected.append(i)

    return [all_rows[i] for i in sorted(selected)]
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/utils/test_csv_utils.py -v
```

Expected: 5 passed

**Step 5: Commit**

```bash
git add app/utils/csv_utils.py tests/unit/utils/test_csv_utils.py
git commit -m "feat: add pick_representative_sample utility for CSV column coverage"
```

---

### Task 2: Extend `CSVUploadProposalResponse` schema

**Files:**
- Modify: `app/schemas/csv_upload.py`

The frontend needs two new fields to render the manual mapping UI:
- `available_fields` — the list of valid target field names to populate dropdowns
- `column_null_rates` — fraction of null values per column (0.0–1.0) so the UI can flag columns it couldn't reliably map

**Step 1: Update the schema**

In `app/schemas/csv_upload.py`, replace `CSVUploadProposalResponse` with:

```python
class CSVUploadProposalResponse(SQLModel):
    """Response from POST /transactions/upload (step 1).

    Returns the proposed column→field mapping and sample rows for the user
    to verify before confirming the import.
    """

    mapping_id: str
    proposed_mapping: Dict[str, str]        # {"Buchungsdatum": "date", "Betrag": "amount", ...}
    sample_rows: List[Dict[str, Any]]       # representative rows for visual verification
    available_fields: List[str]             # valid target field names for the mapping dropdowns
    column_null_rates: Dict[str, float]     # fraction of null values per column (0.0–1.0)
```

No test needed here — the schema change is exercised by the endpoint tests in Task 3.

**Step 2: Commit**

```bash
git add app/schemas/csv_upload.py
git commit -m "feat: add available_fields and column_null_rates to CSVUploadProposalResponse"
```

---

### Task 3: Update the upload endpoint

**Files:**
- Modify: `app/api/v1/transactions.py`

Three changes in the `upload_csv` handler and its `_propose_column_mapping` helper:

1. Extract `SCHEMA_FIELDS` as a module-level constant (removes duplication and makes it easy to keep in sync with the schema)
2. Update `_propose_column_mapping` to accept `sample_rows: list[dict]` (multiple rows → better LLM signal)
3. Wire `pick_representative_sample`, `column_null_rates`, and `available_fields` into the response

**Step 1: Apply the changes**

At the top of `app/api/v1/transactions.py`, add the import:

```python
from app.utils.csv_utils import pick_representative_sample
```

Add the module-level constant right after the imports:

```python
SCHEMA_FIELDS = ["date", "merchant", "amount", "description", "original_category", "is_recurring", "ignore"]
```

Replace `_propose_column_mapping` with:

```python
async def _propose_column_mapping(columns: list[str], sample_rows: list[dict]) -> dict[str, str]:
    """Call OpenAI to map CSV column names to transaction schema fields."""
    prompt = f"""You are a column mapping assistant for a personal finance app.

Map each CSV column to one of these schema fields: {SCHEMA_FIELDS}

Use "ignore" for columns that don't map to any field.
Required fields that MUST be mapped: date, merchant, amount.

CSV columns: {columns}
Sample rows (up to 3 rows shown to help infer meaning from values): {sample_rows}

Return ONLY a JSON object like:
{{"Buchungsdatum": "date", "Empfaenger": "merchant", "Betrag": "amount", "Notiz": "ignore"}}"""

    llm = ChatOpenAI(model=settings.llm.DEFAULT_LLM_MODEL, temperature=0)
    response = await llm.ainvoke(prompt)
    text = response.content.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]

    return json.loads(text)
```

In `upload_csv`, replace the sample selection block and the final return:

```python
    # 5. Pick representative sample rows (maximises non-null column coverage)
    sample_rows = pick_representative_sample(df, n=3)

    # (was: sample_row = df.head(1).to_dicts()[0])
    if cached_profile:
        proposed_mapping = cached_profile.mapping
    else:
        proposed_mapping = await _propose_column_mapping(columns, sample_rows)

        mapped_fields = set(proposed_mapping.values())
        required = {"date", "merchant", "amount"}
        missing = required - mapped_fields
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Required columns could not be mapped: {missing}. "
                       f"Please ensure your CSV contains date, merchant, and amount columns.",
            )

    # 7. Create upload session
    session = await CSVMappingService.create_session(
        db=db,
        user_id=user.id,
        proposed_mapping=proposed_mapping,
        csv_content=csv_text,
    )

    # 8. Compute per-column null rates
    total_rows = len(df)
    null_counts = df.null_count().to_dicts()[0]
    column_null_rates = {
        col: (count / total_rows if total_rows > 0 else 0.0)
        for col, count in null_counts.items()
    }

    return CSVUploadProposalResponse(
        mapping_id=session.mapping_id,
        proposed_mapping=proposed_mapping,
        sample_rows=sample_rows,
        available_fields=SCHEMA_FIELDS,
        column_null_rates=column_null_rates,
    )
```

Note: the existing step numbers in the handler will shift — renumber the inline comments to stay sequential (step 6 becomes the session create, step 7 null rates, no gap).

**Step 2: Run the unit tests to make sure nothing is broken**

```bash
uv run pytest tests/unit/ -q
```

Expected: all pass (same count as before)

**Step 3: Commit**

```bash
git add app/api/v1/transactions.py app/utils/csv_utils.py
git commit -m "feat: use representative sampling and return column metadata in upload response"
```

---

### Task 4: Update integration tests

**Files:**
- Modify: `tests/integration/api/test_transactions_upload.py`

Two changes:
1. Assert `available_fields` and `column_null_rates` are present in the existing `test_upload_valid_csv_returns_proposal`
2. Add one new test: CSV with a column that is null in the first 3 rows — verify `column_null_rates` reflects it

**Step 1: Update `test_upload_valid_csv_returns_proposal`**

Add after the existing assertions:

```python
    assert "available_fields" in body
    assert "date" in body["available_fields"]
    assert "ignore" in body["available_fields"]
    assert "column_null_rates" in body
    assert set(body["column_null_rates"].keys()) == set(body["proposed_mapping"].keys())
```

**Step 2: Add a new test**

```python
@pytest.mark.asyncio
async def test_upload_returns_null_rates_for_sparse_column(auth_client):
    """Columns with all-null values in the file get null_rate=1.0."""
    csv_with_nulls = (
        b"Date,Merchant,Amount,Reference\n"
        b"2026-01-01,Netflix,12.99,\n"
        b"2026-01-02,Spotify,9.99,\n"
    )
    with patch(
        "app.api.v1.transactions.CSVMappingService.get_profile",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.api.v1.transactions._propose_column_mapping",
        new_callable=AsyncMock,
        return_value={"Date": "date", "Merchant": "merchant", "Amount": "amount", "Reference": "ignore"},
    ):
        response = await auth_client.post(
            BASE_URL,
            files={"file": ("test.csv", io.BytesIO(csv_with_nulls), "text/csv")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["column_null_rates"]["Reference"] == 1.0
    assert body["column_null_rates"]["Amount"] == 0.0
```

**Step 3: Run the integration tests (they will error on DB connection in CI, but should show collected correctly)**

```bash
uv run pytest tests/unit/ -q
```

Expected: all unit tests still pass

**Step 4: Commit**

```bash
git add tests/integration/api/test_transactions_upload.py
git commit -m "test: assert available_fields and column_null_rates in upload response"
```
