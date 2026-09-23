"""Supplier domain exceptions."""

from app.exceptions.base import AuthorizationError


class SupplierNotLinkedError(AuthorizationError):
    """Raised when a request requires a supplier link but the current user has none.

    Surfaces to the client as 403 with error_code SUPPLIER_NOT_LINKED.
    Supplier portal users must accept an invitation (which links them during
    JIT provisioning) before any supplier-scoped endpoint will accept them.
    """

    error_code = "SUPPLIER_NOT_LINKED"
