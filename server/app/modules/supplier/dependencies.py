"""Supplier-scoped identity — resolves the caller's supplier_id."""

import uuid
from typing import Annotated

from fastapi import Depends

from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.supplier.exceptions import SupplierNotLinkedError
from app.modules.supplier.service import supplier_service


async def get_supplier_id(current_user: CurrentUser, session: DbSession) -> uuid.UUID:
    """Resolve the supplier_id linked to the current user.

    Raises 403 SUPPLIER_NOT_LINKED if no Supplier.contact_id points at this user.

    Usage (value dep):
        async def handler(supplier_id: SupplierID, ...): ...
    """
    supplier_id = await supplier_service.get_id_for_user(session, current_user.id)
    if supplier_id is None:
        raise SupplierNotLinkedError(
            "User is not linked to a supplier — accept the invitation first",
            user_id=current_user.id,
        )
    return supplier_id


SupplierID = Annotated[uuid.UUID, Depends(get_supplier_id)]
