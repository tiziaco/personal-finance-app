"""The `search_transactions` tool: its arguments, and the pure filter that totals and groups the turn's transactions (spec §3).

Pure: it works on the rows the turn already holds. Money out (negative amounts) and money in
(positive) are totalled apart and never netted, so a refund does not hide spending (spec §1).
"""

import datetime as dt
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Annotated, Literal, Optional

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, ToolException
from pydantic import Field, StringConstraints, WithJsonSchema, model_validator

from app.agents.chatbot.context import TurnContext
from app.modules.conversation.tools.base import CATEGORY_NAMES, NO_TRANSACTIONS, ToolArgs, chat_tool, turn_history
from app.modules.transaction import MAX_DATE, MIN_DATE, AnalysisRow, Category

# Pydantic describes a Decimal as number-or-string with a lookahead regex `pattern`, and a model bound
# to that schema answers nothing. The model sends a JSON number; pydantic reads a float through its
# shortest repr (-0.1 is Decimal("-0.1")), so amounts stay exact server side.
Amount = Annotated[Decimal, WithJsonSchema({"type": "number"})]


class SearchArgs(ToolArgs):
    """Filters for `search_transactions`; every one is optional and they all apply together."""

    merchant: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]] = Field(
        None, description='Part of the merchant name, any case ("lidl" finds "LIDL Berlin").'
    )
    date_from: Optional[dt.date] = Field(
        None, ge=MIN_DATE, le=MAX_DATE, description="First day, inclusive (YYYY-MM-DD)."
    )
    date_to: Optional[dt.date] = Field(None, ge=MIN_DATE, le=MAX_DATE, description="Last day, inclusive (YYYY-MM-DD).")
    categories: Optional[list[Category]] = Field(
        None, max_length=len(Category), description="Only these categories, by slug (the one in brackets)."
    )
    amount_min: Optional[Amount] = Field(
        None,
        description="Smallest signed amount in EUR: spending is negative, so -100 means spending up to 100 or any income.",
    )
    amount_max: Optional[Amount] = Field(
        None, description="Largest signed amount in EUR: -50 keeps spending of at least 50; 0 keeps only spending."
    )
    recurring_only: bool = Field(False, description="Only transactions marked recurring.")
    weekdays: Optional[list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]]] = Field(
        None, max_length=7, description="Only these days of the week."
    )
    group_by: Optional[Literal["month", "merchant", "category", "weekday"]] = Field(
        None, description="Also total the matches per month, merchant, category or weekday."
    )
    sample: Literal["largest", "recent"] = Field(
        "largest", description="Which matches to list: the largest by amount, or the most recent."
    )

    @model_validator(mode="after")
    def _ranges_are_ordered(self) -> "SearchArgs":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError(
                f"date_from {self.date_from.isoformat()} is after date_to {self.date_to.isoformat()}; "
                "date_from must be the earlier day"
            )
        if self.amount_min is not None and self.amount_max is not None and self.amount_min > self.amount_max:
            raise ValueError(
                f"amount_min {self.amount_min} is above amount_max {self.amount_max}; amount_min must be the lower bound"
            )
        return self


SAMPLE_SIZE = 20  # transactions listed
GROUP_LIMIT = 24  # groups listed; 24 covers two years of months
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass
class Totals:
    """How many transactions, and their summed signed amount."""

    count: int = 0
    total: Decimal = Decimal(0)

    def add(self, amount: Decimal) -> None:
        """Count one more transaction."""
        self.count += 1
        self.total += amount


@dataclass
class SearchResult:
    """What the filters matched: totals per direction, groups, a sample and the span covered."""

    money_out: Totals
    money_in: Totals
    # (group label, money out, money in), the biggest spend first
    groups: list[tuple[str, Totals, Totals]]
    sample: list[AnalysisRow]
    matched: int
    span: Optional[tuple[dt.date, dt.date]] = field(default=None)  # first and last day among the matches


def _matches(row: AnalysisRow, args: SearchArgs) -> bool:
    if args.merchant and args.merchant.casefold() not in row.merchant.casefold():
        return False
    if args.date_from and row.date < args.date_from:
        return False
    if args.date_to and row.date > args.date_to:
        return False
    if args.categories and row.category not in {c.value for c in args.categories}:
        return False
    if args.amount_min is not None and row.amount < args.amount_min:
        return False
    if args.amount_max is not None and row.amount > args.amount_max:
        return False
    if args.recurring_only and not row.is_recurring:
        return False
    return not args.weekdays or WEEKDAYS[row.date.weekday()] in args.weekdays


def _group_label(row: AnalysisRow, group_by: str) -> str:
    if group_by == "month":
        return f"{row.date.year}-{row.date.month:02d}"
    if group_by == "merchant":
        return row.merchant_key  # one group per merchant however it was cased; shown by its first spelling
    if group_by == "weekday":
        return WEEKDAYS[row.date.weekday()]
    return row.category


def search_rows(rows: Sequence[AnalysisRow], args: SearchArgs) -> SearchResult:
    """Totals, groups and a capped sample over the rows matching every filter in `args`."""
    # A zero amount is money neither out nor in (as analytics counts it), so it is not a match.
    matches = [r for r in rows if r.amount != 0 and _matches(r, args)]
    money_out, money_in = Totals(), Totals()
    grouped: dict[str, tuple[Totals, Totals]] = defaultdict(lambda: (Totals(), Totals()))
    spelling: dict[str, str] = {}
    for r in matches:
        (money_out if r.amount < 0 else money_in).add(r.amount)
        if args.group_by:
            label = _group_label(r, args.group_by)
            spelling.setdefault(label, r.merchant if args.group_by == "merchant" else label)
            out, into = grouped[label]
            (out if r.amount < 0 else into).add(r.amount)
    ordered = [(spelling[label], out, into) for label, (out, into) in grouped.items()]
    if args.group_by == "month":
        groups = sorted(ordered, key=lambda g: g[0])  # oldest first; the display keeps the newest
    else:
        groups = sorted(ordered, key=lambda g: (g[1].total, -g[2].total))
    if args.sample == "recent":
        sample = sorted(matches, key=lambda r: r.date, reverse=True)
    else:
        sample = sorted(matches, key=lambda r: abs(r.amount), reverse=True)
    days = [r.date for r in matches]
    return SearchResult(
        money_out=money_out,
        money_in=money_in,
        groups=groups,
        sample=sample[:SAMPLE_SIZE],
        matched=len(matches),
        span=(min(days), max(days)) if days else None,
    )


async def _search_transactions(runtime: ToolRuntime[TurnContext], **kwargs) -> tuple[str, dict]:
    # Imported here: display reads this module's result types, so a top-level import would be a cycle.
    from app.modules.conversation.tools.display import search_outcome

    args = SearchArgs(**kwargs)
    history = await turn_history(runtime.context)
    span = history.span()
    if span is None:
        raise ToolException(NO_TRANSACTIONS)
    content, display = search_outcome(search_rows(history.rows, args), args, CATEGORY_NAMES, span)
    return content, display.model_dump()


def search_tool() -> BaseTool:
    """The `search_transactions` tool."""
    return chat_tool(
        _search_transactions,
        name="search_transactions",
        title="Transaction search",
        description="Count and total the transactions matching filters (merchant, dates, categories, amounts, "
        "recurring, weekdays), with money out and money in totalled separately, optionally grouped by month, "
        "merchant, category or weekday, and a sample of the largest or most recent. Use for one merchant, "
        '"how many" and "how much on" questions. It searches the same transactions the analytics tools use. '
        "Amounts are signed: spending is negative.",
        args_schema=SearchArgs,
    )
