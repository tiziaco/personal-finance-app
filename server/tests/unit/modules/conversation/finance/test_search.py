"""search_transactions: filters, never-netted totals, groups and the capped sample, and how they read."""

import datetime as dt
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.conversation.finance.display import search_outcome
from app.modules.conversation.finance.domain.search import GROUP_LIMIT, SAMPLE_SIZE, search_rows
from app.modules.conversation.finance.schemas import SearchArgs
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

NAMES = {"food_groceries": "Food & Groceries", "shopping": "Shopping"}


def args(**kw) -> SearchArgs:
    return SearchArgs.model_validate(kw)


ROWS = [
    row("2026-09-01", "-10.00", "Lidl Berlin", "food_groceries"),  # Tuesday
    row("2026-09-08", "-20.00", "LIDL", "food_groceries"),  # Tuesday
    row("2026-09-12", "-30.00", "Lidl", "food_groceries", recurring=True),  # Saturday
    row("2026-10-03", "-5.00", "Kiosk"),  # Saturday
    row("2026-10-04", "15.00", "Refund Shop"),  # Sunday
]
SPAN = (ROWS[0].date, ROWS[-1].date)


def test_merchant_match_is_case_insensitive_substring():
    assert search_rows(ROWS, args(merchant="lidl")).matched == 3


def test_weekday_filter():
    result = search_rows(ROWS, args(weekdays=["tue"]))
    assert [r.date for r in result.sample] == [dt.date(2026, 9, 8), dt.date(2026, 9, 1)]


def test_date_bounds_are_inclusive_and_may_be_open():
    assert search_rows(ROWS, args(date_from="2026-09-08", date_to="2026-09-12")).matched == 2
    assert search_rows(ROWS, args(date_from="2026-10-01")).matched == 2


def test_categories_amounts_and_recurring_filters():
    assert search_rows(ROWS, args(categories=["food_groceries"])).matched == 3
    assert search_rows(ROWS, args(amount_max="-20")).matched == 2
    assert search_rows(ROWS, args(amount_min="-20", amount_max="-5")).matched == 3
    assert search_rows(ROWS, args(recurring_only=True)).matched == 1


def test_money_in_and_out_are_never_netted():
    r = search_rows([row("2026-09-01", "-50"), row("2026-09-02", "20")], args())
    assert (r.money_out.total, r.money_out.count) == (Decimal("-50"), 1)
    assert (r.money_in.total, r.money_in.count) == (Decimal("20"), 1)


def test_sample_is_capped_largest_first_or_most_recent():
    many = [row(f"2026-09-{d:02d}", f"-{d}.00") for d in range(1, 29)] * 2
    largest = search_rows(many, args())
    assert len(largest.sample) == SAMPLE_SIZE
    assert largest.sample[0].amount == Decimal("-28.00")
    recent = search_rows(many, args(sample="recent"))
    assert recent.sample[0].date == dt.date(2026, 9, 28)
    assert largest.matched == 56


def test_group_by_month_sums_per_month_biggest_spend_first():
    r = search_rows(ROWS, args(group_by="month"))
    assert [(label, out.total, into.total) for label, out, into in r.groups] == [
        ("2026-09", Decimal("-60.00"), Decimal("0")),
        ("2026-10", Decimal("-5.00"), Decimal("15.00")),
    ]


def test_group_by_merchant_merges_spellings_and_weekday_names_days():
    by_merchant = search_rows(ROWS, args(group_by="merchant", merchant="lidl"))
    # "LIDL" and "Lidl" are one merchant; "Lidl Berlin" is another
    assert [(label, out.count) for label, out, _ in by_merchant.groups] == [("LIDL", 2), ("Lidl Berlin", 1)]
    by_day = search_rows(ROWS, args(group_by="weekday"))
    assert {label for label, *_ in by_day.groups} == {"tue", "sat", "sun"}


def test_span_covers_the_matches():
    assert search_rows(ROWS, args(merchant="kiosk")).span == (dt.date(2026, 10, 3), dt.date(2026, 10, 3))
    assert search_rows(ROWS, args(merchant="nothing")).span is None


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ({"categories": ["Snacks"]}, "food_groceries"),
        ({"date_from": "2026-09-30", "date_to": "2026-09-01"}, "date_from 2026-09-30 is after date_to"),
        ({"amount_min": "10", "amount_max": "5"}, "amount_min 10 is above amount_max 5"),
        ({"weekdays": ["monday"]}, "weekdays"),
        ({"user_id": "x"}, "user_id"),
    ],
)
def test_invalid_arguments_are_rejected_with_a_reason(bad, message):
    with pytest.raises(ValidationError, match=message):
        SearchArgs.model_validate(bad)


