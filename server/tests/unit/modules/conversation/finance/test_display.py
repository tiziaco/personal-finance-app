"""Tool outcomes: compact, bounded text for the model that opens with the period; numbers for the UI."""

import datetime as dt

import pytest

from app.agents.chatbot.toolkit import SummaryItem
from app.modules.analytics import (
    AnalyticsHistory,
    AnomaliesResponse,
    CategoryBreakdownResponse,
    DateRange,
    MerchantBreakdownResponse,
    RecurringResponse,
)
from app.modules.conversation.finance.domain.display import (
    MONTHS_SHOWN,
    RECURRING_SHOWN,
    TRENDS_SHOWN,
    category_breakdown_outcome,
    recurring_costs_outcome,
    spending_behaviour_outcome,
    spending_overview_outcome,
    top_merchants_outcome,
    unusual_spending_outcome,
)
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 10, 20)
NAMES = {"food_groceries": "Food & Groceries", "savings_investments": "Savings & Investments"}


def category(slug: str, total: str, **extra) -> dict:
    return {
        "category": slug,
        "total": total,
        "count": 3,
        "average": "10.00",
        "share_pct": 7.14,
        "previous_total": None,
        "change_pct": None,
    } | extra


def trend(slug: str) -> dict:
    return {
        "category": slug,
        "earlier_monthly_average": "10.00",
        "later_monthly_average": "14.00",
        "change_amount": "4.00",
        "change_pct": 40.0,
    }


def breakdown(categories: list[dict], growing: list[dict] = ()) -> CategoryBreakdownResponse:
    return CategoryBreakdownResponse.model_validate(
        {
            "date_from": "2026-09-01",
            "date_to": "2026-09-30",
            "previous_date_from": "2026-08-01",
            "previous_date_to": "2026-08-31",
            "total_expenses": "2184.00",
            "top_categories": categories,
            "by_frequency": categories,
            "top_growing": list(growing),
            "top_declining": [],
        }
    )


def test_category_outcome_is_bounded_and_names_the_period():
    categories = [category(f"cat_{i}", f"{100 + i}.50") for i in range(14)]
    growing = [trend(f"cat_{i}") for i in range(8)]

    out = category_breakdown_outcome(breakdown(categories, growing), "Sep 2026", NAMES)

    assert out.content.startswith("Sep 2026")
    assert out.display.period == "Sep 2026"
    assert out.display.title == "Spending by category"
    assert out.display.summary[0] == SummaryItem(kind="count", value=14, label="categories")
    assert out.display.summary[1] == SummaryItem(kind="money", value=2184.0, label="spent")
    assert len(out.display.table.rows) == 14
    assert all(isinstance(r["total"], float) for r in out.display.table.rows)
    assert out.display.table.rows[0]["total"] == 100.5
    growing_lines = [line for line in out.content.splitlines() if "a month (+40.0%)" in line]
    assert len(growing_lines) == TRENDS_SHOWN


def test_category_outcome_names_categories_and_their_slugs_and_the_previous_period():
    categories = [
        category("savings_investments", "500.00", previous_total="400.00", change_pct=25.0),
        category("food_groceries", "300.00", previous_total="0.00"),
    ]

    out = category_breakdown_outcome(breakdown(categories), "September 2026", NAMES)

    assert "against the previous period of the same length, August 2026" in out.content
    assert "- Savings & Investments (savings_investments): 500.00 EUR" in out.content
    assert "+25.0% on 400.00 EUR before" in out.content
    assert "Food & Groceries (food_groceries): 300.00 EUR" in out.content
    assert "new (nothing in the previous period)" in out.content
    assert [r["category"] for r in out.display.table.rows] == ["Savings & Investments", "Food & Groceries"]


def test_a_period_without_spending_says_so_and_has_no_table():
    out = category_breakdown_outcome(breakdown([]), "September 2026", NAMES)

    assert out.content == "September 2026\nNo spending in this period."
    assert out.display.table is None


def history(rows) -> AnalyticsHistory:
    return AnalyticsHistory(rows=tuple(rows), today=TODAY)


def test_spending_outcome_carries_totals_months_and_the_month_in_progress():
    h = history(
        [
            row("2026-08-10", "2000.00", category="salary"),
            row("2026-08-12", "-500.00"),
            row("2026-09-10", "2000.00", category="salary"),
            row("2026-09-12", "-1500.00"),
            row("2026-10-05", "-12.00"),
        ]
    )

    out = spending_overview_outcome(h.spending(DateRange(months=2)), "Aug – Sep 2026")

    lines = out.content.splitlines()
    assert lines[0] == "Aug – Sep 2026"
    assert lines[1] == (
        "Income 4000.00 EUR, expenses 2000.00 EUR, net 2000.00 EUR, savings rate 50.0%; 4 transactions."
    )
    assert "- Sep 2026: income 2000.00 EUR, expenses 1500.00 EUR, net 500.00 EUR, savings rate 25.0%" in out.content
    assert "Month in progress, Oct 2026 through 2026-10-05" in out.content
    assert out.display.summary == [
        SummaryItem(kind="money", value=2000.0, label="spent"),
        SummaryItem(kind="money", value=4000.0, label="income"),
        SummaryItem(kind="percent", value=50.0, label="savings rate"),
    ]
    assert out.display.table.rows[1] == {
        "month": "Sep 2026",
        "income": 2000.0,
        "expenses": 1500.0,
        "net": 500.0,
        "savings_rate_pct": 25.0,
    }


