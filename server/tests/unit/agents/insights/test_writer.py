"""The insights writer: one model call, a validated answer (spec §5.3–5.4). The model is stubbed."""

import json
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from tenacity import wait_none
from uuid_utils.compat import uuid7

from app.agents.insights import (
    MAX_INSIGHTS,
    InsightLink,
    InsightsInput,
    KeyFigure,
    WrittenInsight,
    write_insights,
)
from app.agents.shared import structured
from app.agents.shared.structured import InvalidModelAnswer
from app.integrations.llm import LLMAPIError, LLMServiceError

pytestmark = pytest.mark.unit

IDS = {"user_id": uuid7(), "generation_id": uuid7()}
WRITER = "app.agents.insights.writer"


def data(*, month_to_date_through: date | None = date(2026, 10, 14)) -> InsightsInput:
    return InsightsInput(
        reference_month="2026-09",
        reference_partial=False,
        month_to_date_through=month_to_date_through,
        figures={"spending": {"total_expenses": "1240.00"}, "merchants": [{"merchant": "REWE", "total": "312.40"}]},
        categories=[("food_groceries", "Food & Groceries"), ("shopping", "Shopping")],
        merchants=frozenset({"REWE", "Netflix"}),
    )


def insight(**overrides) -> dict:
    return {
        "section": "spending",
        "severity": "low",
        "period": "month",
        "summary": "Groceries were your largest category.",
        "narrative": "You spent €312 at REWE.",
        "key_figure": None,
        "link": None,
        **overrides,
    }


@pytest.fixture(autouse=True)
def no_langfuse():
    with patch(f"{WRITER}.create_trace_config", return_value={"metadata": {}}):
        yield


@pytest.fixture(autouse=True)
def no_backoff():
    """The retry's real backoff would sleep a second; tenacity reads `wait` from the decorated function."""
    original = structured._ask_once.retry.wait
    structured._ask_once.retry.wait = wait_none()
    yield
    structured._ask_once.retry.wait = original


def answering(items: list[dict], seen: dict | None = None):
    """An ask_json stub that validates `items` against the writer's own answer shape."""

    async def fake(service, system, user, shape, config):
        if seen is not None:
            seen.update(system=system, user=user, config=config)
        return shape.model_validate(items)

    return fake


async def test_returns_the_insights_in_order():
    items = [
        insight(
            section="savings",
            severity="high",
            summary="You saved 4% of your income.",
            key_figure={"kind": "percent", "value": 4.2, "qualifier": "savings rate"},
            link={"kind": "recurring"},
        ),
        insight(section="anomalies", severity="medium", link={"kind": "merchant", "merchant": "REWE"}),
        insight(section="spending", severity="info", link={"kind": "category", "category": "shopping"}),
    ]
    with patch(f"{WRITER}.ask_json", answering(items)):
        result = await write_insights(data(), **IDS)
    assert result == [
        WrittenInsight(
            section="savings",
            severity="high",
            period="month",
            summary="You saved 4% of your income.",
            narrative="You spent €312 at REWE.",
            key_figure=KeyFigure(kind="percent", value=Decimal("4.2"), qualifier="savings rate"),
            link=InsightLink(kind="recurring", category=None, merchant=None),
        ),
        WrittenInsight(
            section="anomalies",
            severity="medium",
            period="month",
            summary="Groceries were your largest category.",
            narrative="You spent €312 at REWE.",
            key_figure=None,
            link=InsightLink(kind="merchant", category=None, merchant="REWE"),
        ),
        WrittenInsight(
            section="spending",
            severity="info",
            period="month",
            summary="Groceries were your largest category.",
            narrative="You spent €312 at REWE.",
            key_figure=None,
            link=InsightLink(kind="category", category="shopping", merchant=None),
        ),
    ]


async def test_zero_insights_is_valid():
    with patch(f"{WRITER}.ask_json", answering([])):
        assert await write_insights(data(), **IDS) == []


