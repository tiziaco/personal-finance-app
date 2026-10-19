"""The recurring rule: one merchant's rows judged as a series (docs/data-model/transaction.md, D6).

A cadence accepts a +-15 % amount cluster with enough rows (monthly, quarterly, yearly), or a
fixed-amount one (weekly, yearly) that is tighter but needs fewer rows.
"""

import datetime as dt
import uuid
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

DETECTED = "detected"
USER = "user"

_BAND = Decimal("0.15")
_MIN_SLACK = Decimal("1")
_FIT_SHARE = 0.75
_FIXED_BAND = Decimal("0.02")
_FIXED_SLACK = Decimal("0.10")


@dataclass(frozen=True)
class Cadence:
    """A period a series can follow: the days between two rows, and how many rows it needs.

    `min_rows` is the count needed in a ±15 % cluster; None means the cadence never
    accepts one. `fixed_min_rows` is the count needed when every row is within the
    fixed band of the seed; None means there is no fixed form. `fixed_alone` adds that
    no other row of the same side falls strictly between the cluster's first and last dates.
    """

    name: str
    min_days: int
    max_days: int
    min_rows: Optional[int]
    fixed_min_rows: Optional[int]
    fixed_alone: bool = False


CADENCES = (
    Cadence("weekly", 6, 8, None, 4),
    Cadence("monthly", 26, 35, 3, None),
    Cadence("quarterly", 84, 98, 3, None),
    Cadence("yearly", 350, 380, 3, 2, fixed_alone=True),
)


@dataclass(frozen=True)
class RecurringRow:
    """What the rule reads of one active transaction."""

    id: uuid.UUID
    date: dt.date
    amount: Decimal
    source: str


def detect_recurring(rows: list[RecurringRow]) -> dict[uuid.UUID, bool]:
    """is_recurring for every `detected` row among one merchant key's active rows.

    Money in and money out are judged apart; within each, rows are clustered by
    amount and a cluster is a series when it follows a cadence. `user` rows
    count as evidence and get no verdict, so they are never changed.
    """
    verdict: dict[uuid.UUID, bool] = {}
    for incoming in (True, False):
        side = [r for r in rows if (r.amount > 0) is incoming]
        for seed, cluster in _clusters(side):
            recurring = _is_series(cluster, seed, side)
            for row in cluster:
                if row.source == DETECTED:
                    verdict[row.id] = recurring
    return verdict


def _clusters(rows: list[RecurringRow]) -> list[tuple[Decimal, list[RecurringRow]]]:
    """Rows grouped around fixed seeds: the most frequent amounts first, then the smallest.

    A row joins the first cluster whose seed is within ±15 % of the seed (at
    least €1); otherwise it seeds a cluster. A fixed seed does not drift the way
    a running median does. Each cluster comes with its seed.
    """
    counts = Counter(abs(r.amount) for r in rows)
    clusters: list[tuple[Decimal, list[RecurringRow]]] = []
    for row in sorted(rows, key=lambda r: (-counts[abs(r.amount)], abs(r.amount), r.date)):
        size = abs(row.amount)
        for seed, members in clusters:
            if abs(size - seed) <= max(seed * _BAND, _MIN_SLACK):
                members.append(row)
                break
        else:
            clusters.append((size, [row]))
    return clusters


def _fits(gap: int, cadence: Cadence) -> bool:
    """A gap of one period, or of two (one skipped)."""
    return cadence.min_days <= gap <= cadence.max_days or 2 * cadence.min_days <= gap <= 2 * cadence.max_days


def _is_fixed(cluster: list[RecurringRow], seed: Decimal, side: list[RecurringRow], cadence: Cadence) -> bool:
    """Every row within 2 % of the seed (at least €0.10), and, for `fixed_alone`, nothing of the side between."""
    if cadence.fixed_min_rows is None or len(cluster) < cadence.fixed_min_rows:
        return False
    if any(abs(abs(r.amount) - seed) > max(seed * _FIXED_BAND, _FIXED_SLACK) for r in cluster):
        return False
    if cadence.fixed_alone:
        first, last = min(r.date for r in cluster), max(r.date for r in cluster)
        members = {r.id for r in cluster}
        return not any(r.id not in members and first < r.date < last for r in side)
    return True


def _is_series(cluster: list[RecurringRow], seed: Decimal, side: list[RecurringRow]) -> bool:
    """A cluster follows a cadence when 75 % of its gaps fit and it has enough rows, or enough fixed ones."""
    dates = sorted(r.date for r in cluster)
    gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:], strict=False)]
    if not gaps:
        return False
    return any(
        sum(_fits(g, cadence) for g in gaps) >= _FIT_SHARE * len(gaps)
        and (
            (cadence.min_rows is not None and len(cluster) >= cadence.min_rows)
            or _is_fixed(cluster, seed, side, cadence)
        )
        for cadence in CADENCES
    )
