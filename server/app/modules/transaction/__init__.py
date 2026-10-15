"""Transaction — the user's transactions and the category list.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).
"""

from app.modules.transaction.dependencies import UserTransaction, get_user_transaction
from app.modules.transaction.exceptions import (
    DuplicateTransactionError,
    TransactionNotFoundError,
)
from app.modules.transaction.router import router
from app.modules.transaction.schemas import (
    CATEGORIES,
    Category,
    CategoryResponse,
    TransactionFilters,
    TransactionImport,
    TransactionListResponse,
    TransactionResponse,
)
from app.modules.transaction.service import transaction_service

__all__ = [
    "CATEGORIES",
    "Category",
    "CategoryResponse",
    "DuplicateTransactionError",
    "TransactionFilters",
    "TransactionImport",
    "TransactionListResponse",
    "TransactionNotFoundError",
    "TransactionResponse",
    "UserTransaction",
    "get_user_transaction",
    "router",
    "transaction_service",
]

# @events.on is a module-level side effect: importing the root is what subscribes.
from app.modules.transaction import handlers  # noqa: E402
