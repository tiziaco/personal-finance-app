from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from app.agents.transactions_labeler.models import RawTransaction, UserCategoryPreference


class CategorizationState(BaseModel):
    """LangGraph state for the transaction categorization workflow."""

    # Input
    user_id: str
    raw_transactions: List[Dict[str, Any]]
    user_preferences: UserCategoryPreference
    prompt_version: str = "v1"

    # Processing
    enriched_transactions: List[Dict[str, Any]]

    # Output
    categorized_transactions: List[Dict[str, Any]]
    results: List[Dict[str, Any]]
    error: Optional[str] = None
    stats: Optional[Dict[str, Any]] = None
