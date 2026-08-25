"""User service domain exceptions."""

from app.exceptions.base import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
)


class UserServiceError(Exception):
    """Base exception for user service errors."""

    pass


class UserNotFoundError(NotFoundError):
    """Exception raised when a user is not found."""

    error_code = "USER_NOT_FOUND"


class UserAlreadyExistsError(ConflictError):
    """Exception raised when attempting to create a user that already exists."""

    error_code = "USER_ALREADY_EXISTS"


class SupplierNotLinkedError(AuthorizationError):
    """Raised when a request requires a supplier link but the current user has none.

    Surfaces to the client as 403 with error_code SUPPLIER_NOT_LINKED.
    Supplier portal users must accept an invitation (which sets
    Supplier.contact_id during JIT provisioning) before any supplier-scoped
    endpoint will accept them.
    """

    error_code = "SUPPLIER_NOT_LINKED"
