"""Periods named as the dashboard and the analytics page name them."""

import datetime as dt

import pytest

from app.modules.conversation.finance.domain.periods import describe_span, name_period, period_label

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 10, 20)

DATA_LAST = dt.date(2026, 10, 19)


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


def label(first: str, last: str) -> str:
    return period_label(d(first), d(last), today=TODAY, data_last=DATA_LAST)


def test_period_label_names_whole_months_by_month():
    assert label("2026-09-01", "2026-09-30") == "September 2026"
    assert label("2026-07-01", "2026-09-30") == "Jul – Sep 2026"


def test_period_label_of_the_month_in_progress_reads_so_far():
    assert label("2026-10-01", "2026-10-19") == "October 2026 so far"


def test_period_label_ending_before_the_data_in_the_month_in_progress_is_by_day():
    assert label("2026-10-01", "2026-10-10") == "1 – 10 Oct 2026"


def test_describe_span():
    assert describe_span(d("2025-03-02"), d("2026-10-19")) == "data covers March 2025 to October 2026"
