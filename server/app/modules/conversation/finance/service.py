"""The chat's finance toolkit: seven read-only tools over one `AnalyticsHistory` per turn, and the turn's preamble.

Each tool wraps one `AnalyticsHistory` method, so the assistant's figures are the
dashboard's and the analytics page's (spec §3). The history loads once per turn into
`TurnContext.cache` and every tool in the turn reads it (§5.3). No tool takes a user:
they read `TurnContext.user_id`.
"""

import asyncio
import datetime as dt
from collections.abc import Callable
from functools import partial
from typing import TypeVar

from app.agents.chatbot.toolkit import AgentTool, ToolArgumentError, Toolkit, ToolOutcome, TurnContext
from app.modules.analytics import AnalyticsHistory, DateRange, analytics_service
from app.modules.conversation.finance.display import (
    category_breakdown_outcome,
    recurring_costs_outcome,
    search_outcome,
    spending_behaviour_outcome,
    spending_overview_outcome,
    top_merchants_outcome,
    unusual_spending_outcome,
)
from app.modules.conversation.finance.domain.periods import (
    describe_span,
    month_name,
    name_period,
    period_label,
)
from app.modules.conversation.finance.domain.search import search_rows
from app.modules.conversation.finance.schemas import PeriodArgs, SearchArgs, TopMerchantsArgs
from app.modules.transaction import CATEGORIES

A = TypeVar("A", bound=PeriodArgs)
R = TypeVar("R")

HISTORY_KEY = "history"
ONE_DAY = dt.timedelta(days=1)
NO_TRANSACTIONS = "The user has no transactions yet."
CATEGORY_NAMES = dict(CATEGORIES)
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


async def _load_history(ctx: TurnContext) -> AnalyticsHistory:
    async with ctx.session_factory() as session:
        return await analytics_service.history(session, ctx.user_id)


async def turn_history(ctx: TurnContext) -> AnalyticsHistory:
    """The signed-in user's history, loaded once per turn and shared by the turn's tool calls.

    The cache holds the load itself, not its result, so tool calls running concurrently
    wait on the one load instead of each starting their own.
    """
    load = ctx.cache.get(HISTORY_KEY)
    if load is None:
        load = asyncio.ensure_future(_load_history(ctx))
        ctx.cache[HISTORY_KEY] = load
    return await load


def resolve_period(args: PeriodArgs, history: AnalyticsHistory) -> tuple[DateRange, str]:
    """The analytics range for the tool's period and its name; a `ToolArgumentError` naming the data span when it holds no data."""
    span = history.span()
    if span is None:
        raise ToolArgumentError(NO_TRANSACTIONS)
    covers = describe_span(*span)
    if args.date_from and args.date_to and args.date_from > args.date_to:
        raise ToolArgumentError(
            f"date_from {args.date_from.isoformat()} is after date_to {args.date_to.isoformat()}; the {covers}."
        )
    if args.months is not None:
        date_range = DateRange(months=args.months)
    else:
        date_range = DateRange(date_from=args.date_from, date_to=args.date_to)
    period = history.period(date_range)
    if period is None:
        asked = f"{args.date_from.isoformat() if args.date_from else 'the start'} to " + (
            args.date_to.isoformat() if args.date_to else "the end"
        )
        raise ToolArgumentError(f"No transactions from {asked}: the {covers}.")
    return date_range, period_label(period.first_day, period.last_day, today=history.today, data_last=span[1])


async def preamble(ctx: TurnContext) -> str:
    """What the model is told about the user's data each turn: the last finished month and the span covered.

    The calendar's last finished month and the dashboard's differ after a month with no
    transactions: `months` counts back from the latest finished month holding one, so the
    model is told both, or it would call that month "last month".
    """
    history = await turn_history(ctx)
    span = history.span()
    if span is None:
        return NO_TRANSACTIONS
    # The dashboard's reference month: the latest finished month holding a transaction.
    reference = history.period(DateRange(months=1))
    last_day = reference.last_day
    label = period_label(reference.first_day, last_day, today=history.today, data_last=span[1])
    if (last_day.year, last_day.month) == (history.today.year, history.today.month):
        return f"No month has finished yet: the user's data covers only {label}."
    last_finished_end = history.today.replace(day=1) - ONE_DAY
    # A finished month's period runs to its last day, so the gap starts the day after.
    gap_start = last_day + ONE_DAY
    if gap_start > last_finished_end:
        return f"Last finished month: {label}; {describe_span(*span)}."
    return (
        f"Last finished month: {month_name(last_finished_end)}. There are no transactions in "
        f"{name_period(gap_start, last_finished_end)}; the latest finished month with transactions is {label}, "
        f"and `months` counts back from it. The {describe_span(*span)}."
    )


def _analytics_tool(
    name: str,
    title: str,
    description: str,
    args_schema: type[A],
    fetch: Callable[[AnalyticsHistory, DateRange, A], R],
    render: Callable[[R, str], ToolOutcome],
) -> AgentTool:
    """A tool over one analytics method: resolve the period on the turn's history, `fetch` the response, `render` it."""

    async def run(args: A, ctx: TurnContext) -> ToolOutcome:
        history = await turn_history(ctx)
        date_range, label = resolve_period(args, history)
        return render(fetch(history, date_range, args), label)

    return AgentTool(name=name, title=title, description=description + PERIOD_HELP, args_schema=args_schema, run=run)


async def _search_transactions(args: SearchArgs, ctx: TurnContext) -> ToolOutcome:
    history = await turn_history(ctx)
    span = history.span()
    if span is None:
        raise ToolArgumentError(NO_TRANSACTIONS)
    return search_outcome(search_rows(history.rows, args), args, CATEGORY_NAMES, span)


def finance_toolkit() -> Toolkit:
    """The chat's finance tools and preamble, injected into the chatbot agent at startup."""
    tools = [
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
        AgentTool(
            name="search_transactions",
            title="Transaction search",
            description="Count and total the transactions matching filters (merchant, dates, categories, amounts, "
            "recurring, weekdays), with money out and money in totalled separately, optionally grouped by month, "
            "merchant, category or weekday, and a sample of the largest or most recent. Use for one merchant, "
            '"how many" and "how much on" questions. It searches the same transactions the analytics tools use. '
            "Amounts are signed: spending is negative.",
            args_schema=SearchArgs,
            run=_search_transactions,
        ),
    ]
    return Toolkit(tools=tools, preamble=preamble)
