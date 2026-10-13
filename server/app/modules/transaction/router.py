"""Transaction routes under /transactions. Named paths are declared before /{transaction_id}."""

from typing import List

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.limiter import limiter
from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.transaction.dependencies import UserTransaction
from app.modules.transaction.schemas import CategoryResponse, TransactionCreate, TransactionResponse, TransactionUpdate
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
