"""Transaction — the user's transactions and the category list.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).
"""

from app.modules.transaction.dependencies import UserTransaction, get_user_transaction
from app.modules.transaction.domain.dates import MAX_DATE, MIN_DATE
from app.modules.transaction.exceptions import (
    DuplicateTransactionError,
    TransactionNotFoundError,
)
from app.modules.transaction.router import router
from app.modules.transaction.schemas import (
    CATEGORIES,
    AnalysisRow,
    Category,
    CategoryResponse,
    TransactionFilters,
    TransactionImport,
    TransactionListResponse,
    TransactionResponse,
)
from app.modules.transaction.service import transaction_service

__all__ = [
    "AnalysisRow",
    "CATEGORIES",
    "Category",
    "CategoryResponse",
    "DuplicateTransactionError",
    "MAX_DATE",
    "MIN_DATE",
    "TransactionFilters",
    "TransactionImport",
    "TransactionListResponse",
    "TransactionNotFoundError",
    "TransactionResponse",
    "UserTransaction",
    "get_user_transaction",
    "imports_router",
    "router",
    "transaction_service",
]

# @events.on is a module-level side effect: importing the root is what subscribes.
from app.modules.transaction import handlers  # noqa: E402, F401

# After the core, which it imports. Importing it also subscribes its handlers.
from app.modules.transaction.imports import router as imports_router  # noqa: E402
