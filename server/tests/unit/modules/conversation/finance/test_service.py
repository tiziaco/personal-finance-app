"""The finance toolkit without a database: periods checked against the data, the preamble, the tool list."""

import asyncio
import datetime as dt
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.chatbot.toolkit import ToolArgumentError, TurnContext
from app.modules.analytics import AnalyticsHistory, DateRange
from app.modules.conversation.finance import service
from app.modules.conversation.finance.schemas import PeriodArgs
from app.modules.conversation.finance.service import (
    NO_TRANSACTIONS,
    finance_toolkit,
    preamble,
    to_date_range,
    turn_history,
)
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 10, 20)
HISTORY = AnalyticsHistory(
    rows=(row("2025-03-02", "-40.00"), row("2026-09-05", "-300.00"), row("2026-10-19", "-25.00")),
    today=TODAY,
)
EMPTY = AnalyticsHistory(rows=(), today=TODAY)


def args(**kwargs) -> PeriodArgs:
    return PeriodArgs.model_validate(kwargs)


def test_months_become_the_analytics_range():
    assert to_date_range(args(months=3), HISTORY) == DateRange(months=3)


def test_dates_inside_the_data_become_the_analytics_range():
    expected = DateRange(date_from=dt.date(2026, 9, 1), date_to=dt.date(2026, 9, 30))
    assert to_date_range(args(date_from="2026-09-01", date_to="2026-09-30"), HISTORY) == expected


def test_range_before_the_data_names_the_span():
    with pytest.raises(ToolArgumentError, match="data covers March 2025 to October 2026") as error:
        to_date_range(args(date_from="2019-01-01", date_to="2019-12-31"), HISTORY)
    assert "No transactions from 2019-01-01 to 2019-12-31" in str(error.value)


def test_range_after_the_data_names_the_span():
    with pytest.raises(ToolArgumentError, match="data covers March 2025 to October 2026"):
        to_date_range(args(date_from="2026-11-01"), HISTORY)


def test_an_inverted_range_names_the_span():
    with pytest.raises(ToolArgumentError, match="date_from 2026-09-30 is after date_to 2026-09-01; the data covers"):
        to_date_range(args(date_from="2026-09-30", date_to="2026-09-01"), HISTORY)


@pytest.mark.parametrize("period", [{"months": 1}, {"date_from": "2026-09-01"}])
def test_no_transactions_is_an_argument_error_not_zeros(period):
    with pytest.raises(ToolArgumentError, match=NO_TRANSACTIONS):
        to_date_range(args(**period), EMPTY)


def ctx() -> TurnContext:
    return TurnContext(user_id=uuid.uuid4(), session_factory=MagicMock())


async def test_preamble_names_the_last_finished_month_and_the_span():
    with patch.object(service.analytics_service, "history", AsyncMock(return_value=HISTORY)):
        text = await preamble(ctx())
    assert text == "Last finished month: September 2026; data covers March 2025 to October 2026."


@pytest.mark.parametrize(
    ("rows", "gap", "latest"),
    [
        # Today is October: September has no transactions, so the dashboard's month is August.
        ((row("2025-03-02", "-40.00"), row("2026-08-05", "-300.00")), "September 2026", "August 2026"),
        (
            (row("2025-03-02", "-40.00"), row("2026-06-05", "-300.00"), row("2026-10-19", "-25.00")),
            "Jul – Sep 2026",
            "June 2026",
        ),
    ],
)
async def test_preamble_after_a_month_without_transactions_names_both_months(rows, gap, latest):
    history = AnalyticsHistory(rows=rows, today=TODAY)
    with patch.object(service.analytics_service, "history", AsyncMock(return_value=history)):
        text = await preamble(ctx())
    last = rows[-1].date.strftime("%B %Y")
    assert text == (
        f"Last finished month: September 2026. There are no transactions in {gap}; the latest finished month "
        f"with transactions is {latest}, and `months` counts back from it. The data covers March 2025 to {last}."
    )


async def test_preamble_when_no_month_has_finished():
    only_now = AnalyticsHistory(rows=(row("2026-10-03", "-5.00"), row("2026-10-19", "-25.00")), today=TODAY)
    with patch.object(service.analytics_service, "history", AsyncMock(return_value=only_now)):
        text = await preamble(ctx())
    assert text == "No month has finished yet: the user's data covers only October 2026 so far."


async def test_preamble_without_transactions():
    with patch.object(service.analytics_service, "history", AsyncMock(return_value=EMPTY)):
        assert await preamble(ctx()) == NO_TRANSACTIONS


async def test_concurrent_calls_share_one_history_load():
    turn = ctx()
    load = AsyncMock(return_value=HISTORY)
    with patch.object(service.analytics_service, "history", load):
        first, second = await asyncio.gather(turn_history(turn), turn_history(turn))
        third = await turn_history(turn)
    assert first is second is third is HISTORY
    load.assert_awaited_once()
    assert load.await_args.args[1] == turn.user_id


def test_the_toolkit_holds_the_finance_tools():
    toolkit = finance_toolkit()
    assert [t.name for t in toolkit.tools] == [
        "spending_overview",
        "category_breakdown",
        "top_merchants",
        "recurring_costs",
        "spending_behaviour",
        "unusual_spending",
        "search_transactions",
    ]
    assert [t.title for t in toolkit.tools] == [
        "Spending overview",
        "Spending by category",
        "Top merchants",
        "Recurring costs",
        "Spending patterns",
        "Unusual spending",
        "Transaction search",
    ]
    assert toolkit.preamble is preamble
    for tool in (t for t in toolkit.tools if issubclass(t.args_schema, PeriodArgs)):
        parameters = tool.as_schema()["function"]["parameters"]["properties"]
        assert {"months", "date_from", "date_to"} <= parameters.keys()
        assert "user" not in " ".join(parameters)
        assert "Not for" in tool.description
