"""Recurring: spend the stored is_recurring flag marks, its run-rate, and unflagged small regulars.

No detection here: the flag is the one source of truth (docs/ROADMAP.md, decision of 15 Oct 2026).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from app.modules.analytics.domain._aggregate import (
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
from app.modules.analytics.domain.merchants import display_names, merchant_key

HIDDEN_MAX_AVERAGE = Decimal("50.00")
HIDDEN_MIN_PER_MONTH = 3


@dataclass(frozen=True)
class RecurringMerchant:
    """A flagged merchant: its charges, the months they fell in, median charge and monthly cost."""

    merchant: str
    charges: int
    months_charged: int
    median_charge: Decimal
    monthly_cost: Decimal


@dataclass(frozen=True)
class HiddenSubscription:
    """An unflagged merchant that charges small amounts often, a likely subscription."""

    merchant: str
    charges: int
    months_active: int
    average_charge: Decimal
    charges_per_month: float


@dataclass(frozen=True)
class RecurringAnalysis:
    """Flagged spend and its shares, its monthly run-rate, and the merchants behind both."""

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


def recurring_analysis(rows: Sequence[Row]) -> RecurringAnalysis:
    """Flagged spend and share; per flagged merchant, median charge × charges per month; hidden candidates."""
    spent = expenses(rows)
    flagged = [r for r in spent if r.is_recurring]
    unflagged = [r for r in spent if not r.is_recurring]
    names = display_names(spent)

    merchants: list[RecurringMerchant] = []
    for key, group in group_by(flagged, lambda r: merchant_key(r.merchant)).items():
        charge = money(median(spend(r) for r in group))
        months = _months(group)
        merchants.append(
            RecurringMerchant(names[key], len(group), months, charge, money(charge * len(group) / months))
        )
    merchants.sort(key=lambda m: (-m.monthly_cost, m.merchant.casefold()))

    hidden: list[HiddenSubscription] = []
    for key, group in group_by(unflagged, lambda r: merchant_key(r.merchant)).items():
        months = _months(group)
        mean_charge = average(total_spend(group), len(group))
        per_month = round(len(group) / months, 2)
        if mean_charge <= HIDDEN_MAX_AVERAGE and per_month >= HIDDEN_MIN_PER_MONTH:
            hidden.append(HiddenSubscription(names[key], len(group), months, mean_charge, per_month))
    hidden.sort(key=lambda h: (-h.charges_per_month, h.merchant.casefold()))

    whole, recurring_total = total_spend(spent), total_spend(flagged)
    return RecurringAnalysis(
        total_expenses=whole,
        recurring_total=recurring_total,
        recurring_count=len(flagged),
        amount_share_pct=share_pct(recurring_total, whole),
        count_share_pct=share_pct(Decimal(len(flagged)), Decimal(len(spent))),
        monthly_recurring_cost=money(sum((m.monthly_cost for m in merchants), Decimal(0))),
        merchants=tuple(merchants),
        hidden_subscriptions=tuple(hidden),
    )
