"""Turn an analytics response into a tool result: compact text for the model, a summary and table for the user.

`content` opens with the period, then the figures, money as plain decimals with "EUR",
and stays bounded: long lists are cut to a fixed length and say so. `display` carries
amounts as decimal strings and percents as numbers, each with the kind that decides how
the web shows it, as the analytics page shows the same figure; never formatted strings.
"""

import datetime as dt
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Generic, Optional, TypeVar

from app.modules.conversation.schemas import ColumnKind, SummaryItem, TableColumn, ToolDisplay, ToolTable
from app.modules.conversation.tools.periods import MONTH_NAMES, describe_span, name_period, short_month
from app.modules.conversation.tools.search import GROUP_LIMIT, SearchArgs, SearchResult, Totals

if TYPE_CHECKING:
    from app.modules.analytics import (
        AnomaliesResponse,
        BehaviourResponse,
        CategoryBreakdownResponse,
        MerchantBreakdownResponse,
        RecurringResponse,
        SpendingResponse,
    )

T = TypeVar("T")

MONTHS_SHOWN = 24  # months of a spending series; the most recent are kept
TRENDS_SHOWN = 5  # growing and declining categories each, as on the Trends tab
FREQUENT_SHOWN = 5  # merchants ranked by purchases
RECURRING_SHOWN = 20  # recurring merchants, by monthly cost
HIDDEN_SHOWN = 10  # unflagged merchants charging like a subscription
OUTLIERS_SHOWN = 10  # unusual expenses, by z-score
NO_SPENDING = "No spending in this period."


def _eur(value: Decimal) -> str:
    return f"{value:.2f} EUR"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def _change(value: float) -> str:
    return f"{value:+.1f}%"


def _amount(value: Decimal) -> str:
    """An amount on the wire: a decimal string, so the web reads its sign from the text, never a float."""
    return f"{value:.2f}"


Cell = str | float | int | None


@dataclass(frozen=True)
class Col(Generic[T]):
    """One table column, declared once: its key, header and kind, and how a row's cell is read from an item."""

    key: str
    label: str
    kind: ColumnKind
    cell: Callable[[T], Cell]


def _table(cols: Sequence[Col[T]], items: Iterable[T]) -> Optional[ToolTable]:
    """The table of `items` under `cols`; None without a row."""
    rows = [{c.key: c.cell(item) for c in cols} for item in items]
    if not rows:
        return None
    return ToolTable(columns=[TableColumn(key=c.key, label=c.label, kind=c.kind) for c in cols], rows=rows)


def _capped(items: Sequence[T], limit: int, what: str, lines: list[str], *, last: bool = False) -> Sequence[T]:
    """The first (or last) `limit` items; when more were cut, a line in `lines` says how many are shown."""
    if len(items) <= limit:
        return items
    lines.append(f"({'last' if last else 'top'} {limit} of {len(items)} {what} shown)")
    return items[-limit:] if last else items[:limit]


def _name(slug: str, names: Mapping[str, str]) -> str:
    return names.get(slug, slug)


def _named(slug: str, names: Mapping[str, str]) -> str:
    """A category for the model: its name and the slug the other tools take."""
    return f"{_name(slug, names)} ({slug})"


def _outcome(
    title: str, label: str, lines: list[str], summary: list[SummaryItem], table: Optional[ToolTable]
) -> tuple[str, ToolDisplay]:
    display = ToolDisplay(title=title, period=label, summary=summary, table=table)
    return "\n".join([label, *lines]), display


def _total_item(value: Decimal, label: str) -> SummaryItem:
    return SummaryItem(kind="total", value=_amount(value), label=label)


