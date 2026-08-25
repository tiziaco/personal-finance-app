"""Supplier model — external companies that supply goods/services."""

import uuid
from typing import Optional

from sqlmodel import Field

from app.models.base import BaseModel, SoftDeleteMixin



class Supplier(BaseModel, SoftDeleteMixin, table=True):
    """An external supplier company.

    contact_id links to the User who manages this supplier's portal account.
    Nullable — the company record can be created before any portal user exists.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    contact_id: Optional[str] = Field(default=None, foreign_key="user.id", index=True)
    name: str
    code: str = Field(unique=True, index=True)
    vat_number: str = Field(unique=True, index=True)
