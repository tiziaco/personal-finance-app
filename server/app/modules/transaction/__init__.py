"""Transaction — the user's transactions and the category list.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).
"""

from app.modules.transaction.dependencies import UserTransaction, get_user_transaction
from app.modules.transaction.exceptions import (  # noqa: I001
    DuplicateTransactionError,
    TransactionNotFoundError,
)
from app.modules.transaction.router import router
from app.modules.transaction.schemas import (
    CATEGORIES,
    Category,
    CategoryResponse,
    TransactionImport,
    TransactionResponse,
    category_label,
)
from app.modules.transaction.service import transaction_service

__all__ = [
    "CATEGORIES",
    "Category",
    "CategoryResponse",
    "DuplicateTransactionError",
    "TransactionImport",
    "TransactionNotFoundError",
    "TransactionResponse",
    "UserTransaction",
    "category_label",
    "get_user_transaction",
    "router",
    "transaction_service",
]
