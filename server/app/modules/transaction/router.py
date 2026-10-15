"""Transaction routes under /transactions. Named paths are declared before /{transaction_id}."""

from typing import List, Optional

from fastapi import APIRouter, Query, Request

from app.core.config import settings
from app.core.limiter import limiter
from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.transaction.dependencies import TransactionListFilters, UserTransaction
from app.modules.transaction.schemas import (
    BatchCategoryUpdate,
    BatchDeleteResponse,
    BatchIds,
    BatchUpdateResponse,
    CategoryResponse,
    DeleteAllResponse,
    TransactionCreate,
    TransactionListResponse,
    TransactionOrdering,
    TransactionResponse,
    TransactionUpdate,
)
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
    filters: TransactionListFilters,
    search: Optional[str] = Query(None, max_length=100, description="Merchant contains, case-insensitive"),
    ordering: TransactionOrdering = Query("-date", description="Sort field; '-' for descending"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> TransactionListResponse:
    """List the caller's active transactions."""
    items, total = await transaction_service.list(db_session, user.id, filters, ordering, search, offset, limit)
    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in items], total=total, offset=offset, limit=limit
    )


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
async def batch_delete(
    request: Request, body: BatchIds, db_session: DbSession, user: CurrentUser
) -> BatchDeleteResponse:
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
