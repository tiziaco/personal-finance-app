"""Prompt templates for transaction categorization."""

import json
from typing import Any, Dict, List

from app.agents.transactions_labeler.enums import CategoryEnum
from app.agents.transactions_labeler.models import UserCategoryPreference


def build_categorization_prompt(
    transactions: List[Dict[str, Any]],
    user_preferences: UserCategoryPreference,
) -> str:
    """Build the OpenAI prompt for batch transaction categorization."""
    categories_desc = "\n".join(
        f"- {cat.value}" for cat in CategoryEnum
    )

    keywords_section = ""
    if user_preferences.category_keywords:
        keywords_section = "\n\nUser's Category Keywords:\n"
        for category, keywords in user_preferences.category_keywords.items():
            keywords_section += f"- {category.value}: {', '.join(keywords)}\n"

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

    return f"""You are a transaction categorizer for a personal finance app.

Available Categories:
{categories_desc}
{keywords_section}

Transactions to categorize:
{transactions_json}

For EACH transaction return ONLY a valid JSON array:
[
  {{"id": 0, "category": "Food & Groceries", "confidence": 0.95, "is_recurring": false}},
  ...
]

Use the exact category names from the list above. No other text."""
