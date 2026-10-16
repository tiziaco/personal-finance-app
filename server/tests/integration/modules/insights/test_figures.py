"""figures.py: the one reader of analytics, and what it hands the insights agent."""

import datetime as dt
import json

import pytest

from app.modules.analytics import service
from app.modules.insights.figures import BASELINE_MONTHS, gather_figures

pytestmark = pytest.mark.integration

TODAY = dt.date(2026, 10, 16)


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(service, "_today", lambda: TODAY)


async def test_no_transactions_gives_none(db_session, test_user):
    assert await gather_figures(db_session, test_user.id) is None


async def test_reference_month_is_the_last_finished_month(db_session, test_user, add):
    await add(test_user, "2026-08-10", "-50.00")
    await add(test_user, "2026-09-05", "-200.00")
    await add(test_user, "2026-10-03", "-20.00")
    await add(test_user, "2026-10-12", "-30.00")

    gathered = await gather_figures(db_session, test_user.id)

    assert gathered.input.reference_month == "2026-09"
    assert gathered.input.reference_partial is False
    assert gathered.input.month_to_date_through == dt.date(2026, 10, 12)
    assert "categories_month_to_date" in gathered.input.figures
    assert "categories_month_to_date_previous" in gathered.input.figures
    assert gathered.input.figures["month_to_date"]["through"] == "2026-10-12"
    assert "seasonality" not in gathered.input.figures["behaviour"]
    assert ("food_groceries", "Food & Groceries") in gathered.input.categories


async def test_baseline_months_counts_months_with_data(db_session, test_user, add):
    for day in ("2026-06-05", "2026-07-05", "2026-08-05", "2026-09-05"):
        await add(test_user, day, "-10.00")

    gathered = await gather_figures(db_session, test_user.id)

    assert gathered.baseline_months == 3
    assert BASELINE_MONTHS == 6


async def test_no_month_to_date_without_october_rows(db_session, test_user, add):
    await add(test_user, "2026-09-05", "-200.00")

    gathered = await gather_figures(db_session, test_user.id)

    assert gathered.input.month_to_date_through is None
    assert "categories_month_to_date" not in gathered.input.figures
    assert "categories_month_to_date_previous" not in gathered.input.figures


async def test_merchants_are_collected_from_the_figures(db_session, test_user, add):
    await add(test_user, "2026-09-05", "-200.00", merchant="Esselunga")
    await add(test_user, "2026-09-06", "-9.99", merchant="Netflix", recurring=True)

    gathered = await gather_figures(db_session, test_user.id)

    assert {"Esselunga", "Netflix"} <= gathered.input.merchants


async def test_figures_are_json_able(db_session, test_user, add):
    await add(test_user, "2026-09-05", "-200.00", merchant="Esselunga")
    await add(test_user, "2026-10-05", "-20.00", merchant="Esselunga")

    gathered = await gather_figures(db_session, test_user.id)

    json.dumps(gathered.input.figures)


async def test_first_month_only_is_partial(db_session, test_user, add):
    await add(test_user, "2026-10-03", "-20.00")
    await add(test_user, "2026-10-12", "-30.00")

    gathered = await gather_figures(db_session, test_user.id)

    assert gathered.input.reference_month == "2026-10"
    assert gathered.input.reference_partial is True
    assert gathered.baseline_months == 0
    assert gathered.input.month_to_date_through is None
    assert "month_to_date" not in gathered.input.figures
    assert "categories_month_to_date" not in gathered.input.figures
    assert gathered.input.figures["reference_through"] == "2026-10-12"
    assert "month_to_date" not in gathered.input.figures["spending"]
