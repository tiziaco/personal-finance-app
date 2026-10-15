"""Merchants: who gets the money, how often, and how concentrated spending is."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from app.modules.analytics.domain._aggregate import Row, average, expenses, group_by, share_pct, total_spend

HIGH_CONCENTRATION = 2500
MEDIUM_CONCENTRATION = 1500


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
    risk: Literal["low", "medium", "high"]
    unique_merchants: int


@dataclass(frozen=True)
class MerchantBreakdown:
    """Merchants ranked by spend and by frequency, with the concentration of spending."""

    total_expenses: Decimal
    top_by_spend: tuple[MerchantSpend, ...]
    top_by_frequency: tuple[MerchantSpend, ...]
    concentration: MerchantConcentration


def merchant_key(name: str) -> str:
    """Spellings that differ only in case or padding are one merchant."""
    return name.strip().casefold()


def display_names(rows: Sequence[Row]) -> dict[str, str]:
    """Each merchant key's latest spelling (rows are in date order, so the last one wins)."""
    return {merchant_key(r.merchant): r.merchant.strip() for r in rows}


def _concentration(ranked: Sequence[MerchantSpend], whole: Decimal) -> MerchantConcentration:
    shares = [float(m.total / whole * 100) for m in ranked] if whole else []
    hhi = round(sum(s * s for s in shares), 2)
    risk: Literal["low", "medium", "high"] = (
        "high" if hhi > HIGH_CONCENTRATION else "medium" if hhi > MEDIUM_CONCENTRATION else "low"
    )
    return MerchantConcentration(
        top_5_share_pct=round(sum(shares[:5]), 2),
        top_10_share_pct=round(sum(shares[:10]), 2),
        herfindahl_index=hhi,
        risk=risk,
        unique_merchants=len(ranked),
    )


def merchant_breakdown(rows: Sequence[Row], top_n: int = 15) -> MerchantBreakdown:
    """Merchants ranked by spend and by count; concentration over every merchant's share of all spending."""
    spent = expenses(rows)
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
        for key, group in group_by(spent, lambda r: merchant_key(r.merchant)).items()
    ]
    by_spend = sorted(items, key=lambda m: (-m.total, m.merchant.casefold()))
    by_count = sorted(items, key=lambda m: (-m.count, -m.total, m.merchant.casefold()))
    return MerchantBreakdown(
        total_expenses=whole,
        top_by_spend=tuple(by_spend[:top_n]),
        top_by_frequency=tuple(by_count[:top_n]),
        concentration=_concentration(by_spend, whole),
    )