def spending_overview_outcome(response: "SpendingResponse", label: str) -> tuple[str, ToolDisplay]:
    """Income, expenses, net and the savings rate for the period, with the monthly series and month-to-date."""
    r = response
    rate = _pct(r.savings_rate_pct) if r.savings_rate_pct is not None else "none (no income)"
    lines = [
        f"Income {_eur(r.total_income)}, expenses {_eur(r.total_expenses)}, net {_eur(r.net)}, "
        f"savings rate {rate}; {r.transaction_count} transactions."
    ]
    if None not in (r.average_monthly_income, r.average_monthly_expenses, r.average_monthly_net):
        lines.append(
            f"Monthly averages: income {_eur(r.average_monthly_income)}, expenses {_eur(r.average_monthly_expenses)}, "
            f"net {_eur(r.average_monthly_net)}."
        )
    current = r.month_to_date.month if r.month_to_date else None
    lines.append("By month:")
    months = _capped(r.months, MONTHS_SHOWN, "months", lines, last=True)
    for m in months:
        line = f"- {short_month(m.month)}"
        if m.partial:
            line += " (so far)" if m.month == current else " (partial)"
        line += f": income {_eur(m.income)}, expenses {_eur(m.expenses)}, net {_eur(m.net)}"
        if m.savings_rate_pct is not None:
            line += f", savings rate {_pct(m.savings_rate_pct)}"
        if m.expense_change_pct is not None:
            line += f", expenses {_change(m.expense_change_pct)} on the month before"
        lines.append(line)
    if r.latest_month:
        lm = r.latest_month
        line = f"Latest whole month, {short_month(lm.month)}: income {_eur(lm.income)}, expenses {_eur(lm.expenses)}"
        if lm.expenses_vs_average_pct is not None:
            line += f"; expenses {_change(lm.expenses_vs_average_pct)} against the period's monthly average"
        lines.append(line + ".")
    if r.month_to_date:
        mtd = r.month_to_date
        lines.append(
            f"Month in progress, {short_month(mtd.month)} through {mtd.through.isoformat()}: income {_eur(mtd.income)}, "
            f"expenses {_eur(mtd.expenses)}; the same days of {short_month(mtd.previous_month)}: "
            f"income {_eur(mtd.previous_income)}, expenses {_eur(mtd.previous_expenses)}."
        )
    summary = [_total_item(r.total_expenses, "spent"), _total_item(r.total_income, "income")]
    if r.savings_rate_pct is not None:
        summary.append(SummaryItem(kind="rate", value=r.savings_rate_pct, label="savings rate"))
    table = _table(
        [
            Col("month", "Month", "text", lambda m: short_month(m.month)),
            Col("income", "Income", "total", lambda m: _amount(m.income)),
            Col("expenses", "Expenses", "total", lambda m: _amount(m.expenses)),
            Col("net", "Net", "net", lambda m: _amount(m.net)),
            Col("savings_rate_pct", "Savings rate", "rate", lambda m: m.savings_rate_pct),
        ],
        months,
    )
    return _outcome("Spending overview", label, lines, summary, table)


def _trend(change_pct: Optional[float]) -> str:
    """A growing or declining category's change, as the Trends tab words it."""
    if change_pct is None:
        return "new"
    return "stopped" if change_pct == -100 else _change(change_pct)


