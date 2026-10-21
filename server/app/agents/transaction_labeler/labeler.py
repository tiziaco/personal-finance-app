"""The labeller: a category and a confidence for each merchant of an import (docs/product/features/categorisation.md).

Known merchants first, then the model in batches. It imports nothing from a
module (R2): the category list comes in as `(slug, label)` pairs.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, RootModel

from app.agents.core import create_trace_config
from app.agents.shared.structured import ask_json, structured_llm_service
from app.agents.transaction_labeler.known_merchants import match_known
from app.core.logging import logger
from app.integrations.llm import LLMService

KNOWN_CONFIDENCE = 0.95
FALLBACK_CATEGORY = "miscellaneous"
FALLBACK_CONFIDENCE = 0.3
BATCH_SIZE = 50
MAX_CONCURRENT_BATCHES = 5
PROMPT_VERSION = "v2"

_PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")


@dataclass(frozen=True)
class MerchantToLabel:
    """One merchant of an import, as the model sees it."""

    key: str
    merchant: str
    description: Optional[str]
    original_category: Optional[str]
    amount: Decimal


@dataclass(frozen=True)
class Label:
    """A category slug and how sure the labeller is, 0 to 1."""

    category: str
    confidence: float


@dataclass(frozen=True)
class LabelResult:
    """A label for every merchant key, which keys fell back, and whether the model failed entirely."""

    labels: dict[str, Label]
    fallback_keys: set[str]
    all_failed: bool


class _Answer(BaseModel):
    id: int
    category: str
    confidence: float


class _Answers(RootModel[list[_Answer]]):
    pass


async def label(
    merchants: list[MerchantToLabel],
    categories: list[tuple[str, str]],
    *,
    user_id: uuid.UUID,
    upload_id: uuid.UUID,
) -> LabelResult:
    """Label every merchant. A merchant the model cannot place is filed under Miscellaneous at 0.3."""
    labels: dict[str, Label] = {}
    unknown = []
    for item in merchants:
        slug = match_known(item.key)
        if slug is not None:
            labels[item.key] = Label(slug, KNOWN_CONFIDENCE)
        else:
            unknown.append(item)

    batches = [unknown[i : i + BATCH_SIZE] for i in range(0, len(unknown), BATCH_SIZE)]
    config = create_trace_config(
        user_id, upload_id, "transaction_labeler", metadata={"prompt_version": PROMPT_VERSION}
    )
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_BATCHES)

    async def run(batch: list[MerchantToLabel]) -> Optional[dict[str, Label]]:
        async with semaphore:
            try:
                return await _label_batch(structured_llm_service, batch, categories, config)
            except Exception as e:  # noqa: BLE001  any failure of one batch is that batch's fallback, never the import's crash
                logger.warning("label_batch_failed", size=len(batch), error_type=type(e).__name__)
                return None

    answers = await asyncio.gather(*(run(batch) for batch in batches))
    fallback: set[str] = set()
    for batch, answer in zip(batches, answers, strict=True):
        for item in batch:
            got = answer.get(item.key) if answer is not None else None
            if got is None:
                fallback.add(item.key)
                got = Label(FALLBACK_CATEGORY, FALLBACK_CONFIDENCE)
            labels[item.key] = got
    all_failed = bool(batches) and all(answer is None for answer in answers)
    logger.info("merchants_labelled", known=len(merchants) - len(unknown), asked=len(unknown), fallback=len(fallback))
    return LabelResult(labels=labels, fallback_keys=fallback, all_failed=all_failed)


async def _label_batch(
    service: LLMService, batch: list[MerchantToLabel], categories: list[tuple[str, str]], config: RunnableConfig
) -> dict[str, Label]:
    """One model call for up to BATCH_SIZE merchants: the labels it gave that name a real category."""
    slugs = {slug for slug, _ in categories}
    by_label = {label.casefold(): slug for slug, label in categories}
    system = _PROMPT.format(categories="\n".join(f"- {slug}: {label}" for slug, label in categories))
    user = json.dumps(
        [
            {
                "id": i,
                "merchant": item.merchant,
                "amount": str(item.amount),
                "description": item.description or "",
                "bank_category": item.original_category or "",
            }
            for i, item in enumerate(batch)
        ],
        ensure_ascii=False,
    )
    answers = await ask_json(service, system, user, _Answers, config)
    labelled: dict[str, Label] = {}
    for answer in answers.root:
        if not 0 <= answer.id < len(batch):
            continue
        slug = answer.category if answer.category in slugs else by_label.get(answer.category.casefold())
        if slug is not None:
            labelled[batch[answer.id].key] = Label(slug, min(max(answer.confidence, 0.0), 1.0))
    return labelled
