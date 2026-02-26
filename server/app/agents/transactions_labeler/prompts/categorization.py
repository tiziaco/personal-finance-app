"""Prompt builder for transaction categorization."""

import json
from typing import Any, Dict, List

from app.agents.transactions_labeler.enums import CategoryEnum
from app.agents.transactions_labeler.models import UserCategoryPreference
from app.agents.transactions_labeler.prompts import load_categorization_prompt


def build_categorization_prompt(
    transactions: List[Dict[str, Any]],
    user_preferences: UserCategoryPreference,
    version: str = "v2",
) -> str:
    """Build the categorization prompt for a batch of transactions.

    Args:
        transactions: Enriched transaction dicts with "normalized_merchant" key.
        user_preferences: Per-user category keyword overrides.
        version: Prompt template version to use (default "v1").

    Returns:
        Formatted prompt string ready to send to the LLM.
    """
    categories = "\n".join(f"- {cat.value}" for cat in CategoryEnum)

    keywords_section = ""
    if user_preferences.category_keywords:
        lines = "\n".join(
            f"- {cat.value}: {', '.join(kws)}"
            for cat, kws in user_preferences.category_keywords.items()
        )
        keywords_section = f"User's Category Keywords:\n{lines}"

    transactions_json = json.dumps(
        [
            {
                "id": i,
                "merchant": t["normalized_merchant"],
                "amount": int(t["transaction"].get("amount", 0)),
                "description": t["transaction"].get("description", ""),
            }
            for i, t in enumerate(transactions)
        ],
        separators=(",", ":"),
    )

    template = load_categorization_prompt(version)
    return template.format(
        categories=categories,
        keywords_section=keywords_section,
        transactions=transactions_json,
    )
