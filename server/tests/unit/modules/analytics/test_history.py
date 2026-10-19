"""AnalyticsHistory: each analysis over in-memory rows equals the domain call it wraps."""

import datetime as dt

import pytest

from app.modules.analytics.domain.anomalies import find_anomalies
from app.modules.analytics.domain.behaviour import behaviour_analysis
from app.modules.analytics.domain.categories import category_breakdown
from app.modules.analytics.domain.dashboard import build_dashboard
from app.modules.analytics.domain.merchants import merchant_breakdown
from app.modules.analytics.domain.period import resolve_period
from app.modules.analytics.domain.recurring import recurring_analysis
from app.modules.analytics.domain.spending import spending_summary
from app.modules.analytics.history import AnalyticsHistory
from app.modules.analytics.schemas import (
    AnomaliesResponse,
    BehaviourResponse,
    CategoryBreakdownResponse,
    DashboardResponse,
    DateRange,
    MerchantBreakdownResponse,
    RecurringResponse,
    SpendingResponse,
)
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 10, 16)

ROWS = [
    row("2026-06-01", "-800.00"),
    row("2026-07-10", "-1000.00", merchant="Rent Co", category="housing", recurring=True),
    row("2026-07-25", "2000.00", category="salary", merchant="Employer"),
    row("2026-08-10", "-1000.00", merchant="Rent Co", category="housing", recurring=True),
    row("2026-08-25", "2000.00", category="salary", merchant="Employer"),
    row("2026-09-01", "-50.00"),
    row("2026-09-10", "-1000.00", merchant="Rent Co", category="housing", recurring=True),
    row("2026-09-25", "2000.00", category="salary", merchant="Employer"),
    row("2026-10-02", "-100.00"),
]
RANGE = DateRange(months=3)


@pytest.fixture
def history():
    return AnalyticsHistory(rows=tuple(ROWS), today=TODAY)


@pytest.fixture
def period():
    return resolve_period(ROWS, TODAY, months=3)


def test_period(history, period):
    assert history.period(RANGE) == period
    assert history.period(RANGE) is not None


def test_dashboard(history):
    expected = DashboardResponse.model_validate(build_dashboard(ROWS, today=TODAY), from_attributes=True)
    assert history.dashboard() == expected


def test_spending(history, period):
    assert history.spending(RANGE) == SpendingResponse.model_validate(spending_summary(ROWS, period, today=TODAY))


def test_categories(history, period):
    expected = CategoryBreakdownResponse.model_validate(category_breakdown(ROWS, period, 5, today=TODAY))
    assert history.categories(RANGE, 5) == expected


def test_merchants(history, period):
    assert history.merchants(RANGE, 5) == MerchantBreakdownResponse.model_validate(merchant_breakdown(ROWS, period, 5))


def test_recurring(history, period):
    assert history.recurring(RANGE) == RecurringResponse.model_validate(recurring_analysis(ROWS, period))


def test_behaviour(history, period):
    assert history.behaviour(RANGE) == BehaviourResponse.model_validate(behaviour_analysis(ROWS, period))


def test_anomalies(history, period):
    expected = AnomaliesResponse.model_validate(find_anomalies(ROWS, period, 2.0, 90))
    assert history.anomalies(RANGE, 2.0, 90) == expected
