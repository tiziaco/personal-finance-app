"""Filter, total and group the turn's transactions for `search_transactions` (spec §3).

Pure: it works on the rows the turn already holds. Money out (negative amounts) and money in
(positive) are totalled apart and never netted, so a refund does not hide spending (spec §1).
"""

import datetime as dt
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.modules.conversation.finance.schemas import SearchArgs
    from app.modules.transaction import AnalysisRow

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
    sample: list["AnalysisRow"]
    matched: int
    span: Optional[tuple[dt.date, dt.date]] = field(default=None)  # first and last day among the matches


def _matches(row: "AnalysisRow", args: "SearchArgs") -> bool:
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


def _group_label(row: "AnalysisRow", group_by: str) -> str:
    if group_by == "month":
        return f"{row.date.year}-{row.date.month:02d}"
    if group_by == "merchant":
        return row.merchant_key  # one group per merchant however it was cased; shown by its first spelling
    if group_by == "weekday":
        return WEEKDAYS[row.date.weekday()]
    return row.category


def search_rows(rows: Sequence["AnalysisRow"], args: "SearchArgs") -> SearchResult:
    """Totals, groups and a capped sample over the rows matching every filter in `args`."""
    matches = [r for r in rows if _matches(r, args)]
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
    groups = sorted(
        ((spelling[label], out, into) for label, (out, into) in grouped.items()),
        key=lambda g: (g[1].total, -g[2].total),
    )
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