def category_breakdown_outcome(
    response: "CategoryBreakdownResponse", label: str, names: Mapping[str, str]
) -> tuple[str, ToolDisplay]:
    """Spend per category with its share and change against the previous period; growing and declining ones."""
    r = response
    categories = r.top_categories
    if not categories:
        lines = [NO_SPENDING]
    else:
        lines = [f"Expenses {_eur(r.total_expenses)} across {len(categories)} categories."]
        if r.previous_date_from and r.previous_date_to:
            previous = name_period(r.previous_date_from, r.previous_date_to)
            lines.append(f"Changes are against the previous period of the same length, {previous}.")
        else:
            lines.append("No previous period of the same length to compare with.")
        lines.append("By spend:")
        for c in categories:
            line = (
                f"- {_named(c.category, names)}: {_eur(c.total)}, {_pct(c.share_pct)} of expenses, {c.count} purchases"
            )
            if c.change_pct is not None:
                line += f", {_change(c.change_pct)} on {_eur(c.previous_total)} before"
            elif c.previous_total is not None:
                line += ", new (nothing in the previous period)"
            lines.append(line)
        for heading, trends in (("Growing", r.top_growing), ("Declining", r.top_declining)):
            if trends:
                lines.append(f"{heading} (monthly average, earlier half → later half of the period):")
                for t in trends[:TRENDS_SHOWN]:
                    lines.append(
                        f"- {_named(t.category, names)}: {_eur(t.earlier_monthly_average)} → "
                        f"{_eur(t.later_monthly_average)} a month ({_trend(t.change_pct)})"
                    )
    summary = [
        SummaryItem(kind="count", value=len(categories), label="categories"),
        _total_item(r.total_expenses, "spent"),
    ]
    table = _table(
        [
            Col("category", "Category", "text", lambda c: _name(c.category, names)),
            Col("total", "Spent", "total", lambda c: _amount(c.total)),
            Col("share_pct", "Share", "share", lambda c: c.share_pct),
            Col("count", "Purchases", "count", lambda c: c.count),
            Col("change_pct", "Change", "change", _category_change),
        ],
        categories,
    )
    return _outcome("Spending by category", label, lines, summary, table)


def _category_change(c) -> Cell:
    """A category's change, as the analytics page's ranking shows it: "new" when nothing was spent before."""
    if c.change_pct is None and c.previous_total is not None:
        return "new"
    return c.change_pct


def top_merchants_outcome(response: "MerchantBreakdownResponse", label: str) -> tuple[str, ToolDisplay]:
    """The top merchants by spend, the most frequent, and how concentrated spending is."""
    r = response
    c = r.concentration
    if not r.top_by_spend:
        lines = [NO_SPENDING]
    else:
        lines = [
            f"Expenses {_eur(r.total_expenses)} at {c.unique_merchants} merchants; the top 5 take "
            f"{_pct(c.top_5_share_pct)}, the top 10 {_pct(c.top_10_share_pct)}.",
            "Top by spend:",
        ]
        for m in r.top_by_spend:
            lines.append(
                f"- {m.merchant}: {_eur(m.total)}, {_pct(m.share_pct)} of expenses, {m.count} purchases "
                f"(average {_eur(m.average)}), {m.first_date.isoformat()} to {m.last_date.isoformat()}"
            )
        frequent = ", ".join(f"{m.merchant} ({m.count})" for m in r.top_by_frequency[:FREQUENT_SHOWN])
        lines.append(f"Most frequent (purchases): {frequent}.")
    summary = [
        _total_item(r.total_expenses, "spent"),
        SummaryItem(kind="count", value=c.unique_merchants, label="merchants"),
    ]
    if r.top_by_spend:
        summary.append(SummaryItem(kind="share", value=c.top_5_share_pct, label="top 5 share"))
    table = _table(
        [
            Col("merchant", "Merchant", "text", lambda m: m.merchant),
            Col("total", "Spent", "total", lambda m: _amount(m.total)),
            Col("share_pct", "Share", "share", lambda m: m.share_pct),
            Col("count", "Purchases", "count", lambda m: m.count),
        ],
        r.top_by_spend,
    )
    return _outcome("Top merchants", label, lines, summary, table)


