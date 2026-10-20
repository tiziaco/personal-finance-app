"""Periods named as the dashboard and the analytics page name them."""

import datetime as dt

import pytest

from app.modules.analytics import AnalyticsHistory, DateRange
from app.modules.conversation.finance.domain.periods import data_span, describe_span, name_period, period_label
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 10, 20)

HISTORY = AnalyticsHistory(
    rows=(
        row("2025-03-02", "-40.00"),
        row("2026-07-05", "-200.00"),
        row("2026-09-05", "-300.00"),
        row("2026-10-19", "-25.00"),
    ),
    today=TODAY,
)


def d(day: str) -> dt.date:
    return dt.date.fromisoformat(day)


@pytest.mark.parametrize(
    ("first", "last", "name"),
    [
        ("2026-09-01", "2026-09-30", "September 2026"),
        ("2026-07-01", "2026-09-30", "Jul – Sep 2026"),
        ("2025-11-01", "2026-01-31", "Nov 2025 – Jan 2026"),
        ("2026-09-03", "2026-09-19", "3 – 19 Sep 2026"),
        ("2026-08-28", "2026-09-19", "28 Aug – 19 Sep 2026"),
        ("2025-12-28", "2026-01-03", "28 Dec 2025 – 3 Jan 2026"),
        ("2026-09-19", "2026-09-19", "19 Sep 2026"),
        ("2026-07-10", "2026-09-30", "10 Jul – 30 Sep 2026"),  # a first month of data that starts late
    ],
)
def test_name_period(first, last, name):
    assert name_period(d(first), d(last)) == name


def test_a_period_ending_in_the_month_in_progress_reads_so_far():
    assert name_period(d("2026-10-01"), d("2026-10-19"), so_far=True) == "October 2026 so far"
    assert name_period(d("2026-08-01"), d("2026-10-19"), so_far=True) == "Aug – Oct 2026 so far"


def test_period_label_matches_the_analytics_naming():
    assert period_label(HISTORY, DateRange(months=1)) == "September 2026"
    assert period_label(HISTORY, DateRange(months=3)) == "Jul – Sep 2026"


def test_period_label_of_the_month_in_progress_reads_so_far():
    assert period_label(HISTORY, DateRange(date_from=d("2026-10-01"))) == "October 2026 so far"


def test_a_range_cut_before_the_datas_end_is_named_by_day():
    assert period_label(HISTORY, DateRange(date_from=d("2026-10-01"), date_to=d("2026-10-10"))) == "1 – 10 Oct 2026"


def test_period_label_refuses_a_range_with_no_period():
    with pytest.raises(ValueError):
        period_label(HISTORY, DateRange(date_to=d("2019-12-31")))


def test_data_span_and_its_description():
    assert data_span(HISTORY) == (d("2025-03-02"), d("2026-10-19"))
    assert describe_span(*data_span(HISTORY)) == "data covers March 2025 to October 2026"
    assert data_span(AnalyticsHistory(rows=(), today=TODAY)) is None
