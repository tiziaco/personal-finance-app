from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.agents.transactions_labeler.enums import CategoryEnum


class RawTransaction(BaseModel):
    """A transaction row after CSV parsing, before AI categorization."""

    date: str            # ISO string, e.g. "2026-01-15T00:00:00+00:00"
    merchant: str
    amount: float
    description: Optional[str] = None
    original_category: Optional[str] = None


class UserCategoryPreference(BaseModel):
    """User-specific merchant mappings and keyword hints.

    For MVP all fields default to empty — the labeler runs on hardcoded
    common merchant mappings only. User-level preferences are a future feature.
    """

    user_id: str
    merchant_mappings: Dict[str, CategoryEnum] = Field(default_factory=dict)
    category_keywords: Dict[CategoryEnum, List[str]] = Field(default_factory=dict)
