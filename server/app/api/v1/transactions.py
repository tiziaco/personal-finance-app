"""Transaction CRUD endpoints."""

import io
import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

import polars as pl
from langchain_openai import ChatOpenAI

from app.agents.transactions_labeler import run_labeler
from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.database import DbSession
from app.core.config import settings
from app.core.limiter import limiter
from app.schemas.csv_upload import CSVConfirmRequest, CSVUploadProposalResponse, CSVUploadResponse
from app.schemas.transaction import (
    BatchDeleteRequest,
    BatchDeleteResponse,
    BatchUpdateRequest,
    BatchUpdateResponse,
    TransactionCreate,
    TransactionFilters,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)
from app.services.csv_mapping.service import CSVMappingService
from app.services.transaction.service import transaction_service
from app.utils.csv_utils import pick_representative_sample

router = APIRouter()

SCHEMA_FIELDS = ["date", "merchant", "amount", "description", "original_category", "is_recurring", "ignore"]


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

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Column mapping could not be parsed from LLM response: {exc}",
        )


# ── CSV Upload routes (must precede /{transaction_id}) ────────────────────────

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
        df = pl.read_csv(io.StringIO(csv_text), infer_schema_length=10000)
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

    # 5. Pick representative sample rows (maximises non-null column coverage)
    sample_rows = pick_representative_sample(df, n=3)

    if cached_profile:
        proposed_mapping = cached_profile.mapping
    else:
        # 6. Call OpenAI to propose mapping using representative rows
        proposed_mapping = await _propose_column_mapping(columns, sample_rows)

        # 7. Validate required fields are mapped
        mapped_fields = set(proposed_mapping.values())
        required = {"date", "merchant", "amount"}
        missing = required - mapped_fields
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"Required columns could not be mapped: {missing}. "
                       f"Please ensure your CSV contains date, merchant, and amount columns.",
            )

    # 8. Create upload session (stores raw CSV for confirm step)
    session = await CSVMappingService.create_session(
        db=db,
        user_id=user.id,
        proposed_mapping=proposed_mapping,
        csv_content=csv_text,
    )

    # 9. Compute per-column null rates
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
    df = pl.read_csv(io.StringIO(session.csv_content), infer_schema_length=10000)
    rows_raw = df.to_dicts()

    # 4. Validate and transform rows — collect errors, skip bad rows
    valid_rows: list[dict] = []
    errors: list[str] = []

    for i, row in enumerate(rows_raw, start=2):  # row 1 is header
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


# ── Batch routes first (must precede /{transaction_id}) ───────────────────────

@router.patch(
    "/batch",
    response_model=BatchUpdateResponse,
    summary="Batch update transactions",
    description="Update multiple transactions in a single atomic operation. "
                "All-or-nothing: if any ID is not found the entire batch is rolled back.",
)
@limiter.limit("30/minute")
async def batch_update_transactions(
    request: Request,
    body: BatchUpdateRequest,
    db: DbSession,
    user: CurrentUser,
) -> BatchUpdateResponse:
    """Batch update transactions for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        body: List of items to update, max 100.
        db: Database session.
        user: Authenticated user.

    Returns:
        Count of updated transactions.
    """
    count = await transaction_service.batch_update(db, user.id, body.items)
    return BatchUpdateResponse(updated=count)


@router.delete(
    "/batch",
    response_model=BatchDeleteResponse,
    summary="Batch delete transactions",
    description="Soft-delete multiple transactions in a single atomic operation. "
                "All-or-nothing: if any ID is not found the entire batch is rolled back.",
)
@limiter.limit("30/minute")
async def batch_delete_transactions(
    request: Request,
    body: BatchDeleteRequest,
    db: DbSession,
    user: CurrentUser,
) -> BatchDeleteResponse:
    """Batch soft-delete transactions for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        body: List of transaction IDs to delete, max 100.
        db: Database session.
        user: Authenticated user.

    Returns:
        Count of deleted transactions.
    """
    count = await transaction_service.batch_delete(db, user.id, body.ids)
    return BatchDeleteResponse(deleted=count)


# ── Collection routes ─────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=TransactionResponse,
    status_code=201,
    summary="Create a transaction",
    description="Create a single transaction. confidence_score defaults to 1.0 for manual entries.",
)
@limiter.limit("60/minute")
async def create_transaction(
    request: Request,
    body: TransactionCreate,
    db: DbSession,
    user: CurrentUser,
) -> TransactionResponse:
    """Create a new transaction for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        body: Transaction data. user_id is always sourced from auth.
        db: Database session.
        user: Authenticated user.

    Returns:
        The created transaction.
    """
    transaction = await transaction_service.create(db, user.id, body)
    return TransactionResponse.model_validate(transaction)


@router.get(
    "",
    response_model=TransactionListResponse,
    summary="List transactions",
    description="Get a paginated, filtered list of transactions. "
                "Supports both classic pagination and infinite scroll via offset/limit.",
)
@limiter.limit("120/minute")
async def list_transactions(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: TransactionFilters = Depends(),
    offset: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(20, ge=1, le=100, description="Number of items to return"),
) -> TransactionListResponse:
    """List transactions for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        db: Database session.
        user: Authenticated user.
        filters: Query parameter filters (date range, category, merchant, etc.).
        offset: Pagination offset.
        limit: Page size (max 100).

    Returns:
        Paginated list of transactions with total count.
    """
    transactions, total = await transaction_service.list(db, user.id, filters, offset, limit)
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in transactions],
        total=total,
        offset=offset,
        limit=limit,
    )


# ── Item routes ───────────────────────────────────────────────────────────────

@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get a transaction",
    description="Fetch a single transaction by ID. Returns 404 if not found or owned by another user.",
)
@limiter.limit("120/minute")
async def get_transaction(
    request: Request,
    transaction_id: int,
    db: DbSession,
    user: CurrentUser,
) -> TransactionResponse:
    """Get a single transaction by ID for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        transaction_id: The transaction ID to fetch.
        db: Database session.
        user: Authenticated user.

    Returns:
        The transaction.
    """
    transaction = await transaction_service.get(db, user.id, transaction_id)
    return TransactionResponse.model_validate(transaction)


@router.patch(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Update a transaction",
    description="Partially update a transaction. Only provided fields are updated.",
)
@limiter.limit("60/minute")
async def update_transaction(
    request: Request,
    transaction_id: int,
    body: TransactionUpdate,
    db: DbSession,
    user: CurrentUser,
) -> TransactionResponse:
    """Partially update a transaction for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        transaction_id: The transaction ID to update.
        body: Fields to update (all optional).
        db: Database session.
        user: Authenticated user.

    Returns:
        The updated transaction.
    """
    transaction = await transaction_service.update(db, user.id, transaction_id, body)
    return TransactionResponse.model_validate(transaction)


@router.delete(
    "/{transaction_id}",
    status_code=204,
    summary="Delete a transaction",
    description="Soft-delete a transaction (sets deleted_at). The record is excluded from all future queries.",
)
@limiter.limit("60/minute")
async def delete_transaction(
    request: Request,
    transaction_id: int,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """Soft-delete a transaction for the authenticated user.

    Args:
        request: FastAPI request (required for rate limiting).
        transaction_id: The transaction ID to delete.
        db: Database session.
        user: Authenticated user.
    """
    await transaction_service.delete(db, user.id, transaction_id)
