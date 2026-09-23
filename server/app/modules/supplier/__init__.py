"""Supplier — the example domain: an external company and the portal user who manages it.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server-modules.md, R1). No router yet: the module
exists for the contact link and the supplier-scoped identity.
"""

from app.modules.supplier.dependencies import SupplierID, get_supplier_id  # noqa: I001
from app.modules.supplier.exceptions import SupplierNotLinkedError
from app.modules.supplier.service import supplier_service

# @events.on is a module-level side effect: importing the root is what subscribes.
from app.modules.supplier import handlers

__all__ = [
    "SupplierID",
    "SupplierNotLinkedError",
    "get_supplier_id",
    "supplier_service",
]
