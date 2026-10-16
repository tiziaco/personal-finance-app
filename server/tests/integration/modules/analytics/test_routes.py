"""The analytics routes against a real database: auth, ownership, ranges, and one end-to-end dashboard."""

import datetime as dt

import pytest

from app.modules.analytics import service

pytestmark = pytest.mark.integration

BASE = "/api/v1/analytics"
ROUTES = ["dashboard", "spending", "categories", "merchants", "recurring", "behaviour", "anomalies"]
TODAY = dt.date(2026, 10, 16)


@pytest.fixture
def today(monkeypatch):
    """Pin the service's today, so a period resolves the same whenever the suite runs."""
    monkeypatch.setattr(service, "_today", lambda: TODAY)
    return TODAY


@pytest.mark.parametrize("route", ROUTES)
async def test_signed_out_is_401(client, route):
    assert (await client.get(f"{BASE}/{route}")).status_code == 401


@pytest.mark.parametrize("route", ROUTES)
async def test_a_user_with_no_transactions_gets_200(authenticated_client, route):
    assert (await authenticated_client.get(f"{BASE}/{route}")).status_code == 200


@pytest.mark.parametrize("route", ROUTES[1:])
async def test_an_inverted_range_is_422(authenticated_client, route):
    response = await authenticated_client.get(
        f"{BASE}/{route}", params={"date_from": "2026-03-02", "date_to": "2026-03-01"}
    )
    assert response.status_code == 422
    assert response.json()["error"] == "INVALID_DATE_RANGE"


@pytest.mark.parametrize("route", ROUTES[1:])
@pytest.mark.parametrize("params", [{"date_to": "9999-12-31"}, {"date_from": "0001-01-01"}])
async def test_a_date_outside_1900_2100_is_422(authenticated_client, route, params):
    response = await authenticated_client.get(f"{BASE}/{route}", params=params)
    assert response.status_code == 422
    assert response.json()["error"] == "INVALID_DATE_RANGE"


@pytest.mark.parametrize("route", ROUTES[1:])
async def test_months_with_a_bound_is_422(authenticated_client, route):
    response = await authenticated_client.get(f"{BASE}/{route}", params={"months": 3, "date_to": "2026-09-30"})
    assert response.status_code == 422
    assert response.json()["error"] == "INVALID_DATE_RANGE"


@pytest.mark.parametrize("route", ROUTES[1:])
async def test_months_alone_is_200(authenticated_client, route):
    assert (await authenticated_client.get(f"{BASE}/{route}", params={"months": 3})).status_code == 200


async def test_empty_dashboard(authenticated_client):
    body = (await authenticated_client.get(f"{BASE}/dashboard")).json()
    assert body == {
        "reference_month": None,
        "total_spent": "0.00",
        "recurring_spent": "0.00",
        "recurring_count": 0,
        "net_balance": "0.00",
        "average_cashflow": "0.00",
        "cashflow_months": 0,
        "spending_by_category": [],
        "monthly_trend": [],
    }


async def test_dashboard_counts_only_this_users_active_rows(authenticated_client, test_user, other_user, add):
    await add(test_user, "2026-08-10", "2000.00", category="salary")
    await add(test_user, "2026-09-01", "-900.00", category="household_utilities", merchant="Landlord", recurring=True)
    await add(test_user, "2026-09-05", "-200.00")
    await add(test_user, "2026-09-25", "2100.00", category="salary")
    await add(test_user, "2026-09-26", "-5000.00", deleted=True)  # soft-deleted: invisible
    await add(test_user, "2026-10-02", "-1.00", deleted=True)  # would move the reference month if counted
    await add(other_user, "2026-10-01", "-9999.00")  # another user's: invisible

    body = (await authenticated_client.get(f"{BASE}/dashboard")).json()

    assert body["reference_month"] == "2026-09"
    assert body["total_spent"] == "1100.00"
    assert (body["recurring_spent"], body["recurring_count"]) == ("900.00", 1)
    assert body["net_balance"] == "1000.00"
    assert (body["average_cashflow"], body["cashflow_months"]) == ("1500.00", 2)  # (2000 + 1000) ÷ 2
    assert body["spending_by_category"] == [
        {"category": "household_utilities", "amount": "900.00", "share_pct": 81.82},
        {"category": "food_groceries", "amount": "200.00", "share_pct": 18.18},
    ]
    assert [p["month"] for p in body["monthly_trend"]] == [
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
    ]


