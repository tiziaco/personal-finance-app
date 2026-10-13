"""The transaction row."""

import datetime as dt
from decimal import Decimal
from typing import Optional

from sqlalchemy import CHAR, Column, Index
from sqlmodel import Field

from app.models.base import BaseModel, SoftDeleteMixin, UserOwnedMixin, UUIDPrimaryKeyMixin


class Transaction(BaseModel, UUIDPrimaryKeyMixin, UserOwnedMixin, SoftDeleteMixin, table=True):
    """One movement of money on one of the user's accounts.

    Deletes: one row or a batch is soft-deleted (hidden everywhere, kept);
    "delete all" and erasure (USER_ERASING) hard-delete every row the user
    owns. Nothing references a transaction, so removing rows breaks no FK.

    `category` is a Category slug, validated by the app only — the database
    knows no list, so changing the list needs no migration
    (docs/data-model/transaction.md). `fingerprint` is the sha256 of
    user|date|merchant|amount|description (service.fingerprint), recomputed
    on every edit; it is not unique.
    """

    __table_args__ = (
        Index("ix_transaction_user_id_date", "user_id", "date"),
        Index("ix_transaction_user_id_fingerprint", "user_id", "fingerprint"),
    )

    date: dt.date
    merchant: str = Field(max_length=255)
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    description: Optional[str] = Field(default=None, max_length=1000)
    original_category: Optional[str] = Field(default=None, max_length=255)
    category: str = Field(max_length=64)
    confidence: float
    is_recurring: bool = Field(default=False)
    fingerprint: str = Field(sa_column=Column(CHAR(64), nullable=False))
