"""The list query: every filter, search, ordering and paging."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.transaction.repository import transaction_repository
from app.modules.transaction.schemas import TransactionFilters

pytestmark = pytest.mark.integration


async def _list(db_session, user, filters=None, ordering="-date", search=None, offset=0, limit=20):
    return await transaction_repository.list_active_for_user(
        db_session, user.id, filters or TransactionFilters(), ordering, search, offset, limit
    )


@pytest.fixture
async def rows(test_user, make_transaction):
    """Five distinguishable rows for test_user."""
    return {
        "rewe": await make_transaction(
            test_user, date=dt.date(2026, 1, 5), merchant="REWE", amount=Decimal("-30.00"), category="food_groceries"
        ),
        "salary": await make_transaction(
            test_user,
            date=dt.date(2026, 1, 27),
            merchant="Employer GmbH",
            amount=Decimal("2400.00"),
            category="salary",
            is_recurring=True,
        ),
        "rent": await make_transaction(
            test_user,
            date=dt.date(2026, 2, 1),
            merchant="Landlord",
            amount=Decimal("-900.00"),
            category="household_utilities",
            is_recurring=True,
        ),
        "bar": await make_transaction(
            test_user,
            date=dt.date(2026, 2, 14),
            merchant="Bar 100%_off",
            amount=Decimal("-18.50"),
            category="bars_restaurants",
        ),
        "spati": await make_transaction(
            test_user, date=dt.date(2026, 2, 28), merchant="Späti", amount=Decimal("-4.50"), category="food_groceries"
        ),
    }


def _merchants(items):
    return [t.merchant for t in items]


async def test_default_is_newest_first_with_total(db_session, test_user, rows):
    items, total = await _list(db_session, test_user)
    assert total == 5
    assert _merchants(items) == ["Späti", "Bar 100%_off", "Landlord", "Employer GmbH", "REWE"]


async def test_date_bounds_are_inclusive(db_session, test_user, rows):
    f = TransactionFilters(date_from=dt.date(2026, 1, 27), date_to=dt.date(2026, 2, 14))
    items, total = await _list(db_session, test_user, f)
    assert total == 3
    assert set(_merchants(items)) == {"Employer GmbH", "Landlord", "Bar 100%_off"}


async def test_inverted_bounds_are_empty_not_an_error(db_session, test_user, rows):
    """Review Focus 2."""
    f = TransactionFilters(
        date_from=dt.date(2026, 3, 1), date_to=dt.date(2026, 1, 1), amount_min=Decimal("10"), amount_max=Decimal("-10")
    )
    assert await _list(db_session, test_user, f) == ([], 0)


async def test_any_of_several_categories(db_session, test_user, rows):
    f = TransactionFilters(category=["salary", "bars_restaurants"])
    items, _ = await _list(db_session, test_user, f)
    assert set(_merchants(items)) == {"Employer GmbH", "Bar 100%_off"}


async def test_amount_bounds_on_the_signed_amount(db_session, test_user, rows):
    f = TransactionFilters(amount_max=Decimal("-18.50"))
    items, _ = await _list(db_session, test_user, f)
    assert set(_merchants(items)) == {"REWE", "Landlord", "Bar 100%_off"}


async def test_recurring(db_session, test_user, rows):
    items, _ = await _list(db_session, test_user, TransactionFilters(is_recurring=True))
    assert set(_merchants(items)) == {"Employer GmbH", "Landlord"}


async def test_search_is_a_case_insensitive_substring(db_session, test_user, rows):
    items, _ = await _list(db_session, test_user, search="SPÄ")
    assert _merchants(items) == ["Späti"]


@pytest.mark.parametrize("term", ["%", "_", "100%_"])
async def test_search_matches_like_wildcards_literally(db_session, test_user, rows, term):
    items, _ = await _list(db_session, test_user, search=term)
    assert _merchants(items) == ["Bar 100%_off"]


async def test_backslash_in_search_is_literal(db_session, test_user, rows):
    assert await _list(db_session, test_user, search="\\") == ([], 0)


@pytest.mark.parametrize(
    "ordering, first",
    [
        ("date", "REWE"),
        ("-date", "Späti"),
        ("amount", "Landlord"),
        ("-amount", "Employer GmbH"),
        ("merchant", "Bar 100%_off"),
        ("-merchant", "Späti"),
    ],
)
async def test_orderings(db_session, test_user, rows, ordering, first):
    items, _ = await _list(db_session, test_user, ordering=ordering)
    assert items[0].merchant == first


async def test_same_day_ties_break_newest_created_first(db_session, test_user, make_transaction):
    first = await make_transaction(test_user, merchant="A", date=dt.date(2026, 3, 1))
    second = await make_transaction(test_user, merchant="B", date=dt.date(2026, 3, 1))
    items, _ = await _list(db_session, test_user)
    assert [t.id for t in items] == [second.id, first.id]


async def test_paging_and_a_page_past_the_end(db_session, test_user, rows):
    """Review Focus 4."""
    page, total = await _list(db_session, test_user, offset=2, limit=2)
    assert _merchants(page) == ["Landlord", "Employer GmbH"]
    assert total == 5
    assert await _list(db_session, test_user, offset=40, limit=20) == ([], 5)


async def test_soft_deleted_and_other_users_rows_never_appear(
    db_session, test_user, other_user, rows, make_transaction
):
    rows["rewe"].soft_delete()
    await db_session.flush()
    await make_transaction(other_user, merchant="Theirs")
    items, total = await _list(db_session, test_user)
    assert total == 4
    assert "REWE" not in _merchants(items) and "Theirs" not in _merchants(items)