async def test_spending_over_the_last_three_finished_months(authenticated_client, test_user, add, today):
    await add(test_user, "2026-06-01", "-800.00")
    for month in ("07", "08"):
        await add(test_user, f"2026-{month}-10", "-1000.00")
        await add(test_user, f"2026-{month}-25", "2000.00", category="salary")
    await add(test_user, "2026-09-01", "-50.00")
    await add(test_user, "2026-09-10", "-1250.00")
    await add(test_user, "2026-09-25", "2000.00", category="salary")
    await add(test_user, "2026-10-02", "-100.00")

    body = (await authenticated_client.get(f"{BASE}/spending", params={"months": 3})).json()

    assert (body["date_from"], body["date_to"]) == ("2026-07-01", "2026-09-30")
    assert body["average_monthly_net"] == "900.00"
    assert [m["month"] for m in body["months"]] == ["2026-07", "2026-08", "2026-09"]
    assert body["latest_month"]["month"] == "2026-09"
    assert body["month_to_date"]["through"] == "2026-10-02"
    assert body["month_to_date"]["expenses"] == "100.00"


async def test_spending_respects_the_range(authenticated_client, test_user, add, today):
    await add(test_user, "2026-01-15", "-10.00")
    await add(test_user, "2026-02-15", "-20.00")
    await add(test_user, "2026-03-15", "-40.00")

    body = (
        await authenticated_client.get(f"{BASE}/spending", params={"date_from": "2026-02-01", "date_to": "2026-02-28"})
    ).json()

    assert body["total_expenses"] == "20.00"
    assert [m["month"] for m in body["months"]] == ["2026-02"]


async def test_categories_top_n_and_bounds(authenticated_client, test_user, add):
    for category in ("food_groceries", "shopping", "transportation"):
        await add(test_user, "2026-03-01", "-10.00", category=category)
    body = (await authenticated_client.get(f"{BASE}/categories", params={"top_n": 2})).json()
    assert len(body["top_categories"]) == 2
    assert (await authenticated_client.get(f"{BASE}/categories", params={"top_n": 51})).status_code == 422


async def test_anomalies_echo_their_parameters(authenticated_client):
    body = (await authenticated_client.get(f"{BASE}/anomalies", params={"std_threshold": 3, "window_days": 14})).json()
    assert (body["std_threshold"], body["window_days"]) == (3.0, 14)
    assert (await authenticated_client.get(f"{BASE}/anomalies", params={"window_days": 6})).status_code == 422


async def test_rows_outside_1900_2100_are_left_out(authenticated_client, test_user, add, today):
    await add(test_user, "2026-03-15", "-40.00")
    await add(test_user, "9999-12-31", "-10.00")
    await add(test_user, "0001-01-01", "-10.00")

    body = (await authenticated_client.get(f"{BASE}/spending")).json()

    assert body["total_expenses"] == "40.00"
    assert [m["month"] for m in body["months"]] == ["2026-03"]


async def test_categories_over_two_months(authenticated_client, test_user, add, today):
    await add(test_user, "2026-07-05", "-100.00", category="shopping")
    await add(test_user, "2026-08-05", "-150.00", category="shopping")
    await add(test_user, "2026-09-05", "-300.00", category="shopping")

    body = (await authenticated_client.get(f"{BASE}/categories", params={"months": 2})).json()

    assert (body["date_from"], body["date_to"]) == ("2026-08-01", "2026-09-30")
    assert body["top_categories"][0]["total"] == "450.00"


async def test_merchants_over_one_month_has_no_risk_band(authenticated_client, test_user, add, today):
    await add(test_user, "2026-06-05", "-50.00", merchant="June Shop")
    await add(test_user, "2026-09-05", "-20.00", merchant="Sept Shop")

    response = await authenticated_client.get(f"{BASE}/merchants", params={"months": 1})

    assert response.status_code == 200
    body = response.json()
    assert (body["date_from"], body["date_to"]) == ("2026-09-01", "2026-09-30")
    assert [m["merchant"] for m in body["top_by_spend"]] == ["Sept Shop"]
    assert "risk" not in body["concentration"]


async def test_recurring_over_three_months(authenticated_client, test_user, add, today):
    for day in ("2026-06-05", "2026-07-05", "2026-08-05", "2026-09-05"):
        await add(test_user, day, "-10.00", merchant="Netflix", recurring=True)

    response = await authenticated_client.get(f"{BASE}/recurring", params={"months": 3})

    assert response.status_code == 200
    body = response.json()
    assert (body["date_from"], body["date_to"]) == ("2026-07-01", "2026-09-30")
    assert body["merchants"][0]["charges"] == 3
    assert body["merchants"][0]["monthly_cost"] == "10.00"
    assert body["merchants"][0]["active"] is True


async def test_behaviour_over_three_months_echoes_the_period(authenticated_client, test_user, add, today):
    await add(test_user, "2026-07-01", "-10.00")
    await add(test_user, "2026-09-30", "-10.00")

    body = (await authenticated_client.get(f"{BASE}/behaviour", params={"months": 3})).json()

    assert (body["date_from"], body["date_to"]) == ("2026-07-01", "2026-09-30")
    assert [d["days"] for d in body["by_weekday"]] == [13, 13, 14, 13, 13, 13, 13]
