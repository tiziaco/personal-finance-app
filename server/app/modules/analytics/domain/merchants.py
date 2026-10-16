"""Merchants: who gets the money, how often, and how concentrated spending is."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.modules.analytics.domain._aggregate import ZERO, Row, average, expenses, group_by, share_pct, total_spend
from app.modules.analytics.domain.period import Period


@dataclass(frozen=True)
class MerchantSpend:
    """One merchant's spend: total, count, average, first and last day, and share of all spending."""

    merchant: str
    total: Decimal
    count: int
    average: Decimal
    first_date: dt.date
    last_date: dt.date
    share_pct: float


@dataclass(frozen=True)
class MerchantConcentration:
    """How concentrated spending is across merchants, by top shares and the Herfindahl index."""

    top_5_share_pct: float
    top_10_share_pct: float
    herfindahl_index: float
    unique_merchants: int


@dataclass(frozen=True)
class MerchantBreakdown:
    """Merchants ranked by spend and by frequency, with the concentration of spending."""

    date_from: Optional[dt.date]
    date_to: Optional[dt.date]
    total_expenses: Decimal
    top_by_spend: tuple[MerchantSpend, ...]
    top_by_frequency: tuple[MerchantSpend, ...]
    concentration: MerchantConcentration


def display_names(rows: Sequence[Row]) -> dict[str, str]:
    """Each merchant key's latest spelling (rows are in date order, so the last one wins)."""
    return {r.merchant_key: r.merchant.strip() for r in rows}


def _concentration(ranked: Sequence[MerchantSpend], whole: Decimal) -> MerchantConcentration:
    shares = [float(m.total / whole * 100) for m in ranked] if whole else []
    hhi = round(sum(s * s for s in shares), 2)
    return MerchantConcentration(
        top_5_share_pct=round(sum(shares[:5]), 2),
        top_10_share_pct=round(sum(shares[:10]), 2),
        herfindahl_index=hhi,
        unique_merchants=len(ranked),
    )


def merchant_breakdown(rows: Sequence[Row], period: Optional[Period], top_n: int = 15) -> MerchantBreakdown:
    """Merchants ranked by spend and by count over the period; concentration over every merchant's share."""
    if period is None:
        return MerchantBreakdown(None, None, ZERO, (), (), _concentration([], ZERO))
    spent = expenses(period.rows(rows))
    whole = total_spend(spent)
    names = display_names(spent)
    items = [
        MerchantSpend(
            merchant=names[key],
            total=total_spend(group),
            count=len(group),
            average=average(total_spend(group), len(group)),
            first_date=min(r.date for r in group),
            last_date=max(r.date for r in group),
            share_pct=share_pct(total_spend(group), whole),
        )
        for key, group in group_by(spent, lambda r: r.merchant_key).items()
    ]
    by_spend = sorted(items, key=lambda m: (-m.total, m.merchant.casefold()))
    by_count = sorted(items, key=lambda m: (-m.count, -m.total, m.merchant.casefold()))
    return MerchantBreakdown(
        date_from=period.first_day,
        date_to=period.last_day,
        total_expenses=whole,
        top_by_spend=tuple(by_spend[:top_n]),
        top_by_frequency=tuple(by_count[:top_n]),
        concentration=_concentration(by_spend, whole),
    )
