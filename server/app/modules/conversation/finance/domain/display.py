"""Turn an analytics response into a tool outcome: compact text for the model, a summary and table for the user.

`content` opens with the period, then the figures, money as plain decimals with "EUR",
and stays bounded: long lists are cut to a fixed length and say so. `display` carries
money as numbers, never formatted strings; the web formats them (spec §7).
"""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Optional, TypeVar

from app.agents.chatbot.toolkit import SummaryItem, TableColumn, ToolDisplay, ToolOutcome, ToolTable
from app.modules.conversation.finance.domain.periods import MONTH_NAMES, describe_span, name_period, short_month
from app.modules.conversation.finance.domain.search import GROUP_LIMIT, SearchResult, Totals

if TYPE_CHECKING:
    from app.modules.analytics import (
        AnomaliesResponse,
        BehaviourResponse,
        CategoryBreakdownResponse,
        MerchantBreakdownResponse,
        RecurringResponse,
        SpendingResponse,
    )
    from app.modules.conversation.finance.schemas import SearchArgs

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


def _num(value: Decimal) -> float:
    return float(value)


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
    title: str,
    label: str,
    lines: list[str],
    summary: list[SummaryItem],
    columns: list[TableColumn],
    rows: list[dict],
) -> ToolOutcome:
    table = ToolTable(columns=columns, rows=rows) if rows else None
    display = ToolDisplay(title=title, period=label, summary=summary, table=table)
    return ToolOutcome(content="\n".join([label, *lines]), display=display)


def _money_item(value: Decimal, label: str) -> SummaryItem:
    return SummaryItem(kind="money", value=_num(value), label=label)


def spending_overview_outcome(response: "SpendingResponse", label: str) -> ToolOutcome:
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
    summary = [_money_item(r.total_expenses, "spent"), _money_item(r.total_income, "income")]
    if r.savings_rate_pct is not None:
        summary.append(SummaryItem(kind="percent", value=r.savings_rate_pct, label="savings rate"))
    columns = [
        TableColumn(key="month", label="Month", kind="text"),
        TableColumn(key="income", label="Income", kind="money"),
        TableColumn(key="expenses", label="Expenses", kind="money"),
        TableColumn(key="net", label="Net", kind="money"),
        TableColumn(key="savings_rate_pct", label="Savings rate", kind="percent"),
    ]
    rows = [
        {
            "month": short_month(m.month),
            "income": _num(m.income),
            "expenses": _num(m.expenses),
            "net": _num(m.net),
            "savings_rate_pct": m.savings_rate_pct,
        }
        for m in months
    ]
    return _outcome("Spending overview", label, lines, summary, columns, rows)


def _trend(change_pct: Optional[float]) -> str:
    """A growing or declining category's change, as the Trends tab words it."""
    if change_pct is None:
        return "new"
    return "stopped" if change_pct == -100 else _change(change_pct)


def category_breakdown_outcome(
    response: "CategoryBreakdownResponse", label: str, names: Mapping[str, str]
) -> ToolOutcome:
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
        _money_item(r.total_expenses, "spent"),
    ]
    columns = [
        TableColumn(key="category", label="Category", kind="text"),
        TableColumn(key="total", label="Spent", kind="money"),
        TableColumn(key="share_pct", label="Share", kind="percent"),
        TableColumn(key="count", label="Purchases", kind="count"),
        TableColumn(key="change_pct", label="Change", kind="percent"),
    ]
    rows = [
        {
            "category": _name(c.category, names),
            "total": _num(c.total),
            "share_pct": c.share_pct,
            "count": c.count,
            "change_pct": c.change_pct,
        }
        for c in categories
    ]
    return _outcome("Spending by category", label, lines, summary, columns, rows)


def top_merchants_outcome(response: "MerchantBreakdownResponse", label: str) -> ToolOutcome:
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
        _money_item(r.total_expenses, "spent"),
        SummaryItem(kind="count", value=c.unique_merchants, label="merchants"),
    ]
    if r.top_by_spend:
        summary.append(SummaryItem(kind="percent", value=c.top_5_share_pct, label="top 5 share"))
    columns = [
        TableColumn(key="merchant", label="Merchant", kind="text"),
        TableColumn(key="total", label="Spent", kind="money"),
        TableColumn(key="share_pct", label="Share", kind="percent"),
        TableColumn(key="count", label="Purchases", kind="count"),
    ]
    rows = [
        {"merchant": m.merchant, "total": _num(m.total), "share_pct": m.share_pct, "count": m.count}
        for m in r.top_by_spend
    ]
    return _outcome("Top merchants", label, lines, summary, columns, rows)