def recurring_costs_outcome(response: "RecurringResponse", label: str) -> tuple[str, ToolDisplay]:
    """Recurring spend, each recurring merchant's monthly cost, and unflagged subscription-like charges."""
    r = response
    lines = [
        f"Recurring expenses {_eur(r.recurring_total)} in {r.recurring_count} charges, {_pct(r.amount_share_pct)} "
        f"of all expenses ({_eur(r.total_expenses)}). Monthly cost of those still charging: "
        f"{_eur(r.monthly_recurring_cost)}."
    ]
    merchants = sorted(r.merchants, key=lambda m: (-m.monthly_cost, m.merchant))
    if merchants:
        lines.append("Recurring merchants:")
        merchants = _capped(merchants, RECURRING_SHOWN, "recurring merchants", lines)
        for m in merchants:
            rhythm = f"every {m.interval_days} days" if m.interval_days is not None else "one billing day"
            status = "still charging" if m.active else "no longer charging"
            lines.append(
                f"- {m.merchant}: {_eur(m.monthly_cost)} a month, median charge {_eur(m.median_charge)}, {rhythm}, "
                f"{m.charges} charges, last {m.last_charge.isoformat()}, {status}"
            )
    else:
        lines.append("No merchant is marked recurring in this period.")
    if r.hidden_subscriptions:
        lines.append("Charging like a subscription but not marked recurring:")
        hidden = _capped(r.hidden_subscriptions, HIDDEN_SHOWN, "merchants", lines)
        for h in hidden:
            lines.append(
                f"- {h.merchant}: average charge {_eur(h.average_charge)}, {h.charges} charges over "
                f"{h.months_active} months"
            )
    summary = [
        _total_item(r.monthly_recurring_cost, "a month"),
        SummaryItem(kind="count", value=len(r.merchants), label="recurring"),
    ]
    table = _table(
        [
            Col("merchant", "Merchant", "text", lambda m: m.merchant),
            Col("monthly_cost", "A month", "total", lambda m: _amount(m.monthly_cost)),
            Col("median_charge", "Median charge", "total", lambda m: _amount(m.median_charge)),
            Col("last_charge", "Last charge", "date", lambda m: m.last_charge.isoformat()),
            Col("status", "Status", "text", lambda m: "active" if m.active else "stopped"),
        ],
        merchants,
    )
    return _outcome("Recurring costs", label, lines, summary, table)


def spending_behaviour_outcome(
    response: "BehaviourResponse", label: str, names: Mapping[str, str]
) -> tuple[str, ToolDisplay]:
    """Spend by weekday, weekday against weekend, by month of year, and how steady each category is."""
    r = response
    spent = any(w.total for w in r.by_weekday)
    lines: list[str] = []
    if not spent:
        lines.append(NO_SPENDING)
    else:
        lines.append("By weekday (total, purchases, spend per day):")
        for w in r.by_weekday:
            lines.append(
                f"- {w.name}: {_eur(w.total)}, {w.count} purchases, {_eur(w.per_day)} per day over {w.days} days"
            )
        line = f"Weekdays {_eur(r.weekday.per_day)} per day, weekends {_eur(r.weekend.per_day)} per day"
        if r.weekend_bias_pct is not None:
            line += f"; a weekend day costs {_change(r.weekend_bias_pct)} against a weekday"
        lines.append(line + ".")
        seasons = [s for s in r.seasonality if s.years]
        if seasons:
            lines.append("By month of year (average spend; index 100 is a typical month):")
            for s in seasons:
                index = f"index {s.index:.0f}" if s.index is not None else "no index"
                lines.append(f"- {MONTH_NAMES[s.month - 1]}: {_eur(s.average_spend)}, {index}, over {s.years} year(s)")
        if r.stability:
            lines.append("Category stability (variation of whole-month totals):")
            for s in r.stability:
                lines.append(f"- {_named(s.category, names)}: {s.stability}, cv {s.cv:.2f}, over {s.months} months")
            lines.append(
                f"Spend by stability: stable {_pct(r.stable_share_pct)}, moderate {_pct(r.moderate_share_pct)}, "
                f"volatile {_pct(r.volatile_share_pct)}."
            )
        if r.expense_change_pct is not None:
            lines.append(
                f"Expenses changed {_change(r.expense_change_pct)} between the period's last two whole months."
            )
    summary: list[SummaryItem] = []
    if r.weekend_bias_pct is not None:
        summary.append(SummaryItem(kind="weekendBias", value=r.weekend_bias_pct, label="weekend vs weekday, per day"))
    if spent:
        busiest = max(r.by_weekday, key=lambda w: w.per_day)
        summary.append(SummaryItem(kind="text", value=busiest.name, label="busiest day"))
    table = _table(
        [
            Col("weekday", "Day", "text", lambda w: w.name),
            Col("total", "Spent", "total", lambda w: _amount(w.total)),
            Col("count", "Purchases", "count", lambda w: w.count),
            Col("per_day", "Per day", "total", lambda w: _amount(w.per_day)),
        ],
        r.by_weekday if spent else [],
    )
    return _outcome("Spending patterns", label, lines, summary, table)


