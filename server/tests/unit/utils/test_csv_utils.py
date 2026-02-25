import polars as pl
import pytest

from app.utils.csv_utils import pick_representative_sample


def test_empty_dataframe_returns_empty():
    df = pl.DataFrame({"date": [], "amount": []})
    assert pick_representative_sample(df, n=3) == []


def test_fewer_rows_than_n_returns_all():
    df = pl.DataFrame({"date": ["2024-01-01"], "amount": [1.0]})
    rows = pick_representative_sample(df, n=3)
    assert len(rows) == 1


def test_all_non_null_returns_first_n_rows():
    df = pl.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "merchant": ["A", "B", "C", "D"],
        "amount": [1.0, 2.0, 3.0, 4.0],
    })
    rows = pick_representative_sample(df, n=3)
    assert len(rows) == 3


def test_sparse_column_row_is_included():
    """Row 4 is the only one with a non-null description — it must be selected."""
    df = pl.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "description": [None, None, None, "Payment ref 123"],
        "amount": [1.0, 2.0, 3.0, 4.0],
    })
    rows = pick_representative_sample(df, n=3)
    descriptions = [r["description"] for r in rows]
    assert "Payment ref 123" in descriptions


def test_all_null_column_still_returns_n_rows():
    """A permanently-null column should not prevent n rows from being returned."""
    df = pl.DataFrame({
        "date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
        "reference": [None, None, None, None],
        "amount": [1.0, 2.0, 3.0, 4.0],
    })
    rows = pick_representative_sample(df, n=3)
    assert len(rows) == 3
