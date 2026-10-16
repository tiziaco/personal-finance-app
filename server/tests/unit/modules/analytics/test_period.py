"""The period resolver: how a request and the data become finished calendar months (spec §3)."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain._aggregate import AVERAGE_MONTH_DAYS, month_end
from app.modules.analytics.domain.period import (
    FIRST_MONTH_GRACE_DAYS,
    anchor_month,
    calendar_month,
    data_span,
    previous_period,
    resolve_period,
    usable_rows,
)
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

D = dt.date
TODAY = D(2026, 10, 16)

ROWS = [
    row("2026-03-12", "-10.00"),
    row("2026-04-05", "-10.00"),
    row("2026-05-05", "-10.00"),
    row("2026-06-05", "-10.00"),
    row("2026-07-05", "-10.00"),
    row("2026-08-05", "-10.00"),
    row("2026-09-05", "-10.00"),
    row("2026-10-03", "-10.00"),
    row("2027-01-05", "-10.00"),  # a typo: past the current month, in no period
]
OCTOBER_ONLY = [row("2026-10-02", "-5.00"), row("2026-10-05", "-5.00")]


def test_month_end_and_the_average_month():
    assert month_end(D(2026, 2, 14)) == D(2026, 2, 28)
    assert month_end(D(2028, 2, 1)) == D(2028, 2, 29)
    assert month_end(D(2026, 12, 31)) == D(2026, 12, 31)
    assert month_end(D(9999, 12, 1)) == D(9999, 12, 31)
    assert AVERAGE_MONTH_DAYS == Decimal("365.2425") / 12
    assert FIRST_MONTH_GRACE_DAYS == 7


def test_usable_rows_stop_at_the_end_of_the_current_month():
    assert [r.date for r in usable_rows(ROWS, TODAY)][-1] == D(2026, 10, 3)
    assert data_span(ROWS, TODAY) == (D(2026, 3, 12), D(2026, 10, 3))
    assert data_span([], TODAY) is None
    assert data_span([row("2027-01-05", "-1.00")], TODAY) is None


def test_the_anchor_is_the_latest_finished_month_with_data():
    assert anchor_month(ROWS, TODAY) == D(2026, 9, 1)
    assert anchor_month(OCTOBER_ONLY, TODAY) == D(2026, 10, 1)
    assert anchor_month([], TODAY) is None


def test_months_end_at_the_anchor():
    period = resolve_period(ROWS, TODAY, months=3)
    assert period is not None
    assert period.first_day == D(2026, 7, 1)
    assert period.last_day == D(2026, 9, 30)
    assert [m.start for m in period.months] == [D(2026, 7, 1), D(2026, 8, 1), D(2026, 9, 1)]
    assert period.whole_months() == period.months
    assert period.weight() == 3


def test_the_default_runs_from_the_first_data_month_to_the_anchor():
    period = resolve_period(ROWS, TODAY)
    assert period is not None
    assert [m.start for m in period.months] == [D(2026, m, 1) for m in range(3, 10)]
    march = period.months[0]
    assert march.first_day == D(2026, 3, 12)
    assert march.last_day == D(2026, 3, 31)
    assert march.partial
    assert march.weight == Decimal(20) / Decimal(31)
    assert period.whole_months() == period.months[1:]
    assert period.weight() == 6 + Decimal(20) / Decimal(31)


def test_more_months_than_the_history_is_clipped_to_it():
    assert resolve_period(ROWS, TODAY, months=120) == resolve_period(ROWS, TODAY)


def test_explicit_bounds_cut_months_and_the_current_month_ends_at_its_last_row():
    period = resolve_period(ROWS, TODAY, date_from=D(2026, 8, 15), date_to=D(2026, 12, 31))
    assert period is not None
    august, september, october = period.months
    assert (august.first_day, august.last_day, august.partial) == (D(2026, 8, 15), D(2026, 8, 31), True)
    assert august.weight == Decimal(17) / Decimal(31)
    assert (september.partial, september.weight) == (False, Decimal(1))
    assert (october.first_day, october.last_day, october.partial) == (D(2026, 10, 1), D(2026, 10, 3), True)
    assert october.weight == Decimal(3) / Decimal(31)
    assert period.last_day == D(2026, 10, 3)
    assert D(2027, 1, 5) not in [r.date for r in period.rows(ROWS)]
    assert [r.date for r in period.rows(ROWS)] == [D(2026, 9, 5), D(2026, 10, 3)]


def test_a_start_before_the_data_is_clipped_then_the_first_month_starts_at_its_row():
    period = resolve_period(ROWS, TODAY, date_from=D(2025, 1, 1), date_to=D(2026, 4, 30))
    assert period is not None
    assert period.first_day == D(2026, 3, 12)
    assert period.last_day == D(2026, 4, 30)
    assert [m.partial for m in period.months] == [True, False]


def test_a_one_day_range_weighs_one_day_of_its_month():
    period = resolve_period(ROWS, TODAY, date_from=D(2026, 9, 10), date_to=D(2026, 9, 10))
    assert period is not None
    (september,) = period.months
    assert (september.first_day, september.last_day, september.partial) == (D(2026, 9, 10), D(2026, 9, 10), True)
    assert september.weight == Decimal(1) / Decimal(30)
    assert period.contains(D(2026, 9, 10))
    assert not period.contains(D(2026, 9, 11))


def test_a_range_wholly_outside_the_data_or_no_data_is_no_period():
    assert resolve_period(ROWS, TODAY, date_from=D(2027, 2, 1)) is None
    assert resolve_period(ROWS, TODAY, date_to=D(2025, 12, 31)) is None
    assert resolve_period([], TODAY) is None
    assert resolve_period([], TODAY, months=3) is None
    assert resolve_period([], TODAY, date_from=D(2026, 1, 1), date_to=D(2026, 12, 31)) is None


def test_only_this_months_data_gives_the_month_in_progress():
    period = resolve_period(OCTOBER_ONLY, TODAY, months=3)
    assert period is not None
    (october,) = period.months
    assert october.start == D(2026, 10, 1)
    assert october.partial
    assert (october.first_day, october.last_day) == (D(2026, 10, 1), D(2026, 10, 5))
    assert october.weight == Decimal(5) / Decimal(31)


def test_a_gap_between_imports_is_a_zero_filled_period():
    rows = [row("2026-03-02", "-1.00"), row("2026-09-02", "-1.00")]
    period = resolve_period(rows, TODAY, date_from=D(2026, 5, 1), date_to=D(2026, 6, 30))
    assert period is not None
    assert [(m.start, m.partial) for m in period.months] == [(D(2026, 5, 1), False), (D(2026, 6, 1), False)]
    assert period.rows(rows) == []


def test_the_previous_period_of_whole_months_is_as_many_months_before():
    period = resolve_period(ROWS, TODAY, months=3)
    assert period is not None
    previous = previous_period(period, ROWS, TODAY)
    assert previous is not None
    assert (previous.first_day, previous.last_day) == (D(2026, 4, 1), D(2026, 6, 30))
    assert [m.partial for m in previous.months] == [False, False, False]


def test_the_previous_period_of_a_day_span_is_as_many_days_before():
    period = resolve_period(ROWS, TODAY, date_from=D(2026, 8, 15), date_to=D(2026, 9, 20))
    assert period is not None
    assert (period.last_day - period.first_day).days + 1 == 37
    previous = previous_period(period, ROWS, TODAY)
    assert previous is not None
    assert (previous.first_day, previous.last_day) == (D(2026, 7, 9), D(2026, 8, 14))


def test_no_previous_period_before_the_data_or_without_rows():
    period = resolve_period(ROWS, TODAY)
    assert period is not None
    assert previous_period(period, ROWS, TODAY) is None

    gap = [row("2026-03-02", "-1.00"), row("2026-09-02", "-1.00")]
    september = resolve_period(gap, TODAY, months=1)
    assert september is not None
    assert previous_period(september, gap, TODAY) is None  # August is inside the data's months, but empty


def test_months_and_the_previous_period_step_across_a_year():
    today = D(2026, 1, 20)
    rows = [row(day, "-1.00") for day in ("2025-09-03", "2025-10-03", "2025-11-03", "2025-12-03", "2026-01-03")]
    period = resolve_period(rows, today, months=3)
    assert period is not None
    assert [m.start for m in period.months] == [D(2025, 10, 1), D(2025, 11, 1), D(2025, 12, 1)]
    previous = previous_period(period, rows, today)
    assert previous is not None
    assert [m.start for m in previous.months] == [D(2025, 9, 1)]
    assert (previous.first_day, previous.last_day) == (D(2025, 9, 1), D(2025, 9, 30))


def test_calendar_month_is_the_month_as_the_data_sees_it():
    today = D(2028, 2, 20)
    rows = [row("2028-02-10", "-1.00"), row("2028-02-18", "-1.00")]
    february = calendar_month(D(2028, 2, 1), rows, today)
    assert february is not None
    assert february.partial
    assert (february.first_day, february.last_day) == (D(2028, 2, 10), D(2028, 2, 18))
    assert february.weight == Decimal(9) / Decimal(29)
    assert calendar_month(D(2028, 1, 1), rows, today) is None
    assert calendar_month(D(2028, 3, 1), rows, today) is None


def test_calendar_month_of_a_finished_month_is_whole():
    september = calendar_month(D(2026, 9, 1), ROWS, TODAY)
    assert september is not None
    assert (september.first_day, september.last_day, september.partial) == (D(2026, 9, 1), D(2026, 9, 30), False)
    assert september.weight == Decimal(1)
    assert calendar_month(D(2026, 11, 1), ROWS, TODAY) is None  # the typo row does not reach November


def test_a_first_row_within_the_grace_days_leaves_the_first_month_whole():
    rows = [row("2026-03-07", "-1.00"), row("2026-04-07", "-1.00")]
    period = resolve_period(rows, TODAY)
    assert period is not None
    assert period.first_day == D(2026, 3, 1)
    assert not period.months[0].partial
