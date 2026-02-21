"""Transaction CRUD endpoints."""

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.database import DbSession
from app.core.limiter import limiter
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
from app.services.transaction.service import transaction_service

router = APIRouter()


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
