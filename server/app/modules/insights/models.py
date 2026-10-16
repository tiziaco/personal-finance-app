"""The insight_set table: a user's latest generated set of insights."""

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models.base import BaseModel, UserOwnedMixin, UUIDPrimaryKeyMixin


class InsightSet(BaseModel, UUIDPrimaryKeyMixin, UserOwnedMixin, table=True):
    """One user's current insights — one row per user, overwritten on each generation.

    Attributes:
        id: UUID v7 primary key
        user_id: Owner; unique, so a user has at most one set
        generated_at: When the set was generated
        reference_month: The finished month the insights describe, YYYY-MM
        baseline_months: How many earlier months the comparison used
        month_to_date_through: Last day covered by the month-to-date figures, if any
        prompt_version: Version of the prompt that produced the set
        insights: The insights themselves, as stored JSON
    """

    __tablename__ = "insight_set"

    # Redeclared (same column as UserOwnedMixin) to add the unique constraint.
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, unique=True, nullable=False)
    generated_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    reference_month: str = Field(max_length=7, nullable=False)
    baseline_months: int = Field(nullable=False)
    month_to_date_through: Optional[date] = Field(default=None, nullable=True)
    prompt_version: str = Field(max_length=16, nullable=False)
    insights: list[dict[str, Any]] = Field(sa_column=Column(JSONB, nullable=False))
