"""Transaction module domain exceptions."""

from app.exceptions.base import ConflictError, NotFoundError


class TransactionNotFoundError(NotFoundError):
    """A transaction is missing, soft-deleted, or another user's."""

    error_code = "TRANSACTION_NOT_FOUND"


class DuplicateTransactionError(ConflictError):
    """A manual add matches an active transaction's fingerprint."""

    error_code = "DUPLICATE_TRANSACTION"
