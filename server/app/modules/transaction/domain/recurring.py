"""The recurring rule: one merchant's rows judged as a series (docs/data-model/transaction.md, D6).

A cadence accepts a ±15 % amount cluster with enough rows (monthly, quarterly, yearly), or a
same-amount run inside one (weekly, yearly) that is tighter but needs fewer rows.
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
    accepts one. `fixed_min_rows` is the count needed in a same-amount run (2 % of its
    seed, at least €0.10); None means there is no fixed form. `fixed_alone` adds that
    no other row of the same side falls strictly between the run's first and last dates.
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
    amount (±15 %) and each cluster re-clustered into same-amount runs (2 %). A row
    is recurring when its cluster is a series by `min_rows` or its run is a series by
    `fixed_min_rows`, so an odd purchase in a cluster does not undo the run beside it.
    `user` rows count as evidence and get no verdict, so they are never changed.
    """
    verdict: dict[uuid.UUID, bool] = {}
    for incoming in (True, False):
        side = [r for r in rows if (r.amount > 0) is incoming]
        for cluster in _clusters(side):
            series = _is_series(cluster)
            for run in _clusters(cluster, _FIXED_BAND, _FIXED_SLACK):
                recurring = series or _is_fixed_series(run, side)
                for row in run:
                    if row.source == DETECTED:
                        verdict[row.id] = recurring
    return verdict


def _clusters(
    rows: list[RecurringRow], band: Decimal = _BAND, slack: Decimal = _MIN_SLACK
) -> list[list[RecurringRow]]:
    """Rows grouped around fixed seeds: the most frequent amounts first, then the smallest.

    A row joins the first cluster whose seed it is within `band` of (at least
    `slack`; by default ±15 %, at least €1); otherwise it seeds a cluster. A fixed
    seed does not drift the way a running median does.
    """
    counts = Counter(abs(r.amount) for r in rows)
    clusters: list[tuple[Decimal, list[RecurringRow]]] = []
    for row in sorted(rows, key=lambda r: (-counts[abs(r.amount)], abs(r.amount), r.date)):
        size = abs(row.amount)
        for seed, members in clusters:
            if abs(size - seed) <= max(seed * band, slack):
                members.append(row)
                break
        else:
            clusters.append((size, [row]))
    return [members for _, members in clusters]


def _fits(gap: int, cadence: Cadence) -> bool:
    """A gap of one period, or of two (one skipped)."""
    return cadence.min_days <= gap <= cadence.max_days or 2 * cadence.min_days <= gap <= 2 * cadence.max_days


def _follows(rows: list[RecurringRow], cadence: Cadence) -> bool:
    """75 % of the gaps between the rows' dates fit the cadence; a single row has no gaps, so never follows one."""
    dates = sorted(r.date for r in rows)
    gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:], strict=False)]
    return bool(gaps) and sum(_fits(g, cadence) for g in gaps) >= _FIT_SHARE * len(gaps)


def _is_series(cluster: list[RecurringRow]) -> bool:
    """A ±15 % cluster follows a cadence that accepts one, with its `min_rows`."""
    return any(
        cadence.min_rows is not None and len(cluster) >= cadence.min_rows and _follows(cluster, cadence)
        for cadence in CADENCES
    )


def _is_fixed_series(run: list[RecurringRow], side: list[RecurringRow]) -> bool:
    """A same-amount run follows a cadence with a fixed form, and, for `fixed_alone`, nothing of the side is between."""
    return any(
        cadence.fixed_min_rows is not None
        and len(run) >= cadence.fixed_min_rows
        and _follows(run, cadence)
        and (not cadence.fixed_alone or _alone(run, side))
        for cadence in CADENCES
    )


def _alone(run: list[RecurringRow], side: list[RecurringRow]) -> bool:
    """No row of the side outside the run falls strictly between the run's first and last dates."""
    first, last = min(r.date for r in run), max(r.date for r in run)
    members = {r.id for r in run}
    return not any(r.id not in members and first < r.date < last for r in side)
