from typing import Any, Dict, List, Optional, TypedDict

from app.agents.transactions_labeler.models import UserCategoryPreference


class CategorizationState(TypedDict, total=False):
    """LangGraph state for the transaction categorization workflow."""

    # Input
    user_id: str
    raw_transactions: List[Dict[str, Any]]
    user_preferences: UserCategoryPreference
    prompt_version: str

    # Processing
    enriched_transactions: List[Dict[str, Any]]

    # Output
    categorized_transactions: List[Dict[str, Any]]
    results: List[Dict[str, Any]]
    error: Optional[str]
    stats: Optional[Dict[str, Any]]
