"""Transaction service domain exceptions."""

from app.exceptions.base import NotFoundError


class TransactionNotFoundError(NotFoundError):
    """Raised when a transaction is not found or does not belong to the requesting user."""

    error_code = "TRANSACTION_NOT_FOUND"