def recurring_costs_outcome(response: "RecurringResponse", label: str) -> ToolOutcome:
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
        _money_item(r.monthly_recurring_cost, "a month"),
        SummaryItem(kind="count", value=len(r.merchants), label="recurring"),
    ]
    columns = [
        TableColumn(key="merchant", label="Merchant", kind="text"),
        TableColumn(key="monthly_cost", label="A month", kind="money"),
        TableColumn(key="median_charge", label="Median charge", kind="money"),
        TableColumn(key="last_charge", label="Last charge", kind="date"),
        TableColumn(key="status", label="Status", kind="text"),
    ]
    rows = [
        {
            "merchant": m.merchant,
            "monthly_cost": _num(m.monthly_cost),
            "median_charge": _num(m.median_charge),
            "last_charge": m.last_charge.isoformat(),
            "status": "active" if m.active else "stopped",
        }
        for m in merchants
    ]
    return _outcome("Recurring costs", label, lines, summary, columns, rows)


def spending_behaviour_outcome(response: "BehaviourResponse", label: str, names: Mapping[str, str]) -> ToolOutcome:
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
        summary.append(SummaryItem(kind="percent", value=r.weekend_bias_pct, label="weekend vs weekday, per day"))
    if spent:
        busiest = max(r.by_weekday, key=lambda w: w.per_day)
        summary.append(SummaryItem(kind="text", value=busiest.name, label="busiest day"))
    columns = [
        TableColumn(key="weekday", label="Day", kind="text"),
        TableColumn(key="total", label="Spent", kind="money"),
        TableColumn(key="count", label="Purchases", kind="count"),
        TableColumn(key="per_day", label="Per day", kind="money"),
    ]
    rows = (
        [
            {"weekday": w.name, "total": _num(w.total), "count": w.count, "per_day": _num(w.per_day)}
            for w in r.by_weekday
        ]
        if spent
        else []
    )
    return _outcome("Spending patterns", label, lines, summary, columns, rows)


def unusual_spending_outcome(response: "AnomaliesResponse", label: str, names: Mapping[str, str]) -> ToolOutcome:
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
    columns = [
        TableColumn(key="date", label="Date", kind="date"),
        TableColumn(key="merchant", label="Merchant", kind="text"),
        TableColumn(key="category", label="Category", kind="text"),
        TableColumn(key="amount", label="Amount", kind="money"),
    ]
    rows = [
        {
            "date": o.date.isoformat(),
            "merchant": o.merchant,
            "category": _name(o.category, names),
            "amount": _num(o.amount),
        }
        for o in outliers
    ]
    return _outcome("Unusual spending", label, lines, summary, columns, rows)


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


def _describe_filter(args: "SearchArgs", names: Mapping[str, str]) -> str:
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


def search_outcome(result: SearchResult, args: "SearchArgs", names: Mapping[str, str]) -> ToolOutcome:
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
        covers = f"; the {describe_span(*result.data_span)}" if result.data_span else ""
        lines.append(f"{NO_MATCH.capitalize()}{covers}.")
        return _outcome(
            "Transaction search", label, lines, [SummaryItem(kind="count", value=0, label="matches")], [], []
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
    summary = [
        _money_item(result.money_out.total, "money out"),
        _money_item(result.money_in.total, "money in"),
        SummaryItem(kind="count", value=result.matched, label="matches"),
    ]
    if args.group_by:
        columns = [
            TableColumn(key="group", label=args.group_by.capitalize(), kind="text"),
            TableColumn(key="out_count", label="Out", kind="count"),
            TableColumn(key="out_total", label="Money out", kind="money"),
            TableColumn(key="in_count", label="In", kind="count"),
            TableColumn(key="in_total", label="Money in", kind="money"),
        ]
        rows = [
            {
                "group": _group_name(name, args.group_by, names),
                "out_count": out.count,
                "out_total": _num(out.total),
                "in_count": into.count,
                "in_total": _num(into.total),
            }
            for name, out, into in groups
        ]
    else:
        columns = [
            TableColumn(key="date", label="Date", kind="date"),
            TableColumn(key="merchant", label="Merchant", kind="text"),
            TableColumn(key="category", label="Category", kind="text"),
            TableColumn(key="amount", label="Amount", kind="money"),
        ]
        rows = [
            {
                "date": r.date.isoformat(),
                "merchant": r.merchant,
                "category": _name(r.category, names),
                "amount": _num(r.amount),
            }
            for r in result.sample
        ]
    return _outcome("Transaction search", label, lines, summary, columns, rows)
