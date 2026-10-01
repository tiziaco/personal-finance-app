"""Supplier model — external companies that supply goods/services."""

import uuid
from typing import Optional

from sqlmodel import Field

from app.models.base import BaseModel, SoftDeleteMixin, UUIDPrimaryKeyMixin


class Supplier(BaseModel, UUIDPrimaryKeyMixin, SoftDeleteMixin, table=True):
    """An external supplier company.

    contact_id links to the User who manages this supplier's portal account.
    Nullable — the company record can be created before any portal user exists.
    """

    contact_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id", index=True)
    name: str
    code: str = Field(unique=True, index=True)
    vat_number: str = Field(unique=True, index=True)
