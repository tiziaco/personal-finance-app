"""Recurring: spend the stored is_recurring flag marks, its run-rate, and unflagged subscription look-alikes.

No detection here: the flag is the one source of truth (docs/ROADMAP.md, decision of 15 Oct 2026). Hidden
subscriptions are candidates for the user to flag, never counted as recurring.
"""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from statistics import median
from typing import Optional

from app.modules.analytics.domain._aggregate import (
    AVERAGE_MONTH_DAYS,
    ZERO,
    Row,
    average,
    expenses,
    group_by,
    money,
    month_start,
    share_pct,
    spend,
    total_spend,
)
from app.modules.analytics.domain.merchants import display_names
from app.modules.analytics.domain.period import Period

ACTIVE_GAP_FACTOR = Decimal("1.5")
MONTHLY_GAP_DAYS = 25
HIDDEN_MIN_MONTHS = 3
HIDDEN_GAP_DAYS = (25, 35)
HIDDEN_AMOUNT_TOLERANCE = Decimal("0.10")
HIDDEN_MAX_CHARGE = Decimal("50.00")


@dataclass(frozen=True)
class RecurringMerchant:
    """A flagged merchant: its charges, billing rhythm, monthly cost, and whether it still charges."""

    merchant: str
    charges: int
    months_charged: int
    median_charge: Decimal
    interval_days: Optional[int]
    monthly_cost: Decimal
    last_charge: dt.date
    active: bool


@dataclass(frozen=True)
class HiddenSubscription:
    """An unflagged merchant charging like a subscription: a steady, small amount about once a month."""

    merchant: str
    charges: int
    months_active: int
    average_charge: Decimal
    charges_per_month: float


@dataclass(frozen=True)
class RecurringAnalysis:
    """Flagged spend and its shares, its monthly run-rate, and the merchants behind both."""

    date_from: Optional[dt.date]
    date_to: Optional[dt.date]
    total_expenses: Decimal
    recurring_total: Decimal
    recurring_count: int
    amount_share_pct: float
    count_share_pct: float
    monthly_recurring_cost: Decimal
    merchants: tuple[RecurringMerchant, ...]
    hidden_subscriptions: tuple[HiddenSubscription, ...]


def _months(group: Sequence[Row]) -> int:
    return len({month_start(r.date) for r in group})


def _half_up(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _interval_days(group: Sequence[Row]) -> Optional[int]:
    """The median gap in days between consecutive charges, half-up; None with one charge."""
    days = sorted(r.date for r in group)
    gaps = [Decimal((later - earlier).days) for earlier, later in pairwise(days)]
    return _half_up(median(gaps)) if gaps else None


def _monthly_cost(charge: Decimal, interval: Optional[int], period: Period) -> Decimal:
    """The charge spread over its billing rhythm: whole months from 25 days up, else days; one charge, the period."""
    if not interval:  # one charge, or every charge on one day: no rhythm to read
        return money(charge / period.weight())
    if interval >= MONTHLY_GAP_DAYS:
        cadence = max(1, _half_up(Decimal(interval) / AVERAGE_MONTH_DAYS))
        return money(charge / cadence)
    return money(charge * AVERAGE_MONTH_DAYS / interval)


def _active(last_charge: dt.date, interval: Optional[int], period: Period) -> bool:
    """Active unless the period ends more than ACTIVE_GAP_FACTOR intervals after the last charge."""
    if not interval:
        return True
    return (period.last_day - last_charge).days <= ACTIVE_GAP_FACTOR * interval


def _looks_like_a_subscription(group: Sequence[Row]) -> bool:
    """Charged in HIDDEN_MIN_MONTHS months, about monthly, a steady amount of at most HIDDEN_MAX_CHARGE."""
    if _months(group) < HIDDEN_MIN_MONTHS:
        return False
    interval = _interval_days(group)
    charge = median(spend(r) for r in group)
    low, high = HIDDEN_GAP_DAYS
    return (
        interval is not None
        and low <= interval <= high
        and charge <= HIDDEN_MAX_CHARGE
        and all(abs(spend(r) - charge) <= HIDDEN_AMOUNT_TOLERANCE * charge for r in group)
    )


def recurring_analysis(rows: Sequence[Row], period: Optional[Period]) -> RecurringAnalysis:
    """Flagged spend and share over the period; per flagged merchant, its rhythm and cost; hidden candidates."""
    if period is None:
        return RecurringAnalysis(None, None, ZERO, ZERO, 0, 0.0, 0.0, ZERO, (), ())
    spent = expenses(period.rows(rows))
    flagged = [r for r in spent if r.is_recurring]
    unflagged = [r for r in spent if not r.is_recurring]
    names = display_names(spent)

    merchants: list[RecurringMerchant] = []
    for key, group in group_by(flagged, lambda r: r.merchant_key).items():
        charge = money(median(spend(r) for r in group))
        interval = _interval_days(group)
        last_charge = max(r.date for r in group)
        merchants.append(
            RecurringMerchant(
                merchant=names[key],
                charges=len(group),
                months_charged=_months(group),
                median_charge=charge,
                interval_days=interval,
                monthly_cost=_monthly_cost(charge, interval, period),
                last_charge=last_charge,
                active=_active(last_charge, interval, period),
            )
        )
    merchants.sort(key=lambda m: (-m.monthly_cost, m.merchant.casefold()))

    ranked: list[tuple[Decimal, HiddenSubscription]] = []
    for key, group in group_by(unflagged, lambda r: r.merchant_key).items():
        if not _looks_like_a_subscription(group):
            continue
        months = _months(group)
        hidden = HiddenSubscription(
            names[key], len(group), months, average(total_spend(group), len(group)), round(len(group) / months, 2)
        )
        ranked.append((median(spend(r) for r in group) * len(group) / months, hidden))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].merchant.casefold()))

    whole, recurring_total = total_spend(spent), total_spend(flagged)
    return RecurringAnalysis(
        date_from=period.first_day,
        date_to=period.last_day,
        total_expenses=whole,
        recurring_total=recurring_total,
        recurring_count=len(flagged),
        amount_share_pct=share_pct(recurring_total, whole),
        count_share_pct=share_pct(Decimal(len(flagged)), Decimal(len(spent))),
        monthly_recurring_cost=money(sum((m.monthly_cost for m in merchants if m.active), ZERO)),
        merchants=tuple(merchants),
        hidden_subscriptions=tuple(hidden for _, hidden in ranked),
    )
