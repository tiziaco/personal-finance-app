"""CSV import, a feature sub-package of transaction (docs/architecture/server.md §2).

It calls the transaction core; the core never imports it.
"""

from app.modules.transaction.imports.service import import_service

__all__ = ["import_service"]

# @events.on is a module-level side effect: importing the package is what subscribes.
from app.modules.transaction.imports import handlers  # noqa: E402, F401