def unusual_spending_outcome(
    response: "AnomaliesResponse", label: str, names: Mapping[str, str]
) -> tuple[str, ToolDisplay]:
    """Expenses far above their trailing window, and categories spending more than usual lately."""
    r = response
    lines = [
        f"An expense is unusual at {r.std_threshold:g} standard deviations above the mean of the "
        f"{r.window_days} days before it; recurring expenses are never unusual."
    ]
    outliers: Sequence = r.outliers
    if outliers:
        lines.append("Unusual expenses (by z-score):")
        outliers = _capped(outliers, OUTLIERS_SHOWN, "unusual expenses", lines)
        for o in outliers:
            against = "its category" if o.compared_with == "category" else "all one-off spending"
            lines.append(
                f"- {o.date.isoformat()} {o.merchant}, {_named(o.category, names)}: {_eur(o.amount)}, "
                f"z-score {o.z_score:.1f} against {against} (mean {_eur(o.window_mean)})"
            )
    else:
        lines.append("No unusual expenses.")
    if r.spikes and r.spike_window_start and r.spike_window_end:
        window = name_period(r.spike_window_start, r.spike_window_end)
        lines.append(f"Category spikes, {window} against the average 30 days before:")
        for s in r.spikes:
            lines.append(
                f"- {_named(s.category, names)}: {_eur(s.recent_total)} against {_eur(s.baseline_30d)} "
                f"({_change(s.spike_pct)}, {_eur(s.increase_amount)} more)"
            )
    else:
        lines.append("No category spikes.")
    summary = [
        SummaryItem(kind="count", value=len(r.outliers), label="unusual expenses"),
        SummaryItem(kind="count", value=len(r.spikes), label="category spikes"),
    ]
    table = _table(
        [
            Col("date", "Date", "date", lambda o: o.date.isoformat()),
            Col("merchant", "Merchant", "text", lambda o: o.merchant),
            Col("category", "Category", "text", lambda o: _name(o.category, names)),
            # Analytics reports an outlier as positive spend, so it reads as a total, not a signed transaction.
            Col("amount", "Spent", "total", lambda o: _amount(o.amount)),
        ],
        outliers,
    )
    return _outcome("Unusual spending", label, lines, summary, table)


WEEKDAY_NAMES = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}
NO_MATCH = "no transactions match"


def _describe_filter(args: SearchArgs, names: Mapping[str, str]) -> str:
    parts = []
    if args.merchant:
        parts.append(f'merchant contains "{args.merchant}"')
    if args.date_from or args.date_to:
        parts.append(
            f"from {args.date_from.isoformat() if args.date_from else 'the start'} "
            f"to {args.date_to.isoformat() if args.date_to else 'the end'}"
        )
    if args.categories:
        parts.append("categories " + ", ".join(_named(c.value, names) for c in args.categories))
    if args.amount_min is not None:
        parts.append(f"amount at least {args.amount_min} EUR")
    if args.amount_max is not None:
        parts.append(f"amount at most {args.amount_max} EUR")
    if args.recurring_only:
        parts.append("recurring only")
    if args.weekdays:
        parts.append("on " + ", ".join(WEEKDAY_NAMES[d] for d in args.weekdays))
    return "Filter: " + ("; ".join(parts) if parts else "none (all transactions)") + "."


