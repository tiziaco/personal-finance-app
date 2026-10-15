"""The recurring rule: one merchant's rows judged as a series (docs/data-model/transaction.md, D6)."""

import datetime as dt
import uuid
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

DETECTED = "detected"
USER = "user"

_BAND = Decimal("0.15")
_MIN_SLACK = Decimal("1")
_FIT_SHARE = 0.75


@dataclass(frozen=True)
class Cadence:
    """A period a series can follow: the days between two rows, and how many rows it needs."""

    name: str
    min_days: int
    max_days: int
    min_rows: int


CADENCES = (
    Cadence("weekly", 6, 8, 3),
    Cadence("monthly", 26, 35, 3),
    Cadence("quarterly", 84, 98, 3),
    Cadence("yearly", 350, 380, 3),
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
        for cluster in _clusters(side):
            recurring = _is_series(cluster)
            for row in cluster:
                if row.source == DETECTED:
                    verdict[row.id] = recurring
    return verdict


def _clusters(rows: list[RecurringRow]) -> list[list[RecurringRow]]:
    """Rows grouped around fixed seeds: the most frequent amounts first, then the smallest.

    A row joins the first cluster whose seed is within ±15 % of the seed (at
    least €1); otherwise it seeds a cluster. A fixed seed does not drift the way
    a running median does.
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
    return [members for _, members in clusters]


def _fits(gap: int, cadence: Cadence) -> bool:
    """A gap of one period, or of two (one skipped)."""
    return cadence.min_days <= gap <= cadence.max_days or 2 * cadence.min_days <= gap <= 2 * cadence.max_days


def _is_series(cluster: list[RecurringRow]) -> bool:
    dates = sorted(r.date for r in cluster)
    gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:], strict=False)]
    if not gaps:
        return False
    return any(
        len(cluster) >= cadence.min_rows and sum(_fits(g, cadence) for g in gaps) >= _FIT_SHARE * len(gaps)
        for cadence in CADENCES
    )