def test_spending_outcome_keeps_only_the_latest_months():
    rows = [row(f"{2020 + m // 12}-{m % 12 + 1:02d}-10", "-10.00") for m in range(36)]

    out = spending_overview_outcome(history(rows).spending(DateRange(months=36)), "Jan 2020 – Dec 2022")

    assert len(out.display.table.rows) == MONTHS_SHOWN
    assert out.display.table.rows[-1]["month"] == "Dec 2022"
    assert f"(last {MONTHS_SHOWN} of 36 months shown)" in out.content


def test_spending_outcome_without_income_has_no_savings_rate():
    out = spending_overview_outcome(
        history([row("2026-09-10", "-10.00")]).spending(DateRange(months=1)), "September 2026"
    )

    assert "savings rate none (no income)" in out.content
    assert [s.label for s in out.display.summary] == ["spent", "income"]


def test_merchants_outcome():
    h = history([row("2026-09-02", "-30.00", merchant="Lidl"), row("2026-09-03", "-90.00", merchant="Amazon")])

    out = top_merchants_outcome(h.merchants(DateRange(months=1), 10), "September 2026")

    assert "- Amazon: 90.00 EUR, 75.0% of expenses, 1 purchases" in out.content
    assert out.display.summary[:2] == [
        SummaryItem(kind="money", value=120.0, label="spent"),
        SummaryItem(kind="count", value=2, label="merchants"),
    ]
    assert [r["merchant"] for r in out.display.table.rows] == ["Amazon", "Lidl"]


def test_merchants_outcome_without_spending():
    empty = MerchantBreakdownResponse.model_validate(
        {
            "date_from": "2026-09-01",
            "date_to": "2026-09-30",
            "total_expenses": "0.00",
            "top_by_spend": [],
            "top_by_frequency": [],
            "concentration": {
                "top_5_share_pct": 0.0,
                "top_10_share_pct": 0.0,
                "herfindahl_index": 0.0,
                "unique_merchants": 0,
            },
        }
    )

    out = top_merchants_outcome(empty, "September 2026")

    assert out.content == "September 2026\nNo spending in this period."
    assert out.display.table is None


def recurring_merchant(name: str, monthly: str) -> dict:
    return {
        "merchant": name,
        "charges": 3,
        "months_charged": 3,
        "median_charge": monthly,
        "interval_days": 30,
        "monthly_cost": monthly,
        "last_charge": "2026-09-12",
        "active": True,
    }


def test_recurring_outcome_keeps_the_costliest_merchants():
    merchants = [recurring_merchant(f"Service {i}", f"{i + 1}.00") for i in range(RECURRING_SHOWN + 5)]
    response = RecurringResponse.model_validate(
        {
            "date_from": "2026-07-01",
            "date_to": "2026-09-30",
            "total_expenses": "3000.00",
            "recurring_total": "900.00",
            "recurring_count": 75,
            "amount_share_pct": 30.0,
            "count_share_pct": 40.0,
            "monthly_recurring_cost": "325.00",
            "merchants": merchants,
            "hidden_subscriptions": [
                {
                    "merchant": "Spotify",
                    "charges": 3,
                    "months_active": 3,
                    "average_charge": "9.99",
                    "charges_per_month": 1.0,
                }
            ],
        }
    )

    out = recurring_costs_outcome(response, "Jul – Sep 2026")

    assert len(out.display.table.rows) == RECURRING_SHOWN
    assert out.display.table.rows[0]["merchant"] == f"Service {RECURRING_SHOWN + 4}"
    assert out.display.table.rows[0]["monthly_cost"] == float(RECURRING_SHOWN + 5)
    assert f"(top {RECURRING_SHOWN} of {RECURRING_SHOWN + 5} recurring merchants shown)" in out.content
    assert "- Spotify: average charge 9.99 EUR, 3 charges over 3 months" in out.content
    assert out.display.summary[0] == SummaryItem(kind="money", value=325.0, label="a month")


def test_behaviour_outcome():
    h = history([row("2026-09-05", "-60.00"), row("2026-09-07", "-10.00", category="food_groceries")])

    out = spending_behaviour_outcome(h.behaviour(DateRange(months=1)), "September 2026", NAMES)

    assert "- Saturday: 60.00 EUR, 1 purchases" in out.content
    assert out.display.summary[-1] == SummaryItem(kind="text", value="Saturday", label="busiest day")
    assert len(out.display.table.rows) == 7


def test_behaviour_outcome_without_spending():
    response = history([row("2026-09-05", "100.00", category="salary")]).behaviour(DateRange(months=1))

    out = spending_behaviour_outcome(response, "September 2026", NAMES)

    assert out.content == "September 2026\nNo spending in this period."
    assert out.display.table is None


def test_anomalies_outcome():
    response = AnomaliesResponse.model_validate(
        {
            "date_from": "2026-07-01",
            "date_to": "2026-09-30",
            "std_threshold": 2.5,
            "window_days": 30,
            "outliers": [
                {
                    "date": "2026-09-14",
                    "merchant": "MediaMarkt",
                    "category": "food_groceries",
                    "amount": "899.00",
                    "z_score": 4.12,
                    "window_mean": "85.00",
                    "compared_with": "category",
                }
            ],
            "spikes": [],
            "spike_window_start": None,
            "spike_window_end": None,
        }
    )

    out = unusual_spending_outcome(response, "Jul – Sep 2026", NAMES)

    assert (
        "- 2026-09-14 MediaMarkt, Food & Groceries (food_groceries): 899.00 EUR, z-score 4.1 against its category"
        in out.content
    )
    assert "No category spikes." in out.content
    assert out.display.table.rows == [
        {"date": "2026-09-14", "merchant": "MediaMarkt", "category": "Food & Groceries", "amount": 899.0}
    ]
