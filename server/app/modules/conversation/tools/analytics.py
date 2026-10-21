"""The six analytics tools: two argument models and one factory over the turn's `AnalyticsHistory`.

Each tool wraps one `AnalyticsHistory` method, so the assistant's figures are the
dashboard's and the analytics page's (spec §3). The history loads once per turn into
`TurnContext.history` and every tool in the turn reads it (§5.3). No tool takes a user:
they read `runtime.context.user_id`.
"""

import datetime as dt
from collections.abc import Callable
from functools import partial
from typing import Optional, TypeVar

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool
from pydantic import Field, model_validator

from app.agents.chatbot.context import TurnContext
from app.modules.analytics import AnalyticsHistory, DateRange
from app.modules.conversation.schemas import ToolDisplay
from app.modules.conversation.tools.base import CATEGORY_NAMES, ToolArgs, chat_tool, turn_history
from app.modules.conversation.tools.display import (
    category_breakdown_outcome,
    recurring_costs_outcome,
    spending_behaviour_outcome,
    spending_overview_outcome,
    top_merchants_outcome,
    unusual_spending_outcome,
)
from app.modules.conversation.tools.periods import resolve_period
from app.modules.transaction import CATEGORIES, MAX_DATE, MIN_DATE

A = TypeVar("A", bound="PeriodArgs")
R = TypeVar("R")

# Every category: the list is fixed and short, and Savings & Investments must never be cut (spec §1).
CATEGORY_TOP_N = len(CATEGORIES)
# The analytics router's defaults, so "unusual" means what the analytics page means.
ANOMALY_STD_THRESHOLD = 2.5
ANOMALY_WINDOW_DAYS = 30

PERIOD_HELP = (
    " Period: `months` for the last N finished months, counted back from the latest finished month with "
    "transactions as the dashboard counts them (1 = that month), "
    "or `date_from`/`date_to` (YYYY-MM-DD) for a named month, a range, or the month in progress."
)


class PeriodArgs(ToolArgs):
    """The period an analytics tool covers: the last `months` finished months, or ISO date bounds.

    Every analytics tool's arguments extend it. Whether the period holds any data is checked
    against the user's history when the tool runs (`resolve_period`), not here.
    """

    months: Optional[int] = Field(
        None,
        ge=1,
        le=120,
        description="The last N finished months, as the dashboard counts them: back from the latest finished month "
        "with transactions, which the turn context names (1 = that month). Never includes the month in progress.",
    )
    date_from: Optional[dt.date] = Field(
        None,
        ge=MIN_DATE,
        le=MAX_DATE,
        description="First day, inclusive (YYYY-MM-DD). Use date bounds for a named month, a range of months "
        "or the month in progress.",
    )
    date_to: Optional[dt.date] = Field(None, ge=MIN_DATE, le=MAX_DATE, description="Last day, inclusive (YYYY-MM-DD).")

    @model_validator(mode="after")
    def _one_kind_of_period(self) -> "PeriodArgs":
        dated = self.date_from is not None or self.date_to is not None
        if self.months is not None and dated:
            raise ValueError("give either months or date_from/date_to, not both")
        if self.months is None and not dated:
            raise ValueError("give a period: months (the last N finished months) or date_from/date_to")
        return self


class TopMerchantsArgs(PeriodArgs):
    """The period, and how many merchants to rank."""

    top_n: int = Field(10, ge=1, le=15, description="How many merchants to rank by spend.")


def _analytics_tool(
    name: str,
    title: str,
    description: str,
    args_schema: type[A],
    fetch: Callable[[AnalyticsHistory, DateRange, A], R],
    render: Callable[[R, str], tuple[str, ToolDisplay]],
) -> BaseTool:
    """A tool over one analytics method: resolve the period on the turn's history, `fetch` the response, `render` it."""

    async def run(runtime: ToolRuntime[TurnContext], **kwargs) -> tuple[str, dict]:
        args = args_schema(**kwargs)
        history = await turn_history(runtime.context)
        date_range, label = resolve_period(args, history)
        content, display = render(fetch(history, date_range, args), label)
        return content, display.model_dump()

    return chat_tool(run, name=name, title=title, description=description + PERIOD_HELP, args_schema=args_schema)


def analytics_tools() -> list[BaseTool]:
    """The six analytics tools, in the order the model is offered them."""
    return [
        _analytics_tool(
            "spending_overview",
            "Spending overview",
            "Income, expenses, net and the savings rate over a period, with each month's figures and the month in "
            "progress so far. Use for totals, how much was spent or earned, cash flow and the savings rate. Not for "
            "where the money went: use category_breakdown or top_merchants.",
            PeriodArgs,
            lambda h, dr, _: h.spending(dr),
            spending_overview_outcome,
        ),
        _analytics_tool(
            "category_breakdown",
            "Spending by category",
            "Spend per category over a period: total, share, purchases and change against the previous period of the "
            "same length, plus the categories growing and declining. Use for where the money went and for the "
            "Savings & Investments amount. Not for a single merchant: use search_transactions.",
            PeriodArgs,
            lambda h, dr, _: h.categories(dr, CATEGORY_TOP_N),
            partial(category_breakdown_outcome, names=CATEGORY_NAMES),
        ),
        _analytics_tool(
            "top_merchants",
            "Top merchants",
            "The merchants taking the most spend over a period, with share, purchases and dates, the most frequent "
            "ones, and how concentrated spending is. Not for one merchant's transactions: use search_transactions.",
            TopMerchantsArgs,
            lambda h, dr, args: h.merchants(dr, args.top_n),
            top_merchants_outcome,
        ),
        _analytics_tool(
            "recurring_costs",
            "Recurring costs",
            "Spending marked recurring over a period: each recurring merchant's monthly cost, billing rhythm and "
            "whether it still charges, plus merchants charging like a subscription without being marked. Use for "
            "subscriptions and fixed costs. Not for one-off spending.",
            PeriodArgs,
            lambda h, dr, _: h.recurring(dr),
            recurring_costs_outcome,
        ),
        _analytics_tool(
            "spending_behaviour",
            "Spending patterns",
            "How spending is spread over a period: by weekday, weekdays against weekends, by month of the year, and "
            "how steady each category is month to month. Not for totals: use spending_overview.",
            PeriodArgs,
            lambda h, dr, _: h.behaviour(dr),
            partial(spending_behaviour_outcome, names=CATEGORY_NAMES),
        ),
        _analytics_tool(
            "unusual_spending",
            "Unusual spending",
            "Expenses far above what came before them, and categories spending well above their average in the "
            "period's last 30 days. Use for surprises, outliers and spikes. Not for regular spending.",
            PeriodArgs,
            lambda h, dr, _: h.anomalies(dr, ANOMALY_STD_THRESHOLD, ANOMALY_WINDOW_DAYS),
            partial(unusual_spending_outcome, names=CATEGORY_NAMES),
        ),
    ]
