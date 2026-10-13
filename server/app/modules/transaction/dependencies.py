"""Transaction ownership dependency for FastAPI endpoints."""

import uuid
from typing import Annotated

from fastapi import Depends, Path

from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.transaction.exceptions import TransactionNotFoundError
from app.modules.transaction.models import Transaction
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
