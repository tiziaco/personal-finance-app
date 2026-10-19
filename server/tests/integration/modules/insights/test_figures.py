"""figures.py: the one reader of analytics, and what it hands the insights agent."""

import datetime as dt
import json
from decimal import Decimal

import pytest

from app.modules.analytics import AnalyticsHistory, service
from app.modules.insights.figures import gather_figures
from app.modules.transaction import transaction_service

pytestmark = pytest.mark.integration

TODAY = dt.date(2026, 10, 16)


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(service, "_today", lambda: TODAY)


@pytest.fixture
def anomaly_windows(monkeypatch):
    """The `months` each anomalies call was asked for: the spike window it covers is not in the output."""
    seen: list[int | None] = []
    real = AnalyticsHistory.anomalies

    def spy(self, date_range, *args):
        seen.append(date_range.months)
        return real(self, date_range, *args)

    monkeypatch.setattr(AnalyticsHistory, "anomalies", spy)
    return seen


async def test_no_transactions_gives_none(db_session, test_user):
    assert await gather_figures(db_session, test_user.id) is None


async def test_reference_month_is_the_last_finished_month(db_session, test_user, add):
    await add(test_user, "2026-08-10", "-50.00")
    await add(test_user, "2026-09-05", "-200.00")
    await add(test_user, "2026-10-03", "-20.00")
    await add(test_user, "2026-10-12", "-30.00")

    gathered = await gather_figures(db_session, test_user.id)

    assert gathered.reference_month == "2026-09"
    assert gathered.reference_partial is False
    assert gathered.month_to_date_through == dt.date(2026, 10, 12)
    assert "categories_month_to_date" in gathered.figures
    assert "categories_month_to_date_previous" in gathered.figures
    assert gathered.figures["month_to_date"]["through"] == "2026-10-12"
    previous = gathered.figures["categories_month_to_date_previous"]
    assert (previous["date_from"], previous["date_to"]) == ("2026-09-01", "2026-09-12")
    assert "seasonality" not in gathered.figures["behaviour"]
    assert ("food_groceries", "Food & Groceries") in gathered.categories


async def test_no_month_to_date_without_october_rows(db_session, test_user, add):
    await add(test_user, "2026-09-05", "-200.00")

    gathered = await gather_figures(db_session, test_user.id)

    assert gathered.month_to_date_through is None
    assert "categories_month_to_date" not in gathered.figures
    assert "categories_month_to_date_previous" not in gathered.figures


async def test_a_generation_loads_rows_once(db_session, test_user, add, monkeypatch):
    for day in ("2026-07-02", "2026-08-02", "2026-09-02", "2026-10-05"):
        await add(test_user, day, "-300.00")
    loads: list[str] = []
    real_rows = transaction_service.list_for_analysis

    async def rows(*args, **kwargs):
        loads.append("rows")
        return await real_rows(*args, **kwargs)

    def today():
        loads.append("today")
        return TODAY

    monkeypatch.setattr(transaction_service, "list_for_analysis", rows)
    monkeypatch.setattr(service, "_today", today)

    gathered = await gather_figures(db_session, test_user.id)

    assert gathered.month_to_date_through == dt.date(2026, 10, 5)
    assert sorted(loads) == ["rows", "today"]


async def test_merchants_are_collected_from_the_figures(db_session, test_user, add):
    await add(test_user, "2026-09-05", "-200.00", merchant="Esselunga")
    await add(test_user, "2026-09-06", "-9.99", merchant="Netflix", recurring=True)

    gathered = await gather_figures(db_session, test_user.id)

    assert {"Esselunga", "Netflix"} <= gathered.merchants


async def test_figures_are_json_able(db_session, test_user, add):
    await add(test_user, "2026-09-05", "-200.00", merchant="Esselunga")
    await add(test_user, "2026-10-05", "-20.00", merchant="Esselunga")

    gathered = await gather_figures(db_session, test_user.id)

    json.dumps(gathered.figures)


