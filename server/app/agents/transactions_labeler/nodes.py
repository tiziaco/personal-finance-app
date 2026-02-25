"""LangGraph node functions for the transaction categorization workflow."""

import asyncio
import json
import logging
from typing import Any, Dict, List

from langchain_openai import ChatOpenAI

from app.agents.transactions_labeler.enums import CategoryEnum
from app.agents.transactions_labeler.models import UserCategoryPreference
from app.agents.transactions_labeler.prompts.categorization import build_categorization_prompt
from app.agents.transactions_labeler.state import CategorizationState
from app.utils.http_clients import TransactionLabelerHTTPClient
from app.utils.merchant_mappings import get_common_merchant_mappings

logger = logging.getLogger(__name__)

BATCH_SIZE = 50


def normalize_merchant_name(merchant_name: str) -> str:
    """Remove payment processor noise and normalise to Title Case."""
    if not merchant_name:
        return ""
    merchant = merchant_name.strip().split("|")[0].strip()
    upper = merchant.upper()

    if upper.startswith("PAYPAL *"):
        merchant = merchant.split("*", 1)[1].strip()
    elif upper.startswith("SUMUP  *"):
        merchant = merchant.split("*", 1)[1].strip()
    elif upper.startswith("UBR*"):
        extracted = merchant.split("*", 1)[1].strip()
        merchant = "Uber" if "UBER" in extracted.upper() else extracted
    elif upper.startswith(("LSP*", "SPC*")):
        merchant = merchant.split("*", 1)[1].strip()
    elif upper.startswith("ZETTLE_"):
        merchant = merchant[7:].strip()
    else:
        merchant = merchant.split("*")[0].strip()

    if not merchant.startswith("Amazon"):
        merchant = merchant.split("-")[0].strip()

    return merchant.title()


def _build_merchant_lookup(
    merchant_mappings: Dict[str, CategoryEnum],
) -> tuple[dict, list]:
    exact = {k.lower(): v for k, v in merchant_mappings.items()}
    partial = [(k.lower(), v) for k, v in merchant_mappings.items()]
    return exact, partial


def enrich_merchants(state: CategorizationState) -> CategorizationState:
    """Normalise merchant names and check hardcoded + user merchant mappings."""
    # Merge common mappings (base) with user overrides
    common = get_common_merchant_mappings()
    merged = {**common, **state["user_preferences"].merchant_mappings}
    exact, partial = _build_merchant_lookup(merged)

    enriched = []
    for tx in state["raw_transactions"]:
        merchant = normalize_merchant_name(tx.get("merchant", ""))
        merchant_lower = merchant.lower()

        manual_category = exact.get(merchant_lower)
        if manual_category is None:
            for mapped, cat in partial:
                if mapped in merchant_lower or merchant_lower in mapped:
                    manual_category = cat
                    break

        enriched.append({
            "transaction": tx,
            "normalized_merchant": merchant,
            "manual_category": manual_category,
            "has_manual_mapping": manual_category is not None,
        })

    return {**state, "enriched_transactions": enriched}


async def categorize_batch(state: CategorizationState) -> CategorizationState:
    """Batch-categorize transactions via OpenAI, deduplicating by merchant."""
    need_categorization = [e for e in state["enriched_transactions"] if not e["has_manual_mapping"]]
    manually_mapped = [e for e in state["enriched_transactions"] if e["has_manual_mapping"]]

    # Deduplicate by merchant to reduce LLM calls
    merchant_to_txs: Dict[str, list] = {}
    unique_merchants = []
    for e in need_categorization:
        m = e["normalized_merchant"]
        if m not in merchant_to_txs:
            merchant_to_txs[m] = []
            unique_merchants.append(e)
        merchant_to_txs[m].append(e)

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1)
    semaphore = TransactionLabelerHTTPClient.get_semaphore()

    async def process_batch(idx: int, batch: list):
        try:
            prompt = build_categorization_prompt(batch, state["user_preferences"])
            async with semaphore:
                response = await llm.ainvoke(prompt)
            text = response.content
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            parsed = json.loads(text.strip())
            return {
                batch[r["id"]]["normalized_merchant"]: {
                    "category": r["category"],
                    "confidence_score": float(r["confidence"]),
                    "is_recurring": bool(r.get("is_recurring", False)),
                }
                for r in parsed
            }, None
        except Exception as exc:
            return None, f"Batch {idx}: {exc}"

    batches = [unique_merchants[i:i + BATCH_SIZE] for i in range(0, len(unique_merchants), BATCH_SIZE)]
    batch_results = await asyncio.gather(*[process_batch(i, b) for i, b in enumerate(batches)])

    merchant_categories: Dict[str, Any] = {}
    errors = []
    for res, err in batch_results:
        if err:
            errors.append(err)
        if res:
            merchant_categories.update(res)

    if errors:
        return {**state, "error": f"Categorization errors: {'; '.join(errors[:3])}", "categorized_transactions": [], "results": []}

    categorized = []
    for e in need_categorization:
        info = merchant_categories.get(e["normalized_merchant"])
        if info:
            categorized.append({"transaction": e["transaction"], **info})
        else:
            categorized.append({
                "transaction": e["transaction"],
                "category": CategoryEnum.MISCELLANEOUS.value,
                "confidence_score": 0.3,
                "is_recurring": False,
            })

    for e in manually_mapped:
        categorized.append({
            "transaction": e["transaction"],
            "category": e["manual_category"].value,
            "confidence_score": 1.0,
            "is_recurring": False,
        })

    return {**state, "categorized_transactions": categorized}


def validate_categorization(state: CategorizationState) -> CategorizationState:
    """Log confidence stats — no filtering, all rows pass through."""
    txs = state["categorized_transactions"]
    low = sum(1 for t in txs if t["confidence_score"] < 0.6)
    stats = {
        "total": len(txs),
        "high_confidence": len(txs) - low,
        "low_confidence": low,
        "recurring": sum(1 for t in txs if t["is_recurring"]),
        "avg_confidence": sum(t["confidence_score"] for t in txs) / len(txs) if txs else 0,
    }
    logger.info("categorization_stats: %s", stats)
    return {**state, "stats": stats}


def format_results(state: CategorizationState) -> CategorizationState:
    """Format categorized transactions as TransactionCreate-compatible dicts."""
    results = [
        {
            "date": tx["transaction"].get("date"),
            "merchant": tx["transaction"].get("merchant"),
            "amount": tx["transaction"].get("amount"),
            "description": tx["transaction"].get("description"),
            "original_category": tx["transaction"].get("original_category"),
            "category": tx["category"],
            "confidence_score": tx["confidence_score"],
            "is_recurring": tx["is_recurring"],
        }
        for tx in state["categorized_transactions"]
    ]
    return {**state, "results": results}
