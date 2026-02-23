"""Insight model — cached AI-generated insights per user."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, DateTime
from sqlmodel import Field, Relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class Insight(BaseModel, table=True):
    """Cached AI-generated insights for a user.

    One row per user (unique on user_id). Upserted on every regeneration.
    `insights` stores the serialised List[InsightItem] as JSONB.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True, unique=True)
    insights: list = Field(default_factory=list, sa_type=JSON)
    generated_at: datetime = Field(sa_type=DateTime(timezone=True))

    user: Optional["User"] = Relationship(back_populates="insights")