async def test_first_month_only_is_partial(db_session, test_user, add):
    await add(test_user, "2026-10-03", "-20.00")
    await add(test_user, "2026-10-12", "-30.00")

    gathered = await gather_figures(db_session, test_user.id)

    assert gathered.reference_month == "2026-10"
    assert gathered.reference_partial is True
    assert gathered.month_to_date_through is None
    assert "month_to_date" not in gathered.figures
    assert "categories_month_to_date" not in gathered.figures
    assert gathered.figures["reference_through"] == "2026-10-12"
    assert "month_to_date" not in gathered.figures["spending"]
    spending = gathered.figures["spending"]
    assert spending["average_monthly_income"] is None
    assert spending["average_monthly_expenses"] is None
    assert spending["average_monthly_net"] is None
    assert spending["burn_rate"] is None


async def test_a_category_spike_in_the_reference_month_reaches_the_figures(db_session, test_user, add):
    for day in ("2026-06-02", "2026-07-02", "2026-08-02"):
        await add(test_user, day, "-100.00", category="food_groceries")
        await add(test_user, day, "-100.00", category="transportation")
    await add(test_user, "2026-09-02", "-400.00", category="food_groceries")
    await add(test_user, "2026-09-03", "-100.00", category="transportation")

    anomalies = (await gather_figures(db_session, test_user.id)).figures["anomalies"]

    assert [spike["category"] for spike in anomalies["spikes"]] == ["food_groceries"]
    assert anomalies["spike_window_start"] == "2026-09-01"
    assert anomalies["spike_window_end"] == "2026-09-30"
    assert anomalies["date_from"] == "2026-09-01"  # outliers stay the reference month's


async def test_a_new_user_s_usual_spans_only_their_months(db_session, test_user, add, anomaly_windows):
    for day in ("2026-07-02", "2026-08-02", "2026-09-02"):
        await add(test_user, day, "-300.00")

    gathered = await gather_figures(db_session, test_user.id)

    spending = gathered.figures["spending"]
    assert spending["date_from"] == "2026-07-01"
    assert Decimal(spending["average_monthly_expenses"]) == Decimal("300.00")
    figures = gathered.figures
    assert figures["categories_month"]["date_from"] == "2026-09-01"
    for key in ("categories_trend", "recurring", "behaviour"):
        assert figures[key]["date_from"] == "2026-07-01"
    assert anomaly_windows == [1, 3]


async def test_the_usual_starts_at_the_first_month_with_data_and_keeps_a_gap(db_session, test_user, add):
    await add(test_user, "2026-06-02", "-300.00")
    await add(test_user, "2026-09-02", "-300.00")

    gathered = await gather_figures(db_session, test_user.id)

    spending = gathered.figures["spending"]
    assert spending["date_from"] == "2026-06-01"
    assert [m["month"] for m in spending["months"]] == ["2026-06", "2026-07", "2026-08", "2026-09"]
    assert gathered.figures["recurring"]["date_from"] == "2026-06-01"


async def test_a_lone_old_row_does_not_stretch_the_usual_over_empty_months(db_session, test_user, add):
    """A row long before the window (an annual charge) leaves the window's empty first months out."""
    await add(test_user, "2025-07-02", "-99.00", category="leisure_entertainment")
    for day in ("2026-05-02", "2026-06-02", "2026-07-02", "2026-08-02", "2026-09-02"):
        await add(test_user, day, "-300.00")

    gathered = await gather_figures(db_session, test_user.id)

    spending = gathered.figures["spending"]
    assert spending["date_from"] == "2026-05-01"
    assert Decimal(spending["average_monthly_expenses"]) == Decimal("300.00")
    assert gathered.figures["behaviour"]["date_from"] == "2026-05-01"


async def test_a_one_month_user_s_spikes_are_asked_over_two_months(db_session, test_user, add, anomaly_windows):
    await add(test_user, "2026-09-02", "-300.00")

    await gather_figures(db_session, test_user.id)

    assert anomaly_windows == [1, 2]
