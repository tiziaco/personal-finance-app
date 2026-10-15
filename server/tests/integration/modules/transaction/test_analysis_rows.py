"""The read path analytics loads: plain rows, this user's, active, in range, in date order."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.transaction import AnalysisRow, transaction_service

pytestmark = pytest.mark.integration


async def test_returns_plain_rows_in_date_order(db_session, test_user, make_transaction):
    await make_transaction(
        test_user,
        date=dt.date(2026, 2, 1),
        merchant="Landlord",
        amount=Decimal("-900.00"),
        category="household_utilities",
        is_recurring=True,
    )
    await make_transaction(test_user, date=dt.date(2026, 1, 5), merchant="REWE Markt GmbH", amount=Decimal("-30.00"))

    rows = await transaction_service.list_for_analysis(db_session, test_user.id)

    assert rows == [
        AnalysisRow(
            date=dt.date(2026, 1, 5),
            merchant="REWE Markt GmbH",
            merchant_key="rewe markt",
            amount=Decimal("-30.00"),
            category="food_groceries",
            is_recurring=False,
        ),
        AnalysisRow(
            date=dt.date(2026, 2, 1),
            merchant="Landlord",
            merchant_key="landlord",
            amount=Decimal("-900.00"),
            category="household_utilities",
            is_recurring=True,
        ),
    ]


async def test_excludes_deleted_rows_and_other_users(db_session, test_user, other_user, make_transaction):
    kept = await make_transaction(test_user, merchant="Kept")
    gone = await make_transaction(test_user, merchant="Gone")
    gone.soft_delete()
    db_session.add(gone)
    await db_session.flush()
    await make_transaction(other_user, merchant="Theirs")

    rows = await transaction_service.list_for_analysis(db_session, test_user.id)

    assert [r.merchant for r in rows] == [kept.merchant]


async def test_both_bounds_are_inclusive(db_session, test_user, make_transaction):
    for day in (1, 2, 3, 4):
        await make_transaction(test_user, date=dt.date(2026, 3, day), merchant=f"Day {day}")

    rows = await transaction_service.list_for_analysis(
        db_session, test_user.id, date_from=dt.date(2026, 3, 2), date_to=dt.date(2026, 3, 3)
    )

    assert [r.merchant for r in rows] == ["Day 2", "Day 3"]
