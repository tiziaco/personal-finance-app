from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional

from fastapi import Query
from pydantic import ConfigDict
from sqlmodel import Field, SQLModel

from app.models.transaction import CategoryEnum


# ── Request Schemas ───────────────────────────────────────────────────────────

class TransactionCreate(SQLModel):
    """Request body for creating a single transaction.

    confidence_score defaults to 1.0 (human-verified) for manual entries.
    """

    model_config = ConfigDict(allow_inf_nan=False)

    date: datetime
    merchant: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(max_digits=12, decimal_places=2)
    category: CategoryEnum
    description: Optional[str] = Field(default=None, max_length=1000)
    original_category: Optional[str] = Field(default=None, max_length=255)
    is_recurring: bool = False
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class TransactionUpdate(SQLModel):
    """Request body for partially updating a single transaction."""

    model_config = ConfigDict(allow_inf_nan=False)

    date: Optional[datetime] = None
    merchant: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    description: Optional[str] = Field(default=None, max_length=1000)
    original_category: Optional[str] = Field(default=None, max_length=255)
    category: Optional[CategoryEnum] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_recurring: Optional[bool] = None


class BatchUpdateItem(SQLModel):
    """A single item in a batch update request."""

    model_config = ConfigDict(allow_inf_nan=False)

    id: int
    date: Optional[datetime] = None
    merchant: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=2)
    description: Optional[str] = Field(default=None, max_length=1000)
    original_category: Optional[str] = Field(default=None, max_length=255)
    category: Optional[CategoryEnum] = None
    confidence_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    is_recurring: Optional[bool] = None


class BatchUpdateRequest(SQLModel):
    """Request body for batch updating transactions. Max 100 items."""

    items: list[BatchUpdateItem] = Field(min_length=1, max_length=100)


class BatchDeleteRequest(SQLModel):
    """Request body for batch deleting transactions. Max 100 items."""

    ids: list[int] = Field(min_length=1, max_length=100)


# ── Response Schemas ──────────────────────────────────────────────────────────

class TransactionResponse(SQLModel):
    """Response schema for a single transaction."""

    id: int
    user_id: str
    date: datetime
    merchant: str
    amount: Decimal
    description: Optional[str]
    original_category: Optional[str]
    category: CategoryEnum
    confidence_score: float
    is_recurring: bool
    created_at: datetime
    updated_at: datetime


class TransactionListResponse(SQLModel):
    """Paginated list of transactions."""

    items: list[TransactionResponse]
    total: int
    offset: int
    limit: int


class BatchUpdateResponse(SQLModel):
    """Response for a batch update operation."""

    updated: int


class BatchDeleteResponse(SQLModel):
    """Response for a batch delete operation."""

    deleted: int


# ── Filter Dependency ─────────────────────────────────────────────────────────

class TransactionFilters:
    """FastAPI dependency for transaction list query parameters."""

    def __init__(
        self,
        date_from: Optional[datetime] = Query(None, description="Filter transactions on or after this date"),
        date_to: Optional[datetime] = Query(None, description="Filter transactions on or before this date"),
        category: Optional[CategoryEnum] = Query(None, description="Filter by category"),
        merchant: Optional[str] = Query(None, description="Substring match on merchant name"),
        amount_min: Optional[Decimal] = Query(None, description="Minimum transaction amount"),
        amount_max: Optional[Decimal] = Query(None, description="Maximum transaction amount"),
        is_recurring: Optional[bool] = Query(None, description="Filter by recurring status"),
        sort_by: Literal["date", "amount", "merchant"] = Query("date", description="Field to sort by"),
        sort_order: Literal["asc", "desc"] = Query("desc", description="Sort direction"),
    ) -> None:
        self.date_from = date_from
        self.date_to = date_to
        self.category = category
        self.merchant = merchant
        self.amount_min = amount_min
        self.amount_max = amount_max
        self.is_recurring = is_recurring
        self.sort_by = sort_by
        self.sort_order = sort_order
