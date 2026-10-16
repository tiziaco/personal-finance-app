"""The insights writer: the figures of a month, narrated as 0–10 insights (docs/product/features/insights.md).

One model call, no graph. It imports nothing from a module (R2): the figures,
the category list and the merchant names come in as plain values.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, PrivateAttr, RootModel, ValidationError, model_validator

from app.agents.shared.observability import create_trace_config
from app.agents.shared.structured import ask_json, structured_llm_service
from app.core.logging import logger

PROMPT_VERSION = "v1"
MAX_INSIGHTS = 10

_PROMPT = (Path(__file__).parent / "prompts" / f"{PROMPT_VERSION}.md").read_text(encoding="utf-8")

Section = Literal["spending", "recurring", "savings", "anomalies", "comparisons"]
Severity = Literal["info", "low", "medium", "high", "critical"]
Period = Literal["month", "month_to_date"]

_SEVERITY_ORDER: tuple[Severity, ...] = ("info", "low", "medium", "high", "critical")
_MONTH_TO_DATE_CAP: Severity = "medium"


@dataclass(frozen=True)
class InsightsInput:
    """What the model is given: the reference month, the month so far, and the figures as JSON-able values."""

    reference_month: str
    reference_partial: bool
    month_to_date_through: Optional[date]
    figures: dict[str, Any]
    categories: list[tuple[str, str]]
    merchants: frozenset[str]


@dataclass(frozen=True)
class KeyFigure:
    """The card's chip: a number the web formats, and a short qualifier."""

    kind: Literal["amount", "percent", "count"]
    value: Decimal
    qualifier: str


@dataclass(frozen=True)
class InsightLink:
    """Where the card leads: the recurring list, a category slug, or a merchant named in the figures."""

    kind: Literal["recurring", "category", "merchant"]
    category: Optional[str]
    merchant: Optional[str]


@dataclass(frozen=True)
class WrittenInsight:
    """One insight, as validated: its link is real and a month-to-date card is at most `medium`."""

    section: Section
    severity: Severity
    period: Period
    summary: str
    narrative: str
    key_figure: Optional[KeyFigure]
    link: Optional[InsightLink]


class _KeyFigure(BaseModel):
    kind: Literal["amount", "percent", "count"]
    value: Decimal
    qualifier: str


class _Link(BaseModel):
    # A loose shape: a bad link drops the link in write_insights, never the whole answer.
    kind: str
    category: Optional[str] = None
    merchant: Optional[str] = None


class _Insight(BaseModel):
    section: Section
    severity: Severity
    period: Period
    summary: str = Field(min_length=1)
    narrative: str = Field(min_length=1)
    key_figure: Optional[_KeyFigure] = None
    link: Optional[_Link] = None


class _Insights(RootModel[list[_Insight]]):
    """The answer: a list of at most MAX_INSIGHTS. An invalid item is dropped, not the answer, unless all are."""

    root: list[_Insight] = Field(max_length=MAX_INSIGHTS)
    _dropped: int = PrivateAttr(default=0)

    @model_validator(mode="wrap")
    @classmethod
    def _drop_invalid_items(cls, value: Any, handler: Any) -> "_Insights":
        # Not a list, or too long: the strict parse rejects it, and ask_json asks once more.
        if not isinstance(value, list) or len(value) > MAX_INSIGHTS:
            return handler(value)
        valid: list[_Insight] = []
        for item in value:
            try:
                valid.append(_Insight.model_validate(item))
            except ValidationError:
                continue
        if value and not valid:
            raise ValueError("every insight in the answer was invalid")
        answer = handler(valid)
        answer._dropped = len(value) - len(valid)
        return answer


async def write_insights(data: InsightsInput, *, user_id: uuid.UUID, generation_id: uuid.UUID) -> list[WrittenInsight]:
    """The model's insights about `data`, in its order.

    Raises InvalidModelAnswer (still invalid after one retry) and LLMServiceError unchanged.
    """
    config = create_trace_config(user_id, generation_id, "insights", metadata={"prompt_version": PROMPT_VERSION})
    system = _PROMPT.format(categories="\n".join(f"- {slug}: {label}" for slug, label in data.categories))
    user = json.dumps(
        {
            "reference_month": data.reference_month,
            "reference_partial": data.reference_partial,
            "month_to_date_through": data.month_to_date_through.isoformat() if data.month_to_date_through else None,
            "figures": data.figures,
        },
        ensure_ascii=False,
    )
    answer = await ask_json(structured_llm_service, system, user, _Insights, config)
    if answer._dropped:
        logger.warning("insights_items_dropped", generation_id=str(generation_id), dropped=answer._dropped)

    slugs = {slug for slug, _ in data.categories}
    written: list[WrittenInsight] = []
    for item in answer.root:
        if item.period == "month_to_date" and data.month_to_date_through is None:
            continue
        written.append(
            WrittenInsight(
                section=item.section,
                severity=_capped(item.severity) if item.period == "month_to_date" else item.severity,
                period=item.period,
                summary=item.summary,
                narrative=item.narrative,
                key_figure=(
                    KeyFigure(item.key_figure.kind, item.key_figure.value, item.key_figure.qualifier)
                    if item.key_figure
                    else None
                ),
                link=_valid_link(item.link, slugs, data.merchants),
            )
        )
    return written


def _capped(severity: Severity) -> Severity:
    """Half a month is a hint, not a verdict: a month-to-date card stops at `medium`."""
    cap = _SEVERITY_ORDER.index(_MONTH_TO_DATE_CAP)
    return severity if _SEVERITY_ORDER.index(severity) <= cap else _MONTH_TO_DATE_CAP


def _valid_link(link: Optional[_Link], slugs: set[str], merchants: frozenset[str]) -> Optional[InsightLink]:
    """The link if it leads somewhere real, else None: a category slug from the list, a merchant from the figures."""
    if link is None:
        return None
    if link.kind == "recurring":
        return InsightLink("recurring", None, None)
    if link.kind == "category" and link.category in slugs:
        return InsightLink("category", link.category, None)
    if link.kind == "merchant" and link.merchant in merchants:
        return InsightLink("merchant", None, link.merchant)
    return None