def _group_name(label: str, group_by: str, names: Mapping[str, str]) -> str:
    if group_by == "month":
        return short_month(label)
    if group_by == "category":
        return _named(label, names)
    if group_by == "weekday":
        return WEEKDAY_NAMES[label]
    return label


def _totals(side: str, totals: Totals) -> str:
    noun = "transaction" if totals.count == 1 else "transactions"
    return f"{side} {totals.count} {noun}, {_eur(totals.total)}"


def search_outcome(
    result: SearchResult,
    args: SearchArgs,
    names: Mapping[str, str],
    data_span: tuple[dt.date, dt.date],
) -> tuple[str, ToolDisplay]:
    """Matches as counts and totals (money out and in apart), optional groups, and a sample of transactions.

    The table is the groups when `group_by` is set, else the sample.
    """
    if args.date_from and args.date_to:
        label = name_period(args.date_from, args.date_to)
    elif args.date_from or args.date_to:
        label = f"from {args.date_from.isoformat()}" if args.date_from else f"up to {args.date_to.isoformat()}"
    elif result.span is not None:
        label = name_period(*result.span)
    else:
        label = "All transactions"
    lines = [_describe_filter(args, names)]
    if not result.matched:
        lines.append(f"{NO_MATCH.capitalize()}; the {describe_span(*data_span)}.")
        return _outcome(
            "Transaction search", label, lines, [SummaryItem(kind="count", value=0, label="matches")], None
        )
    lines.append(f"{result.matched} {'transaction matches' if result.matched == 1 else 'transactions match'}.")
    lines.append(f"{_totals('Money out:', result.money_out)}; {_totals('money in:', result.money_in)}.")
    groups = result.groups
    if args.group_by:
        lines.append(f"By {args.group_by}:")
        # Months run oldest to newest and keep the newest; other groupings are ranked and keep the top.
        groups = _capped(result.groups, GROUP_LIMIT, "groups", lines, last=args.group_by == "month")
        for name, out, into in groups:
            lines.append(
                f"- {_group_name(name, args.group_by, names)}: "
                f"out {out.count} for {_eur(out.total)}, in {into.count} for {_eur(into.total)}"
            )
    lines.append(
        f"{'Largest' if args.sample == 'largest' else 'Most recent'} {len(result.sample)} of {result.matched}:"
    )
    for r in result.sample:
        lines.append(f"- {r.date.isoformat()} {r.merchant} {_eur(r.amount)} {_named(r.category, names)}")
    # Money out is negative in the data; under its label it shows unsigned, as a total (abs, never "-0.00").
    summary = [
        _total_item(abs(result.money_out.total), "money out"),
        _total_item(result.money_in.total, "money in"),
        SummaryItem(kind="count", value=result.matched, label="matches"),
    ]
    if args.group_by:
        group_by = args.group_by
        table = _table(
            [
                Col("group", group_by.capitalize(), "text", lambda g: _group_name(g[0], group_by, names)),
                Col("out_count", "Out", "count", lambda g: g[1].count),
                Col("out_total", "Money out", "total", lambda g: _amount(abs(g[1].total))),
                Col("in_count", "In", "count", lambda g: g[2].count),
                Col("in_total", "Money in", "total", lambda g: _amount(g[2].total)),
            ],
            groups,
        )
    else:
        table = _table(
            [
                Col("date", "Date", "date", lambda t: t.date.isoformat()),
                Col("merchant", "Merchant", "text", lambda t: t.merchant),
                Col("category", "Category", "text", lambda t: _name(t.category, names)),
                Col("amount", "Amount", "transaction", lambda t: _amount(t.amount)),
            ],
            result.sample,
        )
    return _outcome("Transaction search", label, lines, summary, table)
