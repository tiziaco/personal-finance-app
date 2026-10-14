"""Transaction dependencies: the ownership check, and the list's filters read from the query string."""

import datetime as dt
import uuid
from decimal import Decimal
from typing import Annotated, List, Optional

from fastapi import Depends, Path, Query

from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.transaction.exceptions import TransactionNotFoundError
from app.modules.transaction.models import Transaction
from app.modules.transaction.schemas import Category, TransactionFilters
from app.modules.transaction.service import transaction_service


async def get_user_transaction(
    user: CurrentUser,
    db_session: DbSession,
    transaction_id: uuid.UUID = Path(...),
) -> Transaction:
    """The caller's active transaction. Missing, deleted or another user's all answer 404 alike."""
    transaction = await transaction_service.get_for_user(db_session, user.id, transaction_id)
    if not transaction:
        raise TransactionNotFoundError(f"Transaction {transaction_id} not found", transaction_id=str(transaction_id))
    return transaction


UserTransaction = Annotated[Transaction, Depends(get_user_transaction)]


def get_transaction_filters(
    date_from: Optional[dt.date] = Query(None, description="On or after this day"),
    date_to: Optional[dt.date] = Query(None, description="On or before this day"),
    category: Optional[List[Category]] = Query(None, description="Any of these categories; repeat the parameter"),
    amount_min: Optional[Decimal] = Query(
        None, max_digits=12, decimal_places=2, allow_inf_nan=False, description="Signed amount at least this"
    ),
    amount_max: Optional[Decimal] = Query(
        None, max_digits=12, decimal_places=2, allow_inf_nan=False, description="Signed amount at most this"
    ),
    is_recurring: Optional[bool] = Query(None, description="Only recurring, or only not"),
) -> TransactionFilters:
    """The list's filters. A function, not a Depends() model: a model's list field would be read from the body."""
    return TransactionFilters(
        date_from=date_from,
        date_to=date_to,
        category=category,
        amount_min=amount_min,
        amount_max=amount_max,
        is_recurring=is_recurring,
    )


TransactionListFilters = Annotated[TransactionFilters, Depends(get_transaction_filters)]
