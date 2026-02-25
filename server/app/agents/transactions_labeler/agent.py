"""Public entry point for the transaction labeler workflow."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from langgraph.graph import END, START, StateGraph

from app.agents.shared.observability.langfuse import create_graph_config
from app.agents.transactions_labeler.models import UserCategoryPreference
from app.agents.transactions_labeler.nodes import (
    categorize_batch,
    enrich_merchants,
    format_results,
    validate_categorization,
)
from app.agents.transactions_labeler.state import CategorizationState
from app.schemas.transaction import TransactionCreate
from app.models.transaction import CategoryEnum


def _build_graph():
    workflow = StateGraph(CategorizationState)
    workflow.add_node("enrich", enrich_merchants)
    workflow.add_node("categorize", categorize_batch)
    workflow.add_node("validate", validate_categorization)
    workflow.add_node("format", format_results)
    workflow.add_edge(START, "enrich")
    workflow.add_edge("enrich", "categorize")
    workflow.add_edge("categorize", "validate")
    workflow.add_edge("validate", "format")
    workflow.add_edge("format", END)
    return workflow.compile()


_graph = _build_graph()


async def run_labeler(
    transactions: List[Dict[str, Any]],
    user_id: str,
    user_preferences: Optional[UserCategoryPreference] = None,
) -> List[TransactionCreate]:
    """Run the transaction categorization workflow.

    Args:
        transactions: List of dicts with keys: date, merchant, amount,
                      description (optional), original_category (optional).
                      Date must be an ISO string or datetime.
        user_id: Authenticated user's ID (used for Langfuse tracing).
        user_preferences: Optional user preferences. Defaults to empty
                          (common merchant mappings still apply).

    Returns:
        List of TransactionCreate objects ready for TransactionService.import_from_csv().
    """
    if not transactions:
        return []

    if user_preferences is None:
        user_preferences = UserCategoryPreference(user_id=user_id)

    initial_state = {
        "user_id": user_id,
        "raw_transactions": transactions,
        "user_preferences": user_preferences,
        "enriched_transactions": [],
        "categorized_transactions": [],
        "results": [],
        "error": None,
        "stats": None,
    }

    trace_id = str(uuid.uuid4())
    config = create_graph_config(conversation_id=trace_id, user_id=user_id)

    final_state = await _graph.ainvoke(initial_state, config=config)

    if final_state.get("error"):
        raise RuntimeError(f"Labeler failed: {final_state['error']}")

    labeled: List[TransactionCreate] = []
    for r in final_state["results"]:
        # Normalise date to datetime
        date_val = r["date"]
        if isinstance(date_val, str):
            date_val = datetime.fromisoformat(date_val)
        if date_val.tzinfo is None:
            date_val = date_val.replace(tzinfo=timezone.utc)

        labeled.append(
            TransactionCreate(
                date=date_val,
                merchant=r["merchant"],
                amount=Decimal(str(r["amount"])),
                category=CategoryEnum(r["category"]),
                description=r.get("description"),
                original_category=r.get("original_category"),
                is_recurring=r.get("is_recurring", False),
                confidence_score=float(r.get("confidence_score", 0.5)),
            )
        )

    return labeled
