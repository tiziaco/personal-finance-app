"""The seed's date shift and CSV parsing."""

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from seed_transactions import load_rows, months_to_current, shift_months  # noqa: E402

pytestmark = pytest.mark.unit

HEADER = "date,merchant,amount,description,category,confidence,is_recurring,original_category\n"


def test_shift_keeps_the_day_of_month():
    assert shift_months(date(2026, 1, 27), 9) == date(2026, 10, 27)


def test_shift_clamps_to_the_months_length():
    assert shift_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_shift_crosses_a_year():
    assert shift_months(date(2025, 11, 15), 3) == date(2026, 2, 15)


def test_months_to_current():
    assert months_to_current(date(2026, 1, 23), date(2026, 10, 13)) == 9
    assert months_to_current(date(2026, 10, 1), date(2026, 10, 13)) == 0


def _csv(tmp_path, body):
    path = tmp_path / "seed.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def test_rows_move_so_the_newest_lands_this_month_and_future_rows_drop(tmp_path):
    path = _csv(
        tmp_path,
        "2026-01-10,REWE,-12.70,,food_groceries,0.9,false,Presentment\n"
        "2026-01-20,Späti,-4.50,,food_groceries,0.9,false,Presentment\n",
    )
    rows, unknown = load_rows(path, today=date(2026, 10, 13))
    assert [r.date for r in rows] == [date(2026, 10, 10)]  # 2026-10-20 is after today
    assert rows[0].amount == Decimal("-12.70")
    assert rows[0].original_category == "Presentment"
    assert rows[0].description is None
    assert not unknown


def test_a_true_cell_is_the_users_tick_and_anything_else_is_left_to_the_rule(tmp_path):
    path = _csv(
        tmp_path,
        "2026-10-01,A,-1.00,,food_groceries,0.9,true,\n"
        "2026-10-01,B,-2.00,,food_groceries,0.9,false,\n"
        "2026-10-01,C,-3.00,,food_groceries,0.9,,\n",
    )
    rows, _ = load_rows(path, today=date(2026, 10, 13))
    assert [r.is_recurring for r in rows] == [True, False, False]


def test_an_unknown_slug_becomes_miscellaneous_and_is_counted(tmp_path):
    path = _csv(tmp_path, "2026-10-01,X,-1.00,,retired_slug,0.9,true,\n")
    rows, unknown = load_rows(path, today=date(2026, 10, 13))
    assert rows[0].category == "miscellaneous"
    assert rows[0].is_recurring is True
    assert unknown == {"retired_slug": 1}