def test_no_match_says_so_in_content():
    a = args(merchant="nothing")
    outcome = search_outcome(search_rows(ROWS, a), a, NAMES, SPAN)
    assert "no transactions match" in outcome.content.lower()
    assert 'merchant contains "nothing"' in outcome.content
    assert outcome.display.table is None


def test_content_lists_filter_totals_and_sample_with_named_categories():
    a = args(merchant="lidl", categories=["food_groceries"], date_from="2026-09-01", date_to="2026-09-30")
    outcome = search_outcome(search_rows(ROWS, a), a, NAMES, SPAN)
    lines = outcome.content.splitlines()
    assert lines[0] == "September 2026"
    assert "categories Food & Groceries (food_groceries)" in lines[1]
    assert "Money out: 3 transactions, -60.00 EUR; money in: 0 transactions, 0.00 EUR." in outcome.content
    assert "- 2026-09-12 Lidl -30.00 EUR Food & Groceries (food_groceries)" in outcome.content
    assert [r["amount"] for r in outcome.display.table.rows] == ["-30.00", "-20.00", "-10.00"]
    assert outcome.display.table.columns[-1].kind == "transaction"
    # Money out and in show unsigned under their labels; the content keeps the sign.
    assert [(item.kind, item.value) for item in outcome.display.summary[:2]] == [("total", "60.00"), ("total", "0.00")]


def test_open_ended_range_and_unfiltered_labels():
    assert search_outcome(
        search_rows(ROWS, args(date_from="2026-10-01")), args(date_from="2026-10-01"), NAMES, SPAN
    ).content.startswith("from 2026-10-01")
    assert search_outcome(search_rows(ROWS, args()), args(), NAMES, SPAN).display.period == "1 Sep – 4 Oct 2026"


def test_ranked_groups_are_capped_to_the_top_and_the_table_shows_groups():
    many = [row("2026-09-05", f"-{m + 1}.00", merchant=f"Shop {m}") for m in range(30)]
    a = args(group_by="merchant")
    outcome = search_outcome(search_rows(many, a), a, NAMES, SPAN)
    assert f"(top {GROUP_LIMIT} of 30 groups shown)" in outcome.content
    assert len(outcome.display.table.rows) == GROUP_LIMIT
    assert outcome.display.table.rows[0]["out_total"] == "30.00"


def test_zero_amounts_are_neither_money_out_nor_in_and_not_matches():
    r = search_rows([row("2026-09-01", "0.00"), row("2026-09-02", "-5.00")], args())
    assert (r.matched, r.money_out.count, r.money_in.count) == (1, 1, 0)


def test_months_run_oldest_first_and_the_cap_keeps_the_newest():
    many = [row(f"{2020 + m // 12}-{m % 12 + 1:02d}-05", f"-{m + 1}.00") for m in range(30)]
    a = args(group_by="month")
    outcome = search_outcome(search_rows(many, a), a, NAMES, SPAN)
    assert f"(last {GROUP_LIMIT} of 30 groups shown)" in outcome.content
    months = [r["group"] for r in outcome.display.table.rows]
    assert months[0] == "Jul 2020" and months[-1] == "Jun 2022"
    other = args(group_by="category")
    assert [g[0] for g in search_rows(ROWS, other).groups][0] == "food_groceries"  # ranked by money out


def test_no_match_names_the_data_span():
    a = args(date_from="2019-01-01", date_to="2019-12-31")
    outcome = search_outcome(search_rows(ROWS, a), a, NAMES, SPAN)
    assert "the data covers September 2026 to October 2026" in outcome.content


def test_one_transaction_is_singular():
    a = args(merchant="kiosk")
    content = search_outcome(search_rows(ROWS, a), a, NAMES, SPAN).content
    assert "1 transaction matches." in content and "Money out: 1 transaction, -5.00 EUR" in content


def test_a_blank_merchant_is_no_filter_and_a_padded_one_is_stripped():
    assert search_rows(ROWS, args(merchant="   ")).matched == 5
    assert search_rows(ROWS, args(merchant=" kiosk ")).matched == 1
