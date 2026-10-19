"""The recurring rule: one merchant's rows judged as a series (docs/data-model/transaction.md, D6).

A series is a ±15 % amount cluster that meets a CLUSTER_RULE (monthly, quarterly, yearly),
or a same-amount run inside one that meets a RUN_RULE (weekly, yearly): tighter, so fewer rows.
"""

import datetime as dt
import uuid
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

DETECTED = "detected"
USER = "user"

_FIT_SHARE = 0.75


@dataclass(frozen=True)
class Band:
    """How close an amount must be to a seed: a share of the seed, with at least `slack` in euros."""

    share: Decimal
    slack: Decimal


_CLUSTER_BAND = Band(Decimal("0.15"), Decimal("1"))
_RUN_BAND = Band(Decimal("0.02"), Decimal("0.10"))


@dataclass(frozen=True)
class Cadence:
    """A period a series can follow: the days between two of its rows."""

    name: str
    min_days: int
    max_days: int


WEEKLY = Cadence("weekly", 6, 8)
MONTHLY = Cadence("monthly", 26, 35)
QUARTERLY = Cadence("quarterly", 84, 98)
YEARLY = Cadence("yearly", 350, 380)


@dataclass(frozen=True)
class Rule:
    """A form of series: a cadence and the rows it needs.

    `skip` lets a gap be twice the window, for one skipped period. `alone` adds that no
    other row of the same side falls strictly between the rows' first and last dates.
    """

    cadence: Cadence
    min_rows: int
    skip: bool = True
    alone: bool = False


CLUSTER_RULES = (Rule(MONTHLY, 3), Rule(QUARTERLY, 3), Rule(YEARLY, 3))  # a ±15 % cluster
RUN_RULES = (Rule(WEEKLY, 4), Rule(YEARLY, 2, skip=False, alone=True))  # a same-amount run


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
    is recurring when its cluster is a series or its run is, so an odd purchase in a
    cluster does not undo the run beside it. `user` rows count as evidence and get
    no verdict, so they are never changed.
    """
    verdict: dict[uuid.UUID, bool] = {}
    for incoming in (True, False):
        side = [r for r in rows if (r.amount > 0) is incoming]
        for cluster in _clusters(side, _CLUSTER_BAND):
            series = _is_series(cluster, CLUSTER_RULES, side)
            for run in _clusters(cluster, _RUN_BAND):
                recurring = series or _is_series(run, RUN_RULES, side)
                for row in run:
                    if row.source == DETECTED:
                        verdict[row.id] = recurring
    return verdict


def _clusters(rows: list[RecurringRow], band: Band) -> list[list[RecurringRow]]:
    """Rows grouped around fixed seeds: the most frequent amounts first, then the smallest.

    A row joins the first cluster whose seed it is within `band` of; otherwise it
    seeds a cluster. A fixed seed does not drift the way a running median does.
    """
    counts = Counter(abs(r.amount) for r in rows)
    clusters: list[tuple[Decimal, list[RecurringRow]]] = []
    for row in sorted(rows, key=lambda r: (-counts[abs(r.amount)], abs(r.amount), r.date)):
        size = abs(row.amount)
        for seed, members in clusters:
            if abs(size - seed) <= max(seed * band.share, band.slack):
                members.append(row)
                break
        else:
            clusters.append((size, [row]))
    return [members for _, members in clusters]


def _fits(gap: int, rule: Rule) -> bool:
    """A gap of one period, or, when the rule allows a skip, of two."""
    window = rule.cadence
    if window.min_days <= gap <= window.max_days:
        return True
    return rule.skip and 2 * window.min_days <= gap <= 2 * window.max_days


def _is_series(rows: list[RecurringRow], rules: tuple[Rule, ...], side: list[RecurringRow]) -> bool:
    """The rows meet one of the rules: enough of them, 75 % of their gaps fitting, and, for `alone`, nothing between."""
    dates = sorted(r.date for r in rows)
    gaps = [(later - earlier).days for earlier, later in zip(dates, dates[1:], strict=False)]
    return any(
        len(rows) >= rule.min_rows
        and sum(_fits(g, rule) for g in gaps) >= _FIT_SHARE * len(gaps)
        and (not rule.alone or _alone(rows, side))
        for rule in rules
    )


def _alone(run: list[RecurringRow], side: list[RecurringRow]) -> bool:
    """No row of the side outside the run falls strictly between the run's first and last dates."""
    first, last = min(r.date for r in run), max(r.date for r in run)
    members = {r.id for r in run}
    return not any(r.id not in members and first < r.date < last for r in side)