async def test_more_than_ten_is_invalid():
    """The real parse runs: eleven insights fail validation, are asked once more, then raise."""
    service = MagicMock()
    service.call = AsyncMock(return_value=AIMessage(content=json.dumps([insight()] * (MAX_INSIGHTS + 1))))
    with patch(f"{WRITER}.structured_llm_service", service), pytest.raises(InvalidModelAnswer):
        await write_insights(data(), **IDS)
    assert service.call.await_count == 2


async def test_ten_insights_is_valid_through_the_real_parse():
    service = MagicMock()
    service.call = AsyncMock(return_value=AIMessage(content=json.dumps([insight()] * MAX_INSIGHTS)))
    with patch(f"{WRITER}.structured_llm_service", service):
        assert len(await write_insights(data(), **IDS)) == MAX_INSIGHTS


async def test_an_unknown_merchant_or_category_link_is_dropped_not_the_card():
    items = [
        insight(summary="unknown merchant", link={"kind": "merchant", "merchant": "Lidl"}),
        insight(summary="wrong case", link={"kind": "merchant", "merchant": "rewe"}),
        insight(summary="label not slug", link={"kind": "category", "category": "Shopping"}),
        insight(summary="no slug", link={"kind": "category"}),
        insight(summary="unknown kind", link={"kind": "url", "merchant": "REWE"}),
    ]
    with patch(f"{WRITER}.ask_json", answering(items)):
        result = await write_insights(data(), **IDS)
    assert [(i.summary, i.link) for i in result] == [
        ("unknown merchant", None),
        ("wrong case", None),
        ("label not slug", None),
        ("no slug", None),
        ("unknown kind", None),
    ]


async def test_month_to_date_severity_is_capped_at_medium():
    items = [
        insight(period="month_to_date", severity="critical"),
        insight(period="month_to_date", severity="high"),
        insight(period="month_to_date", severity="low"),
        insight(period="month", severity="critical"),
    ]
    with patch(f"{WRITER}.ask_json", answering(items)):
        result = await write_insights(data(), **IDS)
    assert [(i.period, i.severity) for i in result] == [
        ("month_to_date", "medium"),
        ("month_to_date", "medium"),
        ("month_to_date", "low"),
        ("month", "critical"),
    ]


async def test_month_to_date_insight_without_month_to_date_data_is_dropped():
    items = [
        insight(summary="first", period="month"),
        insight(summary="so far", period="month_to_date"),
        insight(summary="last", period="month"),
    ]
    with patch(f"{WRITER}.ask_json", answering(items)):
        result = await write_insights(data(month_to_date_through=None), **IDS)
    assert [i.summary for i in result] == ["first", "last"]


async def test_the_user_message_carries_the_figures():
    seen: dict = {}
    given = data()
    with patch(f"{WRITER}.ask_json", answering([], seen)):
        await write_insights(given, **IDS)
    user = json.loads(seen["user"])
    assert user == {
        "reference_month": "2026-09",
        "reference_partial": False,
        "month_to_date_through": "2026-10-14",
        "figures": given.figures,
    }
    assert "- food_groceries: Food & Groceries" in seen["system"]
    assert "{categories}" not in seen["system"]


async def test_the_call_is_traced_as_insights_with_the_prompt_version():
    trace = MagicMock(return_value={"metadata": {}})
    with patch(f"{WRITER}.create_trace_config", trace), patch(f"{WRITER}.ask_json", answering([])):
        await write_insights(data(), **IDS)
    trace.assert_called_once_with(IDS["user_id"], IDS["generation_id"], "insights", metadata={"prompt_version": "v1"})


async def test_a_model_error_propagates():
    with (
        patch(f"{WRITER}.ask_json", AsyncMock(side_effect=LLMAPIError("down"))),
        pytest.raises(LLMServiceError),
    ):
        await write_insights(data(), **IDS)
